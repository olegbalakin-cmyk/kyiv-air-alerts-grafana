import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from differentiated_alert_postgres import PostgresShadowStore
import proof_differentiated_alert_shadow_ingestion as shadow

DSN = os.environ.get("DIFFERENTIATED_ALERT_SHADOW_DATABASE_URL", "")
SCHEMA = os.environ.get("PROOF_DIFFERENTIATED_SCHEMA", "differentiated_alert_shadow_proof_20260930") + "_unittest"
FIXTURE = ROOT / "tests/fixtures/differentiated_alert_shadow/kyiv_live_raw_2026-09-29_111347.json"


@unittest.skipUnless(DSN, "proof Postgres DSN not configured")
class PostgresStoreIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store = PostgresShadowStore(DSN, SCHEMA)
        cls.payload = json.loads(FIXTURE.read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()

    def record(self, observed_at="2026-09-30T06:00:00Z"):
        rec = shadow.canonicalize_kyiv(
            self.payload,
            observed_at=observed_at,
            target_city_key="kyiv",
            raw_object_path="$POSTGRES_TEST",
        )
        return shadow.bind(rec, [])

    def test_01_exact_retry_is_idempotent(self):
        rec = self.record()
        self.store.persist(rec)
        before = self.store.counts()
        second = self.store.persist(rec)
        after = self.store.counts()
        self.assertEqual(before, after)
        self.assertEqual(second["inserted_snapshots"], 0)
        self.assertEqual(second["inserted_observations"], 0)

    def test_02_mid_write_failure_rolls_back(self):
        rec = self.record("2026-09-30T06:00:17Z")
        before = self.store.counts()
        with self.assertRaises(RuntimeError):
            self.store.persist(rec, fail_after_snapshot=True)
        self.assertEqual(before, self.store.counts())

    def test_03_has_no_parent_mutation_api(self):
        forbidden = {"create_episode", "update_episode_start", "update_episode_end", "delete_episode"}
        self.assertFalse(any(hasattr(self.store, name) for name in forbidden))


if __name__ == "__main__":
    unittest.main(verbosity=2)
