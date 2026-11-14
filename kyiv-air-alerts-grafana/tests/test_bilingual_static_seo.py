#!/usr/bin/env python3
"""Offline contract checks: two independently crawlable languages; one frontend."""
import importlib.util
from pathlib import Path
import re
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "kyiv-air-alerts-grafana/pages-preview/index.html"
APP = ROOT / "kyiv-air-alerts-grafana/pages-preview/app.js"
MODULE = ROOT / "kyiv-air-alerts-grafana/scripts/build_bilingual_html.py"
spec = importlib.util.spec_from_file_location("build_bilingual_html", MODULE)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class BilingualStaticSEOTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = SOURCE.read_text(encoding="utf-8")
        cls.uk, cls.en = builder.build_pages(cls.template)
        cls.js = APP.read_text(encoding="utf-8")

    def test_two_distinct_languages_and_metadata_before_javascript(self):
        self.assertIn('<html lang="uk">', self.uk)
        self.assertIn('<html lang="en">', self.en)
        self.assertIn("<title>" + builder.ENGLISH["title"] + "</title>", self.en)
        self.assertIn('content="' + builder.ENGLISH["description"] + '"', self.en)
        self.assertIn('content="en_US"', self.en)
        self.assertIn('content="uk_UA"', self.uk)
        self.assertIn('content="' + builder.ENGLISH["image_alt"] + '"', self.en)
        self.assertNotIn('content="' + builder.ENGLISH["og_title"] + '"', self.uk)
        for name in ("twitter:title", "twitter:description", "twitter:image:alt"):
            self.assertEqual(self.en.count('name="' + name + '"'), 1)
        for name in ("og:locale", "og:site_name", "og:title", "og:description", "og:url", "og:image:alt"):
            self.assertEqual(self.en.count('property="' + name + '"'), 1)

    def test_canonical_and_alternates_do_not_collapse_languages(self):
        self.assertIn('rel="canonical" href="' + builder.SITE_URL + '"', self.uk)
        self.assertIn('rel="canonical" href="' + builder.EN_URL + '"', self.en)
        for html in (self.uk, self.en):
            for lang, url in (("uk", builder.SITE_URL), ("en", builder.EN_URL), ("x-default", builder.SITE_URL)):
                self.assertEqual(html.count('hreflang="' + lang + '" href="' + url + '"'), 1)

    def test_english_assets_resolve_from_site_root(self):
        self.assertNotIn('<base href=', self.uk)
        self.assertIn('<base href="/">', self.en)
        for shared in ("styles.css?", "app.js?", "chart-share.js?", "kpi-range.js?", "favicon.svg?", "brand-horizontal-en-dark.svg?"):
            self.assertIn(shared, self.en)
        self.assertEqual(self.en.count('src="app.js?'), 1)
        self.assertEqual(self.en.count('href="styles.css?'), 1)

    def test_generated_pages_are_atomic_and_do_not_rewrite_source(self):
        before = SOURCE.read_bytes()
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "en").mkdir()
            (dest / "index.html").write_text(self.uk, encoding="utf-8")
            (dest / "en" / "index.html").write_text(self.en, encoding="utf-8")
            self.assertEqual((dest / "en" / "index.html").read_text(encoding="utf-8"), self.en)
        self.assertEqual(SOURCE.read_bytes(), before)

    def test_shared_dashboard_and_legacy_language_links(self):
        self.assertIn('function canonicalizeLanguagePath()', self.js)
        self.assertIn('location.replace(url.toString())', self.js)
        self.assertIn('url.searchParams.delete("lang")', self.js)
        self.assertIn('url.pathname=target', self.js)
        self.assertIn('location.assign(url.toString())', self.js)
        self.assertIn('location.hash', self.js)
        self.assertIn('params.set("city",', self.js)
        self.assertIn('params.set("period",', self.js)
        self.assertNotIn('params.set("lang", currentLanguage)', self.js)

    def test_no_duplicate_html_templates_and_fail_closed(self):
        with self.assertRaises(ValueError):
            builder.build_pages(self.template.replace('<html lang="uk">', '<html lang="en">'))
        with self.assertRaises(ValueError):
            builder.build_pages(self.template.replace('</head>', '<meta name="description" content="duplicate"></head>'))


if __name__ == "__main__":
    unittest.main(verbosity=2)
