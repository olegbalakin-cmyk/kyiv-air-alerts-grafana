#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import re
from typing import Any

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

SCHEMA_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _state_raw(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class PostgresShadowStore:
    """Child-only durable store. It intentionally exposes no parent AIR mutation API."""

    def __init__(self, dsn: str, schema: str = "differentiated_alert_shadow") -> None:
        if not dsn:
            raise ValueError("database URL is required")
        if not SCHEMA_RE.fullmatch(schema):
            raise ValueError("invalid differentiated shadow schema name")
        self.schema = schema
        self.conn = psycopg.connect(dsn, autocommit=True)
        self.ensure_schema()

    def _table(self, name: str):
        return sql.SQL("{}.{}").format(sql.Identifier(self.schema), sql.Identifier(name))

    def ensure_schema(self) -> None:
        with self.conn.transaction():
            self.conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))
            self.conn.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {} (
                      snapshot_key TEXT PRIMARY KEY,
                      source TEXT NOT NULL,
                      target_city_key TEXT NOT NULL,
                      source_geo_scope TEXT NOT NULL,
                      source_geo_type_raw TEXT,
                      source_geo_id_raw TEXT,
                      source_alert_id TEXT,
                      alert_type TEXT NOT NULL,
                      observed_at TIMESTAMPTZ NOT NULL,
                      source_state_at TIMESTAMPTZ,
                      source_active BOOLEAN NOT NULL,
                      source_alert_level_raw TEXT,
                      source_state_raw TEXT,
                      binding_status TEXT NOT NULL,
                      episode_id TEXT,
                      raw_payload_hash TEXT NOT NULL,
                      raw_object_path TEXT,
                      payload_json JSONB NOT NULL,
                      CHECK (binding_status IN ('BOUND','AMBIGUOUS','UNBOUND')),
                      CHECK ((binding_status='BOUND' AND episode_id IS NOT NULL) OR
                             (binding_status<>'BOUND' AND episode_id IS NULL))
                    )
                    """
                ).format(self._table("alert_state_snapshot"))
            )
            self.conn.execute(
                sql.SQL(
                    """
                    CREATE TABLE IF NOT EXISTS {} (
                      observation_key TEXT PRIMARY KEY,
                      snapshot_key TEXT NOT NULL REFERENCES {}(snapshot_key) ON DELETE CASCADE,
                      source_threat_id TEXT,
                      component_signature TEXT,
                      component_identity_basis TEXT,
                      level_raw TEXT,
                      cause_raw TEXT,
                      reason_raw TEXT,
                      source_message_raw TEXT,
                      source_started_at TIMESTAMPTZ,
                      source_ended_at TIMESTAMPTZ,
                      severity_normalized TEXT,
                      threat_type_normalized TEXT,
                      payload_json JSONB NOT NULL
                    )
                    """
                ).format(self._table("alert_threat_observation"), self._table("alert_state_snapshot"))
            )

    def close(self) -> None:
        self.conn.close()

    def counts(self) -> dict[str, int]:
        snapshots = self.conn.execute(
            sql.SQL("SELECT count(*) FROM {}").format(self._table("alert_state_snapshot"))
        ).fetchone()[0]
        observations = self.conn.execute(
            sql.SQL("SELECT count(*) FROM {}").format(self._table("alert_threat_observation"))
        ).fetchone()[0]
        return {"snapshots": int(snapshots), "observations": int(observations)}

    def persist(self, record: dict[str, Any], fail_after_snapshot: bool = False) -> dict[str, int]:
        snapshot = copy.deepcopy(record["snapshot"])
        observations = copy.deepcopy(record["threat_observations"])
        if snapshot["binding_state"] != "BOUND":
            snapshot["episode_id"] = None
        payload = {"snapshot": snapshot, "threat_observations": observations}
        inserted_snapshots = 0
        inserted_observations = 0
        with self.conn.transaction():
            cur = self.conn.execute(
                sql.SQL(
                    """
                    INSERT INTO {} (
                      snapshot_key, source, target_city_key, source_geo_scope,
                      source_geo_type_raw, source_geo_id_raw, source_alert_id, alert_type,
                      observed_at, source_state_at, source_active, source_alert_level_raw,
                      source_state_raw, binding_status, episode_id, raw_payload_hash,
                      raw_object_path, payload_json
                    ) VALUES (
                      %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s
                    ) ON CONFLICT (snapshot_key) DO NOTHING
                    """
                ).format(self._table("alert_state_snapshot")),
                (
                    snapshot["snapshot_key"], snapshot["source"], snapshot["target_city_key"],
                    snapshot["source_geography"]["scope"], snapshot["source_geography"].get("type_raw"),
                    snapshot["source_geography"].get("id_raw"), snapshot.get("source_alert_id"),
                    snapshot["alert_type"], snapshot["observed_at"], snapshot.get("source_state_at"),
                    bool(snapshot.get("source_active")), snapshot.get("source_alert_level_raw"),
                    _state_raw(snapshot.get("source_state_raw")), snapshot["binding_state"],
                    snapshot.get("episode_id"), snapshot["raw_payload_hash"],
                    snapshot.get("raw_object_path"), Jsonb(payload),
                ),
            )
            inserted_snapshots += max(cur.rowcount, 0)
            if fail_after_snapshot:
                raise RuntimeError("injected persistence failure after snapshot write")
            for row in observations:
                cur = self.conn.execute(
                    sql.SQL(
                        """
                        INSERT INTO {} (
                          observation_key, snapshot_key, source_threat_id, component_signature,
                          component_identity_basis, level_raw, cause_raw, reason_raw,
                          source_message_raw, source_started_at, source_ended_at,
                          severity_normalized, threat_type_normalized, payload_json
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (observation_key) DO NOTHING
                        """
                    ).format(self._table("alert_threat_observation")),
                    (
                        row["observation_key"], snapshot["snapshot_key"], row.get("source_threat_id"),
                        row.get("component_signature"), row.get("component_identity_basis"),
                        row.get("level_raw"), row.get("cause_raw"), row.get("reason_raw"),
                        row.get("source_message_raw"), row.get("source_started_at"),
                        row.get("source_ended_at"), row.get("severity_normalized"),
                        row.get("threat_type_normalized"), Jsonb(row),
                    ),
                )
                inserted_observations += max(cur.rowcount, 0)
        return {
            "inserted_snapshots": inserted_snapshots,
            "inserted_observations": inserted_observations,
            "existing_snapshots": 1 - inserted_snapshots,
            "existing_observations": len(observations) - inserted_observations,
        }

    def latest_rows(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            sql.SQL(
                """
                SELECT s.source, s.target_city_key, s.observed_at, s.binding_status, s.episode_id,
                       o.threat_type_normalized, o.severity_normalized
                FROM {} s
                LEFT JOIN {} o ON o.snapshot_key=s.snapshot_key
                ORDER BY s.observed_at DESC, s.snapshot_key, o.observation_key
                LIMIT %s
                """
            ).format(self._table("alert_state_snapshot"), self._table("alert_threat_observation")),
            (limit,),
        ).fetchall()
        keys = ["source","target_city_key","observed_at","binding_status","episode_id","threat_type_normalized","severity_normalized"]
        return [dict(zip(keys, row)) for row in rows]
