from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import replay_explosion_history as replay

EVIDENCE = ROOT / "data" / "explosion_research" / "ternopil" / "final_evidence.json"
ARTIFACT = ROOT.parent / "research" / "historical_replay_ternopil_evidence_recovery_proof_2026-09-30.json"
SLICE = ROOT / "data" / "explosion_metric_handoff" / "source_slices" / "ternopil-historical-recovery_alerts.json"

STRICT_IDS = {
    "c9ba590a578eb6ca32b6bbdd",
    "a89f7436765f5d5137e1bb37",
    "c955cc67c99c2bfda392999f",
    "5660359d9daba2bb22acbc03",
    "210be7b00050df45a83a5dd0",
}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_ternopil_denominator_and_complete_screening():
    evidence = load(EVIDENCE)
    artifact = load(ARTIFACT)
    source_slice = load(SLICE)
    assert source_slice["episode_count"] == 125
    assert source_slice["corrected_expected_count"] == 125
    assert evidence["frozen_denominator"] == 125
    ledger = artifact["coverage_ledger"]
    assert len(ledger) == 125
    assert {row["episode_id"] for row in ledger} == {row["episode_id"] for row in source_slice["episodes"]}
    assert all(row["research_status"] != "UNRESOLVED" for row in ledger)
    assert artifact["search_scope"]["unique_episode_dates_searched"] == 81
    assert artifact["search_scope"]["screened_episodes"] == 125
    assert artifact["search_scope"]["unscreened_episodes"] == 0


def test_ternopil_exact_set_binds_under_current_replay_semantics():
    monitor = replay.import_monitor(ROOT)
    baseline = load(ROOT / "data" / "explosion_audited_baseline.json")["cities"]["ternopil"]
    episodes, _ = replay.load_historical_episodes(ROOT, "ternopil", monitor)
    episodes = replay.filter_window(episodes, baseline["coverage_start"], "2026-09-17", monitor)
    validated = replay.evidence_validation(load(EVIDENCE), baseline, episodes, monitor, "ternopil")
    assert validated["errors"] == []
    assert set(validated["strict_ids"]) == STRICT_IDS
    assert set(validated["sensitivity_ids"]) == STRICT_IDS
    assert len(validated["strict_ids"]) == 5
    assert len(validated["sensitivity_ids"]) == 5


def test_ternopil_replay_is_clean(tmp_path):
    out = tmp_path / "ternopil-replay.json"
    rc = replay.replay_city(ROOT, "ternopil", "2026-09-17", out, None)
    result = load(out)
    assert rc == 0
    assert result["episodes_checked"] == 125
    assert result["replayed_strict_episodes"] == 5
    assert result["replayed_sensitivity_episodes"] == 5
    assert result["changed_episodes"] == []
    assert result["errors"] == []
    assert result["verdict"] == "CITY REPLAY CLEAN"
    assert result["protected_files_unchanged"] is True


def test_same_day_multiplicity_and_cross_midnight_binding():
    artifact = load(ARTIFACT)
    strict_ids = set(artifact["exact_sets"]["strict_canonical_episode_ids"])
    assert "a89f7436765f5d5137e1bb37" in strict_ids
    assert "c72dd43fc3a1c6a623f686d5" not in strict_ids
    assert "5660359d9daba2bb22acbc03" in strict_ids
    assert "a5e2ff6d5c5d4129736a16b3" not in strict_ids
    assert "210be7b00050df45a83a5dd0" in strict_ids
    assert "cd8a22462d6ec8c1f173901c" not in strict_ids
    assert "1110df1f2b91591ddd439e50" not in strict_ids
    source_slice = load(SLICE)
    cross = next(row for row in source_slice["episodes"] if row["episode_id"] == "5660359d9daba2bb22acbc03")
    assert cross["alert_start"].startswith("2026-09-02")
    assert cross["alert_end"].startswith("2026-09-02T21:03:20")


def test_regional_only_and_threat_only_are_noncounted():
    evidence = load(EVIDENCE)
    rows = {row["event_id"]: row for row in evidence["research_noncounted_candidates"]}
    assert rows["ternopil-20260903-regional-pvo"]["decision"] == "REJECTED"
    assert rows["ternopil-20260903-regional-pvo"]["reason"] == "REGIONAL_ONLY_EVENT"
    assert rows["ternopil-20260207-threat-toward-city"]["decision"] == "REJECTED"
    assert rows["ternopil-20260207-threat-toward-city"]["reason"] == "THREAT_ONLY"
    assert evidence["sensitivity_only_events"] == []
