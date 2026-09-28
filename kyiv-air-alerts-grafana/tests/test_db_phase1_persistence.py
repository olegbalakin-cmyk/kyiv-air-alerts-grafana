from __future__ import annotations

import copy
import io
import json
import sys
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from db_phase1_lviv_import import build_lviv_persistence_payload, main as lviv_import_main
from db_phase1_persistence import (
    CheckpointConflict,
    EpisodeConflict,
    SourceObservationConflict,
    persist_phase1_payload,
    stream_lock_key,
)


class Clock:
    def __init__(self, start: datetime):
        self.current = start

    def __call__(self) -> datetime:
        value = self.current
        self.current += timedelta(milliseconds=1)
        return value


class FakeConnection:
    def __init__(self, state=None, *, fail_marker=None, fail_occurrence=1):
        self.state = copy.deepcopy(state) if state is not None else {
            "runs": {},
            "episodes": {},
            "sources": {},
            "checkpoints": {},
        }
        self.working = None
        self.events = []
        self.commit_count = 0
        self.rollback_count = 0
        self.fail_marker = fail_marker
        self.fail_occurrence = fail_occurrence
        self.marker_counts = {}

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        if self.working is None:
            raise AssertionError("commit without transaction")
        self.state = self.working
        self.working = None
        self.events.append("COMMIT")
        self.commit_count += 1

    def rollback(self):
        self.working = None
        self.events.append("ROLLBACK")
        self.rollback_count += 1


class FakeCursor:
    def __init__(self, connection: FakeConnection):
        self.connection = connection
        self.result = None

    @property
    def state(self):
        if self.connection.working is None:
            raise AssertionError("operation outside transaction")
        return self.connection.working

    def close(self):
        return None

    def fetchone(self):
        result = self.result
        self.result = None
        return result

    def _marker(self, sql: str) -> str:
        for marker in (
            "BEGIN",
            "LOCK",
            "CHECKPOINT_REREAD",
            "RUN_INSERT",
            "EPISODE_LOOKUP",
            "EPISODE_INSERT",
            "SOURCE_LOOKUP",
            "SOURCE_INSERT",
            "SOURCE_LAST_SEEN_UPDATE",
            "CHECKPOINT_INSERT",
            "RUN_FINALIZE",
        ):
            if f"PHASE1:{marker}" in sql:
                return marker
        raise AssertionError(f"unrecognized SQL in fake: {sql}")

    def execute(self, sql, params=None):
        marker = self._marker(sql)
        self.connection.events.append(marker)
        count = self.connection.marker_counts.get(marker, 0) + 1
        self.connection.marker_counts[marker] = count
        if self.connection.fail_marker == marker and count == self.connection.fail_occurrence:
            raise RuntimeError(f"injected failure at {marker} #{count}")

        if marker == "BEGIN":
            if params not in (None, ()):
                raise AssertionError("BEGIN must not have params")
            self.connection.working = copy.deepcopy(self.connection.state)
            self.result = None
            return self

        if marker == "LOCK":
            if not isinstance(params, tuple) or len(params) != 1 or not isinstance(params[0], int):
                raise AssertionError("lock must receive exactly one bigint parameter")
            self.result = {"pg_advisory_xact_lock": None}
            return self

        if marker == "CHECKPOINT_REREAD":
            source_key, city_key, stream_key = params
            candidates = [
                row for row in self.state["checkpoints"].values()
                if row["source_key"] == source_key
                and row["city_key"] == city_key
                and row["stream_key"] == stream_key
            ]
            self.result = copy.deepcopy(max(candidates, key=lambda row: row["checkpoint_seq"])) if candidates else None
            return self

        if marker == "RUN_INSERT":
            (
                run_id, run_kind, source_key, city_key,
                workflow_repository, workflow_name, workflow_ref, workflow_sha,
                input_repository, input_ref, input_sha,
                github_run_id, github_run_attempt, db_branch,
                schema_version, canonicalization_version, status, started_at,
                parameters_json, stats_json,
            ) = params
            self.state["runs"][run_id] = {
                "run_id": run_id,
                "run_kind": run_kind,
                "source_key": source_key,
                "city_key": city_key,
                "workflow_repository": workflow_repository,
                "workflow_name": workflow_name,
                "workflow_ref": workflow_ref,
                "workflow_sha": workflow_sha,
                "input_repository": input_repository,
                "input_ref": input_ref,
                "input_sha": input_sha,
                "github_run_id": github_run_id,
                "github_run_attempt": github_run_attempt,
                "db_branch": db_branch,
                "schema_version": schema_version,
                "canonicalization_version": canonicalization_version,
                "status": status,
                "started_at": started_at,
                "ingest_committed_at": None,
                "finished_at": None,
                "parameters": json.loads(parameters_json),
                "stats": json.loads(stats_json),
            }
            self.result = None
            return self

        if marker == "EPISODE_LOOKUP":
            self.result = copy.deepcopy(self.state["episodes"].get(params[0]))
            return self

        if marker == "EPISODE_INSERT":
            (
                legacy_episode_id, city_key, alert_type, start_at, end_at,
                episode_state, canonicalization_version, created_by_run_id, updated_by_run_id,
            ) = params
            episode_uid = uuid.uuid4()
            self.state["episodes"][legacy_episode_id] = {
                "episode_uid": episode_uid,
                "legacy_episode_id": legacy_episode_id,
                "city_key": city_key,
                "alert_type": alert_type,
                "start_at": start_at,
                "end_at": end_at,
                "episode_state": episode_state,
                "canonicalization_version": canonicalization_version,
                "created_by_run_id": created_by_run_id,
                "updated_by_run_id": updated_by_run_id,
            }
            self.result = {"episode_uid": episode_uid}
            return self

        if marker == "SOURCE_LOOKUP":
            self.result = copy.deepcopy(self.state["sources"].get(tuple(params)))
            return self

        if marker == "SOURCE_INSERT":
            (
                episode_uid, source_key, source_record_key_version, source_record_key,
                source_native_id, city_key, alert_type, source_start_at, source_end_at,
                source_retrieved_at, binding_state, canonicalization_role,
                duplicate_of_observation_id, match_method, start_delta_ms, end_delta_ms,
                contributes_start_boundary, contributes_end_boundary,
                raw_sha256, raw_object_path, provenance_json,
                first_persisted_by_run_id, last_seen_by_run_id,
                first_persisted_at, last_seen_at,
            ) = params
            identity = (source_key, source_record_key_version, source_record_key)
            source_observation_id = uuid.uuid4()
            self.state["sources"][identity] = {
                "source_observation_id": source_observation_id,
                "episode_uid": episode_uid,
                "source_key": source_key,
                "source_record_key_version": source_record_key_version,
                "source_record_key": source_record_key,
                "source_native_id": source_native_id,
                "city_key": city_key,
                "alert_type": alert_type,
                "source_start_at": source_start_at,
                "source_end_at": source_end_at,
                "source_retrieved_at": source_retrieved_at,
                "binding_state": binding_state,
                "canonicalization_role": canonicalization_role,
                "duplicate_of_observation_id": duplicate_of_observation_id,
                "match_method": match_method,
                "start_delta_ms": start_delta_ms,
                "end_delta_ms": end_delta_ms,
                "contributes_start_boundary": contributes_start_boundary,
                "contributes_end_boundary": contributes_end_boundary,
                "raw_sha256": raw_sha256,
                "raw_object_path": raw_object_path,
                "provenance": json.loads(provenance_json),
                "first_persisted_by_run_id": first_persisted_by_run_id,
                "last_seen_by_run_id": last_seen_by_run_id,
                "first_persisted_at": first_persisted_at,
                "last_seen_at": last_seen_at,
            }
            self.result = {"source_observation_id": source_observation_id}
            return self

        if marker == "SOURCE_LAST_SEEN_UPDATE":
            run_id, seen_at, source_observation_id = params
            matching = [
                row for row in self.state["sources"].values()
                if row["source_observation_id"] == source_observation_id
            ]
            if len(matching) != 1:
                raise AssertionError("source last-seen update did not resolve exactly one row")
            matching[0]["last_seen_by_run_id"] = run_id
            matching[0]["last_seen_at"] = seen_at
            self.result = None
            return self

        if marker == "CHECKPOINT_INSERT":
            (
                source_key, city_key, stream_key, checkpoint_seq, checkpoint_kind,
                previous_checkpoint_id, checked_at, continuity_verified, continuity_method,
                continuity_anchor_at, observed_oldest_start_at, observed_latest_end_at,
                observed_record_count, cursor_json, metadata_json, created_by_run_id,
            ) = params
            checkpoint_id = uuid.uuid4()
            self.state["checkpoints"][checkpoint_id] = {
                "checkpoint_id": checkpoint_id,
                "source_key": source_key,
                "city_key": city_key,
                "stream_key": stream_key,
                "checkpoint_seq": checkpoint_seq,
                "checkpoint_kind": checkpoint_kind,
                "previous_checkpoint_id": previous_checkpoint_id,
                "checked_at": checked_at,
                "continuity_verified": continuity_verified,
                "continuity_method": continuity_method,
                "continuity_anchor_at": continuity_anchor_at,
                "observed_oldest_start_at": observed_oldest_start_at,
                "observed_latest_end_at": observed_latest_end_at,
                "observed_record_count": observed_record_count,
                "cursor": None if cursor_json is None else json.loads(cursor_json),
                "metadata": json.loads(metadata_json),
                "created_by_run_id": created_by_run_id,
                "created_at": datetime.now(timezone.utc),
            }
            self.result = {"checkpoint_id": checkpoint_id}
            return self

        if marker == "RUN_FINALIZE":
            status, ingest_committed_at, finished_at, stats_json, run_id = params
            row = self.state["runs"][run_id]
            row["status"] = status
            row["ingest_committed_at"] = ingest_committed_at
            row["finished_at"] = finished_at
            row["stats"] = json.loads(stats_json)
            self.result = None
            return self

        raise AssertionError(marker)


class PersistenceAdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = build_lviv_persistence_payload()

    def persist(self, connection, payload=None, *, start="2026-09-28T07:00:00+00:00"):
        p = payload or self.payload
        return persist_phase1_payload(
            connection,
            source_key=p["source_key"],
            city_key=p["city_key"],
            stream_key=p["stream_key"],
            db_branch="br-local-unit-test",
            run_provenance=p["run_provenance"],
            episodes=p["episodes"],
            source_observations=p["source_observations"],
            checkpoint_candidate=p["checkpoint_candidate"],
            now_factory=Clock(datetime.fromisoformat(start)),
        )

    def test_initial_bootstrap_counts(self):
        connection = FakeConnection()
        result = self.persist(connection)
        self.assertEqual(len(connection.state["runs"]), 1)
        self.assertEqual(len(connection.state["episodes"]), 126)
        self.assertEqual(len(connection.state["sources"]), 140)
        self.assertEqual(len(connection.state["checkpoints"]), 1)
        self.assertIsNone(next(iter(connection.state["checkpoints"].values()))["cursor"])
        self.assertEqual(
            result["stats"],
            {
                "episodes_inserted": 126,
                "episodes_existing": 0,
                "source_observations_inserted": 140,
                "source_observations_existing": 0,
                "source_observations_last_seen_updated": 0,
                "checkpoints_inserted": 1,
                "exact_retry": False,
            },
        )
        self.assertEqual(connection.commit_count, 1)
        self.assertEqual(connection.rollback_count, 0)

    def test_exact_retry_preserves_identities_and_updates_only_last_seen(self):
        connection = FakeConnection()
        self.persist(connection)
        episode_identity_before = {
            key: (row["episode_uid"], row["created_by_run_id"], row["updated_by_run_id"])
            for key, row in connection.state["episodes"].items()
        }
        source_identity_before = {
            key: (
                row["source_observation_id"],
                row["first_persisted_by_run_id"],
                row["first_persisted_at"],
                row["last_seen_by_run_id"],
            )
            for key, row in connection.state["sources"].items()
        }
        checkpoint_before = next(iter(connection.state["checkpoints"].values()))
        checkpoint_id_before = checkpoint_before["checkpoint_id"]
        checkpoint_created_by_before = checkpoint_before["created_by_run_id"]

        result = self.persist(connection, start="2026-09-28T08:00:00+00:00")

        self.assertEqual(len(connection.state["runs"]), 2)
        self.assertEqual(result["stats"]["episodes_inserted"], 0)
        self.assertEqual(result["stats"]["episodes_existing"], 126)
        self.assertEqual(result["stats"]["source_observations_inserted"], 0)
        self.assertEqual(result["stats"]["source_observations_existing"], 140)
        self.assertEqual(result["stats"]["source_observations_last_seen_updated"], 140)
        self.assertEqual(result["stats"]["checkpoints_inserted"], 0)
        self.assertTrue(result["stats"]["exact_retry"])
        self.assertEqual(
            episode_identity_before,
            {
                key: (row["episode_uid"], row["created_by_run_id"], row["updated_by_run_id"])
                for key, row in connection.state["episodes"].items()
            },
        )
        for key, row in connection.state["sources"].items():
            old = source_identity_before[key]
            self.assertEqual(row["source_observation_id"], old[0])
            self.assertEqual(row["first_persisted_by_run_id"], old[1])
            self.assertEqual(row["first_persisted_at"], old[2])
            self.assertNotEqual(row["last_seen_by_run_id"], old[3])
        checkpoint_after = next(iter(connection.state["checkpoints"].values()))
        self.assertEqual(checkpoint_after["checkpoint_id"], checkpoint_id_before)
        self.assertEqual(checkpoint_after["created_by_run_id"], checkpoint_created_by_before)

    def test_episode_conflict_rolls_back(self):
        connection = FakeConnection()
        self.persist(connection)
        before = copy.deepcopy(connection.state)
        conflict = copy.deepcopy(self.payload)
        conflict["episodes"][0]["end_at"] = "2025-09-01T07:40:45Z"
        with self.assertRaises(EpisodeConflict):
            self.persist(connection, conflict, start="2026-09-28T09:00:00+00:00")
        self.assertEqual(connection.state, before)
        self.assertEqual(connection.rollback_count, 1)

    def test_source_identity_conflict_rolls_back(self):
        connection = FakeConnection()
        self.persist(connection)
        before = copy.deepcopy(connection.state)
        conflict = copy.deepcopy(self.payload)
        conflict["source_observations"][0]["source_end_at"] = "2025-09-01T07:40:45.000000Z"
        with self.assertRaises(SourceObservationConflict):
            self.persist(connection, conflict, start="2026-09-28T09:10:00+00:00")
        self.assertEqual(connection.state, before)
        self.assertEqual(connection.rollback_count, 1)

    def test_bootstrap_checkpoint_conflict_rolls_back_all_last_seen_changes(self):
        connection = FakeConnection()
        self.persist(connection)
        before = copy.deepcopy(connection.state)
        conflict = copy.deepcopy(self.payload)
        conflict["checkpoint_candidate"]["metadata"]["kind"] = "different"
        with self.assertRaises(CheckpointConflict):
            self.persist(connection, conflict, start="2026-09-28T09:20:00+00:00")
        self.assertEqual(connection.state, before)
        self.assertEqual(connection.rollback_count, 1)

    def test_transaction_order_lock_then_checkpoint_then_mutation_then_commit(self):
        connection = FakeConnection()
        self.persist(connection)
        events = connection.events
        self.assertLess(events.index("BEGIN"), events.index("LOCK"))
        self.assertLess(events.index("LOCK"), events.index("CHECKPOINT_REREAD"))
        self.assertLess(events.index("CHECKPOINT_REREAD"), events.index("RUN_INSERT"))
        self.assertLess(events.index("CHECKPOINT_REREAD"), events.index("EPISODE_INSERT"))
        checkpoint_decision = events.index("CHECKPOINT_INSERT")
        self.assertGreater(checkpoint_decision, events.index("CHECKPOINT_REREAD"))
        self.assertLess(checkpoint_decision, events.index("RUN_FINALIZE"))
        self.assertLess(events.index("RUN_FINALIZE"), events.index("COMMIT"))
        self.assertEqual(events[0:3], ["BEGIN", "LOCK", "CHECKPOINT_REREAD"])

    def test_injected_failure_rolls_back_partial_writes_and_never_commits(self):
        connection = FakeConnection(fail_marker="SOURCE_INSERT", fail_occurrence=5)
        with self.assertRaisesRegex(RuntimeError, "injected failure"):
            self.persist(connection)
        self.assertEqual(connection.state["runs"], {})
        self.assertEqual(connection.state["episodes"], {})
        self.assertEqual(connection.state["sources"], {})
        self.assertEqual(connection.state["checkpoints"], {})
        self.assertEqual(connection.commit_count, 0)
        self.assertEqual(connection.rollback_count, 1)
        self.assertNotIn("COMMIT", connection.events)

    def test_stream_lock_key_is_deterministic_signed_bigint_and_stream_specific(self):
        same_a = stream_lock_key("source", "lviv", "region_id:90:AIR")
        same_b = stream_lock_key("source", "lviv", "region_id:90:AIR")
        self.assertEqual(same_a, same_b)
        self.assertGreaterEqual(same_a, -(1 << 63))
        self.assertLessEqual(same_a, (1 << 63) - 1)
        keys = {
            same_a,
            stream_lock_key("other-source", "lviv", "region_id:90:AIR"),
            stream_lock_key("source", "kyiv", "region_id:90:AIR"),
            stream_lock_key("source", "lviv", "region_id:91:AIR"),
        }
        self.assertEqual(len(keys), 4)

    def test_dry_run_does_not_connect_require_or_print_database_url(self):
        secret = "postgresql://user:super-secret@example.invalid/db?sslmode=require"
        stdout = io.StringIO()
        stderr = io.StringIO()

        def forbidden_connect(_url):
            raise AssertionError("dry-run attempted a DB connection")

        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = lviv_import_main(
                ["--dry-run"],
                env={"DATABASE_URL": secret},
                connect_factory=forbidden_connect,
            )
        output = stdout.getvalue() + stderr.getvalue()
        self.assertEqual(code, 0)
        self.assertNotIn(secret, output)
        self.assertNotIn("super-secret", output)
        self.assertEqual(
            stdout.getvalue().splitlines(),
            [
                "canonical episodes = 126",
                "source observations = 140",
                "Vadimkin = 120",
                "UkraineAlarm = 20",
                "checkpoint candidates = 1",
                "oracle parity = PASS",
            ],
        )


if __name__ == "__main__":
    unittest.main()
