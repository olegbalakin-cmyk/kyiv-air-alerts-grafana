import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "scripts" / "replay_explosion_history.py"
SPEC = importlib.util.spec_from_file_location("historical_replay_vinnytsia_reconciliation_test", REPLAY_PATH)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(replay)
monitor = replay.import_monitor(ROOT)

EXPECTED_STRICT = {
    "202fb3f9846f8aaf8fb958f0",
    "61509736be4dbc730fa1ad71",
    "ad02595482a5c1e35f2a8638",
    "226c7cb6fe4124fb3bd3a346",
    "5c4daf5e8e07baa46b129f29",
}
EXPECTED_SENSITIVITY_ONLY = {
    "31dc1063610ef09321175fd8",
    "f9aafb9b87fb1abc661b1e68",
}
DISPUTED_EPISODE = "61509736be4dbc730fa1ad71"


def load_inputs():
    baseline = json.loads((ROOT / "data" / "explosion_audited_baseline.json").read_text(encoding="utf-8"))
    evidence = json.loads((ROOT / "data" / "explosion_research" / "vinnytsia" / "final_evidence.json").read_text(encoding="utf-8"))
    episodes, _ = replay.load_historical_episodes(ROOT, "vinnytsia", monitor)
    episodes = replay.filter_window(episodes, "2025-08-21", "2026-09-17", monitor)
    return baseline["cities"]["vinnytsia"], evidence, episodes


def test_vinnytsia_source_is_ready_and_counts_bind_to_seven_unique_episodes():
    baseline_city, evidence, episodes = load_inputs()
    assert len(episodes) == 362
    check = replay.evidence_validation(evidence, baseline_city, episodes, monitor, "vinnytsia")
    assert check["errors"] == []
    assert set(check["strict_ids"]) == EXPECTED_STRICT
    assert set(check["sensitivity_ids"]) == EXPECTED_STRICT | EXPECTED_SENSITIVITY_ONLY
    assert len(check["strict_ids"]) == 5
    assert len(check["sensitivity_ids"]) == 7
    assert len(set(check["sensitivity_ids"])) == 7


def test_disputed_2026_02_03_is_strict_and_uniquely_bound():
    baseline_city, evidence, episodes = load_inputs()
    row = next(x for x in evidence["strict_events"] if x["event_id"] == "VIN-20260203-01")
    assert row["matched_episode_id"] == DISPUTED_EPISODE
    target = next(x for x in episodes if x["episode_id"] == DISPUTED_EPISODE)
    binding = replay.bind_evidence_record(row, episodes, monitor)
    assert binding["episode_id"] == DISPUTED_EPISODE
    candidate = replay.candidate_from_history(
        "vinnytsia", row, "strict_events", DISPUTED_EPISODE, monitor, target
    )
    decision = monitor.classify_candidate(
        candidate,
        "vinnytsia",
        episodes,
        replay.manual_matching(DISPUTED_EPISODE),
    )
    assert decision["proposed_outcome"] == "approved_strict"
    assert decision["proposed_matched_episode_id"] == DISPUTED_EPISODE


def test_local_four_strict_and_two_sensitivity_cases_are_preserved():
    _, evidence, _ = load_inputs()
    strict_ids = {row["event_id"] for row in evidence["strict_events"]}
    sensitivity_ids = {row["event_id"] for row in evidence["sensitivity_only_events"]}
    assert {
        "VIN-20250910-01",
        "VIN-20260207-01",
        "VIN-20260324-01",
        "VIN-20260902-01",
    } <= strict_ids
    assert "VIN-20251030-REV" in sensitivity_ids
    assert "VIN-20260730-REV" in sensitivity_ids
    assert "VIN-20251030-REV" not in strict_ids
    assert "VIN-20260730-REV" not in strict_ids


def test_precoverage_and_region_only_cases_are_not_promoted():
    _, evidence, episodes = load_inputs()
    excluded = {row["event_id"]: row for row in evidence["excluded_events"]}
    assert excluded["VIN-X-20250716-PRECOV"]["decision"] == "excluded_precoverage"
    assert all(ep.get("alert_start_date_kyiv") != "2025-07-16" for ep in episodes)
    for event_id in [
        "VIN-X-20250927-01",
        "VIN-X-20251005-01",
        "VIN-X-20260120-01",
        "VIN-X-20260226-01",
        "VIN-X-20260731-01",
    ]:
        assert event_id not in {row["event_id"] for row in evidence["strict_events"]}
        assert event_id not in {row["event_id"] for row in evidence["sensitivity_only_events"]}
