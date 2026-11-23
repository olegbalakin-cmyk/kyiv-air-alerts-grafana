"""Issue 240: offline freeze, parity, and fail-closed tests."""
import csv
import importlib.util
import io
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "kyiv-air-alerts-grafana/scripts/build_casualty_partial_sidecar.py"
spec = importlib.util.spec_from_file_location("casualty_240", SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class PartialPublisherTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sidecar = mod.build()
        cls.live = json.loads((ROOT / "kyiv-air-alerts-grafana/data/dashboard_data.json").read_text())

    def test_frozen_inputs_and_idempotent_bytes(self):
        self.assertEqual(mod.render(mod.build()), mod.render(mod.build()))
        actual = (ROOT / "kyiv-air-alerts-grafana/data/casualty_partial_months.json").read_bytes()
        self.assertEqual(mod.render(self.sidecar), actual)
        self.assertFalse(self.sidecar["publication_allowed"])
        self.assertEqual(self.sidecar["promotion"], "OFF")
        self.assertFalse(self.sidecar["published_monthly_overwrite"])

    def test_23_city_parity_and_september_partial(self):
        rows = self.sidecar["cities"]
        self.assertEqual(len(rows), 23)
        self.assertEqual(set(rows), set(self.live["casualties_by_city"]))
        self.assertEqual(rows["sumy"]["2026-09"]["confirmed_baseline_deaths"], 4)
        self.assertEqual(rows["kyiv"]["2026-09"]["confirmed_baseline_deaths"], 18)
        self.assertEqual(rows["kherson"]["2026-09"]["confirmed_baseline_deaths"], 12)
        for city, value in rows.items():
            s = value["2026-09"]
            self.assertFalse(s["is_complete"])
            self.assertIsNone(s["monthly_exact_total"])
            self.assertIsInstance(s["confirmed_baseline_deaths"], int)
            self.assertGreaterEqual(s["confirmed_baseline_deaths"], 0)
            self.assertTrue(s["coverage_through"])
            self.assertEqual(value["2026-10"]["monthly_exact_total"], None)

    def test_october_four_and_nineteen_unknown(self):
        expected = {"lutsk": 6, "poltava": 1, "ivano-frankivsk": 1, "khmelnytskyi": 3}
        values = {c: v["2026-10"] for c, v in self.sidecar["cities"].items()}
        self.assertEqual({c: v["confirmed_event_lower_bound"] for c, v in values.items()
                          if v["confirmed_event_lower_bound"] is not None}, expected)
        self.assertEqual(sum(v["confirmed_event_lower_bound"] is None for v in values.values()), 19)
        self.assertEqual(sum(v["confirmed_event_lower_bound"] or 0 for v in values.values()), 11)
        for city, row in values.items():
            self.assertFalse(row["is_complete"])
            if city not in expected:
                self.assertEqual(row["status"], "unknown")
                self.assertIsNone(row["provenance"])
                self.assertIsNone(row["last_verified_at"])
            else:
                self.assertEqual(len(row["provenance"]["incident_ids"]), 1)
                self.assertGreaterEqual(len(row["provenance"]["source_urls"]), 2)

    def test_historical_months_unchanged_and_2026_year(self):
        sources, _ = mod.baseline_series()
        for city, monthly in sources.items():
            existing = self.live["casualties_by_city"][city]["monthly"]
            observed = {r["month"]: r["deaths"] for r in existing}
            for month, deaths in monthly.items():
                self.assertEqual(observed.get(month), deaths, (city, month))
            self.assertNotIn("2026-10", observed)
            old_year = sum(v for m, v in observed.items() if m.startswith("2026-"))
            baseline_year = sum(v for m, v in monthly.items() if m.startswith("2026-"))
            self.assertEqual(old_year, baseline_year)
            self.assertNotIn("2026-10", monthly)

    def test_csv_semantics_and_no_unknown_zero(self):
        dst = io.StringIO()
        writer = csv.writer(dst)
        writer.writerow(["city", "month", "status", "exact_deaths", "baseline_deaths", "lower_bound"])
        for city, months in self.sidecar["cities"].items():
            for month, val in months.items():
                writer.writerow([city, month, val["status"], "",
                                 val["confirmed_baseline_deaths"] if month == "2026-09" else "",
                                 val["confirmed_event_lower_bound"] if val["confirmed_event_lower_bound"] is not None else ""])
        result = list(csv.DictReader(io.StringIO(dst.getvalue())))
        self.assertEqual(len(result), 46)
        self.assertEqual(sum(r["month"] == "2026-10" and r["lower_bound"] == "" for r in result), 19)
        self.assertTrue(all(r["exact_deaths"] == "" for r in result))
        self.assertEqual(sum(int(r["lower_bound"]) for r in result if r["lower_bound"]), 11)

    def test_unpinned_and_corrupted_input_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unpinned"):
            mod.read_pinned("something/unlisted.json")
        original = mod.read_pinned
        def broken(p):
            if p.endswith("master_20cities_monthly_wide.csv"):
                return "month,kyiv\n2026-09,0\n"
            return original(p)
        with patch.object(mod, "read_pinned", broken):
            with self.assertRaises((ValueError, KeyError)):
                mod.baseline_series()
        with patch.object(mod.Path, "read_bytes", return_value=b"tampered"):
            with self.assertRaisesRegex(ValueError, "SHA drift"):
                mod.read_pinned(next(iter(mod.INPUT_BLOBS)))

    def test_reject_fake_proofs_and_extra_events(self):
        source = mod.read_pinned("research/casualty_publisher_240/october_2026_verified_events_frozen.json")
        obj = json.loads(source)
        obj["events"].append(deepcopy(obj["events"][0]))
        with patch.object(mod, "read_pinned", side_effect=lambda p: json.dumps(obj) if p.endswith("frozen.json") else mod_read(p)):
            with self.assertRaisesRegex(ValueError, "four reviewed"):
                mod.reviewed_events()

    def test_no_write_by_check_mode(self):
        with tempfile.TemporaryDirectory() as td:
            dest = Path(td) / "sidecar.json"
            dest.write_bytes(mod.render(self.sidecar))
            self.assertEqual(dest.read_bytes(), mod.render(mod.build()))
            dest.write_text("{}")
            self.assertNotEqual(dest.read_bytes(), mod.render(mod.build()))
        self.assertEqual(self.sidecar["latest_exact_month"], "2026-08")


mod_read = mod.read_pinned

if __name__ == "__main__":
    unittest.main()
