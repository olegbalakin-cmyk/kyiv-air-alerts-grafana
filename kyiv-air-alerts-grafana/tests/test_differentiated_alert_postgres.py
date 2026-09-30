import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import differentiated_alert_postgres as pg


class FakeCursor:
    def __init__(self, state):
        self.state = state
        self.result = None

    def execute(self, sql, params=None):
        params = params or ()
        if "PARENT_LOOKUP_LEGACY" in sql:
            self.result = (self.state["parents"].get(params[0]),)
        elif "PARENT_LOOKUP_UID" in sql:
            uid = params[0]
            self.result = (uid,) if uid in self.state["parents"].values() else None
        elif "SNAPSHOT_INSERT" in sql:
            key = params[1]
            if key in self.state["snapshots"]:
                self.result = None
            else:
                uid = f"snap-{len(self.state['snapshots'])+1}"
                self.state["snapshots"][key] = uid
                self.result = (uid,)
        elif "SNAPSHOT_EXISTING" in sql:
            self.result = (self.state["snapshots"].get(params[0]),)
        elif "THREAT_INSERT" in sql:
            key = params[2]
            if key in self.state["threats"]:
                self.result = None
            else:
                uid = f"threat-{len(self.state['threats'])+1}"
                self.state["threats"][key] = uid
                self.result = (uid,)
        else:
            self.result = None

    def fetchone(self):
        out = self.result
        self.result = None
        return out

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.state = {
            "parents": {"lviv-legacy-1": "episode-uuid-1"},
            "snapshots": {},
            "threats": {},
        }
        self._savepoint = None
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        self._savepoint = {
            "parents": dict(self.state["parents"]),
            "snapshots": dict(self.state["snapshots"]),
            "threats": dict(self.state["threats"]),
        }
        return FakeCursor(self.state)

    def commit(self):
        self.commits += 1
        self._savepoint = None

    def rollback(self):
        self.rollbacks += 1
        if self._savepoint is not None:
            self.state = self._savepoint
        self._savepoint = None


def rec(binding="UNBOUND", episode_id=None, key="a" * 64, obs="b" * 64):
    return {
        "snapshot": {
            "snapshot_key_version": "differentiated-snapshot-v1",
            "snapshot_key": key,
            "episode_id": episode_id,
            "binding_state": binding,
            "source": "alerts_in_ua",
            "source_alert_id": 123,
            "target_city_key": "lviv" if binding == "BOUND" else "donetsk",
            "alert_type": "AIR",
            "source_geography": {
                "scope": "RAION",
                "type_raw": "raion",
                "id_raw": 42,
            },
            "observed_at": "2026-09-30T10:00:00Z",
            "source_state_at": "2026-09-30T09:59:00Z",
            "source_active": True,
            "source_alert_level_raw": "Yellow",
            "source_state_raw": None,
            "raw_payload_hash": "c" * 64,
            "raw_object_path": "$FIXTURE",
        },
        "threat_observations": [
            {
                "observation_key_version": "differentiated-threat-observation-v1",
                "observation_key": obs,
                "source_threat_id": None,
                "component_signature": "d" * 64,
                "component_identity_basis": "DETERMINISTIC_INFERRED",
                "level_raw": "Red",
                "cause_raw": "ballistic_missiles",
                "reason_raw": None,
                "source_message_raw": "raw",
                "source_started_at": "2026-09-30T09:58:00Z",
                "source_ended_at": None,
            }
        ],
    }


class Tests(unittest.TestCase):
    def test_unbound_insert_and_exact_retry(self):
        connection = FakeConnection()
        record = rec()
        self.assertEqual(
            pg.persist_record(connection, record),
            {
                "inserted_snapshots": 1,
                "existing_snapshots": 0,
                "inserted_observations": 1,
                "existing_observations": 0,
            },
        )
        self.assertEqual(
            pg.persist_record(connection, record),
            {
                "inserted_snapshots": 0,
                "existing_snapshots": 1,
                "inserted_observations": 0,
                "existing_observations": 1,
            },
        )

    def test_bound_resolves_existing_parent(self):
        connection = FakeConnection()
        out = pg.persist_record(connection, rec("BOUND", "lviv-legacy-1"))
        self.assertEqual(out["inserted_snapshots"], 1)

    def test_ambiguous_and_unbound_reject_parent_reference(self):
        for state in ("AMBIGUOUS", "UNBOUND"):
            with self.subTest(state=state):
                connection = FakeConnection()
                with self.assertRaises(pg.ChildPersistenceError):
                    pg.persist_record(connection, rec(state, "lviv-legacy-1"))
                self.assertEqual(connection.rollbacks, 1)

    def test_bound_requires_existing_parent(self):
        connection = FakeConnection()
        with self.assertRaises(pg.ParentBindingError):
            pg.persist_record(connection, rec("BOUND", "missing"))
        self.assertEqual(connection.rollbacks, 1)

    def test_failure_after_snapshot_rolls_back(self):
        connection = FakeConnection()

        def boom(record, uid):
            raise RuntimeError("injected")

        with self.assertRaises(RuntimeError):
            pg.persist_record(connection, rec(), after_snapshot_hook=boom)
        self.assertEqual(connection.state["snapshots"], {})
        self.assertEqual(connection.state["threats"], {})
        self.assertEqual(pg.persist_record(connection, rec())["inserted_snapshots"], 1)

    def test_later_poll_is_new_identity(self):
        connection = FakeConnection()
        self.assertEqual(pg.persist_record(connection, rec())["inserted_snapshots"], 1)
        out = pg.persist_record(connection, rec(key="e" * 64, obs="f" * 64))
        self.assertEqual(out["inserted_snapshots"], 1)
        self.assertEqual(out["inserted_observations"], 1)

    def test_no_parent_mutation_sql(self):
        import inspect

        source = inspect.getsource(pg)
        self.assertNotIn("INSERT INTO alert_episodes", source)
        self.assertNotIn("UPDATE alert_episodes", source)
        self.assertNotIn("DELETE FROM alert_episodes", source)
        self.assertNotIn("INSERT INTO alert_episode_sources", source)
        self.assertNotIn("UPDATE alert_episode_sources", source)
        self.assertNotIn("DELETE FROM alert_episode_sources", source)


if __name__ == "__main__":
    unittest.main()
