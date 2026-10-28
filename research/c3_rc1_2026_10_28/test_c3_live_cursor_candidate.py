# RECONSTRUCTED C3-RC1 (2026-10-28). Based on independently accepted PG16 proof source b1036d43ebd9b2df15eb58fce2192f67eb30ee68.
# The earlier five C3 local-file bytes were unavailable. This is NOT their byte-identical recovery.
#!/usr/bin/env python3
"""Bounded integrated module checks; NOT proof of PostgreSQL transaction behavior."""
import ast
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

root = Path(__file__).resolve().parents[1]
scripts = root / "scripts"
sys.path.insert(0, str(scripts))

import live_canonical_queue as q
import attack_event_canonical_persistence as p

UTC = timezone.utc
NOW = datetime(2026, 10, 11, 9, tzinfo=UTC)
CUTOFF = datetime(2026, 10, 7, 16, 53, 19, tzinfo=UTC)
ORIGIN = {
    "ref": "test", "commit": "0" * 40, "run_id": None,
    "monitor_blob": "0" * 40,
    "origin_provenance": {"kind": "shared_live_attack_event_canonical_persistence_v1"},
    "origin_provenance_sha256": "0" * 64,
}


def episode(index):
    start = datetime(2026, 10, 8, tzinfo=UTC) + timedelta(minutes=20 * index)
    end = start + timedelta(minutes=15)
    return {
        "city_key": "kyiv", "episode_id": f"{index + 1:024x}",
        "alert_start": start.isoformat(),
        "alert_end": end.isoformat(),
        "checks": [{"label": "immediate", "due_at": end.isoformat(), "checked_at": None}],
    }


def run():
    # Imports and invocations use exactly the production monitor/persistence modules.
    monitor_code = (scripts / "monitor_explosion_candidates.py").read_text()
    tree = ast.parse(monitor_code)
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    callnames = [ast.unparse(node.func) for node in ast.walk(main) if isinstance(node, ast.Call)]
    assert "live_canonical_queue.read_current_tips" in callnames
    assert "live_canonical_queue.reconcile_and_select" in callnames
    assert "live_parent_ordering.preclassification_parent_gate" in callnames
    assert "persist_canonical_work" in callnames

    state = {"cities": {"kyiv": {"episodes": [episode(i) for i in range(28)]}}}
    assert q.register_state(state, CUTOFF) == 28
    due = {"kyiv": [(e, e["checks"][0]) for e in state["cities"]["kyiv"]["episodes"]]}
    coverage = q.record_coverage(state, due, {"kyiv": True}, [], NOW)
    assert coverage == {"checks_complete": 28, "checks_retryable": 0}
    state = json.loads(json.dumps(state))
    state["cities"]["kyiv"]["episodes"] = []
    assert len(q.store(state)) == 28

    # Ten already committed classify to the exact same canonical key.
    tips = {}
    for i in range(10):
        e = episode(i)
        k = q.identity_key(q.identity(e))
        rec = p.build_episode_classification(e, [], origin=ORIGIN)
        tips[k] = {
            "classification_uid": f"u{i}",
            "classification_key": rec["classification_key"],
            "origin_kind": "shared_live_attack_event_canonical_persistence_v1",
            "exact_parent": True,
        }
    sel = q.reconcile_and_select(
        state, tips=tips, candidates=[], cutoff=CUTOFF, max_episodes=10, now=NOW
    )
    assert sel["db_committed_current"] == 10
    assert len(sel["selected"]) == 10
    assert [x["episode"]["episode_id"] for x in sel["selected"]] == [
        episode(i)["episode_id"] for i in range(10, 20)
    ]

    # Completed checks without source certificates cannot produce false negatives.
    legacy = {"cities": {"kyiv": {"episodes": [episode(100)]}}}
    legacy["cities"]["kyiv"]["episodes"][0]["checks"][0]["checked_at"] = NOW.isoformat()
    q.register_state(legacy, CUTOFF)
    blocked = q.reconcile_and_select(
        legacy, tips={}, candidates=[], cutoff=CUTOFF, max_episodes=10, now=NOW
    )
    assert blocked["blocked_evidence"] == 1 and not blocked["selected"]

    # Evidence errors leave actual due checks retryable and do not claim coverage.
    fail = {"cities": {"kyiv": {"episodes": [episode(101)]}}}
    q.register_state(fail, CUTOFF)
    due_fail = {"kyiv": [(fail["cities"]["kyiv"]["episodes"][0],
                         fail["cities"]["kyiv"]["episodes"][0]["checks"][0])]}
    assert q.record_coverage(fail, due_fail, {"kyiv": False}, [], NOW)["checks_retryable"] == 1
    assert due_fail["kyiv"][0][1]["checked_at"] is None

    # Persisted positive evidence cannot evaporate when current WIP queue is pruned.
    pos = {"cities": {"kyiv": {"episodes": [episode(102)]}}}
    e = episode(102)
    row = {
        "candidate_id": "evidence1", "city_key": "kyiv", "status": "needs_review",
        "matched_episode_id": e["episode_id"], "classification_reason_codes": [],
        "classification_evidence": {"classification_episode_id": e["episode_id"]},
        "url": "https://example.invalid/item", "title": "Synthetic review hold",
    }
    q.register_state(pos, CUTOFF)
    d = {"kyiv": [(pos["cities"]["kyiv"]["episodes"][0],
                   pos["cities"]["kyiv"]["episodes"][0]["checks"][0])]}
    q.record_coverage(pos, d, {"kyiv": True}, [row], NOW)
    entry = next(iter(q.store(pos).values()))
    retained = q.relevant_evidence(entry, [])
    assert len(retained) == 1
    assert p.build_episode_classification(e, retained, origin=ORIGIN)["verdict"] == "NEEDS_REVIEW"
    encoded = json.dumps({
        "tested": ["monitor_ast_path", "persistence_classifier", "queue_selector",
                   "state_serialize_prune", "db_tip_skip", "legacy_evidence_hold",
                   "failed_coverage_retry", "retained_review"],
        "selected": [x["episode"]["episode_id"] for x in sel["selected"]],
        "db_committed_skipped": 10,
        "remaining_post_batch": 8,
        "limitations": ["No local PostgreSQL transaction", "No 469 committed-backlog replay",
                        "No actual monitor main I/O execution", "No A/B database readback",
                        "No full 23-city regression", "No frozen 28 Kyiv identity proof"],
    }, sort_keys=True, separators=(",", ":"))
    return {"verdict": "PARTIAL", "fingerprint": hashlib.sha256(encoded.encode()).hexdigest(),
            "proof": json.loads(encoded)}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True, indent=2))
