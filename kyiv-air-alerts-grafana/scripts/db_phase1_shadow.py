#!/usr/bin/env python3
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any, Callable

from db_phase1_persistence import (
    SCHEMA_VERSION,
    persist_phase1_payload,
    read_current_checkpoint,
)

SOURCE_KEY = "ukrainealarm_region_history"
CITY_KEY = "lviv"

_LAST_RESULT: dict[str, Any] | None = None
_LAST_PAYLOAD: dict[str, Any] | None = None


def _episode_rows(canonical_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    version = canonical_payload["canonicalization_version"]
    return [
        {
            "legacy_episode_id": episode["legacy_episode_id"],
            "city_key": CITY_KEY,
            "alert_type": "AIR",
            "start_at": episode["start"],
            "end_at": episode["end"],
            "episode_state": "closed",
            "canonicalization_version": version,
        }
        for episode in canonical_payload["episodes"]
    ]


def _source_rows(canonical_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observation in canonical_payload["source_observations"]:
        rows.append({
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
        })
    return rows


def _poll_checkpoint(canonical_payload: Mapping[str, Any], checkpoint_state: Mapping[str, Any]) -> dict[str, Any]:
    base = canonical_payload.get("checkpoint_candidate")
    if not isinstance(base, Mapping):
        raise RuntimeError("shadow poll requires canonical checkpoint state")
    region_id = str(checkpoint_state.get("region_id") or "").strip()
    if not region_id:
        raise RuntimeError("shadow poll requires resolved Lviv region_id")
    candidate = dict(base)
    candidate["source_key"] = SOURCE_KEY
    candidate["city_key"] = CITY_KEY
    candidate["stream_key"] = f"region_id:{region_id}:AIR"
    candidate["checkpoint_kind"] = "poll"
    candidate.pop("checkpoint_seq", None)
    candidate.pop("previous_checkpoint", None)
    candidate.pop("previous_checkpoint_id", None)
    candidate["cursor"] = checkpoint_state.get("cursor")
    candidate.setdefault("continuity_anchor_at", None)
    return candidate


def _run_provenance(canonical_payload: Mapping[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    workflow_sha = str(env.get("GITHUB_SHA") or "").strip()
    if not workflow_sha:
        raise RuntimeError("shadow poll requires GITHUB_SHA for workflow provenance")
    workflow_repository = str(env.get("GITHUB_REPOSITORY") or "").strip() or None
    workflow_ref = str(env.get("GITHUB_REF") or "").strip() or None
    workflow_name = str(env.get("GITHUB_WORKFLOW") or "").strip() or None

    input_repository = (
        str(env.get("PHASE1_INPUT_REPOSITORY") or "").strip()
        or workflow_repository
    )
    input_ref = str(env.get("PHASE1_INPUT_REF") or "").strip() or workflow_ref
    input_sha = str(env.get("PHASE1_INPUT_SHA") or "").strip() or workflow_sha
    if not input_sha:
        raise RuntimeError("shadow poll requires input SHA provenance")

    run_id = str(env.get("GITHUB_RUN_ID") or "").strip()
    run_attempt = str(env.get("GITHUB_RUN_ATTEMPT") or "").strip()
    profile = canonical_payload["assembly_profile"]
    return {
        "run_kind": "shadow_poll",
        "schema_version": SCHEMA_VERSION,
        "canonicalization_version": canonical_payload["canonicalization_version"],
        "assembly_profile": profile,
        "workflow_repository": workflow_repository,
        "workflow_name": workflow_name,
        "workflow_ref": workflow_ref,
        "workflow_sha": workflow_sha,
        "input_repository": input_repository,
        "input_ref": input_ref,
        "input_sha": input_sha,
        "github_run_id": int(run_id) if run_id else None,
        "github_run_attempt": int(run_attempt) if run_attempt else None,
        "parameters": {"assembly_profile": profile, "shadow": True},
    }

def build_shadow_persistence_payload(canonical_payload: Mapping[str, Any], *, checkpoint_state: Mapping[str, Any], env: Mapping[str, str]) -> dict[str, Any]:
    region_id = str(checkpoint_state.get("region_id") or "").strip()
    return {
        "source_key": SOURCE_KEY,
        "city_key": CITY_KEY,
        "stream_key": f"region_id:{region_id}:AIR",
        "run_provenance": _run_provenance(canonical_payload, env),
        "episodes": _episode_rows(canonical_payload),
        "source_observations": _source_rows(canonical_payload),
        "checkpoint_candidate": _poll_checkpoint(canonical_payload, checkpoint_state),
    }


def connect_database(database_url: str) -> Any:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise RuntimeError("PHASE1_DB_SHADOW=1 requires psycopg v3; shadow OFF has no DB dependency") from exc
    return psycopg.connect(database_url, row_factory=dict_row)


def persist_shadow_payload(canonical_payload: Mapping[str, Any], *, checkpoint_state: Mapping[str, Any], env: Mapping[str, str] | None = None, connect_factory: Callable[[str], Any] | None = None) -> dict[str, Any]:
    global _LAST_PAYLOAD, _LAST_RESULT
    source_env = os.environ if env is None else env
    database_url = str(source_env.get("PHASE1_DATABASE_URL") or "").strip()
    db_branch = str(source_env.get("PHASE1_DB_BRANCH") or "").strip()
    if not database_url:
        raise RuntimeError("PHASE1_DB_SHADOW=1 requires PHASE1_DATABASE_URL")
    if not db_branch:
        raise RuntimeError("PHASE1_DB_SHADOW=1 requires PHASE1_DB_BRANCH")
    payload = build_shadow_persistence_payload(canonical_payload, checkpoint_state=checkpoint_state, env=source_env)
    if payload["stream_key"].startswith("region_id::"):
        raise RuntimeError("shadow poll stream identity is missing region_id")
    factory = connect_factory or connect_database
    connection = factory(database_url)
    checkpoint = None
    try:
        result = persist_phase1_payload(
            connection,
            source_key=payload["source_key"],
            city_key=payload["city_key"],
            stream_key=payload["stream_key"],
            db_branch=db_branch,
            run_provenance=payload["run_provenance"],
            episodes=payload["episodes"],
            source_observations=payload["source_observations"],
            checkpoint_candidate=payload["checkpoint_candidate"],
        )
        cursor = connection.cursor()
        try:
            checkpoint = read_current_checkpoint(
                cursor,
                payload["source_key"],
                payload["city_key"],
                payload["stream_key"],
            )
        finally:
            close_cursor = getattr(cursor, "close", None)
            if callable(close_cursor):
                close_cursor()
        if checkpoint is None:
            raise RuntimeError(
                "shadow persistence committed but current checkpoint could not be resolved"
            )
    finally:
        close = getattr(connection, "close", None)
        if callable(close):
            close()

    output = dict(result)
    output["checkpoint_id"] = str(checkpoint["checkpoint_id"])
    output["checkpoint_seq"] = int(checkpoint["checkpoint_seq"])
    output["db_branch"] = db_branch
    output["workflow_sha"] = payload["run_provenance"].get("workflow_sha")
    output["input_sha"] = payload["run_provenance"].get("input_sha")
    _LAST_PAYLOAD = payload
    _LAST_RESULT = output
    return output

def last_shadow_payload() -> dict[str, Any] | None:
    return _LAST_PAYLOAD


def last_shadow_result() -> dict[str, Any] | None:
    return _LAST_RESULT
