#!/usr/bin/env python3
"""Build two SEO entrypoints from the single Ukrainian dashboard HTML template.

The dashboard's JavaScript, data, and static assets remain shared. This script
only localizes English document metadata and the pre-JS language/brand state.
"""
from __future__ import annotations

import argparse
from html import escape
from pathlib import Path
import re

SITE_URL = "https://ukraine-air-alerts.netlify.app/"
EN_URL = SITE_URL + "en/"

ENGLISH = {
    "title": "Air alerts in Ukrainian cities — charts and comparisons",
    "description": (
        "Air-alert statistics for Kyiv and Ukrainian regional centres: alert counts, "
        "hours under alert, average duration, city comparisons and deaths from aerial attacks."
    ),
    "og_site_name": "Air alerts — Ukrainian cities",
    "og_title": "Air-alert statistics in Ukrainian cities",
    "image_alt": "Illustrated chart of air-alert statistics",
}


def one_replace(text: str, before: str, after: str) -> str:
    count = text.count(before)
    if count != 1:
        raise ValueError(f"Expected exactly one occurrence of {before!r}, found {count}")
    return text.replace(before, after, 1)


def replace_meta(text: str, kind: str, key: str, value: str) -> str:
    tag_re = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
    selector = re.compile(rf'\b{re.escape(kind)}="{re.escape(key)}"')
    matching = [tag for tag in tag_re.findall(text) if selector.search(tag)]
    if len(matching) != 1:
        raise ValueError(f"Expected one {kind}={key} meta tag; found {len(matching)}")
    tag = matching[0]
    content = re.compile(r'(\bcontent=")[^"]*(")')
    if not content.search(tag):
        raise ValueError(f"Missing content attribute for {kind}={key}")
    updated = content.sub(
        lambda match: match.group(1) + escape(value, quote=True) + match.group(2),
        tag,
        count=1,
    )
    return one_replace(text, tag, updated)


def replace_link(text: str, rel: str, href: str) -> str:
    tags = re.findall(r"<link\b[^>]*>", text, flags=re.IGNORECASE)
    matching = [tag for tag in tags if f'rel="{rel}"' in tag]
    if len(matching) != 1:
        raise ValueError(f"Expected one link with rel={rel}")
    tag = matching[0]
    updated, count = re.subn(
        r'(\bhref=")[^"]*(")',
        lambda match: match.group(1) + escape(href, quote=True) + match.group(2),
        tag,
        count=1,
    )
    if count != 1:
        raise ValueError(f"Missing href in rel={rel}")
    return one_replace(text, tag, updated)


def build_pages(template: str) -> tuple[str, str]:
    # Fail closed if the source or generator starts managing duplicate locale tags.
    if "hreflang=" in template or '<base href=' in template:
        raise ValueError("Template must not contain generated hreflang/base tags")
    if '<html lang="uk">' not in template or '<head>' not in template:
        raise ValueError("Expected the Ukrainian source document")
    if template.count("</head>") != 1:
        raise ValueError("Expected one head closing tag")
    if 'href="' + SITE_URL + '"' not in template:
        raise ValueError("Unexpected Ukrainian canonical URL")

    alternates = (
        '  <link rel="alternate" hreflang="uk" href="' + SITE_URL + '">\n'
        '  <link rel="alternate" hreflang="en" href="' + EN_URL + '">\n'
        '  <link rel="alternate" hreflang="x-default" href="' + SITE_URL + '">'
    )
    uk = one_replace(template, "</head>", alternates + "\n</head>")
    en = one_replace(uk, '<html lang="uk">', '<html lang="en">')
    # All existing script, CSS, image and fetch URLs are relative to the
    # document base. EN serves from /en/, but assets remain ONLY at the root.
    en = one_replace(en, "<head>", '<head>\n  <base href="/">')
    en = replace_link(en, "canonical", EN_URL)
    en = replace_meta(en, "name", "description", ENGLISH["description"])
    en = replace_meta(en, "property", "og:locale", "en_US")
    en = replace_meta(en, "property", "og:site_name", ENGLISH["og_site_name"])
    en = replace_meta(en, "property", "og:title", ENGLISH["og_title"])
    en = replace_meta(en, "property", "og:description", ENGLISH["description"])
    en = replace_meta(en, "property", "og:url", EN_URL)
    en = replace_meta(en, "property", "og:image:alt", ENGLISH["image_alt"])
    en = replace_meta(en, "name", "twitter:title", ENGLISH["og_title"])
    en = replace_meta(en, "name", "twitter:description", ENGLISH["description"])
    en = replace_meta(en, "name", "twitter:image:alt", ENGLISH["image_alt"])
    en, title_count = re.subn(
        r"<title>[^<]*</title>",
        "<title>" + escape(ENGLISH["title"]) + "</title>",
        en,
        count=1,
    )
    if title_count != 1:
        raise ValueError("Expected exactly one HTML title")
    en = one_replace(
        en,
        'src="brand-horizontal-uk-dark.svg?v=20261019-logo12-1"',
        'src="brand-horizontal-en-dark.svg?v=20261019-logo12-1"',
    )
    en = one_replace(
        en,
        '<button id="langUk" class="language-button" type="button" aria-pressed="true">',
        '<button id="langUk" class="language-button" type="button" aria-pressed="false">',
    )
    en = one_replace(
        en,
        '<button id="langEn" class="language-button" type="button" aria-pressed="false">',
        '<button id="langEn" class="language-button" type="button" aria-pressed="true">',
    )

    # Footer link in EN must lead to the English static archive, not UA.
    en = one_replace(en, '<a href="/stats/" id="staticStatsFooterLink" class="footer-stats-link">Статистика у таблицях</a>',
                     '<a href="/en/stats/" id="staticStatsFooterLink" class="footer-stats-link">Data tables</a>')

    # Both pages still refer to one shared application, not copied frontends.
    if en.count('src="app.js?') != 1 or en.count('href="styles.css?') != 1:
        raise ValueError("Unexpected shared asset references")
    return uk, en


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    uk, en = build_pages(args.source.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "en").mkdir(parents=True, exist_ok=True)
    (args.output_dir / "index.html").write_text(uk, encoding="utf-8")
    (args.output_dir / "en" / "index.html").write_text(en, encoding="utf-8")
    print("BILINGUAL_STATIC_HTML_PASS: / + /en/; shared assets and data unchanged")


if __name__ == "__main__":
    main()
