import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/explosion_metric_handoff/source_slices/rivne-historical-recovery_alerts.json"
EVIDENCE = ROOT / "data/explosion_research/rivne/final_evidence.json"

EXPECTED_STRICT_IDS = [
    'a77f486661e77a776137dbe3',
    'cd034b8fcbf76c47a365beef',
    'c293666818985e94fe545e75',
    '9b796acb29256400a172c388',
    '7e902cf3136c3df84d1fc758',
    '8d433555c714dbe7cc1985c9',
    '30360edb6c58f30a8a770974',
    '306fbb22f7356839a902a80c',
    '83363241e6dcabdc432be441',
    '5065ee65e6b3d9ef0ce365cf',
    'd280de57ad4d95125620d22f',
    'ab4696eb424ba82f0b2c2b8c',
    '7d255bed7072f60502b07ceb'
]
EXPECTED_START_BY_ID = {
    'a77f486661e77a776137dbe3': '2025-08-20T21:49:53Z',
    'cd034b8fcbf76c47a365beef': '2025-09-02T20:11:03Z',
    'c293666818985e94fe545e75': '2025-09-09T19:59:02Z',
    '9b796acb29256400a172c388': '2025-09-13T12:10:42Z',
    '7e902cf3136c3df84d1fc758': '2025-10-04T22:26:40Z',
    '8d433555c714dbe7cc1985c9': '2025-12-23T02:14:34Z',
    '30360edb6c58f30a8a770974': '2026-01-20T04:26:10Z',
    '306fbb22f7356839a902a80c': '2026-02-07T01:12:27Z',
    '83363241e6dcabdc432be441': '2026-05-01T10:49:01Z',
    '5065ee65e6b3d9ef0ce365cf': '2026-05-13T09:04:16Z',
    'd280de57ad4d95125620d22f': '2026-05-17T23:41:48Z',
    'ab4696eb424ba82f0b2c2b8c': '2026-09-05T12:25:57Z',
    '7d255bed7072f60502b07ceb': '2026-09-12T19:44:53Z'
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_rivne_denominator_and_final_counts():
    source = load(SOURCE)
    evidence = load(EVIDENCE)
    assert source["corrected_expected_count"] == 232
    assert source["episode_count"] == 232
    assert len(source["episodes"]) == 232
    assert evidence["frozen_denominator"] == 232
    assert evidence["final_counts"]["alerts_total"] == 232
    assert evidence["final_counts"]["strict_n"] == 13
    assert evidence["final_counts"]["sensitivity_n"] == 13
    assert evidence["sensitivity_only_events"] == []


def test_rivne_exact_strict_canonical_episode_set():
    evidence = load(EVIDENCE)
    strict = evidence["strict_events"]
    ids = [row["matched_episode_id"] for row in strict]
    assert len(ids) == 13
    assert len(set(ids)) == 13
    assert set(ids) == set(EXPECTED_STRICT_IDS)
    for row in strict:
        assert row["matched_episode_start"] == EXPECTED_START_BY_ID[row["matched_episode_id"]]
        assert row["canonical_binding"]["episode_id"] == row["matched_episode_id"]


def test_rivne_geography_and_non_military_exclusions_retained():
    evidence = load(EVIDENCE)
    strict_ids = {row["event_id"] for row in evidence["strict_events"]}
    reviews = {row["event_id"]: row for row in evidence["review_events"]}
    assert "rivne-review-2026-05-30-regional-enterprise" in reviews
    assert "regional_only_not_exact_city" in reviews["rivne-review-2026-05-30-regional-enterprise"]["basis"]
    assert "rivne-review-2026-05-31-regional-enterprise" in reviews
    assert "regional_only_not_exact_city" in reviews["rivne-review-2026-05-31-regional-enterprise"]["basis"]
    assert "rivne-review-2025-12-09-gas" in reviews
    assert "non_military" in reviews["rivne-review-2025-12-09-gas"]["basis"]
    assert not strict_ids.intersection(reviews)


def test_rivne_transition_boundary_and_cross_midnight_binding():
    source = load(SOURCE)
    evidence = load(EVIDENCE)
    assert source["historical_cutoff"] == "2026-09-17"
    assert min(ep["alert_start_date_kyiv"] for ep in source["episodes"]) >= "2025-08-01"
    strict_by_id = {row["matched_episode_id"]: row for row in evidence["strict_events"]}
    cross = strict_by_id["7d255bed7072f60502b07ceb"]
    assert cross["event_time"] == "2026-09-13T00:40:00+03:00"
    assert cross["canonical_binding"]["alert_start"].startswith("2026-09-12T")
    assert cross["canonical_binding"]["alert_end"].startswith("2026-09-13T")


def test_rivne_same_day_multiple_episode_binding_is_specific():
    source = load(SOURCE)
    evidence = load(EVIDENCE)
    by_date = {}
    for ep in source["episodes"]:
        by_date.setdefault(ep["alert_start_date_kyiv"], []).append(ep["episode_id"])
    strict_ids = {row["matched_episode_id"] for row in evidence["strict_events"]}
    assert len(by_date["2026-01-20"]) > 1
    assert "30360edb6c58f30a8a770974" in strict_ids
    assert len(strict_ids.intersection(by_date["2026-01-20"])) == 1
    assert len(by_date["2026-02-07"]) > 1
    assert "306fbb22f7356839a902a80c" in strict_ids
    assert len(strict_ids.intersection(by_date["2026-02-07"])) == 1


def test_rivne_threat_only_does_not_create_positive_episode():
    source = load(SOURCE)
    evidence = load(EVIDENCE)
    strict_ids = {row["matched_episode_id"] for row in evidence["strict_events"]}
    may31_ids = {
        ep["episode_id"]
        for ep in source["episodes"]
        if ep["alert_start_date_kyiv"] == "2026-05-31"
    }
    assert may31_ids
    assert not strict_ids.intersection(may31_ids)


def test_rivne_full_screening_metadata():
    source = load(SOURCE)
    evidence = load(EVIDENCE)
    assert evidence["qa"]["unique_episode_start_dates_screened"] == len(
        {ep["alert_start_date_kyiv"] for ep in source["episodes"]}
    )
    assert evidence["qa"]["unresolved_cases"] == 0
