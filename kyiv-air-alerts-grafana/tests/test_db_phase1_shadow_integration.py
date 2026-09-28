from __future__ import annotations

import builtins
import inspect
import json
import sys
import types
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_ukrainealarm_bridge as bridge
import db_phase1_lviv_canonical as canonical
import db_phase1_lviv_import as importer
import db_phase1_shadow as shadow

FIXTURES = ROOT / "tests" / "fixtures" / "db_phase1"
FAKE_ENV = {
    "PHASE1_DB_SHADOW": "1",
    "PHASE1_DATABASE_URL": "postgresql://not-used",
    "PHASE1_DB_BRANCH": "proof-branch",
    "GITHUB_REPOSITORY": "olegbalakin-cmyk/kyiv-air-alerts-grafana",
    "GITHUB_WORKFLOW": "Phase-1 Shadow Ingestion Integration Proof",
    "GITHUB_REF": "refs/heads/db-phase1-shadow-integration-v2-2026-09-28",
    "GITHUB_SHA": "a" * 40,
    "GITHUB_RUN_ID": "123",
    "GITHUB_RUN_ATTEMPT": "1",
}


class ShadowIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        vad_rows = json.loads((FIXTURES / "lviv" / "vadimkin_rows.json").read_text(encoding="utf-8"))["rows"]
        cls.ua_fixture = json.loads((FIXTURES / "lviv" / "ukrainealarm_bridge.json").read_text(encoding="utf-8"))
        cls.vad_obs, _ = canonical.vadimkin_rows_to_observations(vad_rows)
        cls.ua_obs = canonical.ukrainealarm_rows_to_observations(cls.ua_fixture["events"])
        cls.canonical_payload = canonical.canonicalize_lviv(
            cls.vad_obs, cls.ua_obs, checkpoint_state=cls.ua_fixture["checkpoint_state"]
        )

    def test_shadow_translation_matches_accepted_historical_rows(self):
        got = shadow.build_shadow_persistence_payload(
            self.canonical_payload, checkpoint_state=self.ua_fixture["checkpoint_state"], env=FAKE_ENV
        )
        accepted = importer.build_lviv_persistence_payload(FIXTURES)
        self.assertEqual(accepted["episodes"], got["episodes"])
        self.assertEqual(accepted["source_observations"], got["source_observations"])
        self.assertEqual(
            accepted["run_provenance"]["canonicalization_version"],
            got["run_provenance"]["canonicalization_version"],
        )

    def test_poll_candidate_has_adapter_owned_chain_fields(self):
        got = shadow.build_shadow_persistence_payload(
            self.canonical_payload, checkpoint_state=self.ua_fixture["checkpoint_state"], env=FAKE_ENV
        )
        candidate = got["checkpoint_candidate"]
        self.assertEqual("poll", candidate["checkpoint_kind"])
        self.assertNotIn("checkpoint_seq", candidate)
        self.assertNotIn("previous_checkpoint_id", candidate)
        self.assertNotIn("previous_checkpoint", candidate)
        self.assertEqual("region_id:90:AIR", candidate["stream_key"])
        for field in (
            "source_key", "city_key", "stream_key", "checked_at", "continuity_verified",
            "continuity_method", "continuity_anchor_at", "observed_oldest_start_at",
            "observed_latest_end_at", "observed_record_count", "cursor", "metadata",
        ):
            self.assertIn(field, candidate)

    def test_shadow_provenance_uses_current_workflow_sha(self):
        got = shadow.build_shadow_persistence_payload(
            self.canonical_payload, checkpoint_state=self.ua_fixture["checkpoint_state"], env=FAKE_ENV
        )
        provenance = got["run_provenance"]
        self.assertEqual("shadow_poll", provenance["run_kind"])
        self.assertEqual("001_phase1_core", provenance["schema_version"])
        self.assertEqual("alert-canonicalization-v1", provenance["canonicalization_version"])
        self.assertEqual("lviv-historical-v1", provenance["assembly_profile"])
        self.assertEqual(FAKE_ENV["GITHUB_SHA"], provenance["input_sha"])
        self.assertEqual(FAKE_ENV["GITHUB_SHA"], provenance["workflow_sha"])
        self.assertTrue(provenance["parameters"]["shadow"])

    def test_shadow_provenance_separates_workflow_and_checked_out_input(self):
        env = {
            **FAKE_ENV,
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_SHA": "a" * 40,
            "PHASE1_INPUT_REPOSITORY": FAKE_ENV["GITHUB_REPOSITORY"],
            "PHASE1_INPUT_REF": "site-prod",
            "PHASE1_INPUT_SHA": "b" * 40,
        }
        got = shadow.build_shadow_persistence_payload(
            self.canonical_payload,
            checkpoint_state=self.ua_fixture["checkpoint_state"],
            env=env,
        )
        provenance = got["run_provenance"]
        self.assertEqual("refs/heads/main", provenance["workflow_ref"])
        self.assertEqual("a" * 40, provenance["workflow_sha"])
        self.assertEqual("site-prod", provenance["input_ref"])
        self.assertEqual("b" * 40, provenance["input_sha"])
        self.assertNotEqual(provenance["workflow_sha"], provenance["input_sha"])

    def test_alertsinua_is_absent_from_shadow_source_rows(self):
        got = shadow.build_shadow_persistence_payload(
            self.canonical_payload, checkpoint_state=self.ua_fixture["checkpoint_state"], env=FAKE_ENV
        )
        keys = {row["source_key"] for row in got["source_observations"]}
        self.assertEqual({"vadimkin_official_data_uk", "ukrainealarm_region_history"}, keys)
        self.assertNotIn("alerts-in-ua", keys)

    def test_shadow_off_returns_before_canonicalizer_or_db_import(self):
        original_import = builtins.__import__
        def guarded_import(name, *args, **kwargs):
            if name in {"db_phase1_shadow", "psycopg"}:
                raise AssertionError(f"unexpected shadow DB import: {name}")
            return original_import(name, *args, **kwargs)
        with patch.object(bridge, "canonicalize_lviv") as canonicalize, patch(
            "builtins.__import__", side_effect=guarded_import
        ):
            result = bridge.persist_lviv_shadow_if_enabled(
                lviv_fetched_this_run=False, vadimkin_observations=[],
                ukrainealarm_observations=[], checkpoint_state=None,
                env={"PHASE1_DB_SHADOW": "0"},
            )
        self.assertIsNone(result)
        canonicalize.assert_not_called()

    def test_shadow_on_passes_current_sources_through_accepted_canonicalizer(self):
        fake = types.ModuleType("db_phase1_shadow")
        captured = {}
        def persist(payload, *, checkpoint_state, env):
            captured["payload"] = payload
            captured["checkpoint_state"] = checkpoint_state
            captured["env"] = env
            return {"run_id": "fake", "stats": {}}
        fake.persist_shadow_payload = persist
        with patch.dict(sys.modules, {"db_phase1_shadow": fake}), patch.object(
            bridge, "canonicalize_lviv", return_value=self.canonical_payload
        ) as canonicalize:
            result = bridge.persist_lviv_shadow_if_enabled(
                lviv_fetched_this_run=True, vadimkin_observations=self.vad_obs,
                ukrainealarm_observations=self.ua_obs, checkpoint_state=self.ua_fixture["checkpoint_state"],
                env=FAKE_ENV,
            )
        self.assertEqual("fake", result["run_id"])
        canonicalize.assert_called_once()
        self.assertIs(self.vad_obs, canonicalize.call_args.args[0])
        self.assertIs(self.ua_obs, canonicalize.call_args.args[1])
        self.assertIs(self.canonical_payload, captured["payload"])

    def test_shadow_on_rejects_missing_fresh_lviv_conditions(self):
        with self.assertRaisesRegex(RuntimeError, "fresh verified Lviv inputs"):
            bridge.persist_lviv_shadow_if_enabled(
                lviv_fetched_this_run=False, vadimkin_observations=self.vad_obs,
                ukrainealarm_observations=[], checkpoint_state={"region_id": "90", "continuous": False},
                env=FAKE_ENV,
            )

    def test_shadow_persistence_failure_propagates(self):
        fake = types.ModuleType("db_phase1_shadow")
        def fail(*args, **kwargs):
            raise RuntimeError("db fail")
        fake.persist_shadow_payload = fail
        with patch.dict(sys.modules, {"db_phase1_shadow": fake}), patch.object(
            bridge, "canonicalize_lviv", return_value=self.canonical_payload
        ):
            with self.assertRaisesRegex(RuntimeError, "db fail"):
                bridge.persist_lviv_shadow_if_enabled(
                    lviv_fetched_this_run=True, vadimkin_observations=self.vad_obs,
                    ukrainealarm_observations=self.ua_obs, checkpoint_state=self.ua_fixture["checkpoint_state"],
                    env=FAKE_ENV,
                )

    def test_shadow_fail_open_swallows_only_shadow_failure_and_writes_diagnostic(self):
        fake = types.ModuleType("db_phase1_shadow")
        def fail(*args, **kwargs):
            raise RuntimeError("forced db fail")
        fake.persist_shadow_payload = fail
        with TemporaryDirectory() as tmp, patch.dict(
            sys.modules, {"db_phase1_shadow": fake}
        ), patch.object(
            bridge, "canonicalize_lviv", return_value=self.canonical_payload
        ):
            diagnostic = Path(tmp) / "phase1.json"
            env = {
                **FAKE_ENV,
                "PHASE1_DB_SHADOW_FAILURE_POLICY": "fail_open",
                "PHASE1_DB_SHADOW_DIAGNOSTIC": str(diagnostic),
            }
            result = bridge.persist_lviv_shadow_if_enabled(
                lviv_fetched_this_run=True,
                vadimkin_observations=self.vad_obs,
                ukrainealarm_observations=self.ua_obs,
                checkpoint_state=self.ua_fixture["checkpoint_state"],
                env=env,
            )
            self.assertIsNone(result)
            payload = json.loads(diagnostic.read_text(encoding="utf-8"))
            self.assertEqual("failed", payload["status"])
            self.assertEqual("fail_open", payload["failure_policy"])
            self.assertEqual("RuntimeError", payload["error_type"])
            self.assertFalse(payload["credentials_exposed"])

    def test_shadow_fail_closed_remains_default_and_propagates(self):
        fake = types.ModuleType("db_phase1_shadow")
        def fail(*args, **kwargs):
            raise RuntimeError("db fail closed")
        fake.persist_shadow_payload = fail
        with patch.dict(sys.modules, {"db_phase1_shadow": fake}), patch.object(
            bridge, "canonicalize_lviv", return_value=self.canonical_payload
        ):
            with self.assertRaisesRegex(RuntimeError, "db fail closed"):
                bridge.persist_lviv_shadow_if_enabled(
                    lviv_fetched_this_run=True,
                    vadimkin_observations=self.vad_obs,
                    ukrainealarm_observations=self.ua_obs,
                    checkpoint_state=self.ua_fixture["checkpoint_state"],
                    env=FAKE_ENV,
                )

    def test_shadow_failure_diagnostic_redacts_database_url_password_and_tokens(self):
        with TemporaryDirectory() as tmp:
            diagnostic = Path(tmp) / "phase1.json"
            fake_url = "postgresql://user:super-secret-password@example.test/neondb"
            fake_api_key = "fake-neon-api-key"
            fake_ua_token = "fake-ukrainealarm-token"
            env = {
                **FAKE_ENV,
                "PHASE1_DATABASE_URL": fake_url,
                "NEON_API_KEY": fake_api_key,
                "UKRAINEALARM_API_TOKEN": fake_ua_token,
                "PHASE1_DB_SHADOW_FAILURE_POLICY": "fail_open",
                "PHASE1_DB_SHADOW_DIAGNOSTIC": str(diagnostic),
            }
            exc = RuntimeError(
                f"connect failed {fake_url} {fake_api_key} {fake_ua_token}"
            )
            payload = bridge._shadow_failure_diagnostic(exc, env, "fail_open")
            bridge._write_shadow_diagnostic(payload, env)
            raw = diagnostic.read_text(encoding="utf-8")
            self.assertNotIn(fake_url, raw)
            self.assertNotIn("super-secret-password", raw)
            self.assertNotIn(fake_api_key, raw)
            self.assertNotIn(fake_ua_token, raw)
            self.assertIn("[REDACTED]", raw)

    def test_invalid_failure_policy_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, "must be one of"):
            bridge.phase1_db_shadow_failure_policy(
                {"PHASE1_DB_SHADOW_FAILURE_POLICY": "ignore_everything"}
            )

    def test_real_bridge_uses_phase1_proxy_fetch_once(self):
        source = inspect.getsource(bridge.main)
        self.assertEqual(1, source.count("base.fetch_proxy_alerts_with_phase1()"))
        self.assertNotIn("base.fetch_proxy_alerts()", source)

    def test_shadow_persistence_precedes_product_file_writes(self):
        source = inspect.getsource(bridge.main)
        shadow_index = source.index("persist_lviv_shadow_if_enabled(")
        self.assertLess(shadow_index, source.index("STORE_FILE.write_text"))
        self.assertLess(shadow_index, source.index("DATA_FILE.write_text"))


if __name__ == "__main__":
    unittest.main()
