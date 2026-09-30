import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import differentiated_alert_shadow_runtime as runtime

FIX = ROOT / "tests" / "fixtures" / "differentiated_alert_shadow"


class FakeStore:
    def __init__(self, target):
        self.target = target
        self.rows = []
        self.closed = False

    def persist(self, record):
        self.rows.append(record)
        return {
            "inserted_snapshots": 1,
            "inserted_observations": len(record.get("threat_observations", [])),
        }

    def counts(self):
        return {
            "snapshots": len(self.rows),
            "observations": sum(len(r.get("threat_observations", [])) for r in self.rows),
        }

    def close(self):
        self.closed = True


def fixture_env(db_path):
    return {
        runtime.FEATURE_FLAG: "1",
        runtime.DB_ENV: str(db_path),
        runtime.KYIV_INPUT_ENV: str(FIX / "kyiv_live_raw_2026-09-29_111347.json"),
        runtime.KYIV_INPUT_CLASS_ENV: "FIXTURE",
        runtime.UA_INPUT_ENV: str(FIX / "ukrainealarm_overlap_stored_raw_2026-09-14.json"),
        runtime.AIU_INPUT_ENV: str(FIX / "alerts_in_ua_stored_raw_2026-09-16.json"),
    }


class Tests(unittest.TestCase):
    def test_disabled_requires_no_backend_or_connection(self):
        called = False

        def should_not_run(_target):
            nonlocal called
            called = True
            raise AssertionError("store factory must not run while disabled")

        out = runtime.run_shadow(
            [],
            env={
                runtime.FEATURE_FLAG: "0",
                runtime.BACKEND_ENV: "postgres",
                runtime.DATABASE_URL_ENV: "postgresql://invalid.example/never-used",
            },
            store_factory=should_not_run,
        )
        self.assertFalse(called)
        self.assertFalse(out["attempted"])
        self.assertEqual(out["status"], "DISABLED")

    def test_sqlite_default_remains_backward_compatible_and_idempotent(self):
        with tempfile.TemporaryDirectory() as td:
            db = Path(td) / "shadow.sqlite"
            env = fixture_env(db)
            now = datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc)
            first = runtime.run_shadow([], env=env, now=now)
            second = runtime.run_shadow([], env=env, now=now)
        self.assertEqual(first["status"], "SUCCEEDED")
        self.assertEqual(first["backend"], "sqlite")
        self.assertEqual((first["inserted_snapshots"], first["inserted_observations"]), (3, 3))
        self.assertEqual(second["status"], "SUCCEEDED")
        self.assertEqual((second["inserted_snapshots"], second["inserted_observations"]), (0, 0))
        self.assertEqual(second["store_counts"], {"snapshots": 3, "observations": 3})

    def test_postgres_backend_uses_separate_database_url_contract(self):
        captured = {}

        def factory(target):
            captured["target"] = target
            return FakeStore(target)

        env = fixture_env("/must-not-be-used.sqlite")
        env[runtime.BACKEND_ENV] = "postgres"
        env[runtime.DATABASE_URL_ENV] = "postgresql://proof-only.example/db"
        out = runtime.run_shadow(
            [],
            env=env,
            store_factory=factory,
            now=datetime(2026, 9, 30, 20, 0, tzinfo=timezone.utc),
        )
        self.assertEqual(captured["target"], env[runtime.DATABASE_URL_ENV])
        self.assertEqual(out["backend"], "postgres")
        self.assertEqual(out["status"], "SUCCEEDED")

    def test_unknown_backend_fails_closed_inside_sidecar(self):
        out = runtime.run_shadow(
            [],
            env={runtime.FEATURE_FLAG: "1", runtime.BACKEND_ENV: "oracle"},
        )
        self.assertTrue(out["attempted"])
        self.assertEqual(out["status"], "FAILED")
        self.assertEqual(out["error_type"], "RuntimeError")


if __name__ == "__main__":
    unittest.main()
