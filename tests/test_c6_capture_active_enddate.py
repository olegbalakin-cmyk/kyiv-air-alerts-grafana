"""Offline regression for UkraineAlarm's open AIR endDate sentinel.

No source HTTP, Neon access, or publication. Import the exact history
capture verifier used by the research readback adapter.
"""
import base64
import importlib.util
import json
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "kyiv-air-alerts-grafana" / "scripts" / "c2_history_capture.py"
SPEC = importlib.util.spec_from_file_location("c6_active_sentinel_capture", SCRIPT)
capture = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture)

class CaptureReplayActiveEndSentinelTests(unittest.TestCase):
    @staticmethod
    def receipt(alarms):
        raw = json.dumps({"alarms": alarms}).encode("utf-8")
        return {"source_key": "ukrainealarm_region_history", "pages": [
            {"body_base64": base64.b64encode(raw).decode("ascii")}]}

    @staticmethod
    def air(start, end):
        return {"alertType": "AIR", "startDate": start, "endDate": end}

    def test_ongoing_air_sentinel_ignored_but_closed_air_retained(self):
        row = self.receipt([
            self.air("2026-11-11T09:00:00Z", "2026-11-11T10:00:00Z"),
            self.air("2026-11-11T11:00:00Z", "0001-01-01T00:00:00"),
        ])
        self.assertEqual(capture.replay(row), [{
            "start": "2026-11-11T09:00:00+00:00",
            "end": "2026-11-11T10:00:00+00:00",
        }])

    def test_only_active_sentinel_returns_no_completed_alert(self):
        row = self.receipt([self.air(
            "2026-11-11T11:00:00Z", "0001-01-01T00:00:00")])
        self.assertEqual(capture.replay(row), [])

    def test_other_naive_end_must_still_fail_closed(self):
        row = self.receipt([self.air(
            "2026-11-11T09:00:00Z", "2026-11-11T10:00:00")])
        with self.assertRaisesRegex(ValueError, "CAPTURE_NAIVE_TIMESTAMP"):
            capture.replay(row)

    def test_duplicate_closed_air_still_deduplicates(self):
        a = self.air("2026-11-11T09:00:00Z", "2026-11-11T10:00:00Z")
        row = self.receipt([a, a, self.air(
            "2026-11-11T11:00:00Z", "0001-01-01T00:00:00")])
        self.assertEqual(len(capture.replay(row)), 1)

if __name__ == "__main__":
    unittest.main()
