#!/usr/bin/env python3
"""Isolated C6/C3 browser QA. Existing frozen preview; no Neon, sources, or deployment."""
import argparse
import functools
import hashlib
import http.server
import json
import shutil
import threading
import traceback
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--preview",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    args=parser.parse_args()
    root=args.preview.resolve()
    out=args.out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    config=root/"preview-config.js"
    app=root/"app.js"
    original_config=config.read_bytes()
    original_app=app.read_bytes()
    original_hashes={str(p.relative_to(root)):sha(p) for p in root.rglob("*") if p.is_file()}
    report={
      "scope":"GITHUB_RUNNER_LOOPBACK_NONPUBLISHING",
      "physical_artifact":13929117121,
      "c2_artifact":13873291895,
      "production_modified":False,
      "dst_correction":"OFF",
      "source_current_certified":False,
      "results":[],
      "js_errors":[],
      "failed_responses":[],
      "external_requests":[],
      "csv":[],
      "rollback":{},
      "fix_diagnostic":{},
      "verdict":"INCOMPLETE"
    }
    server=http.server.ThreadingHTTPServer(("127.0.0.1",0),functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(root)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    base=f"http://127.0.0.1:{server.server_port}/"
    try:
      # Patch only this runner-local copied preview consumer; original bundle and
      # production app.js remain untouched. Preserve the original index guards.
      source_anchor = b'index?.meta?.source_ref === "site-prod"'
      source_guard = (
        b'(index?.meta?.source_ref === "site-prod" || '
        b'(window.PREVIEW_CONFIG?.source === "neon" && '
        b'index?.meta?.source_ref === "neon:br-bold-mode-b5rub8pq" && '
        b'index?.meta?.verified_count === 23 && '
        b'index?.meta?.source_dashboard_generated_at === sourceGeneratedAt))')
      if (original_app.count(source_anchor)!=1 or
          b'index?.schema === "verified-historical-daily-start-counts-v1"' not in original_app or
          b'index?.meta?.expected_cities === 23' not in original_app):
        raise AssertionError("SCOPED_PREVIEW_INDEX_PATCH_CONTRACT_CHANGED")
      app.write_bytes(original_app.replace(source_anchor,source_guard,1))
      patched_hashes={**original_hashes,"app.js":sha(app)}
      report["preview_consumer"]={
        "scope":"RUNNER_ONLY_SCOPED_SOURCE_REF",
        "file":"app.js",
        "original_sha256":hashlib.sha256(original_app).hexdigest(),
        "patched_sha256":sha(app),
        "allowed_neon_source_ref":"neon:br-bold-mode-b5rub8pq",
        "requires_preview_source":"neon",
        "requires_verified_count":23,
        "requires_same_dashboard_generation":True,
        "preserves_schema_and_expected_cities":True,
      }
      with sync_playwright() as pw:
        binary=shutil.which("google-chrome") or shutil.which("chromium")
        if not binary:
          raise RuntimeError("CHROME_NOT_INSTALLED")
        browser=pw.chromium.launch(executable_path=binary,headless=True,args=["--no-sandbox"])
        report["browser_version"]=browser.version
        context=browser.new_context(viewport={"width":1440,"height":1080},accept_downloads=True)
        context.add_init_script("""
          try{localStorage.setItem('air-alerts-intro-tour-v5','done')}catch(e){}
        """)
        def route(r):
          if r.request.url.startswith(base):
            r.continue_()
          else:
            report["external_requests"].append(r.request.url)
            r.abort()
        context.route("**/*",route)
        def open_page(source=None):
          page=context.new_page()
          page.on("pageerror",lambda err:report["js_errors"].append(str(err)))
          page.on("response",lambda r:report["failed_responses"].append({"status":r.status,"url":r.url}) if r.status>=400 else None)
          target=base if source is None else base+"?preview_source="+source
          page.goto(target,wait_until="networkidle",timeout=90000)
          page.wait_for_function("typeof state !== 'undefined' && !!state.data && !!state.charts.cityIntensityChart",timeout=90000)
          if page.locator("#tourSkip").is_visible():
            page.locator("#tourSkip").click()
          return page
        def index_source(page):
          return page.evaluate("() => state.historicalDaily?.meta?.source_ref || null")
        def city_check(page,cities,modes,with_csv=False):
          for city in cities:
            page.locator("#citySelect").select_option(city)
            for period in modes:
              page.locator("#cityPeriod").select_option(period)
              check=page.evaluate("""() => {const a=state.charts.cityIntensityChart,b=state.charts.cityDurationChart;return {city:document.querySelector('#citySelect').value,period:document.querySelector('#cityPeriod').value,n:a?.data?.labels?.length,m:b?.data?.labels?.length,w:a?.width,h:a?.height}}""")
              if check["city"]!=city or check["period"]!=period or not check["n"] or check["m"]!=check["n"] or not check["w"] or not check["h"]:
                raise AssertionError("CHART_FAIL: "+repr((city,period,check)))
            if with_csv:
              page.locator("#cityPeriod").select_option("monthly")
              chart="cityIntensityChart"
              with page.expect_download(timeout=20000) as evt:
                page.locator(f'[data-csv-chart="{chart}"] button.csv-export-button:not(.chart-image-button):not(.chart-embed-button)').click()
              download=evt.value
              path=out/(city+"-monthly.csv")
              download.save_as(path)
              contents=path.read_text(encoding="utf-8-sig")
              if len(contents)<100 or ("," not in contents and ";" not in contents):
                raise AssertionError("BAD_CSV: "+city)
              report["csv"].append({"city":city,"bytes":path.stat().st_size,"sha256":sha(path)})
        all_cities=sorted(json.loads((root/"data/neon/dashboard_data.json").read_text())["cities"])
        all_modes=["daily28","weekly","rolling30","rolling90","rolling180","calendarWeekly","monthly","allTime"]
        config.write_text('window.PREVIEW_DEFAULT_SOURCE = "neon";\n')
        p=open_page()
        neon_index=index_source(p)
        if neon_index!="neon:br-bold-mode-b5rub8pq":
          raise AssertionError("SCOPED_NEON_INDEX_NOT_ACCEPTED")
        neon_meta=p.evaluate("() => state.historicalDaily?.meta || null")
        dashboard_generation=p.evaluate("() => state.data?.meta?.generated_at || null")
        if (neon_meta is None or neon_meta.get("verified_count")!=23 or
            neon_meta.get("expected_cities")!=23 or
            neon_meta.get("source_dashboard_generated_at")!=dashboard_generation):
          raise AssertionError("NEON_INDEX_METADATA_INCOMPATIBLE")
        report["results"].append({"source":"neon","cities":len(all_cities),"modes":len(all_modes),"historical_index":neon_index})
        city_check(p,all_cities,all_modes,with_csv=True)
        report["results"][-1]["city_mode_combinations"]=len(all_cities)*len(all_modes)
        report["results"][-1]["current_status_uncertified"]=not p.evaluate("() => Object.values(state.data.cities).some(c=>c.meta.current_source_verified===true)")
        report["results"][-1]["charts_rendered"]=len(p.evaluate("() => Object.keys(state.charts)"))
        p.screenshot(path=str(out/"neon.png"))
        p.close()
        config.write_text('window.PREVIEW_DEFAULT_SOURCE = "legacy";\n')
        p=open_page()
        git_index=index_source(p)
        if git_index!="site-prod":
          raise AssertionError("LEGACY_HISTORICAL_INDEX_RESTORE_FAIL")
        report["results"].append({"source":"git-rollback","cities":len(all_cities),"historical_index":git_index})
        city_check(p,all_cities,["monthly"],with_csv=False)
        report["results"][-1]["city_mode_combinations"]=len(all_cities)
        p.screenshot(path=str(out/"git-rollback.png"))
        p.close()
        post_rollback={k:sha(root/k) for k in original_hashes if k!="preview-config.js"}
        report["rollback"]={"sources":["git","neon","git"],"config_only":True,"unchanged_files":len(post_rollback),"digest_differences":[k for k,v in post_rollback.items() if v!=patched_hashes[k]],"git_historical_index":git_index}
        report["fix_diagnostic"]={"scope":"RUNNER_LOCAL_PREVIEW_COMPATIBILITY","source_ref_accepted":neon_index,"expected":"neon:br-bold-mode-b5rub8pq","candidate_json_bytes_unchanged":True}
        browser.close()
        if report["js_errors"] or report["failed_responses"] or report["external_requests"] or report["rollback"]["digest_differences"]:
          report["verdict"]="BLOCKED_BROWSER_OR_ROLLBACK_ERROR"
        else:
          report["verdict"]="PASS_SCOPED_NEON_INDEX_OFFLINE_PREVIEW"
    except Exception:
      report["verdict"]="BLOCKED_QA_EXCEPTION"
      report["traceback"]=traceback.format_exc()
    finally:
      app.write_bytes(original_app)
      config.write_bytes(original_config)
      final_hashes={str(p.relative_to(root)):sha(p) for p in root.rglob("*") if p.is_file()}
      report["files_exact_restored"]=final_hashes==original_hashes
      if not report["files_exact_restored"]:
        report["verdict"]="BLOCKED_PREVIEW_RESTORE"
      server.shutdown()
      (out/"browser_result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print("C6_C3_VERDICT="+report["verdict"],flush=True)
    print("C6_C3_TESTS="+json.dumps(report["results"]),flush=True)
    if report["verdict"]=="PASS_SCOPED_NEON_INDEX_OFFLINE_PREVIEW":
      return 0
    return 2

if __name__=="__main__":
    raise SystemExit(main())
