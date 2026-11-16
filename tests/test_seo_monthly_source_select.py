"""Select monthly archive sources without network or production writes."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import importlib.util
import json
import sys
import unittest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "kyiv-air-alerts-grafana/scripts"
sys.path.insert(0, str(SCRIPT_DIR))
spec = importlib.util.spec_from_file_location("seo_monthly_source_select", SCRIPT_DIR / "seo_monthly_source_select.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SeoMonthlySourceSelectionTests(unittest.TestCase):
    def setUp(self):
        self.early = "2026-11-13T10:00:00+02:00"
        self.late = "2026-12-03T10:00:00+02:00"
        self.old = {"schema": "verified-historical-daily-start-counts-v1", "meta": {"generated_at": self.early}, "value": 1}
        self.dashboard = {"meta": {"generated_at": self.late},
                          "historical_daily_kpi": {"meta": {
                              "generated_at": self.late, "source_dashboard_generated_at": self.late
                          }, "value": 2}}

    def test_select_newer_embedded_and_bind(self):
        selected, origin = module.choose(self.old, self.dashboard)
        self.assertEqual(origin, "embedded_dashboard_historical_daily_kpi")
        self.assertEqual(selected["value"], 2)

    def test_select_standalone_when_older_embedded(self):
        old_nested = {"meta": {"generated_at": self.early,
                                "source_dashboard_generated_at": self.late}, "value": 1}
        self.dashboard["historical_daily_kpi"] = old_nested
        selected, origin = module.choose(self.old, self.dashboard)
        self.assertEqual(origin, "standalone_historical_daily_kpi")
        self.assertEqual(selected["value"], 1)

    def test_missing_embedded_falls_back(self):
        selected, origin = module.choose(self.old, {"meta": {"generated_at": self.late}})
        self.assertEqual(origin, "standalone_historical_daily_kpi")

    def test_unbound_embedded_fails_closed(self):
        self.dashboard["historical_daily_kpi"]["meta"]["source_dashboard_generated_at"] = "2026-12-02T00:00:00+02:00"
        with self.assertRaisesRegex(ValueError, "not bound"):
            module.choose(self.old, self.dashboard)

    def test_same_timestamp_conflict_fails_closed(self):
        self.dashboard["meta"]["generated_at"] = self.early
        self.dashboard["historical_daily_kpi"] = {
            "meta": {"generated_at": self.early,
                     "source_dashboard_generated_at": self.early},
            "value": 2
        }
        with self.assertRaisesRegex(ValueError, "conflicting"):
            module.choose(self.old, self.dashboard)

    def test_embedded_cannot_be_from_future_relative_to_dashboard(self):
        self.dashboard["meta"]["generated_at"] = self.early
        self.dashboard["historical_daily_kpi"]["meta"]["source_dashboard_generated_at"] = self.early
        with self.assertRaisesRegex(ValueError, "newer"):
            module.choose(self.old, self.dashboard)


if __name__ == "__main__":
    unittest.main()
