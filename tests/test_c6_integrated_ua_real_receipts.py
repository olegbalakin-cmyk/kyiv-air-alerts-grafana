"""Real frozen C2 completed-interval replay for all 21 UkraineAlarm cities.

Uses only the archived payload and stdlib, never live source HTTP or Neon.
"""
import importlib.util
import json
import os
from pathlib import Path
import unittest
import zipfile

CAPTURE_FILE = Path(__file__).resolve().parents[1] / "kyiv-air-alerts-grafana" / "scripts" / "c2_history_capture.py"
spec = importlib.util.spec_from_file_location("integrated_c2_history_capture", CAPTURE_FILE)
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)

class RealCapturedUaReplay(unittest.TestCase):
    def test_completed_ua_receipts_replay_exactly_21_of_23(self):
        with zipfile.ZipFile(Path(os.environ["C6_REAL_C2_BUNDLE"])) as bundle:
            payload = json.loads(bundle.read("payload.json"))
        receipts = payload["historical_source_receipts"]
        self.assertEqual(len(receipts), 23)
        ua = {city: row for city, row in receipts.items()
              if row["source_key"] == "ukrainealarm_region_history"}
        self.assertEqual(len(ua), 21)
        for city, row in sorted(ua.items()):
            with self.subTest(city=city):
                self.assertEqual(capture.replay(row), row["completed_air"])
                self.assertEqual(capture.fingerprint(row["completed_air"]), row["completed_air_sha256"])

if __name__ == "__main__":
    unittest.main()
