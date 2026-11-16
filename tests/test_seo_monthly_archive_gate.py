"""Monthly SEO preflight should never authorize production publishing."""
import copy
from datetime import date
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "kyiv-air-alerts-grafana/scripts/seo_monthly_archive_gate.py"
SOURCE = ROOT / "historical-daily-kpi.json"

spec = importlib.util.spec_from_file_location("seo_monthly_gate", SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class MonthlySeoReadinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = SOURCE.read_bytes()
        cls.source = json.loads(cls.raw)
        cls.current = cls.source["cities"]
        cls.baseline = {
            "schema": gate.MANIFEST_SCHEMA,
            "cities": 23,
            "per_city_months": {slug: len(row["verified_metric_months"]) for slug, row in cls.current.items()},
            "source_git_blob": gate.git_blob_sha(cls.raw),
        }

    def check_block(self, proof, expected):
        self.assertEqual(proof["decision"], "BLOCKED")
        self.assertEqual(proof["reason"], expected)
        self.assertFalse(proof["production_deploy_allowed"])
        self.assertFalse(proof["git_publish_allowed"])
        self.assertFalse(proof["neon_access_allowed"])

    def test_bounded_calendar_logic(self):
        self.assertEqual(gate.month_before(date(2026, 12, 3)), "2026-11")
        self.assertEqual(gate.month_before(date(2027, 1, 3)), "2026-12")
        self.assertEqual(gate.month_before(date(2026, 11, 1)), "2026-10")

    def test_current_stale_month_blocks_in_december(self):
        proof = gate.evaluate(self.raw, self.baseline, as_of=date(2026, 12, 3))
        self.check_block(proof, "SOURCE_BEFORE_MONTH_END")

    def test_unverified_new_month_blocks_on_newer_timestamp(self):
        changed = copy.deepcopy(self.source)
        changed["meta"]["generated_at"] = "2026-12-03T08:00:00+02:00"
        raw = json.dumps(changed).encode()
        proof = gate.evaluate(raw, self.baseline, as_of=date(2026, 12, 3))
        self.check_block(proof, "PREVIOUS_MONTH_NOT_VERIFIED_FOR_23")
        self.assertEqual(proof["expected_completed_month"], "2026-11")
        self.assertEqual(len(proof["missing_month_cities"]), 23)

    def test_current_archive_without_published_baseline_blocks(self):
        proof = gate.evaluate(self.raw, None, as_of=date(2026, 11, 16))
        self.check_block(proof, "NO_VERIFIED_PUBLISHED_BASELINE")

    def test_unchanged_published_archive_is_noop(self):
        proof = gate.evaluate(self.raw, self.baseline, as_of=date(2026, 11, 16))
        self.assertEqual(proof["decision"], "NO_CHANGE")
        self.assertEqual(proof["reason"], "ALREADY_PUBLISHED")
        self.assertFalse(proof["production_deploy_allowed"])

    def test_ready_preview_only_when_all_23_advance(self):
        old = copy.deepcopy(self.baseline)
        old["per_city_months"] = {slug: value-1 for slug,value in old["per_city_months"].items()}
        old["source_git_blob"] = "a"*40
        proof = gate.evaluate(self.raw, old, as_of=date(2026, 11, 16))
        self.assertEqual(proof["decision"], "READY_FOR_DRAFT")
        self.assertEqual(len(proof["updated_cities"]), 23)
        self.assertFalse(proof["production_deploy_allowed"])
        self.assertFalse(proof["git_publish_allowed"])

    def test_partial_advance_blocks(self):
        old = copy.deepcopy(self.baseline)
        old["per_city_months"]["kyiv"] -= 1
        old["source_git_blob"] = "a"*40
        proof = gate.evaluate(self.raw, old, as_of=date(2026, 11, 16))
        self.check_block(proof, "PARTIAL_CITY_MONTH_ADVANCEMENT")

    def test_revision_without_new_month_blocks(self):
        old = copy.deepcopy(self.baseline)
        old["source_git_blob"] = "a"*40
        proof = gate.evaluate(self.raw, old, as_of=date(2026, 11, 16))
        self.check_block(proof, "HISTORICAL_REVISION_REQUIRES_REVIEW")

    def test_regression_blocks(self):
        old = copy.deepcopy(self.baseline)
        old["per_city_months"]["kyiv"] += 1
        proof = gate.evaluate(self.raw, old, as_of=date(2026, 11, 16))
        self.check_block(proof, "PUBLISHED_COVERAGE_REGRESSION")

    def test_bad_datetime_and_checksum_block(self):
        changed = copy.deepcopy(self.source)
        changed["meta"]["generated_at"] = "2026-11-13T10:08:11"
        proof = gate.evaluate(json.dumps(changed).encode(), self.baseline, as_of=date(2026, 11, 16))
        self.check_block(proof, "SOURCE_TIMEZONE_MISSING")
        changed = copy.deepcopy(self.source)
        changed["cities"]["kyiv"]["monthly_total_alert_duration_seconds"]["2026-10"]["seconds"] += 60
        proof = gate.evaluate(json.dumps(changed).encode(), self.baseline, as_of=date(2026, 11, 16))
        self.check_block(proof, "UNVERIFIED_SOURCE")

    def test_future_and_wrong_baseline_block(self):
        future = gate.evaluate(self.raw,self.baseline,as_of=date(2026, 11, 5))
        self.check_block(future, "SOURCE_FROM_FUTURE")
        invalid = {**self.baseline,"per_city_months":{}}
        proof = gate.evaluate(self.raw,invalid,as_of=date(2026,11,16))
        self.check_block(proof, "INVALID_PUBLISHED_BASELINE")


if __name__ == "__main__":
    unittest.main()
