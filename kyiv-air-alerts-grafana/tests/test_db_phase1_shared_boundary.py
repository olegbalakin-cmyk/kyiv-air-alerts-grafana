from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import apply_ukrainealarm_bridge as bridge  # noqa: E402
import db_phase1_lviv_canonical as canonical  # noqa: E402
import db_phase1_lviv_proof as proof  # noqa: E402
import expand_multicity_production as production  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "db_phase1"


class SharedCanonicalBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vad_rows = json.loads(
            (FIXTURES / "lviv" / "vadimkin_rows.json").read_text(encoding="utf-8")
        )["rows"]
        cls.ua_fixture = json.loads(
            (FIXTURES / "lviv" / "ukrainealarm_bridge.json").read_text(encoding="utf-8")
        )
        cls.vad_obs, _ = canonical.vadimkin_rows_to_observations(cls.vad_rows)
        cls.ua_obs = canonical.ukrainealarm_rows_to_observations(
            cls.ua_fixture["events"]
        )

    def test_vadimkin_raw_rows_become_accepted_source_observations(self):
        self.assertEqual(120, len(self.vad_obs))
        self.assertTrue(
            all(x["source_key"] == "vadimkin_official_data_uk" for x in self.vad_obs)
        )
        self.assertEqual(120, len({x["source_record_key"] for x in self.vad_obs}))

    def test_ukrainealarm_rows_become_accepted_source_observations(self):
        self.assertEqual(20, len(self.ua_obs))
        self.assertTrue(
            all(x["source_key"] == "ukrainealarm_region_history" for x in self.ua_obs)
        )
        self.assertEqual(20, len({x["source_record_key"] for x in self.ua_obs}))

    def test_shared_boundary_matches_accepted_counts_and_regression_ids(self):
        result = canonical.canonicalize_lviv(
            self.vad_obs,
            self.ua_obs,
            checkpoint_state=self.ua_fixture["checkpoint_state"],
        )
        self.assertEqual(126, len(result["episodes"]))
        self.assertEqual(140, len(result["source_observations"]))
        ids = {x["legacy_episode_id"] for x in result["episodes"]}
        self.assertIn("b3df9090f7264ddbd726e113", ids)
        self.assertNotIn("7dd411c2a2587efc740a1a66", ids)
        self.assertEqual([], result["boundary_errors"])
        self.assertEqual("alert-canonicalization-v1", result["canonicalization_version"])
        self.assertEqual("lviv-historical-v1", result["assembly_profile"])

    def test_build_lviv_delegates_to_shared_boundary(self):
        with patch.object(
            proof.lviv_canonical,
            "canonicalize_lviv",
            wraps=proof.lviv_canonical.canonicalize_lviv,
        ) as delegated:
            result = proof.build_lviv(FIXTURES)
        self.assertEqual(126, result["canonical_episode_count"])
        self.assertEqual(1, delegated.call_count)

    def test_input_order_and_duplicate_observations_are_deterministic(self):
        baseline = canonical.canonicalize_lviv(self.vad_obs, self.ua_obs)
        reversed_result = canonical.canonicalize_lviv(
            list(reversed(self.vad_obs)), list(reversed(self.ua_obs))
        )
        duplicate_result = canonical.canonicalize_lviv(
            self.vad_obs + self.vad_obs,
            self.ua_obs + self.ua_obs,
        )
        self.assertEqual(baseline["serial"], reversed_result["serial"])
        self.assertEqual(
            baseline["source_record_keys"], reversed_result["source_record_keys"]
        )
        self.assertEqual(baseline["serial"], duplicate_result["serial"])
        self.assertEqual(
            baseline["source_record_keys"], duplicate_result["source_record_keys"]
        )
        self.assertEqual(140, len(duplicate_result["source_observations"]))

    def test_alertsinua_is_not_a_phase1_source_observation(self):
        result = canonical.canonicalize_lviv(self.vad_obs, self.ua_obs)
        self.assertNotIn(
            "alerts_in_ua",
            {x["source_key"] for x in result["source_observations"]},
        )

    def test_production_vadimkin_path_exposes_observations_before_merge(self):
        old_config = production.PROXY_CONFIG
        old_keys = production.PROXY_KEYS
        old_labels = production.CITY_LABELS
        try:
            production.PROXY_CONFIG = {"lviv": old_config["lviv"]}
            production.PROXY_KEYS = ["lviv"]
            production.CITY_LABELS = {"lviv": "Львів"}
            alerts, observations = production.proxy_alerts_and_lviv_observations_from_rows(
                self.vad_rows
            )
        finally:
            production.PROXY_CONFIG = old_config
            production.PROXY_KEYS = old_keys
            production.CITY_LABELS = old_labels
        self.assertTrue(alerts["lviv"])
        self.assertEqual(120, len(observations))
        self.assertEqual(
            {x["source_record_key"] for x in self.vad_obs},
            {x["source_record_key"] for x in observations},
        )

    def test_production_ukrainealarm_path_exposes_observations_before_union(self):
        history = [
            {
                "start": bridge.parse_dt(row["start"]),
                "end": bridge.parse_dt(row["end"]),
            }
            for row in self.ua_fixture["events"]
            if row["city_key"] == "lviv"
        ]
        observations = bridge.lviv_phase1_observations_from_history(
            history,
            region_id="90",
            api_region_name="Львівський район",
        )
        self.assertEqual(
            {x["source_record_key"] for x in self.ua_obs},
            {x["source_record_key"] for x in observations},
        )


if __name__ == "__main__":
    unittest.main()
