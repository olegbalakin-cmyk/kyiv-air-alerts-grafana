from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from db_phase1_core import alerts_in_ua_source_record_key  # noqa: E402
from db_phase1_lviv_proof import (  # noqa: E402
    ASSEMBLY_PROFILE,
    EXPECTED_ADDITIONS,
    EXPECTED_BRIDGE_COUNT,
    EXPECTED_FINAL,
    EXPECTED_FROZEN_COUNT,
    EXPECTED_OVERLAP,
    _vadimkin_rows_to_observations,
    bootstrap_summary,
    build_lviv,
    build_recovery,
    load_json,
)

FIXTURES = ROOT / "tests" / "fixtures" / "db_phase1"


class LvivCanonicalizationProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = build_lviv(FIXTURES)

    def test_exact_oracle_parity(self):
        r = self.result
        self.assertEqual(EXPECTED_FROZEN_COUNT, r["historical_merged_count"])
        self.assertEqual(EXPECTED_BRIDGE_COUNT, r["ukrainealarm_interval_count"])
        self.assertEqual(EXPECTED_OVERLAP, r["api_overlap_refinement_count"])
        self.assertEqual(EXPECTED_ADDITIONS, r["api_additions"])
        self.assertEqual(EXPECTED_FINAL, r["canonical_episode_count"])
        self.assertEqual(EXPECTED_FINAL, r["unique_legacy_id_count"])
        self.assertEqual([], r["missing_ids"])
        self.assertEqual([], r["unexpected_ids"])
        self.assertEqual([], r["interval_mismatches"])
        self.assertEqual([], r["duplicate_ids"])

    def test_previous_static_seam_blocker_is_resolved_by_composition(self):
        b = self.result["blocker_regression"]
        self.assertTrue(b["api_interval_is_canonical_input"])
        self.assertFalse(b["alerts_in_ua_static_in_stage_c"])
        self.assertTrue(b["expected_episode_present"])
        self.assertEqual("b3df9090f7264ddbd726e113", b["expected_id"])
        self.assertFalse(b["incorrect_expanded_id_present"])
        self.assertEqual("PASS", b["result"])

    def test_boundary_contribution_is_complete_and_exact(self):
        self.assertEqual([], self.result["boundary_errors"])

    def test_duplicate_semantic_observation_is_idempotent(self):
        rows = load_json(FIXTURES / "lviv" / "vadimkin_rows.json")["rows"]
        baseline, _ = _vadimkin_rows_to_observations(rows)
        duplicated, _ = _vadimkin_rows_to_observations(rows + [dict(rows[-1])])
        self.assertEqual(
            {x["source_record_key"] for x in baseline},
            {x["source_record_key"] for x in duplicated},
        )

    def test_lviv_stage_c_sources_are_exactly_profile_sources(self):
        keys = {x["source_key"] for x in self.result["observations"]}
        self.assertEqual(
            {"vadimkin_official_data_uk", "ukrainealarm_region_history"}, keys
        )
        self.assertEqual(ASSEMBLY_PROFILE, "lviv-historical-v1")

    def test_bootstrap_preserves_static_match_only_as_checkpoint_metadata(self):
        b = bootstrap_summary(self.result["checkpoint_state"])
        self.assertEqual(
            {"assembly_profile": "lviv-historical-v1"},
            b["ingestion_run"]["parameters"],
        )
        c = b["checkpoint_candidate"]
        self.assertEqual(1, c["checkpoint_seq"])
        self.assertEqual("bootstrap", c["checkpoint_kind"])
        self.assertIsNone(c["previous_checkpoint"])
        self.assertTrue(c["continuity_verified"])
        self.assertEqual(
            "static_alertsinua_event_matches_api", c["continuity_method"]
        )
        self.assertEqual(20, c["observed_record_count"])
        self.assertIn("initial_static_match", c["metadata"])
        self.assertFalse(
            c["metadata"]["observed_latest_end_is_coverage_watermark"]
        )
        self.assertFalse(b["alerts_in_ua_static_episode_observation_created"])


class RecoveryDuplicateTests(unittest.TestCase):
    def test_real_recovery_pair_stage_b(self):
        r = build_recovery(FIXTURES)
        self.assertTrue(r["stage_b"]["matched"])
        self.assertEqual("canonical_input", r["stage_b"]["api_role"])
        self.assertEqual("duplicate_alias", r["stage_b"]["manual_role"])
        self.assertEqual("manual_minus_api", r["stage_b"]["sign_convention"])
        self.assertAlmostEqual(
            -268.574, r["stage_b"]["start_delta_ms_exact"], places=3
        )
        self.assertAlmostEqual(
            -446.657, r["stage_b"]["end_delta_ms_exact"], places=3
        )
        self.assertEqual(-269, r["stage_b"]["start_delta_ms"])
        self.assertEqual(-447, r["stage_b"]["end_delta_ms"])
        self.assertEqual(2, r["retained_observations"])
        self.assertEqual(1, r["effective_bridge_intervals"])
        self.assertTrue(r["recovery_provenance_preserved"])
        self.assertEqual("NO", r["static_manual_same_key_collision"])

    def test_manual_identity_is_acquisition_path_independent(self):
        f = load_json(FIXTURES / "recovery_api_duplicate.json")
        manual = f["manual_recovery_observation"]
        key = alerts_in_ua_source_record_key(manual)[1]
        modified = dict(
            manual,
            source_files=["different.csv"],
            recovery_artifact="different.json",
            source_kind="other_path",
        )
        self.assertEqual(key, alerts_in_ua_source_record_key(modified)[1])


if __name__ == "__main__":
    unittest.main()
