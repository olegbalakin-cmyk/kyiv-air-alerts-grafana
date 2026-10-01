#!/usr/bin/env python3
"""Persist already-canonical multicity AIR parent episodes to PostgreSQL.

This module deliberately does not canonicalize source observations. It validates
and classifies a frozen canonical corpus, then reuses Phase-1 persist_episode()
for the parent-row identity/conflict contract. Source provenance, checkpoints,
and differentiated child tables are out of scope.
"""
from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from db_phase1_core import CANONICALIZATION_VERSION, legacy_episode_id
from db_phase1_persistence import (
    SCHEMA_VERSION,
    finalize_ingestion_run,
    insert_ingestion_run,
    persist_episode,
)

RUN_KIND = "multicity_canonical_bootstrap_proof"
UTC = timezone.utc


class MulticityPersistenceError(RuntimeError):
    pass


class CorpusValidationError(MulticityPersistenceError):
    pass


class MulticityPersistenceConflict(MulticityPersistenceError):
    pass


class ForcedMulticityFailure(MulticityPersistenceError):
    pass


_EXISTING_COLUMNS = (
    "episode_uid",
    "legacy_episode_id",
    "city_key",
    "alert_type",
    "start_at",
    "end_at",
    "episode_state",
    "canonicalization_version",
)


def _mapping_row(row: Any, columns: tuple[str, ...]) -> dict[str, Any]:
    if isinstance(row, Mapping):
        return dict(row)
    return dict(zip(columns, row, strict=True))


def _as_utc(value: Any) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise CorpusValidationError(f"timestamp must be timezone-aware: {value!r}")
    return dt.astimezone(UTC)


def _time_key(value: Any) -> str:
    return _as_utc(value).isoformat(timespec="microseconds")


def _interval_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row["city_key"]),
        str(row["alert_type"]),
        _time_key(row["start_at"]),
        _time_key(row["end_at"]),
    )


def _semantic_mismatches(existing: Mapping[str, Any], candidate: Mapping[str, Any]) -> list[str]:
    mismatches: list[str] = []
    for field in ("city_key", "alert_type", "episode_state", "canonicalization_version"):
        if existing.get(field) != candidate.get(field):
            mismatches.append(field)
    for field in ("start_at", "end_at"):
        if _time_key(existing.get(field)) != _time_key(candidate.get(field)):
            mismatches.append(field)
    return mismatches


def scan_candidates(episodes: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = [dict(x) for x in episodes]
    if not rows:
        raise CorpusValidationError("canonical corpus is empty")

    seen_ids: dict[str, int] = {}
    seen_intervals: dict[tuple[str, str, str, str], int] = {}
    duplicate_ids: list[str] = []
    duplicate_intervals: list[tuple[str, str, str, str]] = []

    for index, row in enumerate(rows):
        city_key = str(row.get("city_key", "")).strip()
        alert_type = str(row.get("alert_type", "")).strip()
        state = str(row.get("episode_state", ""))
        version = str(row.get("canonicalization_version", ""))
        legacy = str(row.get("legacy_episode_id", ""))

        if not city_key:
            raise CorpusValidationError(f"row {index}: empty city_key")
        if not alert_type:
            raise CorpusValidationError(f"row {index}: empty alert_type")
        if alert_type != "AIR":
            raise CorpusValidationError(f"row {index}: unsupported alert_type={alert_type!r}")
        if state != "closed":
            raise CorpusValidationError(f"row {index}: only closed episodes are supported")
        if version != CANONICALIZATION_VERSION:
            raise CorpusValidationError(
                f"row {index}: unsupported canonicalization_version={version!r}"
            )
        if row.get("end_at") is None:
            raise CorpusValidationError(f"row {index}: closed episode has no end_at")

        start = _as_utc(row.get("start_at"))
        end = _as_utc(row.get("end_at"))
        if end <= start:
            raise CorpusValidationError(f"row {index}: invalid closed interval end <= start")

        expected_legacy = legacy_episode_id(city_key, start, end)
        if legacy != expected_legacy:
            raise CorpusValidationError(
                f"row {index}: legacy_episode_id mismatch: {legacy!r} != {expected_legacy!r}"
            )

        interval = _interval_key(row)
        if legacy in seen_ids:
            duplicate_ids.append(legacy)
        else:
            seen_ids[legacy] = index
        if interval in seen_intervals:
            duplicate_intervals.append(interval)
        else:
            seen_intervals[interval] = index

    return {
        "episodes": rows,
        "duplicate_candidate_legacy_id": len(duplicate_ids),
        "duplicate_candidate_interval": len(duplicate_intervals),
        "duplicate_legacy_ids": duplicate_ids,
        "duplicate_intervals": duplicate_intervals,
    }


def classify_candidates(
    episodes: Iterable[Mapping[str, Any]],
    existing_rows: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    scanned = scan_candidates(episodes)
    rows = scanned["episodes"]
    existing = [dict(x) for x in existing_rows]

    by_legacy = {
        str(row["legacy_episode_id"]): row
        for row in existing
        if row.get("legacy_episode_id") is not None
    }
    by_interval = {_interval_key(row): row for row in existing}

    exact: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    legacy_conflicts: list[dict[str, Any]] = []
    interval_conflicts: list[dict[str, Any]] = []
    semantic_conflicts: list[dict[str, Any]] = []

    for row in rows:
        legacy = str(row["legacy_episode_id"])
        interval = _interval_key(row)
        old_by_legacy = by_legacy.get(legacy)
        old_by_interval = by_interval.get(interval)

        if old_by_legacy is not None:
            mismatches = _semantic_mismatches(old_by_legacy, row)
            if mismatches:
                item = {"legacy_episode_id": legacy, "mismatches": mismatches}
                legacy_conflicts.append(item)
                semantic_conflicts.append(item)
                continue
            if old_by_interval is not None and str(old_by_interval.get("legacy_episode_id")) != legacy:
                item = {
                    "legacy_episode_id": legacy,
                    "existing_interval_legacy_episode_id": old_by_interval.get("legacy_episode_id"),
                }
                interval_conflicts.append(item)
                semantic_conflicts.append(item)
                continue
            exact.append(old_by_legacy)
            continue

        if old_by_interval is not None:
            item = {
                "legacy_episode_id": legacy,
                "existing_interval_legacy_episode_id": old_by_interval.get("legacy_episode_id"),
            }
            interval_conflicts.append(item)
            semantic_conflicts.append(item)
            continue

        missing.append(row)

    return {
        "candidate_count": len(rows),
        "existing_db_count": len(existing),
        "exact_existing": len(exact),
        "missing_to_insert": len(missing),
        "conflicting_legacy_id": len(legacy_conflicts),
        "conflicting_exact_interval": len(interval_conflicts),
        "semantic_conflict": len(semantic_conflicts),
        "duplicate_candidate_legacy_id": scanned["duplicate_candidate_legacy_id"],
        "duplicate_candidate_interval": scanned["duplicate_candidate_interval"],
        "exact_existing_rows": exact,
        "missing_rows": missing,
        "legacy_conflicts": legacy_conflicts,
        "interval_conflicts": interval_conflicts,
        "duplicate_legacy_ids": scanned["duplicate_legacy_ids"],
        "duplicate_intervals": scanned["duplicate_intervals"],
    }


def _read_existing(cursor: Any) -> list[dict[str, Any]]:
    cursor.execute(
        """/* MULTICITY:EXISTING_EPISODES */
        SELECT episode_uid, legacy_episode_id, city_key, alert_type, start_at, end_at,
               episode_state, canonicalization_version
        FROM alert_episodes
        """
    )
    return [_mapping_row(row, _EXISTING_COLUMNS) for row in cursor.fetchall()]


def preflight(connection: Any, episodes: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        result = classify_candidates(episodes, _read_existing(cursor))
        connection.rollback()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        close = getattr(cursor, "close", None)
        if callable(close):
            close()


def _has_conflicts(classification: Mapping[str, Any]) -> bool:
    return any(
        int(classification.get(field, 0))
        for field in (
            "conflicting_legacy_id",
            "conflicting_exact_interval",
            "semantic_conflict",
            "duplicate_candidate_legacy_id",
            "duplicate_candidate_interval",
        )
    )


def _conflict_summary(classification: Mapping[str, Any]) -> str:
    keys = (
        "conflicting_legacy_id",
        "conflicting_exact_interval",
        "semantic_conflict",
        "duplicate_candidate_legacy_id",
        "duplicate_candidate_interval",
    )
    return ", ".join(f"{key}={classification.get(key, 0)}" for key in keys)


def persist_canonical_episodes(
    connection: Any,
    episodes: Iterable[Mapping[str, Any]],
    *,
    provenance: Mapping[str, Any],
    db_branch: str,
    force_failure_after_new: int | None = None,
) -> dict[str, Any]:
    scanned = scan_candidates(episodes)
    rows = scanned["episodes"]
    if scanned["duplicate_candidate_legacy_id"] or scanned["duplicate_candidate_interval"]:
        raise CorpusValidationError(
            "candidate duplicates rejected before transaction: "
            f"legacy={scanned['duplicate_candidate_legacy_id']}, "
            f"interval={scanned['duplicate_candidate_interval']}"
        )
    if force_failure_after_new is not None and force_failure_after_new <= 0:
        raise ValueError("force_failure_after_new must be positive")

    cursor = connection.cursor()
    run_id = uuid.uuid4()
    inserted_count = 0
    existing_count = 0
    try:
        cursor.execute("/* MULTICITY:BEGIN */ BEGIN")
        classification = classify_candidates(rows, _read_existing(cursor))
        if _has_conflicts(classification):
            raise MulticityPersistenceConflict(_conflict_summary(classification))

        if classification["missing_to_insert"] == 0:
            connection.rollback()
            return {
                "status": "already_persisted",
                "run_id": None,
                "episodes_inserted": 0,
                "episodes_existing": len(rows),
                "episodes_updated": 0,
                "source_observations_inserted": 0,
                "checkpoint_changes": 0,
                "writes": 0,
                "preflight": classification,
            }

        insert_ingestion_run(
            cursor,
            run_id=run_id,
            source_key=None,
            city_key=None,
            db_branch=db_branch,
            provenance={
                **dict(provenance),
                "run_kind": provenance.get("run_kind", RUN_KIND),
                "schema_version": provenance.get("schema_version", SCHEMA_VERSION),
                "canonicalization_version": provenance.get(
                    "canonicalization_version", CANONICALIZATION_VERSION
                ),
            },
            started_at=datetime.now(tz=UTC),
        )

        for row in rows:
            _episode_uid, inserted = persist_episode(cursor, row, run_id=run_id)
            if inserted:
                inserted_count += 1
                if (
                    force_failure_after_new is not None
                    and inserted_count == force_failure_after_new
                ):
                    raise ForcedMulticityFailure(
                        f"forced failure after {force_failure_after_new} new episodes"
                    )
            else:
                existing_count += 1

        finished_at = datetime.now(tz=UTC)
        stats = {
            "episodes_inserted": inserted_count,
            "episodes_existing": existing_count,
            "episodes_updated": 0,
            "source_observations_inserted": 0,
            "checkpoint_changes": 0,
            "canonical_episode_count": len(rows),
        }
        finalize_ingestion_run(
            cursor,
            run_id=run_id,
            stats=stats,
            committed_at=finished_at,
            finished_at=finished_at,
        )
        connection.commit()
        return {
            "status": "persisted",
            "run_id": str(run_id),
            **stats,
            "writes": inserted_count + 2,
            "preflight": classification,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        close = getattr(cursor, "close", None)
        if callable(close):
            close()
