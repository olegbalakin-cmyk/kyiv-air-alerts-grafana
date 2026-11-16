"""Read-only regression checks for the frozen October 2026 SEO pilot.

Run: python -m unittest tests/test_seo_static_pilot.py
No HTTP requests or production writes.
"""
import json
from datetime import date, timedelta
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ROOT / "kyiv-air-alerts-grafana/pages-preview"
MONTH = "2026-10"
CITIES = {"kyiv": "exact_city", "kharkiv": "exact_city", "lviv": "raion_proxy"}

class StaticSeoPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads((ROOT / "historical-daily-kpi.json").read_text(encoding="utf-8"))
        cls.proof = json.loads((ROOT / "research/seo_pilot_2026_11_16/verified_snapshot.json").read_text(encoding="utf-8"))

    def test_source_contract(self):
        self.assertEqual(self.source["schema"], "verified-historical-daily-start-counts-v1")
        self.assertEqual(self.source["meta"]["verified_count"], 23)
        self.assertEqual(self.source["meta"]["timezone"], "Europe/Kyiv")
        self.assertEqual(len(self.proof["cities"]), 3)
        self.assertEqual(self.proof["source_generated_at"], self.source["meta"]["generated_at"])

    def test_city_snapshots(self):
        for item in self.proof["cities"]:
            slug = item["slug"]
            with self.subTest(city=slug):
                self.assertEqual(item["scope"], CITIES[slug])
                series = self.source["cities"][slug]
                self.assertEqual(series["source_type"], CITIES[slug])
                self.assertEqual(series["status"], "verified")
                self.assertIn(MONTH, series["verified_metric_months"])
                start = date.fromisoformat(series["start"])
                end = date.fromisoformat(series["end"])
                first = date(2026, 10, 1)
                last = date(2026, 10, 31)
                self.assertLessEqual(start, first)
                self.assertGreaterEqual(end, last)
                expected_len = (end - start).days + 1
                for field in ("counts", "daily_total_alert_duration_seconds", "daily_started_alert_duration_seconds"):
                    self.assertEqual(len(series[field]), expected_len)
                index = (first - start).days
                counts = sum(series["counts"][index:index + 31])
                seconds = sum(series["daily_total_alert_duration_seconds"][index:index + 31])
                started = sum(series["daily_started_alert_duration_seconds"][index:index + 31])
                monthly = series["monthly_total_alert_duration_seconds"][MONTH]
                self.assertEqual(counts, monthly["alerts_started"])
                self.assertAlmostEqual(seconds, monthly["seconds"], delta=0.01)
                self.assertEqual(item["month_count"], counts)
                self.assertAlmostEqual(item["month_seconds"], seconds, delta=0.01)
                self.assertAlmostEqual(item["started_full_duration_seconds"], started, delta=0.01)
                self.assertEqual(item["days"], 31)
                for prefix, language in (("", "uk"), ("en/", "en")):
                    page = PAGES / prefix / "stats" / slug / MONTH / "index.html"
                    html = page.read_text(encoding="utf-8")
                    self.assertIn('<html lang="' + language + '">', html)
                    self.assertIn('rel="canonical"', html)
                    self.assertIn('hreflang="uk"', html)
                    self.assertIn('hreflang="en"', html)
                    self.assertIn('application/ld+json', html)
                    self.assertIn('data-month-count="' + str(counts) + '"', html)
                    match = re.search(r'data-month-seconds="([0-9.]+)"', html)
                    self.assertIsNotNone(match)
                    self.assertAlmostEqual(float(match.group(1)), seconds, delta=0.01)
                    self.assertEqual(html.count('<tr><th scope="row"><time datetime='), 31)
                    self.assertIn("Europe/Kyiv", html)
                    for day in range(31):
                        stamp = (first + timedelta(days=day)).isoformat()
                        self.assertIn('<time datetime="' + stamp + '">', html)
                    if slug == "lviv":
                        self.assertIn("Raion" if language == "en" else "район", html)

    def test_index_and_footer(self):
        for prefix, language in (("", "uk"), ("en/", "en")):
            html = (PAGES / prefix / "stats/index.html").read_text(encoding="utf-8")
            self.assertIn('<html lang="' + language + '">', html)
            self.assertIn('rel="canonical"', html)
            for slug in CITIES:
                self.assertIn('/stats/' + slug + '/' + MONTH + '/', html)
        dashboard = (PAGES / "index.html").read_text(encoding="utf-8")
        self.assertEqual(dashboard.count('id="staticStatsFooterLink"'), 1)
        self.assertIn('href="/stats/" id="staticStatsFooterLink"', dashboard)
        self.assertIn('class="footer-stats-link"', dashboard)
        self.assertRegex(dashboard, r'</span>\s*<a href="/stats/" id="staticStatsFooterLink"')
        bilingual = (ROOT / "kyiv-air-alerts-grafana/scripts/build_bilingual_html.py").read_text(encoding="utf-8")
        self.assertIn('href="/en/stats/" id="staticStatsFooterLink"', bilingual)
        netlify = (ROOT / "netlify.toml").read_text(encoding="utf-8")
        self.assertIn('cp -R kyiv-air-alerts-grafana/pages-preview/stats _site/stats', netlify)
        self.assertIn('cp -R kyiv-air-alerts-grafana/pages-preview/en/stats _site/en/stats', netlify)

if __name__ == "__main__":
    unittest.main()
