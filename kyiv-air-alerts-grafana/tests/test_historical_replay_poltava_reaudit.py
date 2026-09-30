import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "explosion_research" / "poltava" / "final_evidence.json"


def test_poltava_reaudit_completion_contract():
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    strict = payload["strict_events"]
    sensitivity_only = payload["sensitivity_only_events"]
    strict_ids = [row["episode_id"] for row in strict]
    sensitivity_ids = [row["episode_id"] for row in sensitivity_only]

    assert payload["frozen_denominator"] == 1805
    assert len(strict) == 51
    assert len(sensitivity_only) == 2
    assert len(set(strict_ids)) == 51
    assert len(set(strict_ids + sensitivity_ids)) == 53
    assert set(strict_ids).isdisjoint(sensitivity_ids)
    assert payload["final_counts"]["strict_n"] == 51
    assert payload["final_counts"]["sensitivity_n"] == 53
    assert payload["final_counts"]["qa_n"] == 0
    assert payload["qa"]["duplicate_counted_canonical_ids"] == 0
    assert payload["qa"]["all_counted_bound"] is True


def test_poltava_reaudit_review_rows_are_noncounted_and_unbound():
    payload = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    reviews = payload["review_events"]
    assert {row["event_id"] for row in reviews} == {
        "POL-20260125-01",
        "POL-20260829-REV",
        "POL-20260901-01",
        "POL-TG-20260902-01",
    }
    assert all(row["decision"] == "REVIEW_NONCOUNTED" for row in reviews)
    assert all(row["canonical_episode_id"] is None for row in reviews)
