import inspect
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import lviv_canonical_boundary_repair as r


class TestRepairPlan(unittest.TestCase):
    def test_exact_plan_and_source_record_keys(self):
        plan = r.repair_plan()
        self.assertEqual(len(plan), 3)
        self.assertEqual([x["episode_uid"] for x in plan], list(r.TARGET_UIDS))
        self.assertEqual(
            [x["alerts_in_ua"]["source_record_key"] for x in plan],
            list(r.EXPECTED_SOURCE_RECORD_KEYS),
        )
        self.assertEqual(
            [x["new"]["legacy_episode_id"] for x in plan],
            [
                "7dd411c2a2587efc740a1a66",
                "c2cd9a96768756d84c250735",
                "94ce779cf047984e881bfdd5",
            ],
        )

    def test_boundaries_and_flags(self):
        plan = r.repair_plan()
        self.assertEqual(
            (plan[0]["old"]["start_at"], plan[0]["old"]["end_at"]),
            ("2026-09-12T22:00:05.398348Z", "2026-09-12T22:14:23.315771Z"),
        )
        self.assertEqual(
            (plan[0]["new"]["start_at"], plan[0]["new"]["end_at"]),
            ("2026-09-12T22:00:05.398348Z", "2026-09-12T22:14:27Z"),
        )
        expected = [
            ((True, False), (False, True)),
            ((False, True), (True, False)),
            ((False, False), (True, True)),
        ]
        for row, pair in zip(plan, expected):
            self.assertEqual(
                (
                    row["ukrainealarm_flags"]["contributes_start_boundary"],
                    row["ukrainealarm_flags"]["contributes_end_boundary"],
                ),
                pair[0],
            )
            self.assertEqual(
                (
                    row["alerts_in_ua"]["contributes_start_boundary"],
                    row["alerts_in_ua"]["contributes_end_boundary"],
                ),
                pair[1],
            )

    def test_provenance_has_frozen_recovery_fields_and_no_row_raw_hash(self):
        t = r.TARGETS[0]
        preimage, _ = t.source_identity
        p = r._provenance(t, preimage)
        self.assertEqual(p["source_family"], "alerts_in_ua_static_bridge")
        self.assertEqual(p["frozen_production_ref"], r.FROZEN_PRODUCTION_REF)
        self.assertEqual(p["git_blob_sha"], r.RAW_OBJECT_GIT_BLOB_SHA)
        self.assertEqual(p["decoded_csv_sha256"], r.DECODED_CSV_SHA256)
        self.assertEqual(p["raw_local_start"], "2026-09-13T01:00:06+03:00")
        self.assertNotIn("raw_sha256", p)


class StateFactory:
    @staticmethod
    def pristine():
        episodes, sources = [], []
        for t in r.TARGETS:
            episodes.append(
                {
                    "episode_uid": t.episode_uid,
                    "legacy_episode_id": t.old_legacy_id,
                    "start_at": r._six(t.old_start),
                    "end_at": r._six(t.old_end),
                    "city_key": "lviv",
                    "alert_type": "AIR",
                    "episode_state": "closed",
                    "canonicalization_version": r.CANONICALIZATION_VERSION,
                }
            )
            sources.append(
                {
                    "episode_uid": t.episode_uid,
                    "source_key": "ukrainealarm_region_history",
                    "binding_state": "bound",
                    "canonicalization_role": "canonical_input",
                    "contributes_start_boundary": True,
                    "contributes_end_boundary": True,
                }
            )
        return {
            "episodes": episodes,
            "sources": sources,
            "non_target_123_md5": r.EXPECTED_NON_TARGET_123_MD5,
        }

    @staticmethod
    def repaired():
        state = StateFactory.pristine()
        state["episodes"] = []
        state["sources"] = []
        for t, key in zip(r.TARGETS, r.EXPECTED_SOURCE_RECORD_KEYS):
            state["episodes"].append(
                {
                    "episode_uid": t.episode_uid,
                    "legacy_episode_id": t.new_legacy_id,
                    "start_at": r._six(t.new_start),
                    "end_at": r._six(t.new_end),
                    "city_key": "lviv",
                    "alert_type": "AIR",
                    "episode_state": "closed",
                    "canonicalization_version": r.CANONICALIZATION_VERSION,
                }
            )
            state["sources"].append(
                {
                    "episode_uid": t.episode_uid,
                    "source_key": "ukrainealarm_region_history",
                    "binding_state": "bound",
                    "canonicalization_role": "canonical_input",
                    "contributes_start_boundary": t.ua_start_flag,
                    "contributes_end_boundary": t.ua_end_flag,
                }
            )
            state["sources"].append(
                {
                    "episode_uid": t.episode_uid,
                    "source_key": r.SOURCE_KEY,
                    "source_record_key": key,
                    "source_start_at": r._six(t.static_start),
                    "source_end_at": r._six(t.static_end),
                    "binding_state": "bound",
                    "canonicalization_role": "canonical_input",
                    "contributes_start_boundary": t.static_start_flag,
                    "contributes_end_boundary": t.static_end_flag,
                }
            )
        return state


class TestClassifier(unittest.TestCase):
    def test_precondition_pristine(self):
        self.assertEqual(r.classify_state(StateFactory.pristine()), "pristine")

    def test_exact_retry_state(self):
        self.assertEqual(r.classify_state(StateFactory.repaired()), "already_repaired")

    def test_reject_changed_old_boundary(self):
        state = StateFactory.pristine()
        state["episodes"][0]["end_at"] = "2026-09-12T22:14:24.000000Z"
        with self.assertRaises(r.RepairBlocked):
            r.classify_state(state)

    def test_reject_old_legacy_mismatch(self):
        state = StateFactory.pristine()
        state["episodes"][1]["legacy_episode_id"] = "0" * 24
        with self.assertRaises(r.RepairBlocked):
            r.classify_state(state)

    def test_reject_unexpected_second_source(self):
        state = StateFactory.pristine()
        state["sources"].append(dict(state["sources"][0]))
        with self.assertRaises(r.RepairBlocked):
            r.classify_state(state)

    def test_reject_inconsistent_contributor_state(self):
        state = StateFactory.pristine()
        state["sources"][2]["contributes_end_boundary"] = False
        with self.assertRaises(r.RepairBlocked):
            r.classify_state(state)

    def test_reject_nontarget_change(self):
        state = StateFactory.pristine()
        state["non_target_123_md5"] = "bad"
        with self.assertRaises(r.RepairBlocked):
            r.classify_state(state)


class FakeCursor:
    def __init__(self):
        self.rowcount = 1
        self._one = ("run-proof",)
        self.commands = []

    def execute(self, sql, params=()):
        self.commands.append(sql)
        if "RUN_INSERT" in sql:
            self._one = ("00000000-0000-0000-0000-000000000001",)
        elif "count(*) FROM alert_episode_sources" in sql:
            self._one = (0,)
        elif "count(*) FROM alert_episodes WHERE legacy_episode_id" in sql:
            self._one = (0,)
        elif "count(*) FROM alert_episodes WHERE city_key='lviv'" in sql:
            self._one = (0,)
        else:
            self._one = ("00000000-0000-0000-0000-000000000001",)
        self.rowcount = 1

    def fetchone(self):
        return self._one

    def close(self):
        pass


class FakeConnection:
    def __init__(self):
        self.cur = FakeCursor()
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return self.cur

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def pristine_inspector(cursor, lock=False):
    return StateFactory.pristine()


def repaired_inspector(cursor, lock=False):
    return StateFactory.repaired()


class TestTransactionControl(unittest.TestCase):
    def test_forced_failure_rolls_back_after_source_insert(self):
        c = FakeConnection()
        with self.assertRaises(r.ForcedRepairFailure):
            r.repair(c, force_failure_after_first_source=True, inspector=pristine_inspector, db_branch="br-test")
        self.assertEqual(c.commits, 0)
        self.assertEqual(c.rollbacks, 1)
        self.assertTrue(any("RUN_INSERT" in x for x in c.cur.commands))
        self.assertTrue(any("SOURCE_INSERT" in x for x in c.cur.commands))
        self.assertFalse(any("RUN_FINALIZE" in x for x in c.cur.commands))

    def test_exact_retry_is_zero_write(self):
        c = FakeConnection()
        out = r.repair(c, inspector=repaired_inspector, db_branch="br-test")
        self.assertEqual(out["status"], "already_repaired")
        self.assertEqual(out["writes"], 0)
        self.assertEqual(c.commits, 0)
        self.assertEqual(c.rollbacks, 1)
        self.assertFalse(any("RUN_INSERT" in x for x in c.cur.commands))


    def test_mutating_repair_requires_explicit_db_branch(self):
        c = FakeConnection()
        with self.assertRaises(r.RepairBlocked):
            r.repair(c, inspector=pristine_inspector)
        self.assertEqual(c.commits, 0)
        self.assertEqual(c.rollbacks, 1)

    def test_fresh_connection_retry_is_zero_write(self):
        a = r.repair(FakeConnection(), inspector=repaired_inspector, db_branch="br-test")
        b = r.repair(FakeConnection(), inspector=repaired_inspector, db_branch="br-test")
        self.assertEqual((a["writes"], b["writes"]), (0, 0))


class CollisionCursor:
    def __init__(self, first=0, second=0, interval=0):
        self.values = [first, second, interval, interval, interval]

    def execute(self, sql, params=()):
        self.sql = sql

    def fetchone(self):
        return (self.values.pop(0),)


class TestCollisionGuards(unittest.TestCase):
    def test_reject_existing_static_source_record_key(self):
        with self.assertRaises(r.RepairBlocked):
            r._guard_collisions(CollisionCursor(first=1))

    def test_reject_new_legacy_id_collision(self):
        with self.assertRaises(r.RepairBlocked):
            r._guard_collisions(CollisionCursor(second=1))

    def test_reject_exact_new_interval_collision(self):
        with self.assertRaises(r.RepairBlocked):
            r._guard_collisions(CollisionCursor(interval=1))

    def test_repair_source_has_no_checkpoint_or_differentiated_mutation(self):
        src = inspect.getsource(r)
        for forbidden in (
            "INSERT INTO ingestion_checkpoints",
            "UPDATE ingestion_checkpoints",
            "DELETE FROM ingestion_checkpoints",
            "INSERT INTO alert_state_snapshots",
            "UPDATE alert_state_snapshots",
            "DELETE FROM alert_state_snapshots",
            "INSERT INTO alert_threat_observations",
            "UPDATE alert_threat_observations",
            "DELETE FROM alert_threat_observations",
        ):
            self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
