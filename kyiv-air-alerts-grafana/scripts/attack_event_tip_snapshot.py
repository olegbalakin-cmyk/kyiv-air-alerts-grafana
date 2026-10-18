#!/usr/bin/env python3
"""Read an episode-bound, authoritative pre-classification revision snapshot.

The read is a single PostgreSQL REPEATABLE READ READ ONLY transaction. A
successful empty classification query proves an absent current tip; missing
inputs, parent ambiguity and query failure never mean an absent tip.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import psycopg

from attack_event_canonical_persistence import (
    PersistenceContractError,
    _parse_dt,
    utc_microseconds,
)


def episode_identity(episode: dict[str, Any]) -> tuple[str, str, str, str]:
    city = str(episode.get("city_key") or "").strip()
    episode_id = str(episode.get("episode_id") or "").strip()
    start = _parse_dt(episode.get("alert_start"))
    end = _parse_dt(episode.get("alert_end"))
    if not city or not episode_id or start is None or end is None or end <= start:
        raise PersistenceContractError("INVALID_EPISODE_IDENTITY_FOR_TIP_SNAPSHOT")
    return (city, episode_id, utc_microseconds(start), utc_microseconds(end))


def observe_expected_tips(
    due: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]],
    *,
    dsn: str | None = None,
    connection=None,
) -> dict[tuple[str, str, str, str], dict[str, Any]]:
    """Take one atomic read-only DB snapshot before classification preparation.

    A snapshot value binds the exact logical episode, canonical parent,
    due-check attempt, observed current UID or observed absence. The writer
    revalidates identity, attempt and parent, then performs CAS under an
    advisory transaction lock using this unchanged value.
    """
    if connection is None and not str(dsn or "").strip():
        raise PersistenceContractError("EXPECTED_TIP_SNAPSHOT_DATABASE_UNAVAILABLE")
    selected: list[tuple[tuple[str, str, str, str], dict[str, Any]]] = []
    seen = set()
    for city, rows in sorted(due.items()):
        for episode, check in rows:
            identity = episode_identity(episode)
            if identity[0] != city or identity in seen:
                raise PersistenceContractError("EXPECTED_TIP_SNAPSHOT_EPISODE_COLLISION")
            label = str(check.get("label") or "").strip()
            due_at = str(check.get("due_at") or "").strip()
            if not label or _parse_dt(due_at) is None:
                raise PersistenceContractError("EXPECTED_TIP_SNAPSHOT_ATTEMPT_UNBOUND")
            if check.get("checked_at"):
                raise PersistenceContractError("EXPECTED_TIP_SNAPSHOT_ALREADY_CHECKED")
            seen.add(identity)
            selected.append((identity, check))
    if not selected:
        return {}

    own = connection is None
    try:
        conn = connection if connection is not None else psycopg.connect(str(dsn), autocommit=True)
    except psycopg.Error as exc:
        raise PersistenceContractError("EXPECTED_TIP_SNAPSHOT_DATABASE_UNAVAILABLE") from exc
    output = {}
    try:
        if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
            raise PersistenceContractError("EXPECTED_TIP_SNAPSHOT_REQUIRES_IDLE_CONNECTION")
        with conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            conn.execute("SET LOCAL statement_timeout = '15s'")
            conn.execute("SET LOCAL lock_timeout = '5s'")
            for (city, episode_id, start_us, end_us), check in selected:
                parent_rows = conn.execute(
                    """SELECT episode_uid FROM public.alert_episodes
                       WHERE city_key = %s AND legacy_episode_id = %s
                         AND start_at = %s AND end_at = %s
                         AND alert_type = 'AIR' AND episode_state = 'closed'
                         AND canonicalization_version = 'alert-canonicalization-v1'""",
                    (city, episode_id, start_us, end_us),
                ).fetchall()
                if len(parent_rows) != 1:
                    raise PersistenceContractError(
                        "EXPECTED_TIP_CANONICAL_PARENT_NOT_UNIQUE: "
                        f"{city}:{episode_id} count={len(parent_rows)}"
                    )
                parent_uid = str(parent_rows[0][0])
                rows = conn.execute(
                    """SELECT c.classification_uid, c.classification_key, c.verdict,
                              c.origin_provenance, c.alert_episode_uid
                       FROM public.attack_event_classifications c
                       WHERE c.city_key = %s AND c.historical_episode_id = %s
                         AND c.alert_start_at = %s AND c.alert_end_at = %s
                         AND NOT EXISTS (
                            SELECT 1 FROM public.attack_event_classifications n
                            WHERE n.supersedes_classification_uid = c.classification_uid
                         )
                       ORDER BY c.created_at, c.classification_uid""",
                    (city, episode_id, start_us, end_us),
                ).fetchall()
                if len(rows) > 1:
                    raise PersistenceContractError(
                        "EXPECTED_TIP_MULTIPLE_CURRENT_REVISIONS: "
                        f"{city}:{episode_id}"
                    )
                if rows and str(rows[0][4]) != parent_uid:
                    raise PersistenceContractError("EXPECTED_TIP_PARENT_IDENTITY_CONFLICT")
                foreign_count = conn.execute(
                    """SELECT count(*) FROM public.attack_event_classifications
                       WHERE city_key = %s AND historical_episode_id = %s
                         AND alert_start_at = %s AND alert_end_at = %s
                         AND alert_episode_uid IS DISTINCT FROM %s::uuid""",
                    (city, episode_id, start_us, end_us, parent_uid),
                ).fetchone()[0]
                if foreign_count:
                    raise PersistenceContractError("EXPECTED_TIP_HISTORICAL_PARENT_CONFLICT")
                key = (city, episode_id, start_us, end_us)
                output[key] = {
                    "episode_identity": list(key),
                    "canonical_parent_uid": parent_uid,
                    "check_label": str(check["label"]),
                    "check_due_at": str(check["due_at"]),
                    "expected_current_tip": str(rows[0][0]) if rows else None,
                    "observed_classification_key": str(rows[0][1]) if rows else None,
                    "observed_verdict": str(rows[0][2]) if rows else None,
                    "observed_origin_kind": (
                        (rows[0][3] or {}).get("kind")
                        if rows and isinstance(rows[0][3], dict) else None
                    ),
                    "observation_id": str(uuid.uuid4()),
                    "provenance": "PG18_REPEATABLE_READ_READ_ONLY_CANONICAL_TABLES",
                }
        return output
    except psycopg.Error as exc:
        raise PersistenceContractError("EXPECTED_TIP_SNAPSHOT_SQL_FAILED") from exc
    finally:
        if own:
            conn.close()
