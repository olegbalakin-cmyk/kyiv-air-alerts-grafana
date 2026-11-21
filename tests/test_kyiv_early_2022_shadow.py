#!/usr/bin/env python3
"""Synthetic OFF-by-default Kyiv candidate-contract tests."""
import csv
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/kyiv_early_2022_shadow.py"
spec = importlib.util.spec_from_file_location("early_kyiv_shadow", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
FIELDS = ["Оголошено о", "Закінчено о", "Район/Громада/Місто", "Регіон", "Країна", "Тип", "Повідомлення"]


def write_day(root, n):
    p = root / f"alerts_2022-02-{n:02d}.csv"
    with p.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerow({"Оголошено о": f"{n:02d}.02.2022, 12:10:00",
                    "Закінчено о": f"{n:02d}.02.2022, 12:40:00",
                    "Регіон": "м. Київ", "Країна": "Україна", "Тип": "Повітряна тривога"})
        w.writerow({"Оголошено о": f"{n:02d}.02.2022, 12:12:00",
                    "Закінчено о": f"{n:02d}.02.2022, 12:42:00",
                    "Регіон": "Київська область", "Країна": "Україна", "Тип": "Повітряна тривога"})
    return p


class TestEarlyKyiv(unittest.TestCase):
    def test_no_fabricated_ends(self):
        with tempfile.TemporaryDirectory() as d:
            files = [write_day(Path(d), n) for n in (24,25,26,27)]
            output = mod.build_report(files)
            self.assertEqual(output["summary"]["unique_kyiv_starts"], 4)
            self.assertFalse(output["publish_allowed"])
            self.assertFalse(output["neon_write_allowed"])
            self.assertFalse(output["input_existing_checked"])
            self.assertEqual(output["canonical_intervals"], [])
            self.assertTrue(all(x["end"] is None and x["duration_seconds"] is None for x in output["candidates"]))
            self.assertTrue(all(x["hours_under_alert"] is None for x in output["daily_preview"]))

    def test_duplicate_check_is_read_only(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            files = [write_day(root, n) for n in (24,25,26,27)]
            canonical = root / "existing.json"
            canonical.write_text(json.dumps([{
                "start":"2022-02-25T12:12:00+02:00",
                "end":"2022-02-25T13:00:00+02:00"}]))
            result = mod.build_report(files, canonical)
            self.assertTrue(result["input_existing_checked"])
            self.assertEqual(result["summary"]["possible_duplicates"], 1)
            self.assertEqual(result["summary"]["unique_kyiv_starts"], 4)

    def test_incomplete_days_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            files = [write_day(Path(d), n) for n in (24,25,26,27)]
            with self.assertRaises(ValueError):
                mod.build_report(files[:3])

    def test_bad_end_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            files = [write_day(Path(d), n) for n in (24,25,26,27)]
            p=files[0]
            p.write_text(p.read_text(encoding="utf-8-sig").replace("12:40:00","12:09:00"),encoding="utf-8")
            with self.assertRaises(ValueError):
                mod.build_report(files)


if __name__ == "__main__":
    unittest.main()
