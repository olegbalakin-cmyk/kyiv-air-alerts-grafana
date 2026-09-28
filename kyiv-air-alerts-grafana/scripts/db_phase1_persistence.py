#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Callable

STREAM_LOCK_VERSION = "phase1-stream-lock-v1"
SCHEMA_VERSION = "001_phase1_core"


class PersistenceConflict(RuntimeError):
    """Base class for semantic persistence conflicts that must abort the transaction."""


class EpisodeConflict(PersistenceConflict):
    pass


class SourceObservationConflict(PersistenceConflict):
    pass


class CheckpointConflict(PersistenceConflict):
    pass


def stream_lock_key(source_key: str, city_key: str, stream_key: str) -> int:
    """Return a stable signed PostgreSQL bigint advisory-lock key for one stream."""
    preimage = "\x1f".join((STREAM_LOCK_VERSION, source_key, city_key, stream_key))
    digest = hashlib.sha256(preimage.encode("utf-8")).digest()
    unsigned = int.from_bytes(digest[:8], byteorder="big", signed=False)
    return unsigned if unsigned < (1 << 63) else unsigned - (1 << 64)


def acquire_stream_lock(cursor: Any, source_key: str, city_key: str, stream_key: str) -> int:
    key = stream_lock_key(source_key, city_key, stream_key)
    cursor.execute(
        "/* PHASE1:LOCK */ SELECT pg_advisory_xact_lock(%s)",
        (key,),
    )
    return key


def _mapping_row(row: Any, columns: tuple[str, ...]) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, Mapping):
        return dict(row)
    return dict(zip(columns, row, strict=True))


def _as_utc(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        raise ValueError(f"Expected timezone-aware timestamp, got {value!r}")
    return dt.astimezone(timezone.utc)


def _json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _same_timestamp(left: Any, right: Any) -> bool:
    return _as_utc(left) == _as_utc(right)


def _semantic_mismatches(
    existing: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    timestamp_fields: tuple[str, ...] = (),
    json_fields: tuple[str, ...] = (),
    fields: tuple[str, ...],
) -> list[str]:
    mismatches: list[str] = []
    for field in fields:
        left, right = existing.get(field), candidate.get(field)
        if field in timestamp_fields:
            equal = _same_timestamp(left, right)
        elif field in json_fields:
            equal = _json_value(left) == _json_value(right)
        else:
            equal = left == right
        if not equal:
            mismatches.append(field)
    return mismatches


_CHECKPOINT_COLUMNS = (
    "checkpoint_id",
    "source_key",
    "city_key",
    "stream_key",
    "checkpoint_seq",
    "checkpoint_kind",
    "previous_checkpoint_id",
    "checked_at",
    "continuity_verified",
    "continuity_method",
    "continuity_anchor_at",
    "observed_oldest_start_at",
    "observed_latest_end_at",
    "observed_record_count",
    "cursor",
    "metadata",
    "created_by_run_id",
    "created_at",
)


def read_current_checkpoint(cursor: Any, source_key: str, city_key: str, stream_key: str) -> dict[str, Any] | None:
    cursor.execute(
        """/* PHASE1:CHECKPOINT_REREAD */
        SELECT checkpoint_id, source_key, city_key, stream_key, checkpoint_seq,
               checkpoint_kind, previous_checkpoint_id, checked_at,
               continuity_verified, continuity_method, continuity_anchor_at,
               observed_oldest_start_at, observed_latest_end_at,
               observed_record_count, cursor, metadata, created_by_run_id, created_at
        FROM current_ingestion_checkpoints
        WHERE source_key = %s AND city_key = %s AND stream_key = %s
        """,
        (source_key, city_key, stream_key),
    )
    return _mapping_row(cursor.fetchone(), _CHECKPOINT_COLUMNS)


def insert_ingestion_run(
    cursor: Any,
    *,
    run_id: uuid.UUID,
    source_key: str,
    city_key: str,
    db_branch: str,
    provenance: Mapping[str, Any],
    started_at: datetime,
) -> None:
    parameters = provenance.get("parameters", {})
    cursor.execute(
        """/* PHASE1:RUN_INSERT */
        INSERT INTO ingestion_runs (
            run_id, run_kind, source_key, city_key,
            workflow_repository, workflow_name, workflow_ref, workflow_sha,
            input_repository, input_ref, input_sha,
            github_run_id, github_run_attempt, db_branch,
            schema_version, canonicalization_version, status, started_at,
            parameters, stats
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s::jsonb, %s::jsonb
        )
        """,
        (
            run_id,
            provenance["run_kind"],
            source_key,
            city_key,
            provenance.get("workflow_repository"),
            provenance.get("workflow_name"),
            provenance.get("workflow_ref"),
            provenance.get("workflow_sha"),
            provenance.get("input_repository"),
            provenance.get("input_ref"),
            provenance.get("input_sha"),
            provenance.get("github_run_id"),
            provenance.get("github_run_attempt"),
            db_branch,
            provenance.get("schema_version", SCHEMA_VERSION),
            provenance.get("canonicalization_version"),
            "running",
            started_at,
            json.dumps(parameters, ensure_ascii=False, sort_keys=True),
            json.dumps({}, sort_keys=True),
        ),
    )


def finalize_ingestion_run(
    cursor: Any,
    *,
    run_id: uuid.UUID,
    stats: Mapping[str, Any],
    committed_at: datetime,
    finished_at: datetime,
) -> None:
    cursor.execute(
        """/* PHASE1:RUN_FINALIZE */
        UPDATE ingestion_runs
        SET status = %s,
            ingest_committed_at = %s,
            finished_at = %s,
            stats = %s::jsonb
        WHERE run_id = %s
        """,
        (
            "succeeded",
            committed_at,
            finished_at,
            json.dumps(dict(stats), ensure_ascii=False, sort_keys=True),
            run_id,
        ),
    )


_EPISODE_COLUMNS = (
    "episode_uid",
    "legacy_episode_id",
    "city_key",
    "alert_type",
    "start_at",
    "end_at",
    "episode_state",
    "canonicalization_version",
    "created_by_run_id",
    "updated_by_run_id",
)
_EPISODE_SEMANTIC_FIELDS = (
    "city_key",
    "alert_type",
    "start_at",
    "end_at",
    "episode_state",
    "canonicalization_version",
)


def persist_episode(cursor: Any, episode: Mapping[str, Any], *, run_id: uuid.UUID) -> tuple[Any, bool]:
    legacy_episode_id = episode["legacy_episode_id"]
    cursor.execute(
        """/* PHASE1:EPISODE_LOOKUP */
        SELECT episode_uid, legacy_episode_id, city_key, alert_type, start_at, end_at,
               episode_state, canonicalization_version, created_by_run_id, updated_by_run_id
        FROM alert_episodes
        WHERE legacy_episode_id = %s
        """,
        (legacy_episode_id,),
    )
    existing = _mapping_row(cursor.fetchone(), _EPISODE_COLUMNS)
    if existing is not None:
        mismatches = _semantic_mismatches(
            existing,
            episode,
            fields=_EPISODE_SEMANTIC_FIELDS,
            timestamp_fields=("start_at", "end_at"),
        )
        if mismatches:
            raise EpisodeConflict(
                f"episode semantic conflict for legacy_episode_id={legacy_episode_id}: "
                + ", ".join(mismatches)
            )
        return existing["episode_uid"], False

    cursor.execute(
        """/* PHASE1:EPISODE_INSERT */
        INSERT INTO alert_episodes (
            legacy_episode_id, city_key, alert_type, start_at, end_at,
            episode_state, canonicalization_version, created_by_run_id, updated_by_run_id
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING episode_uid
        """,
        (
            legacy_episode_id,
            episode["city_key"],
            episode["alert_type"],
            episode["start_at"],
            episode.get("end_at"),
            episode["episode_state"],
            episode["canonicalization_version"],
            run_id,
            run_id,
        ),
    )
    inserted = cursor.fetchone()
    row = _mapping_row(inserted, ("episode_uid",))
    if not row:
        raise RuntimeError("episode insert did not return episode_uid")
    return row["episode_uid"], True


_SOURCE_COLUMNS = (
    "source_observation_id",
    "episode_uid",
    "source_key",
    "source_record_key_version",
    "source_record_key",
    "city_key",
    "alert_type",
    "source_start_at",
    "source_end_at",
    "binding_state",
    "canonicalization_role",
    "duplicate_of_observation_id",
    "contributes_start_boundary",
    "contributes_end_boundary",
    "first_persisted_by_run_id",
    "last_seen_by_run_id",
    "first_persisted_at",
    "last_seen_at",
)
_SOURCE_SEMANTIC_FIELDS = (
    "episode_uid",
    "city_key",
    "alert_type",
    "source_start_at",
    "source_end_at",
    "binding_state",
    "canonicalization_role",
    "duplicate_of_observation_id",
    "contributes_start_boundary",
    "contributes_end_boundary",
)


def persist_source_observation(
    cursor: Any,
    observation: Mapping[str, Any],
    *,
    episode_uid: Any,
    run_id: uuid.UUID,
    seen_at: datetime,
) -> tuple[Any, bool]:
    identity = (
        observation["source_key"],
        observation["source_record_key_version"],
        observation["source_record_key"],
    )
    cursor.execute(
        """/* PHASE1:SOURCE_LOOKUP */
        SELECT source_observation_id, episode_uid, source_key, source_record_key_version,
               source_record_key, city_key, alert_type, source_start_at, source_end_at,
               binding_state, canonicalization_role, duplicate_of_observation_id,
               contributes_start_boundary, contributes_end_boundary,
               first_persisted_by_run_id, last_seen_by_run_id,
               first_persisted_at, last_seen_at
        FROM alert_episode_sources
        WHERE source_key = %s
          AND source_record_key_version = %s
          AND source_record_key = %s
        """,
        identity,
    )
    existing = _mapping_row(cursor.fetchone(), _SOURCE_COLUMNS)
    candidate = dict(observation)
    candidate["episode_uid"] = episode_uid
    if existing is not None:
        mismatches = _semantic_mismatches(
            existing,
            candidate,
            fields=_SOURCE_SEMANTIC_FIELDS,
            timestamp_fields=("source_start_at", "source_end_at"),
        )
        if mismatches:
            raise SourceObservationConflict(
                "source observation semantic conflict for identity="
                f"{identity!r}: {', '.join(mismatches)}"
            )
        cursor.execute(
            """/* PHASE1:SOURCE_LAST_SEEN_UPDATE */
            UPDATE alert_episode_sources
            SET last_seen_by_run_id = %s,
                last_seen_at = %s
            WHERE source_observation_id = %s
            """,
            (run_id, seen_at, existing["source_observation_id"]),
        )
        return existing["source_observation_id"], False

    cursor.execute(
        """/* PHASE1:SOURCE_INSERT */
        INSERT INTO alert_episode_sources (
            episode_uid, source_key, source_record_key_version, source_record_key,
            source_native_id, city_key, alert_type, source_start_at, source_end_at,
            source_retrieved_at, binding_state, canonicalization_role,
            duplicate_of_observation_id, match_method, start_delta_ms, end_delta_ms,
            contributes_start_boundary, contributes_end_boundary,
            raw_sha256, raw_object_path, provenance,
            first_persisted_by_run_id, last_seen_by_run_id,
            first_persisted_at, last_seen_at
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s::jsonb,
            %s, %s, %s, %s
        )
        RETURNING source_observation_id
        """,
        (
            episode_uid,
            observation["source_key"],
            observation["source_record_key_version"],
            observation["source_record_key"],
            observation.get("source_native_id"),
            observation["city_key"],
            observation["alert_type"],
            observation["source_start_at"],
            observation.get("source_end_at"),
            observation.get("source_retrieved_at"),
            observation["binding_state"],
            observation["canonicalization_role"],
            observation.get("duplicate_of_observation_id"),
            observation.get("match_method"),
            observation.get("start_delta_ms"),
            observation.get("end_delta_ms"),
            bool(observation.get("contributes_start_boundary", False)),
            bool(observation.get("contributes_end_boundary", False)),
            observation.get("raw_sha256"),
            observation.get("raw_object_path"),
            json.dumps(observation.get("provenance", {}), ensure_ascii=False, sort_keys=True),
            run_id,
            run_id,
            seen_at,
            seen_at,
        ),
    )
    inserted = _mapping_row(cursor.fetchone(), ("source_observation_id",))
    if not inserted:
        raise RuntimeError("source observation insert did not return source_observation_id")
    return inserted["source_observation_id"], True


_CHECKPOINT_SEMANTIC_FIELDS = (
    "source_key",
    "city_key",
    "stream_key",
    "checkpoint_kind",
    "checked_at",
    "continuity_verified",
    "continuity_method",
    "continuity_anchor_at",
    "observed_oldest_start_at",
    "observed_latest_end_at",
    "observed_record_count",
    "cursor",
    "metadata",
)


def checkpoint_semantically_equal(existing: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    return not _semantic_mismatches(
        existing,
        candidate,
        fields=_CHECKPOINT_SEMANTIC_FIELDS,
        timestamp_fields=(
            "checked_at",
            "continuity_anchor_at",
            "observed_oldest_start_at",
            "observed_latest_end_at",
        ),
        json_fields=("cursor", "metadata"),
    )


def _insert_checkpoint(
    cursor: Any,
    candidate: Mapping[str, Any],
    *,
    checkpoint_seq: int,
    previous_checkpoint_id: Any,
    run_id: uuid.UUID,
) -> Any:
    cursor.execute(
        """/* PHASE1:CHECKPOINT_INSERT */
        INSERT INTO ingestion_checkpoints (
            source_key, city_key, stream_key, checkpoint_seq, checkpoint_kind,
            previous_checkpoint_id, checked_at, continuity_verified, continuity_method,
            continuity_anchor_at, observed_oldest_start_at, observed_latest_end_at,
            observed_record_count, cursor, metadata, created_by_run_id
        ) VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s::jsonb, %s::jsonb, %s
        )
        RETURNING checkpoint_id
        """,
        (
            candidate["source_key"],
            candidate["city_key"],
            candidate["stream_key"],
            checkpoint_seq,
            candidate["checkpoint_kind"],
            previous_checkpoint_id,
            candidate["checked_at"],
            bool(candidate["continuity_verified"]),
            candidate.get("continuity_method"),
            candidate.get("continuity_anchor_at"),
            candidate.get("observed_oldest_start_at"),
            candidate.get("observed_latest_end_at"),
            candidate.get("observed_record_count"),
            (
                None
                if candidate.get("cursor") is None
                else json.dumps(candidate.get("cursor"), ensure_ascii=False, sort_keys=True)
            ),
            json.dumps(candidate.get("metadata", {}), ensure_ascii=False, sort_keys=True),
            run_id,
        ),
    )
    inserted = _mapping_row(cursor.fetchone(), ("checkpoint_id",))
    if not inserted:
        raise RuntimeError("checkpoint insert did not return checkpoint_id")
    return inserted["checkpoint_id"]


def persist_bootstrap_checkpoint(
    cursor: Any,
    candidate: Mapping[str, Any],
    *,
    current_checkpoint: Mapping[str, Any] | None,
    run_id: uuid.UUID,
) -> tuple[Any, bool, bool]:
    if candidate.get("checkpoint_seq") != 1 or candidate.get("checkpoint_kind") != "bootstrap":
        raise CheckpointConflict("Phase-1 bootstrap candidate must be bootstrap checkpoint_seq=1")
    if candidate.get("previous_checkpoint_id") is not None:
        raise CheckpointConflict("Phase-1 bootstrap checkpoint must have previous_checkpoint_id=NULL")

    if current_checkpoint is not None:
        if current_checkpoint.get("checkpoint_seq") != 1:
            raise CheckpointConflict(
                "bootstrap candidate cannot be applied after a non-bootstrap checkpoint chain"
            )
        if not checkpoint_semantically_equal(current_checkpoint, candidate):
            mismatches = _semantic_mismatches(
                current_checkpoint,
                candidate,
                fields=_CHECKPOINT_SEMANTIC_FIELDS,
                timestamp_fields=(
                    "checked_at",
                    "continuity_anchor_at",
                    "observed_oldest_start_at",
                    "observed_latest_end_at",
                ),
                json_fields=("cursor", "metadata"),
            )
            raise CheckpointConflict(
                "bootstrap checkpoint semantic conflict: " + ", ".join(mismatches)
            )
        return current_checkpoint["checkpoint_id"], False, True

    checkpoint_id = _insert_checkpoint(
        cursor,
        candidate,
        checkpoint_seq=1,
        previous_checkpoint_id=None,
        run_id=run_id,
    )
    return checkpoint_id, True, False


def persist_poll_checkpoint(
    cursor: Any,
    candidate: Mapping[str, Any],
    *,
    current_checkpoint: Mapping[str, Any] | None,
    run_id: uuid.UUID,
) -> tuple[Any, bool, bool]:
    if candidate.get("checkpoint_kind") != "poll":
        raise CheckpointConflict("Phase-1 poll candidate must have checkpoint_kind=poll")

    forbidden_chain_fields = [
        field for field in ("checkpoint_seq", "previous_checkpoint_id") if field in candidate
    ]
    if forbidden_chain_fields:
        raise CheckpointConflict(
            "poll candidate must omit transaction-derived chain fields: "
            + ", ".join(forbidden_chain_fields)
        )

    if current_checkpoint is None:
        raise CheckpointConflict("poll checkpoint cannot start a stream; bootstrap is required")

    if checkpoint_semantically_equal(current_checkpoint, candidate):
        return current_checkpoint["checkpoint_id"], False, True

    next_seq = int(current_checkpoint["checkpoint_seq"]) + 1
    checkpoint_id = _insert_checkpoint(
        cursor,
        candidate,
        checkpoint_seq=next_seq,
        previous_checkpoint_id=current_checkpoint["checkpoint_id"],
        run_id=run_id,
    )
    return checkpoint_id, True, False


def persist_checkpoint_candidate(
    cursor: Any,
    candidate: Mapping[str, Any],
    *,
    current_checkpoint: Mapping[str, Any] | None,
    run_id: uuid.UUID,
) -> tuple[Any, bool, bool]:
    checkpoint_kind = candidate.get("checkpoint_kind")
    if checkpoint_kind == "bootstrap":
        return persist_bootstrap_checkpoint(
            cursor,
            candidate,
            current_checkpoint=current_checkpoint,
            run_id=run_id,
        )
    if checkpoint_kind == "poll":
        return persist_poll_checkpoint(
            cursor,
            candidate,
            current_checkpoint=current_checkpoint,
            run_id=run_id,
        )
    raise CheckpointConflict(f"unsupported checkpoint_kind={checkpoint_kind!r}")

def persist_phase1_payload(
    connection: Any,
    *,
    source_key: str,
    city_key: str,
    stream_key: str,
    db_branch: str,
    run_provenance: Mapping[str, Any],
    episodes: list[Mapping[str, Any]],
    source_observations: list[Mapping[str, Any]],
    checkpoint_candidate: Mapping[str, Any],
    now_factory: Callable[[], datetime] | None = None,
    post_lock_callback: Callable[[Mapping[str, Any] | None], None] | None = None,
) -> dict[str, Any]:
    """Persist one already-built Phase-1 payload as one all-or-nothing transaction."""
    now = now_factory or (lambda: datetime.now(timezone.utc))
    run_id = uuid.uuid4()
    cursor = connection.cursor()
    try:
        cursor.execute("/* PHASE1:BEGIN */ BEGIN")
        acquire_stream_lock(cursor, source_key, city_key, stream_key)
        current_checkpoint = read_current_checkpoint(cursor, source_key, city_key, stream_key)
        if post_lock_callback is not None:
            post_lock_callback(current_checkpoint)

        started_at = now()
        insert_ingestion_run(
            cursor,
            run_id=run_id,
            source_key=source_key,
            city_key=city_key,
            db_branch=db_branch,
            provenance=run_provenance,
            started_at=started_at,
        )

        episode_uids: dict[str, Any] = {}
        stats: dict[str, Any] = {
            "episodes_inserted": 0,
            "episodes_existing": 0,
            "source_observations_inserted": 0,
            "source_observations_existing": 0,
            "source_observations_last_seen_updated": 0,
            "checkpoints_inserted": 0,
            "exact_retry": False,
        }
        for episode in episodes:
            episode_uid, inserted = persist_episode(cursor, episode, run_id=run_id)
            episode_uids[str(episode["legacy_episode_id"])] = episode_uid
            stats["episodes_inserted" if inserted else "episodes_existing"] += 1

        for observation in source_observations:
            legacy_id = str(observation["episode_legacy_id"])
            if legacy_id not in episode_uids:
                raise PersistenceConflict(
                    f"source observation references unknown episode legacy id {legacy_id}"
                )
            _, inserted = persist_source_observation(
                cursor,
                observation,
                episode_uid=episode_uids[legacy_id],
                run_id=run_id,
                seen_at=now(),
            )
            if inserted:
                stats["source_observations_inserted"] += 1
            else:
                stats["source_observations_existing"] += 1
                stats["source_observations_last_seen_updated"] += 1

        _, checkpoint_inserted, checkpoint_exact_retry = persist_checkpoint_candidate(
            cursor,
            checkpoint_candidate,
            current_checkpoint=current_checkpoint,
            run_id=run_id,
        )
        stats["checkpoints_inserted"] = int(checkpoint_inserted)
        stats["exact_retry"] = bool(
            checkpoint_exact_retry
            and stats["episodes_inserted"] == 0
            and stats["source_observations_inserted"] == 0
        )

        committed_at = now()
        finished_at = now()
        finalize_ingestion_run(
            cursor,
            run_id=run_id,
            stats=stats,
            committed_at=committed_at,
            finished_at=finished_at,
        )
        connection.commit()
        return {"run_id": str(run_id), "stats": stats}
    except Exception:
        connection.rollback()
        raise
    finally:
        close = getattr(cursor, "close", None)
        if callable(close):
            close()
