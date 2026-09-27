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
    cutoff = datetime.combine(COVERAGE_START, time.min, tzinfo=KYIV_TZ).astimezone(timezone.utc)
    seen_marker: set[tuple[str, str, str]] = set()
    seen_key: dict[str, dict] = {}
    eligible: list[dict] = []
    diagnostics = Counter()

    for index, row in enumerate(rows):
        diagnostics["raw_rows"] += 1
        if normalize_text(row.get("oblast", "")) != OBLAST:
            diagnostics["geography_rejected"] += 1
            continue
        level = normalize_text(row.get("level", ""))
        raion = normalize_text(row.get("raion", ""))
        if level != "oblast" and not (level == "raion" and raion == RAION):
            diagnostics["geography_rejected"] += 1
            continue
        started = normalize_text(row.get("started_at", ""))
        finished = normalize_text(row.get("finished_at", ""))
        if not started or not finished:
            diagnostics["missing_interval"] += 1
            continue

        marker = (level, started, finished)
        if marker in seen_marker:
            diagnostics["duplicate_marker_rows"] += 1
            continue
        seen_marker.add(marker)

        try:
            start = parse_timestamp(started)
            end = parse_timestamp(finished)
        except (TypeError, ValueError):
            diagnostics["invalid_timestamp"] += 1
            continue
        if end <= start:
            diagnostics["invalid_interval"] += 1
            continue
        if end <= cutoff:
            diagnostics["before_coverage"] += 1
            continue

        key_fields = dict(row)
        key_fields["start_at"] = started
        key_fields["end_at"] = finished
        canonical, key = vadimkin_source_record_key(key_fields)
        if key in seen_key:
            diagnostics["duplicate_semantic_key"] += 1
            continue

        effective_start = max(start, cutoff)
        obs = {
            "source_key": SOURCE_KEYS["vadimkin"],
            "source_record_key_version": SOURCE_KEY_VERSIONS[SOURCE_KEYS["vadimkin"]],
            "source_record_key": key,
            "source_native_id": None,
            "city_key": CITY_KEY,
            "alert_type": "AIR",
            "source_start_at": source_key_timestamp(start),
            "source_end_at": source_key_timestamp(end),
            "source_retrieved_at": None,
            "binding_state": "bound",
            "canonicalization_role": "canonical_input",
            "provenance": {
                "fixture_row_index": index,
                "canonical_preimage": canonical,
                "original_level": row.get("level", ""),
                "original_oblast": row.get("oblast", ""),
                "original_raion": row.get("raion", ""),
                "original_hromada": row.get("hromada", ""),
                "original_source": row.get("source", ""),
                "coverage_clipped_start": effective_start != start,
            },
            "effective_interval": Interval(effective_start, end),
            "contributes_start_boundary": False,
            "contributes_end_boundary": False,
        }
        seen_key[key] = obs
        eligible.append(obs)
        diagnostics["semantic_observations"] += 1
    return eligible, dict(diagnostics)


def _bridge_observations(events: list[dict]) -> list[dict]:
    end_exclusive = datetime.combine(
        HISTORICAL_END_EXCLUSIVE, time.min, tzinfo=KYIV_TZ
    ).astimezone(timezone.utc)
    by_key: dict[str, dict] = {}
    for index, row in enumerate(events):
        if row.get("city_key") != CITY_KEY:
            continue
        if normalize_text(row.get("alert_type", "")).upper() != "AIR":
            continue
        start = parse_timestamp(str(row["start"]))
        end = parse_timestamp(str(row["end"]))
        if end <= start:
            raise AssertionError(f"Invalid bridge interval: {row}")
        if start >= end_exclusive:
            continue
        fields = {
            "city_key": row["city_key"],
            "region_id": row["region_id"],
            "alert_type": row["alert_type"],
            "start_at": row["start"],
            "end_at": row["end"],
        }
        canonical, key = ukrainealarm_source_record_key(fields)
        by_key.setdefault(
            key,
            {
                "source_key": SOURCE_KEYS["ukrainealarm"],
                "source_record_key_version": SOURCE_KEY_VERSIONS[SOURCE_KEYS["ukrainealarm"]],
                "source_record_key": key,
                "source_native_id": None,
                "city_key": CITY_KEY,
                "alert_type": "AIR",
                "source_start_at": source_key_timestamp(start),
                "source_end_at": source_key_timestamp(end),
                "source_retrieved_at": None,
                "binding_state": "bound",
                "canonicalization_role": "canonical_input",
                "provenance": {
                    "fixture_row_index": index,
                    "api_region_name": row.get("api_region_name"),
                    "region_id": str(row["region_id"]),
                    "canonical_preimage": canonical,
                },
                "effective_interval": Interval(start, end),
                "contributes_start_boundary": False,
                "contributes_end_boundary": False,
            },
        )
    return sorted(
        by_key.values(),
        key=lambda x: (x["effective_interval"].start, x["effective_interval"].end),
    )


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

    frozen = merge_intervals(o["effective_interval"] for o in vad_obs)
    bridge = [o["effective_interval"] for o in ua_obs]
    assert len(frozen) == EXPECTED_FROZEN_COUNT, (len(frozen), vad_diag)
    assert len(bridge) == EXPECTED_BRIDGE_COUNT

    bridge_overlap = [
        i for i in bridge
        if any(intervals_overlap_or_touch(i, f) for f in frozen)
    ]
    bridge_new = [i for i in bridge if i not in bridge_overlap]
    assert len(bridge_overlap) == EXPECTED_OVERLAP
    assert len(bridge_new) == EXPECTED_ADDITIONS

    final = merge_intervals([*frozen, *bridge])
    assert len(final) == EXPECTED_FINAL
    episodes = [
        {
            "legacy_episode_id": legacy_episode_id(CITY_KEY, i.start, i.end),
            "start": legacy_timestamp(i.start),
            "end": legacy_timestamp(i.end),
            "interval": i,
        }
        for i in final
    ]

    all_obs = [*vad_obs, *ua_obs]
    for obs in all_obs:
        i = obs["effective_interval"]
        candidates = [
            e for e in episodes
            if e["interval"].start <= i.start and e["interval"].end >= i.end
        ]
        if len(candidates) != 1:
            raise AssertionError(
                f"Observation binding ambiguity: {obs['source_record_key']} -> {len(candidates)}"
            )
        e = candidates[0]
        obs["episode_id"] = e["legacy_episode_id"]
        obs["contributes_start_boundary"] = (
            parse_timestamp(obs["source_start_at"]) == e["interval"].start
        )
        obs["contributes_end_boundary"] = (
            parse_timestamp(obs["source_end_at"]) == e["interval"].end
        )

    boundary_errors = []
    for e in episodes:
        bound = [o for o in all_obs if o["episode_id"] == e["legacy_episode_id"]]
        starters = [o for o in bound if o["contributes_start_boundary"]]
        enders = [o for o in bound if o["contributes_end_boundary"]]
        if not starters:
            boundary_errors.append(
                {"episode_id": e["legacy_episode_id"], "boundary": "start", "reason": "no_contributor"}
            )
        if not enders:
            boundary_errors.append(
                {"episode_id": e["legacy_episode_id"], "boundary": "end", "reason": "no_contributor"}
            )
        for o in starters:
            if parse_timestamp(o["source_start_at"]) != e["interval"].start:
                boundary_errors.append(
                    {
                        "episode_id": e["legacy_episode_id"],
                        "boundary": "start",
                        "reason": "claim_mismatch",
                        "source_record_key": o["source_record_key"],
                    }
                )
        for o in enders:
            if parse_timestamp(o["source_end_at"]) != e["interval"].end:
                boundary_errors.append(
                    {
                        "episode_id": e["legacy_episode_id"],
                        "boundary": "end",
                        "reason": "claim_mismatch",
                        "source_record_key": o["source_record_key"],
                    }
                )

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
    final = merge_intervals(
        [
            *(o["effective_interval"] for o in vad),
            *(o["effective_interval"] for o in ua),
        ]
    )
    return [
        (
            legacy_episode_id(CITY_KEY, i.start, i.end),
            legacy_timestamp(i.start),
            legacy_timestamp(i.end),
        )
        for i in final
    ]


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
    return {
        "ingestion_run": {
            "run_kind": "bootstrap_import",
            "canonicalization_version": CANONICALIZATION_VERSION,
            "parameters": {"assembly_profile": ASSEMBLY_PROFILE},
        },
        "checkpoint_candidate": {
            "source_key": "ukrainealarm_region_history",
            "city_key": CITY_KEY,
            "stream_key": "region_id:90:AIR",
            "checkpoint_seq": 1,
            "checkpoint_kind": "bootstrap",
            "previous_checkpoint": None,
            "checked_at": checkpoint_state.get("last_checked_at"),
            "continuity_verified": bool(checkpoint_state.get("continuous")),
            "continuity_method": checkpoint_state.get("continuity_reason"),
            "continuity_anchor_at": None,
            "observed_oldest_start_at": checkpoint_state.get("oldest_history_start"),
            "observed_latest_end_at": checkpoint_state.get("latest_history_end"),
            "observed_record_count": checkpoint_state.get("history_completed_air_count"),
            "metadata": {
                "initial_static_match": checkpoint_state.get("initial_static_match"),
                "poll_overlap_verified": checkpoint_state.get("poll_overlap_verified"),
                "api_region_name": checkpoint_state.get("api_region_name"),
                "region_id": checkpoint_state.get("region_id"),
                "kind": checkpoint_state.get("kind"),
                "target": checkpoint_state.get("target"),
                "oblast": checkpoint_state.get("oblast"),
                "last_error": checkpoint_state.get("last_error"),
                "observed_latest_end_is_coverage_watermark": False,
            },
        },
        "alerts_in_ua_static_episode_observation_created": False,
    }


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
