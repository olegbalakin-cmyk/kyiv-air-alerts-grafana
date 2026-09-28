#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Callable, Mapping

from db_phase1_core import CANONICALIZATION_VERSION
from db_phase1_lviv_proof import ASSEMBLY_PROFILE, bootstrap_summary, build_lviv
from db_phase1_persistence import SCHEMA_VERSION, persist_phase1_payload

SOURCE_KEY = "ukrainealarm_region_history"
CITY_KEY = "lviv"
STREAM_KEY = "region_id:90:AIR"
INPUT_REPOSITORY = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
INPUT_REF = "db-phase1-lviv-proof-v2-2026-09-27"
INPUT_SHA = "c96340736f95bcd97ba032862f3cd9c3a2e7827f"


def build_lviv_persistence_payload(fixtures: Path | None = None) -> dict[str, Any]:
    fixtures = fixtures or (Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "db_phase1")
    built = build_lviv(fixtures)
    oracle_ok = (
        not built["missing_ids"]
        and not built["unexpected_ids"]
        and not built["interval_mismatches"]
        and not built["duplicate_ids"]
        and not built["boundary_errors"]
        and built["blocker_regression"]["result"] == "PASS"
    )
    if not oracle_ok:
        raise RuntimeError(
            "Lviv Phase-1 oracle validation failed before persistence: "
            f"missing={len(built['missing_ids'])}, "
            f"unexpected={len(built['unexpected_ids'])}, "
            f"interval_mismatches={len(built['interval_mismatches'])}, "
            f"duplicate_ids={len(built['duplicate_ids'])}, "
            f"boundary_errors={len(built['boundary_errors'])}, "
            f"blocker={built['blocker_regression']['result']}"
        )

    episodes = [
        {
            "legacy_episode_id": episode["legacy_episode_id"],
            "city_key": CITY_KEY,
            "alert_type": "AIR",
            "start_at": episode["start"],
            "end_at": episode["end"],
            "episode_state": "closed",
            "canonicalization_version": CANONICALIZATION_VERSION,
        }
        for episode in built["episodes"]
    ]
    observations = []
    for observation in built["observations"]:
        observations.append(
            {
                "episode_legacy_id": observation["episode_id"],
                "source_key": observation["source_key"],
                "source_record_key_version": observation["source_record_key_version"],
                "source_record_key": observation["source_record_key"],
                "source_native_id": observation.get("source_native_id"),
                "city_key": observation["city_key"],
                "alert_type": observation["alert_type"],
                "source_start_at": observation["source_start_at"],
                "source_end_at": observation.get("source_end_at"),
                "source_retrieved_at": observation.get("source_retrieved_at"),
                "binding_state": observation["binding_state"],
                "canonicalization_role": observation["canonicalization_role"],
                "duplicate_of_observation_id": observation.get("duplicate_of_observation_id"),
                "match_method": observation.get("match_method"),
                "start_delta_ms": observation.get("start_delta_ms"),
                "end_delta_ms": observation.get("end_delta_ms"),
                "contributes_start_boundary": observation["contributes_start_boundary"],
                "contributes_end_boundary": observation["contributes_end_boundary"],
                "raw_sha256": observation.get("raw_sha256"),
                "raw_object_path": observation.get("raw_object_path"),
                "provenance": observation.get("provenance", {}),
            }
        )

    checkpoint = dict(bootstrap_summary(built["checkpoint_state"])["checkpoint_candidate"])
    checkpoint["previous_checkpoint_id"] = checkpoint.pop("previous_checkpoint")
    checkpoint["cursor"] = None

    return {
        "source_key": SOURCE_KEY,
        "city_key": CITY_KEY,
        "stream_key": STREAM_KEY,
        "run_provenance": {
            "run_kind": "bootstrap_import",
            "schema_version": SCHEMA_VERSION,
            "canonicalization_version": CANONICALIZATION_VERSION,
            "parameters": {"assembly_profile": ASSEMBLY_PROFILE},
            "input_repository": INPUT_REPOSITORY,
            "input_ref": INPUT_REF,
            "input_sha": INPUT_SHA,
            "workflow_repository": None,
            "workflow_name": None,
            "workflow_ref": None,
            "workflow_sha": None,
            "github_run_id": None,
            "github_run_attempt": None,
        },
        "episodes": episodes,
        "source_observations": observations,
        "checkpoint_candidate": checkpoint,
        "validation": {
            "missing_ids": built["missing_ids"],
            "unexpected_ids": built["unexpected_ids"],
            "interval_mismatches": built["interval_mismatches"],
            "duplicate_ids": built["duplicate_ids"],
            "boundary_errors": built["boundary_errors"],
            "blocker_regression": built["blocker_regression"]["result"],
            "oracle_parity": "PASS",
            "vadimkin_count": built["vadimkin_semantic_observations"],
            "ukrainealarm_count": built["ukrainealarm_semantic_observations"],
        },
    }


def _print_dry_run(payload: Mapping[str, Any]) -> None:
    validation = payload["validation"]
    print(f"canonical episodes = {len(payload['episodes'])}")
    print(f"source observations = {len(payload['source_observations'])}")
    print(f"Vadimkin = {validation['vadimkin_count']}")
    print(f"UkraineAlarm = {validation['ukrainealarm_count']}")
    print("checkpoint candidates = 1")
    print(f"oracle parity = {validation['oracle_parity']}")


def connect_database(database_url: str) -> Any:
    try:
        import psycopg  # type: ignore[import-not-found]
        from psycopg.rows import dict_row  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError(
            "--apply requires psycopg v3; install the isolated requirements-db-phase1.txt dependency set"
        ) from exc
    return psycopg.connect(database_url, row_factory=dict_row)


def main(
    argv: list[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
    connect_factory: Callable[[str], Any] | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Persist the accepted Phase-1 Lviv bootstrap payload")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="validate/reconstruct only; this is the default")
    mode.add_argument("--apply", action="store_true", help="persist the validated payload")
    parser.add_argument("--database-url-env", default="DATABASE_URL")
    parser.add_argument("--db-branch")
    parser.add_argument("--fixtures", type=Path)
    args = parser.parse_args(argv)

    # The payload and all oracle checks are completed before any database connection is considered.
    payload = build_lviv_persistence_payload(args.fixtures)
    if not args.apply:
        _print_dry_run(payload)
        return 0

    if not args.db_branch:
        parser.error("--apply requires --db-branch")
    source_env = os.environ if env is None else env
    database_url = source_env.get(args.database_url_env)
    if not database_url:
        parser.error(f"--apply requires database URL via environment variable {args.database_url_env}")

    factory = connect_factory or connect_database
    try:
        connection = factory(database_url)
    except RuntimeError as exc:
        parser.exit(2, f"error: {exc}\n")

    try:
        result = persist_phase1_payload(
            connection,
            source_key=payload["source_key"],
            city_key=payload["city_key"],
            stream_key=payload["stream_key"],
            db_branch=args.db_branch,
            run_provenance=payload["run_provenance"],
            episodes=payload["episodes"],
            source_observations=payload["source_observations"],
            checkpoint_candidate=payload["checkpoint_candidate"],
        )
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()

    stats = result["stats"]
    print("Phase-1 Lviv persistence committed")
    print(f"episodes inserted = {stats['episodes_inserted']}")
    print(f"source observations inserted = {stats['source_observations_inserted']}")
    print(f"source observations last-seen updated = {stats['source_observations_last_seen_updated']}")
    print(f"checkpoints inserted = {stats['checkpoints_inserted']}")
    print(f"exact retry = {str(stats['exact_retry']).lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
