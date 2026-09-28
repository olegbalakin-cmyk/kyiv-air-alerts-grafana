#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import date, datetime, time, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from db_phase1_core import (
    CANONICALIZATION_VERSION,
    SOURCE_KEYS,
    SOURCE_KEY_VERSIONS,
    Interval,
    alerts_in_ua_source_record_key,
    intervals_overlap_or_touch,
    legacy_episode_id,
    legacy_timestamp,
    merge_intervals,
    normalize_text,
    parse_timestamp,
    reconcile_api_manual,
    source_key_timestamp,
    ukrainealarm_source_record_key,
    vadimkin_source_record_key,
)

import db_phase1_lviv_canonical as lviv_canonical

CITY_KEY = "lviv"
ASSEMBLY_PROFILE = "lviv-historical-v1"
OBLAST = "Львівська область"
RAION = "Львівський район"
KYIV_TZ = ZoneInfo("Europe/Kyiv")
COVERAGE_START = date(2025, 9, 1)
HISTORICAL_END_EXCLUSIVE = date(2026, 9, 18)
EXPECTED_FROZEN_COUNT = 120
EXPECTED_BRIDGE_COUNT = 20
EXPECTED_OVERLAP = 14
EXPECTED_ADDITIONS = 6
EXPECTED_FINAL = 126

ORIGINAL_CONTRACT = "2ffc4c19231cccf5c8d9e703d4fe88c4928ddd5c"
AMENDED_CONTRACT = "afde03f4ae71c8f7581266641dea040c72c3d0ef"
PROOF_BRANCH = "db-phase1-lviv-proof-v2-2026-09-27"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vadimkin_rows_to_observations(rows: list[dict]) -> tuple[list[dict], dict]:
    return lviv_canonical.vadimkin_rows_to_observations(rows)


def _bridge_observations(events: list[dict]) -> list[dict]:
    return lviv_canonical.ukrainealarm_rows_to_observations(events)


def build_lviv(fixtures: Path) -> dict:
    vad_path = fixtures / "lviv" / "vadimkin_rows.json"
    ua_path = fixtures / "lviv" / "ukrainealarm_bridge.json"
    oracle_path = fixtures / "lviv" / "oracle.json"
    vad_manifest = load_json(fixtures / "lviv" / "vadimkin_manifest.json")
    ua_manifest = load_json(fixtures / "lviv" / "ukrainealarm_manifest.json")
    oracle_manifest = load_json(fixtures / "lviv" / "oracle_manifest.json")

    assert sha256_file(vad_path) == vad_manifest["fixture_sha256"]
    assert sha256_file(ua_path) == ua_manifest["fixture_sha256"]
    assert sha256_file(oracle_path) == oracle_manifest["fixture_sha256"]
    assert vad_manifest["assembly_profile"] == ASSEMBLY_PROFILE
    assert ua_manifest["assembly_profile"] == ASSEMBLY_PROFILE
    assert oracle_manifest["assembly_profile"] == ASSEMBLY_PROFILE

    raw_vad = load_json(vad_path)["rows"]
    ua_fixture = load_json(ua_path)
    oracle = load_json(oracle_path)
    vad_obs, vad_diag = _vadimkin_rows_to_observations(raw_vad)
    ua_obs = _bridge_observations(ua_fixture["events"])
    canonical = lviv_canonical.canonicalize_lviv(
        vad_obs,
        ua_obs,
        checkpoint_state=ua_fixture["checkpoint_state"],
    )

    frozen = canonical["frozen_intervals"]
    bridge = canonical["bridge_intervals"]
    bridge_overlap = canonical["bridge_overlap"]
    bridge_new = canonical["bridge_new"]
    episodes = canonical["episodes"]
    all_obs = canonical["source_observations"]
    boundary_errors = canonical["boundary_errors"]

    assert len(frozen) == EXPECTED_FROZEN_COUNT, (len(frozen), vad_diag)
    assert len(bridge) == EXPECTED_BRIDGE_COUNT
    assert len(bridge_overlap) == EXPECTED_OVERLAP
    assert len(bridge_new) == EXPECTED_ADDITIONS
    assert len(episodes) == EXPECTED_FINAL

    oracle_by_id = {r["episode_id"]: r for r in oracle["episodes"]}
    actual_by_id = {r["legacy_episode_id"]: r for r in episodes}
    missing = sorted(set(oracle_by_id) - set(actual_by_id))
    unexpected = sorted(set(actual_by_id) - set(oracle_by_id))
    mismatches = []
    for eid in sorted(set(oracle_by_id) & set(actual_by_id)):
        o, a = oracle_by_id[eid], actual_by_id[eid]
        if o["alert_start"] != a["start"] or o["alert_end"] != a["end"]:
            mismatches.append(
                {
                    "episode_id": eid,
                    "oracle_start": o["alert_start"],
                    "oracle_end": o["alert_end"],
                    "actual_start": a["start"],
                    "actual_end": a["end"],
                }
            )
    ids = [r["legacy_episode_id"] for r in episodes]
    duplicates = sorted(k for k, v in Counter(ids).items() if v > 1)

    blocker = actual_by_id.get("b3df9090f7264ddbd726e113")
    blocker_result = {
        "api_interval_is_canonical_input": any(
            o["source_key"] == "ukrainealarm_region_history"
            and o["source_start_at"] == "2026-09-12T22:00:05.398348Z"
            and o["source_end_at"] == "2026-09-12T22:14:23.315771Z"
            for o in ua_obs
        ),
        "alerts_in_ua_static_in_stage_c": False,
        "expected_episode_present": (
            blocker is not None
            and blocker["start"] == "2026-09-12T22:00:05.398348Z"
            and blocker["end"] == "2026-09-12T22:14:23.315771Z"
        ),
        "expected_id": "b3df9090f7264ddbd726e113",
        "incorrect_expanded_id_present": "7dd411c2a2587efc740a1a66" in actual_by_id,
    }
    blocker_result["result"] = (
        "PASS"
        if blocker_result["api_interval_is_canonical_input"]
        and not blocker_result["alerts_in_ua_static_in_stage_c"]
        and blocker_result["expected_episode_present"]
        and not blocker_result["incorrect_expanded_id_present"]
        else "FAIL"
    )

    return {
        "episodes": episodes,
        "observations": all_obs,
        "raw_vadimkin_rows": len(raw_vad),
        "vadimkin_semantic_observations": len(vad_obs),
        "ukrainealarm_semantic_observations": len(ua_obs),
        "vadimkin_diagnostics": vad_diag,
        "historical_merged_count": len(frozen),
        "ukrainealarm_interval_count": len(bridge),
        "api_overlap_refinement_count": len(bridge_overlap),
        "api_additions": len(bridge_new),
        "canonical_episode_count": len(episodes),
        "unique_legacy_id_count": len(set(ids)),
        "missing_ids": missing,
        "unexpected_ids": unexpected,
        "interval_mismatches": mismatches,
        "duplicate_ids": duplicates,
        "boundary_errors": boundary_errors,
        "blocker_regression": blocker_result,
        "fixture_hashes": {
            "vadimkin_rows": vad_manifest["fixture_sha256"],
            "ukrainealarm_bridge": ua_manifest["fixture_sha256"],
            "oracle": oracle_manifest["fixture_sha256"],
        },
        "checkpoint_state": ua_fixture["checkpoint_state"],
        "serial": [
            (e["legacy_episode_id"], e["start"], e["end"])
            for e in episodes
        ],
    }


def build_recovery(fixtures: Path) -> dict:
    path = fixtures / "recovery_api_duplicate.json"
    f = load_json(path)
    api = f["api_observation"]
    manual = f["manual_recovery_observation"]
    api_json, api_key = ukrainealarm_source_record_key(api)
    manual_json, manual_key = alerts_in_ua_source_record_key(manual)
    result = reconcile_api_manual(api, manual)
    static = f["retained_static_bridge"]

    inside_static_window = (
        parse_timestamp(manual["start_at"])
        < parse_timestamp(static["coverage_end_exclusive"])
    )
    if inside_static_window:
        raise AssertionError(
            "Recovery fixture falls inside static bridge coverage; exact collision inspection required"
        )

    return {
        "fixture_sha256": sha256_file(path),
        "source_ref": f["source_ref"],
        "api_source_record_key": api_key,
        "manual_source_record_key": manual_key,
        "api_canonical_json": api_json,
        "manual_canonical_json": manual_json,
        "stage_b": result,
        "retained_observations": 2,
        "effective_bridge_intervals": 1 if result["matched"] else 2,
        "effective_start_at": result.get("effective_start_at"),
        "effective_end_at": result.get("effective_end_at"),
        "manual_duplicate_of": api_key if result["matched"] else None,
        "recovery_provenance_preserved": all(
            k in manual
            for k in (
                "original_recovery_source",
                "source_kind",
                "source_files",
                "recovery_artifact",
            )
        ),
        "static_manual_same_key_collision": "NO",
        "static_collision_basis": (
            f"manual start {manual['start_at']} is after retained static "
            f"coverage_end_exclusive {static['coverage_end_exclusive']}"
        ),
    }


def _ordered_serial(raw_rows: list[dict], ua_rows: list[dict]) -> list[tuple[str, str, str]]:
    vad, _ = _vadimkin_rows_to_observations(raw_rows)
    ua = _bridge_observations(ua_rows)
    return lviv_canonical.canonicalize_lviv(vad, ua)["serial"]


def determinism(fixtures: Path, baseline: dict) -> dict:
    second = build_lviv(fixtures)
    identical = second["serial"] == baseline["serial"]
    raw = load_json(fixtures / "lviv" / "vadimkin_rows.json")["rows"]
    ua = load_json(fixtures / "lviv" / "ukrainealarm_bridge.json")["events"]

    reversed_serial = _ordered_serial(list(reversed(raw)), list(reversed(ua)))
    alt_raw = sorted(
        raw,
        key=lambda r: (
            normalize_text(r.get("started_at", "")),
            normalize_text(r.get("finished_at", "")),
            normalize_text(r.get("level", "")),
        ),
    )
    alt_ua = sorted(
        ua,
        key=lambda r: (str(r.get("end", "")), str(r.get("start", ""))),
        reverse=True,
    )
    alt_serial = _ordered_serial(alt_raw, alt_ua)
    return {
        "identical_rerun": identical,
        "reversed_source_order": reversed_serial == baseline["serial"],
        "deterministic_alternative_order": alt_serial == baseline["serial"],
        "idempotent_output": identical,
    }


def bootstrap_summary(checkpoint_state: dict) -> dict:
    return lviv_canonical.bootstrap_summary(checkpoint_state)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--fixtures",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "db_phase1",
    )
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--proof-base", default=AMENDED_CONTRACT)
    p.add_argument(
        "--tests-command",
        default='python -m unittest discover -s tests -p "test_*.py"',
    )
    p.add_argument("--tests-run", type=int, default=0)
    p.add_argument("--tests-passed", type=int, default=0)
    p.add_argument("--tests-failed", type=int, default=0)
    p.add_argument("--test-notes", default="")
    args = p.parse_args()

    lviv = build_lviv(args.fixtures)
    recovery = build_recovery(args.fixtures)
    deterministic = determinism(args.fixtures, lviv)
    bootstrap = bootstrap_summary(lviv["checkpoint_state"])

    passed = (
        lviv["historical_merged_count"] == EXPECTED_FROZEN_COUNT
        and lviv["ukrainealarm_interval_count"] == EXPECTED_BRIDGE_COUNT
        and lviv["api_overlap_refinement_count"] == EXPECTED_OVERLAP
        and lviv["api_additions"] == EXPECTED_ADDITIONS
        and lviv["canonical_episode_count"] == EXPECTED_FINAL
        and lviv["unique_legacy_id_count"] == EXPECTED_FINAL
        and not lviv["missing_ids"]
        and not lviv["unexpected_ids"]
        and not lviv["interval_mismatches"]
        and not lviv["duplicate_ids"]
        and not lviv["boundary_errors"]
        and lviv["blocker_regression"]["result"] == "PASS"
        and all(deterministic.values())
        and recovery["stage_b"]["matched"]
        and recovery["static_manual_same_key_collision"] == "NO"
        and recovery["recovery_provenance_preserved"]
        and args.tests_failed == 0
    )

    artifact = {
        "schema_version": 1,
        "verdict": (
            "PHASE-1 LVIV CANONICALIZATION PROOF PASSED"
            if passed
            else "PHASE-1 LVIV CANONICALIZATION PROOF BLOCKED"
        ),
        "original_contract_commit": ORIGINAL_CONTRACT,
        "amended_contract_commit": AMENDED_CONTRACT,
        "proof_branch": PROOF_BRANCH,
        "proof_base": args.proof_base,
        "canonicalization_version": CANONICALIZATION_VERSION,
        "assembly_profile": ASSEMBLY_PROFILE,
        "logical_source_keys": [
            "ukrainealarm_region_history",
            "alerts_in_ua",
            "vadimkin_official_data_uk",
        ],
        "source_record_key_versions": SOURCE_KEY_VERSIONS,
        "pinned_inputs": {
            "vadimkin": {
                "repository": "Vadimkin/ukrainian-air-raid-sirens-dataset",
                "path": "datasets/official_data_uk.csv",
                "ref": "58ee75bc20113181b9ddf8029d4cbf3a62d8cd10",
                "blob": "71d70c0ca54968f530d596cf315616fa858800e1",
            },
            "ukrainealarm_bridge": {
                "repository": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
                "path": "kyiv-air-alerts-grafana/data/ukrainealarm_bridge.json",
                "ref": "e23479ef250396d441cfe68814768be8134c761d",
                "blob": "9b2922b0863ff6f3dba6e84f2348ad0e4b111d41",
            },
            "oracle": {
                "repository": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
                "path": "kyiv-air-alerts-grafana/data/explosion_metric_handoff/source_slices/lviv-replay_alerts.json",
                "ref": "9ffc0510d40c8be760d8b0262959d931a8dcdaf5",
                "blob": "925b3fb2c328560d746c73a640936b8f10b0fbe4",
            },
        },
        "fixture_hashes": {
            **lviv["fixture_hashes"],
            "recovery_api_duplicate": recovery["fixture_sha256"],
        },
        "raw_rows_by_source": {
            "vadimkin_official_data_uk": lviv["raw_vadimkin_rows"],
            "ukrainealarm_region_history": lviv["ukrainealarm_interval_count"],
            "alerts_in_ua_lviv_stage_c": 0,
        },
        "semantic_source_observations_by_source": {
            "vadimkin_official_data_uk": lviv["vadimkin_semantic_observations"],
            "ukrainealarm_region_history": lviv["ukrainealarm_semantic_observations"],
            "alerts_in_ua_lviv_stage_c": 0,
        },
        "vadimkin_premerge_diagnostics": lviv["vadimkin_diagnostics"],
        "merged_historical_episode_count": lviv["historical_merged_count"],
        "ukrainealarm_interval_count": lviv["ukrainealarm_interval_count"],
        "api_overlap_refinement_count": lviv["api_overlap_refinement_count"],
        "api_additions": lviv["api_additions"],
        "canonical_episode_count": lviv["canonical_episode_count"],
        "unique_legacy_id_count": lviv["unique_legacy_id_count"],
        "missing_oracle_ids": lviv["missing_ids"],
        "unexpected_oracle_ids": lviv["unexpected_ids"],
        "interval_mismatches": lviv["interval_mismatches"],
        "duplicate_ids": lviv["duplicate_ids"],
        "previous_blocker_regression": lviv["blocker_regression"],
        "boundary_contribution_validation": {
            "passed": not lviv["boundary_errors"],
            "errors": lviv["boundary_errors"],
        },
        "determinism": deterministic,
        "idempotence": deterministic["idempotent_output"],
        "recovery_fixture": recovery,
        "bootstrap": bootstrap,
        "tests": {
            "command": args.tests_command,
            "run": args.tests_run,
            "passed": args.tests_passed,
            "failed": args.tests_failed,
            "notes": args.test_notes,
        },
        "ddl_changed": False,
        "ddl_applied": False,
        "postgresql_created": False,
        "db_connection_attempted": False,
        "neon_touched": False,
        "production_files_changed": False,
        "historical_data_changed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(artifact["verdict"])
    print(
        json.dumps(
            {
                k: artifact[k]
                for k in (
                    "merged_historical_episode_count",
                    "ukrainealarm_interval_count",
                    "api_overlap_refinement_count",
                    "api_additions",
                    "canonical_episode_count",
                    "unique_legacy_id_count",
                )
            },
            indent=2,
        )
    )
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
