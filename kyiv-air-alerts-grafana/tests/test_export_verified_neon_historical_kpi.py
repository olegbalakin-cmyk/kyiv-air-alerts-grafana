"""Offline fail-closed contract for reusing an exact Neon-generated KPI index."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from export_verified_neon_historical_kpi import IndexRejected, export, verified_index


def fixture():
    keys = [f"city_{i}" for i in range(23)]
    gen = "2026-11-15T13:30:12+02:00"
    row = dict(status="verified", counts=[1], checked_complete_months=1,
               checked_recent_days=1)
    return {
        "meta": {"generated_at": gen},
        "multicity_meta": {"production_city_keys": keys},
        "cities": {k: {"monthly": []} for k in keys},
        "historical_daily_kpi": {
            "schema": "verified-historical-daily-start-counts-v1",
            "meta": dict(expected_cities=23, verified_count=23,
                         verified_cities=keys, timezone="Europe/Kyiv",
                         source_ref="neon:br-bold-mode-b5rub8pq",
                         generated_at=gen, source_dashboard_generated_at=gen),
            "cities": {k: copy.deepcopy(row) for k in keys},
        },
    }


class NeonIndexExport(unittest.TestCase):
    def test_exact_verified_source(self):
        data = fixture()
        self.assertEqual(verified_index(data), data["historical_daily_kpi"])

    def test_source_and_generation_locked(self):
        for field, value in [
            ("verified_count", 19),
            ("source_ref", "site-prod"),
            ("generated_at", "2026-11-14T01:00:00+02:00"),
        ]:
            with self.subTest(field=field):
                data = fixture()
                data["historical_daily_kpi"]["meta"][field] = value
                with self.assertRaises(IndexRejected):
                    verified_index(data)

    def test_no_silent_city_fallback(self):
        for variant in ("missing", "wrong_status", "wrong_value"):
            data = fixture()
            key = "city_3"
            if variant == "missing":
                del data["historical_daily_kpi"]["cities"][key]
            elif variant == "wrong_status":
                data["historical_daily_kpi"]["cities"][key]["status"] = "unverified"
            else:
                data["historical_daily_kpi"]["cities"][key]["counts"] = [-1]
            with self.subTest(variant=variant), self.assertRaises(IndexRejected):
                verified_index(data)

    def test_export_no_overwrite(self):
        data = fixture()
        with tempfile.TemporaryDirectory() as td:
            src, dst = Path(td)/"dashboard.json", Path(td)/"kpi.json"
            src.write_text(json.dumps(data), encoding="utf-8")
            export(src, dst)
            self.assertEqual(json.loads(dst.read_text()),
                             data["historical_daily_kpi"])
            with self.assertRaises(IndexRejected):
                export(src, dst)


if __name__ == "__main__":
    unittest.main()
