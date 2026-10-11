#!/usr/bin/env python3
"""Isolated deterministic checks for canonical-work journal; no database imports or I/O."""
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from live_canonical_queue import (
    CanonicalQueueError, identity, identity_key, register_city,
    register_state, reconcile_and_select, retry, quarantine, committed_readback,
    store,
)

NOW = datetime(2026, 10, 11, 6, tzinfo=timezone.utc)
CUTOFF = datetime(2026, 10, 7, 16, 53, 19, tzinfo=timezone.utc)
def fixture(city, seq):
    start = datetime(2026, 10, 8, tzinfo=timezone.utc) + timedelta(minutes=seq)
    return {
        "city_key": city,
        "episode_id": format(seq + 1, "024x"),
        "alert_start": start.isoformat(),
        "alert_end": (start + timedelta(minutes=10)).isoformat(),
        "checks": [{"checked_at": NOW.isoformat(), "due_at": NOW.isoformat()}],
    }

def run():
    s = {"cities": {"kyiv": {"episodes": [fixture("kyiv", i) for i in range(28)]}}}
    register_state(s, CUTOFF)
    assert len(store(s)) == 28
    first = reconcile_and_select(s, tips={}, candidates=[], cutoff=CUTOFF, max_episodes=10, now=NOW)
    assert len(first["selected"]) == 10
    # WIP pruning may remove all active episodes, but not the obligation journal.
    s["cities"]["kyiv"]["episodes"].clear()
    assert len(store(s)) == 28
    selected_ids = []
    for batch in range(3):
        results = reconcile_and_select(s, tips={}, candidates=[], cutoff=CUTOFF, max_episodes=10, now=NOW)
        rows = results["selected"]
        assert len(rows) <= 10
        selected_ids.extend(row["work_id"] for row in rows)
        # Mock a committed result and confirm read-back key is necessary.
        for row in rows:
            committed_readback(s, row["work_id"], "fingerprint", "fingerprint")
        # Reconciliation with no DB tip must reverse WIP-only success.
        retry_selection = reconcile_and_select(s, tips={}, candidates=[], cutoff=CUTOFF, max_episodes=10, now=NOW)
        assert retry_selection["selected"][0]["work_id"] == rows[0]["work_id"]
        # Simulate DB commits by removing completed records from this isolated
        # selection view, rather than claiming that flags are authoritative.
        for row in rows:
            store(s)[row["work_id"]]["status"] = "quarantined"
            store(s)[row["work_id"]]["quarantine_reason"] = "SIMULATED_COMPLETED_SLOT"
    assert len(set(selected_ids)) == 28
    # 469 items -> 47 capped batches, as a pure capacity upper bound.
    assert (469 + 9) // 10 == 47
    one = {"cities": {}}
    register_city(one, "kyiv", [fixture("kyiv", 1)], CUTOFF)
    key = next(iter(store(one)))
    retry(one, key, NOW, "simulated rollback")
    delayed = reconcile_and_select(one, tips={}, candidates=[], cutoff=CUTOFF, max_episodes=10, now=NOW)
    assert not delayed["selected"] and delayed["retry_waiting"] == 1
    resumed = reconcile_and_select(one, tips={}, candidates=[], cutoff=CUTOFF, max_episodes=10, now=NOW + timedelta(minutes=16))
    assert len(resumed["selected"]) == 1
    try:
        committed_readback(one, key, "a", "b")
        raise AssertionError("mismatched read-back was accepted")
    except CanonicalQueueError:
        pass
    quarantine(one, key, "EXACT_PARENT_CONFLICT")
    result = reconcile_and_select(one, tips={}, candidates=[], cutoff=CUTOFF, max_episodes=10, now=NOW + timedelta(hours=1))
    assert result["quarantined"] == 1 and not result["selected"]
    before = len(store(one))
    register_city(one, "kyiv", [fixture("kyiv", 1)], CUTOFF)
    assert len(store(one)) == before
    register_city(one, "kyiv", [fixture("kyiv", 99)], CUTOFF)
    assert len(store(one)) == before + 1
    payload = {
        "verdict": "PARTIAL",
        "test_scope": "standalone journal and simulated selector; no canonical DB, no integrated monitor",
        "frozen_base": "92d57bbbfad60e6c09bb92372b1e84f38fa6ced4",
        "mock_kyiv_pending": 28,
        "mock_kyiv_selected_unique": len(set(selected_ids)),
        "capped_batches": 3,
        "simulated_469_batch_count": (469 + 9) // 10,
        "cap": 10,
        "restart_prune_journal_survival": True,
        "status_without_db_tip_is_not_commit": True,
        "retry_waiting": True,
        "postcommit_mismatch_rejected": True,
        "quarantined_conflict_skipped": True,
        "deduped_exact_identity": True,
        "remaining": [
            "Not integrated into monitor or persistence",
            "No live snapshot of all 28 exact Kyiv identities",
            "No committed DB exact-tip read-back exercised",
            "No A/B independent separate-environment proof",
            "No source coverage or classifier regression replay",
        ],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    payload["fingerprint_sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload

if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True, indent=2))
