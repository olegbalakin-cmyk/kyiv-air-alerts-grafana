"""Fail-closed checks for all verified months in static bilingual archive."""
import hashlib
import importlib.util
import json
import math
import re
import unittest
from collections import defaultdict
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "kyiv-air-alerts-grafana/scripts/build_historical_static_archive.py"
SOURCE = ROOT / "historical-daily-kpi.json"
SAMPLE = ["kyiv", "kharkiv", "lviv", "sevastopol", "chernivtsi"]


def load_builder():
    spec = importlib.util.spec_from_file_location("static_history_generator", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StaticFullHistoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_builder()
        cls.source = json.loads(SOURCE.read_bytes())
        cls.series = cls.mod.verified_series(cls.source)
        cls.expected = sum(len(v["months"]) for v in cls.series.values())

    def test_source_full_history(self):
        self.assertEqual(len(self.series), 23)
        self.assertEqual(self.expected, 392)
        self.assertEqual(self.expected, self.source["meta"]["verified_full_metric_months"])
        self.assertEqual(self.series["kyiv"]["months"][0]["ym"], "2022-03")
        self.assertEqual(self.series["lviv"]["type"], "raion_proxy")
        self.assertEqual(self.series["kharkiv"]["type"], "exact_city")
        self.assertEqual(self.series["sevastopol"]["type"], "exact_city")
        for slug, city in self.series.items():
            with self.subTest(slug=slug):
                self.assertTrue(city["months"])
                for month in city["months"]:
                    self.assertEqual(len(month["days"]), len(self.mod.month_dates(month["ym"])))
                    self.assertEqual(month["count"], sum(d["count"] for d in month["days"]))
                    self.assertTrue(math.isfinite(month["seconds"]))

    def test_all_generated_pages_and_sitemap(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            result = self.mod.generate(SOURCE, output)
            self.assertEqual(result["cities"], 23)
            self.assertEqual(result["verified_full_months"], 392)
            self.assertEqual(result["month_pages_both_languages"], 784)
            self.assertEqual(result["source_git_blob"], hashlib.sha1(
                b"blob " + str(len(SOURCE.read_bytes())).encode() + b"\x00" + SOURCE.read_bytes()
            ).hexdigest())
            self.assertEqual(result["sitemap_url_count"],
                             4 + 46 + result["year_pages_both_languages"] + 784)
            urls = ET.parse(output / "sitemap.xml")
            namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
            links = [node.text for node in urls.findall(f".//{namespace}loc")]
            self.assertEqual(len(links), result["sitemap_url_count"])
            self.assertEqual(len(set(links)), len(links))
            self.assertIn("Sitemap: https://ukraine-air-alerts.netlify.app/sitemap.xml",
                          (output / "robots.txt").read_text())
            self.assertEqual(result["per_city_months"]["kyiv"], 56)
            for link in links:
                relative = link.removeprefix(self.mod.SITE)
                # / and /en/ are produced by the existing bilingual dashboard builder,
                # not by this archive generator, and are checked in the full build.
                if relative in ("/", "/en/"):
                    continue
                html_path = output / relative.lstrip("/") / "index.html"
                self.assertTrue(html_path.is_file(), relative)
                html = html_path.read_text(encoding="utf-8")
                self.assertIn(f'<link rel="canonical" href="{link}">', html)
                self.assertEqual(html.count('hreflang="uk"'), 1)
                self.assertEqual(html.count('hreflang="en"'), 1)
                self.assertIn('<html lang="en">' if relative.startswith("/en/") else '<html lang="uk">', html)
            for lang_prefix in ("", "en/"):
                index = (output / lang_prefix / "stats/index.html").read_text(encoding="utf-8")
                self.assertEqual(index.count('<tr><th scope="row">'), 23)
                for slug in SAMPLE:
                    item = self.series[slug]
                    city_html = (output / lang_prefix / f"stats/{slug}/index.html").read_text()
                    self.assertIn('application/ld+json', city_html)
                    if slug == "lviv":
                        self.assertIn("Raion" if lang_prefix else "район", city_html)
                    for ym in (item["months"][0]["ym"], item["months"][-1]["ym"]):
                        page = (output / lang_prefix / f"stats/{slug}/{ym}/index.html").read_text()
                        self.assertIn('data-month-count=', page)
                        self.assertIn('data-month-seconds=', page)
                        self.assertIn('application/ld+json', page)
                        self.assertEqual(page.count('<tr><th scope="row"><time datetime='), len(self.mod.month_dates(ym)))
                kyiv_partial = (output / lang_prefix / "stats/kyiv/2022/index.html").read_text()
                self.assertIn("Partial year" if lang_prefix else "Частковий рік", kyiv_partial)
                kyiv_complete = (output / lang_prefix / "stats/kyiv/2025/index.html").read_text()
                self.assertIn("All 12 months" if lang_prefix else "Усі 12 місяців", kyiv_complete)

    def test_mutated_month_fails_closed(self):
        import copy
        corrupted = copy.deepcopy(self.source)
        first = corrupted["cities"]["kyiv"]["verified_metric_months"][0]
        corrupted["cities"]["kyiv"]["monthly_total_alert_duration_seconds"][first]["seconds"] += 60
        with self.assertRaisesRegex(ValueError, "Monthly KPI parity failure"):
            self.mod.verified_series(corrupted)

    def test_build_wiring(self):
        import tomllib
        html = (ROOT / "kyiv-air-alerts-grafana/pages-preview/index.html").read_text()
        self.assertIn('<a id="staticStatsFooterLink" href="/stats/"', html)
        self.assertIn('</span>\n    <a id="staticStatsFooterLink"', html)
        gen = (ROOT / "kyiv-air-alerts-grafana/scripts/build_bilingual_html.py").read_text()
        self.assertIn('<a id="staticStatsFooterLink" href="/en/stats/"', gen)
        recipe = tomllib.loads((ROOT / "netlify.toml").read_text())
        self.assertIn("build_historical_static_archive.py", recipe["build"]["command"])
        self.assertNotIn("netlify deploy --prod", recipe["build"]["command"])


if __name__ == "__main__":
    unittest.main()
