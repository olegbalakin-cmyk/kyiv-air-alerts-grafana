#!/usr/bin/env python3
"""PostgreSQL persistence adapter for differentiated-alert child facts.

The adapter accepts records produced by the already-proven differentiated-alert
canonicalizers/binder. It has no API for mutating parent AIR episodes or their
source observations; parent tables are read only and are used only to resolve a
BOUND record to its existing episode_uid.
"""
from __future__ import annotations

import copy
import json
from collections.abc import Callable, Iterable, Mapping
from typing import Any

COMPONENT_SIGNATURE_VERSION = "differentiated-component-signature-v1"
BOUND_STATES = {"BOUND", "AMBIGUOUS", "UNBOUND"}


class ChildPersistenceError(RuntimeError):
    """Base class for differentiated child persistence failures."""


class ParentBindingError(ChildPersistenceError):
    """Raised when a BOUND record cannot resolve exactly one existing parent."""


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _one(row: Any, key: str) -> Any:
    if row is None:
        return None
    if isinstance(row, Mapping):
        return row.get(key)
    return row[0]


def _resolve_episode_uid(cursor: Any, snapshot: Mapping[str, Any]) -> Any:
    state = snapshot.get("binding_state")
    if state not in BOUND_STATES:
        raise ChildPersistenceError(f"unsupported binding_state={state!r}")

    explicit_uid = snapshot.get("episode_uid")
    legacy_id = snapshot.get("episode_id")

    if state != "BOUND":
        if explicit_uid is not None or legacy_id is not None:
            raise ChildPersistenceError(
                f"{state} child record must not carry a parent episode reference"
            )
        return None

    if explicit_uid is None and legacy_id is None:
        raise ParentBindingError("BOUND child record has no parent episode identity")

    if explicit_uid is not None:
        cursor.execute(
            """/* DIFFERENTIATED_CHILD:PARENT_LOOKUP_UID */
            SELECT episode_uid
            FROM alert_episodes
            WHERE episode_uid = %s
              AND city_key = %s
              AND alert_type = %s
            """,
            (
                explicit_uid,
                snapshot.get("target_city_key"),
                snapshot.get("alert_type", "AIR"),
            ),
        )
    else:
        cursor.execute(
            """/* DIFFERENTIATED_CHILD:PARENT_LOOKUP_LEGACY */
            SELECT episode_uid
            FROM alert_episodes
            WHERE legacy_episode_id = %s
              AND city_key = %s
              AND alert_type = %s
            """,
            (
                legacy_id,
                snapshot.get("target_city_key"),
                snapshot.get("alert_type", "AIR"),
            ),
        )

    row = cursor.fetchone()
    uid = _one(row, "episode_uid")
    if uid is None:
        identity = explicit_uid if explicit_uid is not None else legacy_id
        raise ParentBindingError(f"BOUND parent episode not found: {identity}")
    return uid


def _insert_snapshot(cursor: Any, record: Mapping[str, Any]) -> tuple[Any, bool]:
    snapshot = copy.deepcopy(record["snapshot"])
    threats = copy.deepcopy(record.get("threat_observations", []))
    episode_uid = _resolve_episode_uid(cursor, snapshot)

    source_observation_id = snapshot.get("episode_source_observation_id")
    if snapshot.get("binding_state") != "BOUND" and source_observation_id is not None:
        raise ChildPersistenceError(
            "Only BOUND child records may reference episode_source_observation_id"
        )

    provenance = {
        "adapter": "differentiated-alert-postgres-child-v1",
        "snapshot": snapshot,
        "threat_observations": threats,
    }

    cursor.execute(
        """/* DIFFERENTIATED_CHILD:SNAPSHOT_INSERT */
        INSERT INTO alert_state_snapshots (
            snapshot_key_version, snapshot_key,
            episode_uid, episode_source_observation_id, binding_state,
            source_key, source_alert_id, alert_type,
            target_city_key, source_geo_scope, source_geo_type_raw, source_geo_id_raw,
            observed_at, source_state_at, source_alert_started_at, source_alert_ended_at,
            source_active, source_alert_level_raw, source_state_raw,
            raw_sha256, raw_object_path, provenance
        ) VALUES (
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s::jsonb
        )
        ON CONFLICT (snapshot_key) DO NOTHING
        RETURNING snapshot_uid
        """,
        (
            snapshot["snapshot_key_version"],
            snapshot["snapshot_key"],
            episode_uid,
            source_observation_id,
            snapshot["binding_state"],
            snapshot["source"],
            None if snapshot.get("source_alert_id") is None else str(snapshot.get("source_alert_id")),
            snapshot.get("alert_type", "AIR"),
            snapshot["target_city_key"],
            snapshot["source_geography"]["scope"],
            snapshot["source_geography"].get("type_raw"),
            None if snapshot["source_geography"].get("id_raw") is None else str(snapshot["source_geography"].get("id_raw")),
            snapshot["observed_at"],
            snapshot.get("source_state_at"),
            snapshot.get("source_alert_started_at"),
            snapshot.get("source_alert_ended_at"),
            snapshot.get("source_active"),
            snapshot.get("source_alert_level_raw"),
            None if snapshot.get("source_state_raw") is None else str(snapshot.get("source_state_raw")),
            snapshot["raw_payload_hash"],
            snapshot.get("raw_object_path"),
            _json(provenance),
        ),
    )
    inserted = cursor.fetchone()
    uid = _one(inserted, "snapshot_uid")
    if uid is not None:
        return uid, True

    cursor.execute(
        """/* DIFFERENTIATED_CHILD:SNAPSHOT_EXISTING */
        SELECT snapshot_uid
        FROM alert_state_snapshots
        WHERE snapshot_key = %s
        """,
        (snapshot["snapshot_key"],),
    )
    uid = _one(cursor.fetchone(), "snapshot_uid")
    if uid is None:
        raise ChildPersistenceError("snapshot conflict returned no existing row")
    return uid, False


def _insert_threat(cursor: Any, snapshot_uid: Any, threat: Mapping[str, Any]) -> bool:
    cursor.execute(
        """/* DIFFERENTIATED_CHILD:THREAT_INSERT */
        INSERT INTO alert_threat_observations (
            snapshot_uid,
            threat_observation_key_version, threat_observation_key,
            source_threat_id,
            component_signature_version, component_signature, component_identity_basis,
            level_raw, cause_raw, reason_raw, source_message_raw,
            source_started_at, source_ended_at
        ) VALUES (
            %s,
            %s, %s,
            %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s
        )
        ON CONFLICT (threat_observation_key) DO NOTHING
        RETURNING threat_observation_uid
        """,
        (
            snapshot_uid,
            threat["observation_key_version"],
            threat["observation_key"],
            None if threat.get("source_threat_id") is None else str(threat.get("source_threat_id")),
            COMPONENT_SIGNATURE_VERSION if threat.get("component_signature") else None,
            threat.get("component_signature"),
            threat["component_identity_basis"],
            threat.get("level_raw"),
            threat.get("cause_raw"),
            threat.get("reason_raw"),
            threat.get("source_message_raw"),
            threat.get("source_started_at"),
            threat.get("source_ended_at"),
        ),
    )
    return _one(cursor.fetchone(), "threat_observation_uid") is not None


def persist_records(
    connection: Any,
    records: Iterable[Mapping[str, Any]],
    *,
    after_snapshot_hook: Callable[[Mapping[str, Any], Any], None] | None = None,
) -> dict[str, int]:
    """Persist differentiated child records as one all-or-nothing transaction."""
    cursor = connection.cursor()
    stats = {
        "inserted_snapshots": 0,
        "existing_snapshots": 0,
        "inserted_observations": 0,
        "existing_observations": 0,
    }
    try:
        cursor.execute("/* DIFFERENTIATED_CHILD:BEGIN */ BEGIN")
        for record in records:
            snapshot_uid, inserted = _insert_snapshot(cursor, record)
            stats["inserted_snapshots" if inserted else "existing_snapshots"] += 1

            if after_snapshot_hook is not None:
                after_snapshot_hook(record, snapshot_uid)

            for threat in record.get("threat_observations", []):
                if _insert_threat(cursor, snapshot_uid, threat):
                    stats["inserted_observations"] += 1
                else:
                    stats["existing_observations"] += 1
        connection.commit()
        return stats
    except Exception:
        connection.rollback()
        raise
    finally:
        close = getattr(cursor, "close", None)
        if callable(close):
            close()


def persist_record(
    connection: Any,
    record: Mapping[str, Any],
    *,
    after_snapshot_hook: Callable[[Mapping[str, Any], Any], None] | None = None,
) -> dict[str, int]:
    """Persist one child record using the same transaction semantics as a batch."""
    return persist_records(connection, [record], after_snapshot_hook=after_snapshot_hook)
