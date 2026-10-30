"""Browser test of the existing frontend with research-generated JSON only."""
from __future__ import annotations

import argparse
import csv
import functools
import hashlib
import http.server
import json
import shutil
import subprocess
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", type=Path, required=True)
    ap.add_argument("--candidate", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--chrome")
    args = ap.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    preview = out / "preview"
    shutil.copytree(args.site / "pages-preview", preview, dirs_exist_ok=True)
    data = preview / "data"
    shutil.copytree(args.candidate / "site", data, dirs_exist_ok=True)
    shutil.copy(args.site / "data/kyiv_threat_mix.json", data / "kyiv_threat_mix.json")
    js = preview / "app.js"
    old = "https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/"
    source = js.read_text()
    assert source.count(old) == 1
    js.write_text(source.replace(old, "./data/"))
    (preview / ".gitignore").write_text(".netlify/\n")
    (preview / "_headers").write_text("/*\n  X-Robots-Tag: noindex, nofollow\n")
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(preview))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    report = {"scope": "LOCAL_BROWSER_RESEARCH_SNAPSHOT", "netlify_deployment": False,
              "city_results": [], "downloads": [], "page_errors": [], "rollback": {}}
    # The same three-file source switch that existing app.js consumes. Retain
    # byte identities for the legacy rollback and for the candidate bundle.
    names = ["dashboard_data.json", "site_derived.json", "kyiv_threat_mix.json"]
    before = {name: digest(data / name) for name in names}
    try:
        with sync_playwright() as pw:
            chrome = args.chrome or shutil.which("google-chrome") or shutil.which("chromium")
            browser = pw.chromium.launch(executable_path=chrome, headless=True, args=["--no-sandbox"])
            page = browser.new_page(viewport={"width": 1440, "height": 1050}, accept_downloads=True)
            page.on("pageerror", lambda error: report["page_errors"].append(str(error)))
            base = f"http://127.0.0.1:{server.server_port}/"
            page.goto(base, wait_until="networkidle")
            page.wait_for_function("typeof state !== 'undefined' && state.data && state.charts.cityIntensityChart && state.explorations", timeout=60000)
            keys = page.locator("#citySelect option").evaluate_all("els => els.map(e=>e.value).filter(Boolean)")
            assert len(keys) == 23 and len(set(keys)) == 23
            # Dismiss the existing optional tour through its visible control.
            skip = page.locator("#tourSkip")
            if skip.is_visible():
                skip.click()
            for key in keys:
                page.locator("#citySelect").select_option(key)
                chart = page.evaluate("({labels: state.charts.cityIntensityChart.data.labels.length, series: state.charts.cityIntensityChart.data.datasets.length, kpi: document.querySelector('#kpiAlerts').textContent, title: document.querySelector('#cityTitle').textContent})")
                assert chart["labels"] > 0 and chart["series"] > 0 and chart["kpi"].strip() not in ("", "—")
                report["city_results"].append({"key": key, **chart})
            page.locator("#citySelect").select_option("kyiv")
            for period in ("monthly", "weekly", "daily28"):
                page.locator("#cityPeriod").select_option(period)
                with page.expect_download(timeout=15000) as download:
                    page.locator('[data-csv-chart="cityIntensityChart"] button').click()
                item = download.value
                path = out / item.suggested_filename
                item.save_as(path)
                rows = list(csv.reader(path.read_text(encoding="utf-8-sig").splitlines()))
                assert len(rows) > 1 and len(rows[0]) >= 2
                report["downloads"].append({"period": period, "file": path.name, "rows": len(rows)-1, "sha256": digest(path)})
            page.screenshot(path=str(out / "candidate-browser.png"), full_page=False)
            # Rehearse switching the complete consumed data family back to the
            # pinned Git files, reload the same frontend, and test a CSV again.
            for name in names:
                shutil.copy(args.site / "data" / name, data / name)
            expected = {name: digest(args.site / "data" / name) for name in names}
            actual = {name: digest(data / name) for name in names}
            assert expected == actual
            page.reload(wait_until="networkidle")
            page.wait_for_function("typeof state !== 'undefined' && state.data && state.charts.cityIntensityChart", timeout=60000)
            assert page.locator("#citySelect option").count() == 23
            report["rollback"] = {"scope": "LOCAL_SOURCE_BUNDLE_ONLY", "byte_exact_legacy": expected == actual,
                                  "legacy_sha256": actual, "candidate_sha256": before,
                                  "frontend_reload": "PASS", "netlify_rollback": "NOT_EXECUTED"}
            page.screenshot(path=str(out / "legacy-rollback-browser.png"), full_page=False)
            assert not report["page_errors"], report["page_errors"]
            report["verdict"] = "PASS_BOUNDED_BROWSER_AND_SOURCE_ROLLBACK"
            browser.close()
    finally:
        server.shutdown()
        (out / "browser_result.json").write_text(json.dumps(report, indent=2, ensure_ascii=False)+"\n")
    print(json.dumps({"verdict": report.get("verdict"), "cities": len(report["city_results"]), "csv": len(report["downloads"]), "rollback": report["rollback"].get("byte_exact_legacy")}))


if __name__ == "__main__":
    main()
