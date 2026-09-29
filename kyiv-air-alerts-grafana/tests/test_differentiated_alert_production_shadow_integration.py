import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import differentiated_alert_shadow_runtime as runtime
import proof_differentiated_alert_shadow_ingestion as shadow

F = ROOT / "tests" / "fixtures" / "differentiated_alert_shadow"
KYIV = F / "kyiv_live_raw_2026-09-29_111347.json"
UA = F / "ukrainealarm_overlap_stored_raw_2026-09-14.json"
AIU = F / "alerts_in_ua_stored_raw_2026-09-16.json"
NOW = datetime(2026, 9, 29, 11, 14, 0, tzinfo=timezone.utc)


def alerts():
    return [
        SimpleNamespace(
            start=datetime(2026, 9, 29, 8, 30, tzinfo=timezone.utc),
            end=datetime(2026, 9, 29, 9, 0, tzinfo=timezone.utc),
        )
    ]


def base_env(db_path):
    return {
        runtime.FEATURE_FLAG: "1",
        runtime.DB_ENV: str(db_path),
        runtime.KYIV_INPUT_ENV: str(KYIV),
        runtime.KYIV_INPUT_CLASS_ENV: "LIVE_RAW",
        runtime.UA_INPUT_ENV: str(UA),
        runtime.AIU_INPUT_ENV: str(AIU),
    }


class Integration(unittest.TestCase):
    def temp_db(self):
        f = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        f.close()
        Path(f.name).unlink(missing_ok=True)
        self.addCleanup(lambda: Path(f.name).unlink(missing_ok=True))
        return f.name

    def test_01_flag_off_is_noop(self):
        touched = {"fetch": 0, "store": 0}
        def bad_fetch(url, timeout):
            touched["fetch"] += 1
            raise AssertionError("fetch should not run")
        def bad_store(path):
            touched["store"] += 1
            raise AssertionError("store should not open")
        r = runtime.run_shadow(alerts(), env={}, fetch_json=bad_fetch, store_factory=bad_store, now=NOW)
        self.assertEqual(r["status"], "DISABLED")
        self.assertFalse(r["attempted"])
        self.assertEqual(touched, {"fetch": 0, "store": 0})

    def test_02_flag_on_persists_children(self):
        db = self.temp_db()
        r = runtime.run_shadow(alerts(), env=base_env(db), now=NOW)
        self.assertEqual(r["status"], "SUCCEEDED")
        self.assertEqual(r["inserted_snapshots"], 3)
        self.assertEqual(r["inserted_observations"], 3)
        self.assertEqual(r["store_counts"], {"snapshots": 3, "observations": 3})
        self.assertEqual(r["sources"]["kyiv"]["input_class"], "LIVE_RAW")
        self.assertEqual(r["sources"]["ukrainealarm"]["input_class"], "STORED_RAW")
        self.assertEqual(r["sources"]["alerts_in_ua"]["input_class"], "STORED_RAW")

    def test_03_exact_replay_idempotent(self):
        db = self.temp_db()
        env = base_env(db)
        first = runtime.run_shadow(alerts(), env=env, now=NOW)
        second = runtime.run_shadow(alerts(), env=env, now=NOW)
        self.assertEqual((first["inserted_snapshots"], first["inserted_observations"]), (3, 3))
        self.assertEqual((second["inserted_snapshots"], second["inserted_observations"]), (0, 0))
        self.assertEqual(second["store_counts"], {"snapshots": 3, "observations": 3})

    def test_04_missing_optional_credentials_fail_open(self):
        db = self.temp_db()
        env = {
            runtime.FEATURE_FLAG: "1",
            runtime.DB_ENV: db,
            runtime.KYIV_INPUT_ENV: str(KYIV),
            runtime.KYIV_INPUT_CLASS_ENV: "LIVE_RAW",
        }
        r = runtime.run_shadow(alerts(), env=env, now=NOW)
        self.assertEqual(r["status"], "SUCCEEDED")
        self.assertEqual(r["sources"]["ukrainealarm"]["input_class"], "SKIPPED_NO_CREDENTIAL")
        self.assertEqual(r["sources"]["alerts_in_ua"]["input_class"], "SKIPPED_NO_CREDENTIAL")
        self.assertEqual(r["store_counts"], {"snapshots": 1, "observations": 0})

    def test_05_source_failure_does_not_suppress_other_sources(self):
        db = self.temp_db()
        env = base_env(db)
        env.pop(runtime.KYIV_INPUT_ENV)
        def fail_fetch(url, timeout):
            raise OSError("forced live source failure")
        r = runtime.run_shadow(alerts(), env=env, fetch_json=fail_fetch, now=NOW)
        self.assertEqual(r["status"], "PARTIAL_FAILURE")
        self.assertEqual(r["sources"]["kyiv"]["status"], "FAILED")
        self.assertEqual(r["sources"]["ukrainealarm"]["status"], "SUCCEEDED")
        self.assertEqual(r["sources"]["alerts_in_ua"]["status"], "SUCCEEDED")
        self.assertEqual(r["store_counts"], {"snapshots": 2, "observations": 3})

    def test_06_persistence_failure_is_source_isolated(self):
        db = self.temp_db()
        class FailFirstStore(shadow.ShadowStore):
            def __init__(self, path):
                super().__init__(path)
                self.calls = 0
            def persist(self, record, fail_after_snapshot=False):
                self.calls += 1
                if self.calls == 1:
                    return super().persist(record, True)
                return super().persist(record, fail_after_snapshot)
        r = runtime.run_shadow(alerts(), env=base_env(db), store_factory=FailFirstStore, now=NOW)
        self.assertEqual(r["status"], "PARTIAL_FAILURE")
        self.assertEqual(r["sources"]["kyiv"]["status"], "FAILED")
        self.assertEqual(r["sources"]["ukrainealarm"]["status"], "SUCCEEDED")
        self.assertEqual(r["sources"]["alerts_in_ua"]["status"], "SUCCEEDED")
        self.assertEqual(r["store_counts"], {"snapshots": 2, "observations": 3})

    def test_07_store_open_failure_is_fail_open(self):
        def fail_store(path):
            raise sqlite3.OperationalError("forced store open failure")
        env = {runtime.FEATURE_FLAG: "1", runtime.DB_ENV: "/irrelevant"}
        r = runtime.run_shadow(alerts(), env=env, store_factory=fail_store, now=NOW)
        self.assertEqual(r["status"], "FAILED")
        self.assertEqual(r["error_type"], "OperationalError")
        self.assertFalse(r["production_output_mutation"])

    def test_08_missing_store_configuration_is_fail_open(self):
        r = runtime.run_shadow(alerts(), env={runtime.FEATURE_FLAG: "1"}, now=NOW)
        self.assertEqual(r["status"], "FAILED")
        self.assertIn(runtime.DB_ENV, r["error"])

    def test_09_sidecar_does_not_mutate_publication_file(self):
        db = self.temp_db()
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(tmp, ignore_errors=True))
        pub = tmp / "dashboard_data.json"
        pub.write_text(json.dumps({"authoritative": True}, sort_keys=True), encoding="utf-8")
        before = hashlib.sha256(pub.read_bytes()).hexdigest()
        runtime.run_shadow(alerts(), env=base_env(db), now=NOW)
        after = hashlib.sha256(pub.read_bytes()).hexdigest()
        self.assertEqual(before, after)

    def test_10_parent_input_unchanged_and_no_parent_api(self):
        parent = alerts()
        before = [(a.start, a.end) for a in parent]
        db = self.temp_db()
        runtime.run_shadow(parent, env=base_env(db), now=NOW)
        self.assertEqual(before, [(a.start, a.end) for a in parent])
        self.assertFalse(any(hasattr(shadow.ShadowStore, name) for name in [
            "create_episode", "update_episode_start", "update_episode_end", "delete_episode"
        ]))

    def test_11_last_resort_boundary_never_raises(self):
        with patch.object(runtime, "run_shadow", side_effect=RuntimeError("forced boundary failure")):
            r = runtime.run_from_updater(alerts(), env={runtime.FEATURE_FLAG: "1"})
        self.assertEqual(r["status"], "FAILED")
        self.assertEqual(r["error_type"], "RuntimeError")
        self.assertFalse(r["production_output_mutation"])

    def test_12_updater_seam_is_default_off_and_post_write(self):
        text = (ROOT / "scripts" / "update_data.py").read_text(encoding="utf-8")
        gate = 'if os.getenv("DIFFERENTIATED_ALERT_SHADOW", "").strip().lower() in {"1", "true", "yes", "on"}:'
        self.assertIn(gate, text)
        self.assertIn("from differentiated_alert_shadow_runtime import run_from_updater", text)
        self.assertGreater(text.index(gate), text.index('(DATA_DIR / "alerts_combined.json").write_text'))
        self.assertNotIn("differentiated_alert_shadow_runtime", text[:text.index(gate)])


if __name__ == "__main__":
    unittest.main(verbosity=2)
