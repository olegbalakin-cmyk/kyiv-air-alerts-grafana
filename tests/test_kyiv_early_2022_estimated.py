#!/usr/bin/env python3
"""No network or production dependencies: tests for approximate early Kyoto alert endings."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import kyiv_early_2022_shadow as v1
import kyiv_early_2022_estimated as v2
HEADERS = ["Оголошено о", "Закінчено о", "Район/Громада/Місто",
           "Регіон", "Країна", "Тип", "Повідомлення"]


def make_export(root, day):
    file = root / f"alerts_2022-02-{day:02d}.csv"
    with file.open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerow({"Оголошено о":f"{day:02d}.02.2022, 12:10:00",
                         "Закінчено о":f"{day:02d}.02.2022, 12:40:00",
                         "Регіон":"м. Київ", "Країна":"Україна", "Тип":"Повітряна тривога"})
        writer.writerow({"Оголошено о":f"{day:02d}.02.2022, 12:12:00",
                         "Закінчено о":f"{day:02d}.02.2022, 12:42:00",
                         "Регіон":"Київська область", "Країна":"Україна",
                         "Тип":"Повітряна тривога"})
    return file


class EstimatedEarlyKyivTests(unittest.TestCase):
    def sample(self):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        return v1.build_report([make_export(Path(d.name), day) for day in (24, 25, 26, 27)])

    def test_estimates_preserve_both_times_without_canonical_end(self):
        data = v2.add_estimates(self.sample())
        self.assertEqual(data["summary"]["unique_kyiv_starts"], 4)
        self.assertEqual(data["summary"]["exported_end_count"], 4)
        self.assertEqual(data["summary"]["exported_ends_exactly_30min_count"], 4)
        self.assertEqual(data["canonical_intervals"], [])
        self.assertFalse(data["publish_allowed"])
        self.assertFalse(data["neon_write_allowed"])
        for row in data["candidates"]:
            self.assertEqual(row["estimated_duration_seconds"], 1800)
            self.assertIsNone(row["end"])
            self.assertIsNone(row["duration_seconds"])
            self.assertEqual(row["end_confidence"], "UNVERIFIED")

    def test_daily_estimates_separate_from_verified_hours(self):
        data = v2.add_estimates(self.sample())
        for row in data["daily_preview"]:
            self.assertEqual(row["estimated_occupied_minutes"], 30)
            self.assertIsNone(row["hours_under_alert"])
            self.assertIsNone(row["average_alert_duration"])

    def test_midnight_carryover_not_counted_in_verified_feb28(self):
        src = self.sample()
        final = src["candidates"][-1]
        final["start"] = "2022-02-27T23:53:36+02:00"
        final["raw_exported_end_not_for_statistics"] = "2022-02-28T00:23:36+02:00"
        data = v2.add_estimates(src)
        self.assertEqual(data["summary"]["estimated_carryover_minutes_2022_02_28"], 23.6)
        self.assertFalse(data["estimated_carryover_not_official"][0]["canonical_daily_kpi_included"])

    def test_refuse_canonical_end_or_promotion(self):
        original = self.sample()
        original["candidates"][0]["end"] = "2022-02-24T12:40:00+02:00"
        with self.assertRaises(ValueError):
            v2.add_estimates(original)
        original = self.sample()
        original["publish_allowed"] = True
        with self.assertRaises(ValueError):
            v2.add_estimates(original)

    def test_refuse_out_of_window_export(self):
        original = self.sample()
        original["candidates"][0]["raw_exported_end_not_for_statistics"] = "2022-03-10T12:40:00+02:00"
        with self.assertRaises(ValueError):
            v2.add_estimates(original)

    def test_repeatable_result(self):
        original = self.sample()
        self.assertEqual(json.dumps(v2.add_estimates(original), sort_keys=True),
                         json.dumps(v2.add_estimates(original), sort_keys=True))


if __name__ == "__main__":
    unittest.main()
