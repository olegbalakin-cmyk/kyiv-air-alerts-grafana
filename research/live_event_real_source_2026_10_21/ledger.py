#!/usr/bin/env python3
"""Isolated, non-authoritative durable replay ledger. No network/DB/Git writes."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import tempfile
from datetime import datetime, timezone

SCHEMA = 1
TERMINAL = "COMPLETED_AND_ACKNOWLEDGED"
STATES = {
    "DISCOVERED", "SOURCE_PENDING", "SOURCE_INCOMPLETE",
    "CLASSIFICATION_PENDING", "CLASSIFIED_NOT_ACKNOWLEDGED",
    TERMINAL, "RETRYABLE_ERROR",
}


def clock():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def encoded(document):
    return (json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def atomic_save(path, document, *, inject_fail=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="." + path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded(document))
            handle.flush()
            os.fsync(handle.fileno())
        if inject_fail:
            raise OSError("INJECTED_BEFORE_ATOMIC_REPLACE")
        os.replace(temp, path)
        if os.name == "posix":
            directory = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def validate(state):
    assert state["schema_version"] == SCHEMA
    assert state["non_authoritative"] is True
    assert state["canonical_writes"] == 0
    assert state["neon_writes"] == 0
    assert len(state["order"]) == len(set(state["order"])) == len(state["work"])
    for key, row in state["work"].items():
        assert key in state["order"] and row["episode_id"] == key
        assert row["status"] in STATES
        assert row["acknowledged"] == (row["status"] == TERMINAL)
        if row["acknowledged"]:
            assert row.get("result") is not None
            assert row.get("completed_at") and row["source_complete"] is True
            assert row.get("result", {}).get("classifier_identity") == state["classifier_identity"]
        else:
            assert not row.get("completed_at")
    return state


def initialize(path, cohort, classifier_identity):
    path = Path(path)
    ids = [str(item["episode_id"]) for item in cohort]
    assert ids and len(set(ids)) == len(ids), "EMPTY_OR_DUPLICATED_COHORT"
    assert classifier_identity and len(classifier_identity) >= 10
    if path.exists():
        state = validate(load(path))
        assert state["order"] == ids, "COHORT_IDENTITY_CHANGED"
        assert state["classifier_identity"] == classifier_identity, "CLASSIFIER_IDENTITY_CHANGED"
        return state
    doc = {
        "schema_version": SCHEMA,
        "non_authoritative": True,
        "canonical_writes": 0,
        "neon_writes": 0,
        "local_ack_only": True,
        "classifier_identity": classifier_identity,
        "sequence": 0,
        "order": ids,
        "work": {
            eid: {
                "episode_id": eid,
                "status": "DISCOVERED",
                "acknowledged": False,
                "attempts": 0,
                "last_attempt_sequence": -1,
                "source_complete": False,
                "result": None,
                "last_error": None,
                "completed_at": None,
                "updated_at": None,
            } for eid in ids
        },
    }
    atomic_save(path, doc)
    return validate(load(path))


def _change(path, state, episode_id, status, **fields):
    assert status in STATES
    result = copy.deepcopy(state)
    row = result["work"][episode_id]
    row.update(fields)
    row["status"] = status
    row["acknowledged"] = status == TERMINAL
    row["updated_at"] = clock()
    if status != TERMINAL:
        row["completed_at"] = None
    atomic_save(path, validate(result))
    return validate(load(path))


def select_due(state, limit=1):
    assert isinstance(limit, int) and limit > 0
    rows = [state["work"][eid] for eid in state["order"] if state["work"][eid]["status"] != TERMINAL]
    index = {eid: i for i, eid in enumerate(state["order"])}
    # Least-recently attempted first. Persistent errors cannot monopolize a capped batch.
    rows.sort(key=lambda row: (row["last_attempt_sequence"], index[row["episode_id"]]))
    return [row["episode_id"] for row in rows[:limit]]


def attempt(path, item, classifier, *, fault=None):
    """Run one bounded episode. Faults are test-only, never marked as real evidence."""
    eid = str(item["episode_id"])
    state = validate(load(path))
    assert eid in state["work"], "UNPINNED_EPISODE"
    if state["work"][eid]["status"] == TERMINAL:
        return {"episode_id": eid, "status": "ALREADY_ACKNOWLEDGED", "new_results": 0}
    if fault not in {None, "source", "classification", "storage"}:
        raise ValueError("UNKNOWN_TEST_FAULT")
    previous = state["work"][eid]
    seq = state["sequence"] + 1
    new_state = copy.deepcopy(state)
    new_state["sequence"] = seq
    new_state["work"][eid]["attempts"] = previous["attempts"] + 1
    new_state["work"][eid]["last_attempt_sequence"] = seq
    new_state["work"][eid]["status"] = "SOURCE_PENDING"
    new_state["work"][eid]["acknowledged"] = False
    new_state["work"][eid]["updated_at"] = clock()
    new_state["work"][eid]["last_error"] = None
    atomic_save(path, validate(new_state))
    state = validate(load(path))

    if fault == "source" or item.get("source_complete") is not True:
        state = _change(path, state, eid, "SOURCE_INCOMPLETE",
                        source_complete=False,
                        last_error=("INJECTED_SOURCE_FAILURE" if fault == "source"
                                    else "FROZEN_SOURCE_SCOPE_INCOMPLETE"))
        return {"episode_id": eid, "status": "RETRYABLE_SOURCE_INCOMPLETE", "new_results": 0}
    state = _change(path, state, eid, "CLASSIFICATION_PENDING", source_complete=True)
    if fault == "classification":
        _change(path, state, eid, "RETRYABLE_ERROR", last_error="INJECTED_CLASSIFICATION_FAILURE")
        return {"episode_id": eid, "status": "RETRYABLE_CLASSIFICATION_ERROR", "new_results": 0}
    try:
        classification = classifier(item)
        if not isinstance(classification, dict) or classification.get("classifier_identity") != state["classifier_identity"]:
            raise RuntimeError("CLASSIFIER_IDENTITY_OR_RESULT_MISSING")
        if classification.get("classifier_errors"):
            raise RuntimeError("ACCEPTED_CLASSIFIER_REPORTED_ERRORS")
        if classification.get("candidate_count") != len(classification.get("candidates", [])):
            raise RuntimeError("CLASSIFIER_CANDIDATE_COUNT_MISMATCH")
        if classification["candidate_count"] != item["candidate_count"]:
            raise RuntimeError("FROZEN_INPUT_CANDIDATE_COUNT_MISMATCH")
    except Exception as exc:
        _change(path, state, eid, "RETRYABLE_ERROR", last_error=f"{type(exc).__name__}:{exc}")
        return {"episode_id": eid, "status": "RETRYABLE_CLASSIFICATION_ERROR", "new_results": 0}
    state = _change(path, state, eid, "CLASSIFIED_NOT_ACKNOWLEDGED",
                    result=classification, last_error=None)
    # The ACK and the final classification are part of ONE atomic state envelope.
    finished = copy.deepcopy(state)
    row = finished["work"][eid]
    row["status"] = TERMINAL
    row["acknowledged"] = True
    row["completed_at"] = clock()
    row["last_error"] = None
    atomic_save(path, validate(finished), inject_fail=(fault == "storage"))
    committed = validate(load(path))
    assert committed["work"][eid]["acknowledged"]
    assert committed["work"][eid]["result"] == classification
    return {"episode_id": eid, "status": TERMINAL,
            "new_results": len(classification["candidates"])}


def run_batch(path, items, classifier, limit=1, faults=None):
    state = validate(load(path))
    by_id = {str(x["episode_id"]): x for x in items}
    assert set(by_id) == set(state["order"])
    results = []
    for eid in select_due(state, limit=limit):
        results.append(attempt(path, by_id[eid], classifier,
                               fault=(faults or {}).get(eid)))
    return results


def isolated_regression_test():
    """Synthetic ledger-only controls: NOT source records or physical attacks."""
    with tempfile.TemporaryDirectory(prefix="live-ledger-tests-") as tmp:
        path = Path(tmp) / "state.json"
        items = [{"episode_id": "SYNTHETIC_LEDGER_EP_" + str(i),
                  "candidate_count": 0, "source_complete": True} for i in range(3)]
        identity = "TEST_STUB_ONLY_NOT_ACCEPTED_CLASSIFIER"
        def dummy(_):
            return {"classifier_identity": identity, "candidate_count": 0,
                    "candidates": [], "verdict": "BOUNDED_NO_CANDIDATE",
                    "classifier_errors": []}
        initialize(path, items, identity)
        a = attempt(path, items[0], dummy, fault="source")
        assert a["status"] == "RETRYABLE_SOURCE_INCOMPLETE"
        assert load(path)["work"][items[0]["episode_id"]]["acknowledged"] is False
        assert select_due(load(path), 1) == [items[1]["episode_id"]], "CAPPED_BATCH_STARVATION"
        b = attempt(path, items[1], dummy, fault="classification")
        assert b["status"] == "RETRYABLE_CLASSIFICATION_ERROR"
        assert select_due(load(path), 1) == [items[2]["episode_id"]], "RETRY_STARVATION"
        try:
            attempt(path, items[2], dummy, fault="storage")
            raise AssertionError("STORAGE_FAULT_HIDDEN")
        except OSError as exc:
            assert "INJECTED_BEFORE_ATOMIC_REPLACE" in str(exc)
        row = load(path)["work"][items[2]["episode_id"]]
        assert row["status"] == "CLASSIFIED_NOT_ACKNOWLEDGED" and not row["acknowledged"]
        assert select_due(load(path), 1) == [items[0]["episode_id"]], "PENDING_STARVATION"
        for i in range(3):
            out = run_batch(path, items, dummy, limit=1)
            assert out[0]["status"] == TERMINAL
        before = Path(path).read_bytes()
        assert not select_due(load(path), 1)
        assert attempt(path, items[0], dummy)["status"] == "ALREADY_ACKNOWLEDGED"
        assert Path(path).read_bytes() == before, "IDEMPOTENCY_CHANGED_COMMITTED_BYTES"
        assert sum(r["acknowledged"] for r in load(path)["work"].values()) == 3
    return {
        "source_fault_retry": "PASS",
        "classification_fault_retry": "PASS",
        "storage_fault_no_false_ack": "PASS",
        "restart_after_classified_not_acknowledged": "PASS",
        "three_episodes_cap_one_no_starvation": "PASS",
        "committed_idempotency": "PASS",
        "synthetic_tests_not_real_events": True,
    }


if __name__ == "__main__":
    print(json.dumps(isolated_regression_test(), indent=2))
