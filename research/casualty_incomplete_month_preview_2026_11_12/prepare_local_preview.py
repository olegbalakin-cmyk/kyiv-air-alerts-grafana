#!/usr/bin/env python3
"""Build *only* a local isolated frontend copy from the exact site-prod checkout.
Requires a local copy of chart.js dist/chart.umd.js (v4.4.7) at --chart-js.
No production files are edited. No network request is made by this script.
"""
import argparse
import pathlib
import shutil
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
REPO = HERE.parents[1]
SITE = REPO / "kyiv-air-alerts-grafana"
SRC = SITE / "pages-preview"
DATA = SITE / "data"


def build(target, chart_js):
    target = pathlib.Path(target).resolve()
    if target == SRC or str(target).startswith(str(SRC) + "/"):
        raise ValueError("Cannot generate inside production frontend path")
    target.mkdir(parents=True, exist_ok=True)
    for path in SRC.iterdir():
        if path.is_file():
            shutil.copy2(path, target / path.name)
    (target / "data").mkdir(exist_ok=True)
    for name in ("dashboard_data.json", "site_derived.json", "kyiv_threat_mix.json"):
        shutil.copy2(DATA / name, target / "data" / name)
    shutil.copy2(HERE / "coverage-preview.js", target / "coverage-preview.js")
    shutil.copy2(HERE / "local-fixture-loader.js", target / "local-fixture-loader.js")
    shutil.copy2(chart_js, target / "chart.umd.js")

    app = (target / "app.js").read_text(encoding="utf-8")
    source = 'const RAW_DATA_BASE = "https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/";'
    assert app.count(source) == 1, "Exact app source changed; fail closed"
    app = app.replace(source, 'const RAW_DATA_BASE = "/data/";')
    (target / "app.js").write_text(app, encoding="utf-8")

    index = (target / "index.html").read_text(encoding="utf-8")
    external = 'https://cdn.jsdelivr.net/npm/chart.js@4.4.7/dist/chart.umd.min.js'
    assert index.count(external) == 1, "Unknown Chart.js source"
    index = index.replace(external, "chart.umd.js")
    tag = '<script src="app.js?v=20261023-daily28-allcities180-prod1"></script>'
    assert index.count(tag) == 1, "Unknown original app tag"
    index = index.replace(tag, tag +
        '\n  <script src="local-fixture-loader.js"></script>' +
        '\n  <script src="coverage-preview.js"></script>')
    index = index.replace('<meta name="robots" content="index,follow,max-snippet:large">',
                          '<meta name="robots" content="noindex,nofollow">')
    # No possibility of public crawling when served on localhost, but also set an unambiguous watermark.
    index = index.replace('</body>', '<div id="fixture-watermark" style="position:fixed;bottom:4px;left:6px;font:12px system-ui;color:#f8e45c;z-index:9999;pointer-events:none">LOCAL RESEARCH FIXTURE · NOT PUBLISHED</div>\n</body>')
    (target / "index.html").write_text(index, encoding="utf-8")
    print("LOCAL_PREVIEW_DIR=" + str(target))
    print("Serve only on 127.0.0.1 (never deploy):")
    print(f"python -m http.server 8765 --bind 127.0.0.1 --directory {target}")
    print("http://127.0.0.1:8765/?coverage_fixture=1&city=zaporizhzhia&casyear=2026")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chart-js", type=pathlib.Path, required=True,
                        help="Local Chart.js 4.4.7 UMD file, never fetched by this script")
    parser.add_argument("--output", type=pathlib.Path)
    args = parser.parse_args()
    target = args.output or pathlib.Path(tempfile.mkdtemp(prefix="casualty-coverage-preview-"))
    build(target, args.chart_js)


if __name__ == "__main__":
    main()
