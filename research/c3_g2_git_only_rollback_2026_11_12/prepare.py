#!/usr/bin/env python3
"""Isolated G2 Git-only rollback snapshot and no-loss proof. NEVER deploy or write Git."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

SITE = "d0a7d22de2828c93236562cccc9d2e68c6a66e3d"
FRONT = "19446ba9b9513ec962be08a128b4132de3f1912c"
NETLIFY = "a18e20295a7aa148c57fce4c5913ad68c3bd4c34"
C2_RUN = 43262387718
DATA = Path("kyiv-air-alerts-grafana/data")
FIVE = ("dashboard_data.json","site_derived.json","alerts_combined.json",
        "kyiv_threat_mix.json","sevastopol_events.json")
STATIC = ("index.html","styles.css","app.js","features.json","chart-share.js",
          "kpi-range.js","brand-mark.svg","brand-horizontal-uk-dark.svg",
          "brand-horizontal-en-dark.svg","favicon.svg","favicon-32.png")

def must(ok, why):
    if not ok:
        raise RuntimeError(why)

def git(root, *args):
    return subprocess.check_output(["git","-C",str(root),*args],text=True).strip()

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def canon(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()

def metadata(path,root=None,rel=None):
    raw=path.read_bytes()
    r={"sha256":digest(raw),"bytes":len(raw)}
    if root and rel:
        r["git_blob_sha1"]=git(root,"hash-object",str(rel))
    return r

def verify_dashboard(d):
    m=d.get("meta") or {}
    generation=m.get("generated_at")
    keys=(d.get("multicity_meta") or {}).get("production_city_keys")
    must(isinstance(generation,str) and generation,"NO_GENERATION")
    must(isinstance(keys,list) and len(keys)==23 and len(set(keys))==23,"CITY_KEYS_23")
    must(set(keys)==set((d.get("cities") or {}).keys()),"CITY_SET")
    must(isinstance(d["cities"].get("kyiv"),dict),"KYIV_MISSING")
    index=d.get("historical_daily_kpi")
    must(isinstance(index,dict),"EMBEDDED_GIT_KPI_MISSING")
    im=index.get("meta") or {}
    must(index.get("schema")=="verified-historical-daily-start-counts-v1","KPI_SCHEMA")
    must(im.get("source_ref")=="site-prod","NOT_GIT_ONLY")
    must(im.get("source_dashboard_generated_at")==generation,"GENERATION_DRIFT")
    must(im.get("expected_cities")==23 and im.get("verified_count")==23,"KPI_NOT_23")
    must(set(index.get("cities") or {})==set(keys),"KPI_CITY_KEYS")
    must(all(isinstance(row,dict) and row.get("status")=="verified"
             for row in index["cities"].values()),"KPI_CITY_STATUS")
    return generation,keys,index

def recovery_decision(before,after,source,generation_matches):
    # NO git reset, no restoration of old JSON. Never silently drop intervening writes.
    if source!="site-prod" or not generation_matches:
        return "STOP_REQUIRE_NEW_C2_GIT_ONLY_AND_RECONCILIATION"
    if before==after:
        return "UNCHANGED_NO_GIT_WRITE"
    return "RECAPTURE_LATEST_GIT_ONLY_NO_RESTORE"

def test_no_loss(runtime,queue_hash):
    sample=dict(runtime)
    sample["casualty/review_queue.json"]=queue_hash.encode()
    baseline={k:digest(v) for k,v in sample.items()}
    cases={}
    options=[
      ("unchanged",{},"site-prod",True,"UNCHANGED_NO_GIT_WRITE"),
      ("later_C2",{"dashboard_data.json":b"new C2"},"site-prod",True,
       "RECAPTURE_LATEST_GIT_ONLY_NO_RESTORE"),
      ("later_casualty",{"casualty/review_queue.json":b"new casualty"},"site-prod",True,
       "RECAPTURE_LATEST_GIT_ONLY_NO_RESTORE"),
      ("later_aux",{"kyiv_threat_mix.json":b"new auxiliary"},"site-prod",True,
       "RECAPTURE_LATEST_GIT_ONLY_NO_RESTORE"),
      ("later_Sevastopol",{"sevastopol_events.json":b"new auxiliary"},"site-prod",True,
       "RECAPTURE_LATEST_GIT_ONLY_NO_RESTORE"),
      ("combined",{"dashboard_data.json":b"new C2","casualty/review_queue.json":b"new casualty",
                   "sevastopol_events.json":b"new auxiliary"},"site-prod",True,
       "RECAPTURE_LATEST_GIT_ONLY_NO_RESTORE"),
      ("neon_current",{},"neon",True,"STOP_REQUIRE_NEW_C2_GIT_ONLY_AND_RECONCILIATION"),
      ("stale_index",{},"site-prod",False,
       "STOP_REQUIRE_NEW_C2_GIT_ONLY_AND_RECONCILIATION")
    ]
    for name,edits,source,valid,expected in options:
        newer=dict(sample)
        for key,extra in edits.items():
            newer[key]=sample[key]+b"\n"+extra
        observed={k:digest(v) for k,v in newer.items()}
        decision=recovery_decision(baseline,observed,source,valid)
        must(decision==expected,"NO_LOSS_DECISION_"+name)
        must(all(newer[k].endswith(v) for k,v in edits.items()),"NO_LOSS_PRESERVATION_"+name)
        cases[name]={"pass":True,"decision":decision,"modified_keys":sorted(edits)}
    return cases

def zip_deterministic(path,files):
    with zipfile.ZipFile(path,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
        for name,data in sorted(files.items()):
            info=zipfile.ZipInfo(name,date_time=(2026,11,12,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o100644<<16
            out.writestr(info,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)

def main():
    ap=argparse.ArgumentParser()
    for arg in ("site","frontend","netlify","out"):
        ap.add_argument("--"+arg,required=True,type=Path)
    a=ap.parse_args()
    a.out.mkdir(parents=True,exist_ok=True)
    checks=[]
    def check(cond,name):
        must(cond,name);checks.append(name)
    check(git(a.site,"rev-parse","HEAD")==SITE,"PIN_SITE")
    check(git(a.frontend,"rev-parse","HEAD")==FRONT,"PIN_PR100")
    check(git(a.netlify,"rev-parse","HEAD")==NETLIFY,"PIN_PR104")
    check(git(a.frontend,"merge-base",SITE,FRONT)==SITE,"ANCESTRY_PR100")
    check(git(a.netlify,"merge-base",SITE,NETLIFY)==SITE,"ANCESTRY_PR104")
    app=(a.frontend/"kyiv-air-alerts-grafana/pages-preview/app.js").read_text()
    workflow=(a.netlify/".github/workflows/netlify-production.yml").read_text()
    check("matchesDashboardGeneration(index)" in app and
          "PRODUCTION_NEON_GIT_RELEASE" in app and "RAW_DATA_BASE" in app,
          "FRONTEND_GUARD")
    check("!inputs.neon_release_mode" in workflow and
          "build_preview_historical_daily.py" in workflow and "default: false" in workflow,
          "GIT_ONLY_NETLIFY_DEFAULT")
    front_allowed={".github/workflows/c6-c3-six-json-preview-qa.yml",
       "kyiv-air-alerts-grafana/pages-preview/app.js",
       "kyiv-air-alerts-grafana/tests/test_live_history_binding.js",
       "research/c6_c3_preview_2026_11_12/browser_qa.py"}
    netlify_allowed={".github/workflows/netlify-production.yml",
       ".github/workflows/c3-gated-netlify-offline.yml",
       "tests/test_c3_neon_netlify_binding.py"}
    check(set(git(a.frontend,"diff","--name-only",SITE,FRONT).splitlines())
          <=front_allowed,"PR100_SCOPE")
    check(set(git(a.netlify,"diff","--name-only",SITE,NETLIFY).splitlines())
          <=netlify_allowed,"PR104_SCOPE")
    dashboard=json.loads((a.site/DATA/"dashboard_data.json").read_bytes())
    generation,city_keys,index=verify_dashboard(dashboard)
    check(len(city_keys)==23,"EXACT_GIT_23_CITIES")
    captures=json.loads((a.site/DATA/"c2_history_capture_checkpoints.json").read_bytes())
    check(set(captures)==set(city_keys) and all(
        c.get("github_run_id")==C2_RUN and c.get("github_run_attempt")==1 and
        c.get("workflow_sha")=="375e69351e6a5aee1be16892821f7cdde2a8f21a" and
        isinstance(c.get("source_sha256"),str) and len(c["source_sha256"])==64
        for c in captures.values()),"PHYSICAL_C2_23_RECEIPTS")
    entries={}
    runtime={}
    raw_data={}
    for name in FIVE:
        rel=DATA/name
        binary=(a.site/rel).read_bytes()
        check(len(binary)>0,"RUNTIME_NONEMPTY_"+name)
        if name!="dashboard_data.json":
            json.loads(binary)
        entries["git-json/"+str(rel)]=binary
        runtime[name]=metadata(a.site/rel,a.site,rel)
        raw_data[name]=binary
    check(len(runtime)==5,"FIVE_RUNTIME_BLOBS")
    prefix=str(DATA/"casualties/")
    tracked=git(a.site,"ls-files",prefix).splitlines()
    casualty={p:metadata(a.site/p,a.site,p) for p in tracked}
    check(bool(casualty) and
          any(p.endswith("review_queue.json") for p in casualty) and
          any(p.endswith("source_state.json") for p in casualty),"CASUALTY_TRACKED")
    aux={p:metadata(a.site/DATA/p,a.site,DATA/p) for p in
       ("c2_history_capture_checkpoints.json","dashboard_qa.json")}
    index_raw=canon(index)+b"\n"
    for name in STATIC:
        p=a.frontend/"kyiv-air-alerts-grafana/pages-preview"/name
        check(p.exists() and p.stat().st_size>0,"NETLIFY_FILE_"+name)
        entries["netlify/_site/"+name]=p.read_bytes()
    entries["netlify/_site/historical-daily-kpi.json"]=index_raw
    entries["netlify/_site/data.json"]=raw_data["dashboard_data.json"]
    check(len(entries)==18,"PACKAGE_5_GIT_12_STATIC_1_DATA")
    check(json.loads(index_raw)==dashboard["historical_daily_kpi"] and
          json.loads(index_raw)["meta"]["source_dashboard_generated_at"]==generation,
          "STATIC_KPI_MATCHES_GIT_GENERATION")
    queue_hash=next(val["sha256"] for p,val in casualty.items()
                    if p.endswith("review_queue.json"))
    no_loss=test_no_loss(raw_data,queue_hash)
    check(len(no_loss)==8 and all(v["pass"] for v in no_loss.values()),
          "EIGHT_POST_SNAPSHOT_NO_LOSS_CASES")
    manifest={
      "schema":"c3-g2-git-only-rollback-manifest-v1","repo":"olegbalakin-cmyk/kyiv-air-alerts-grafana",
      "production_changed":False,"offline_only":True,"cutover_time_fresh":False,
      "netlify_authority_proven":False,"global_cutover":"NO","dst_correction":"OFF",
      "site_id":"b5aafc46-7468-4070-baf1-db80a4d30501",
      "site_prod_commit":SITE,"frontend_pr100_commit":FRONT,"netlify_pr104_commit":NETLIFY,
      "c2_run_id":C2_RUN,"c2_attempt":1,"source_receipts":23,
      "dashboard_generated_at":generation,"city_keys":sorted(city_keys),"verified_city_count":23,
      "static_index_origin":"GIT_EMBEDDED_INDEX_COPY_NO_EXTERNAL_SOURCE_HTTP",
      "static_index_sha256":digest(index_raw),
      "kyiv_city_sha256":digest(canon(dashboard["cities"]["kyiv"])),
      "git_json":runtime,"casualty_tracked_files":casualty,"auxiliary_audit":aux,
      "package_entries":{k:{"sha256":digest(v),"bytes":len(v)} for k,v in sorted(entries.items())},
      "must_refresh_immediately_before_cutover":[
        "latest site-prod SHA and C2 exact run attempt / 23 source receipts",
        "five Git JSON byte SHA-256 and git blob SHA-1",
        "dashboard generated_at + full 23-city embedded/static index",
        "Kyiv full city row, casualty queue/source_state and all tracked casualty hashes",
        "auxiliary Kyiv threat / Sevastopol / C2 checkpoints SHA",
        "PR100 frontend and PR104 Git-only workflow accepted/deployed SHA",
        "12 static file digests, Netlify deploy ID, and operator recover authority"],
      "recovery_policy":"never reset site-prod or restore older JSON; recapture current Git-only or STOP",
      "ROLLBACK_OFFLINE_READY":"YES","ROLLBACK_OPERATIONAL_READY":"NO"}
    (a.out/"manifest.json").write_bytes(canon(manifest)+b"\n")
    (a.out/"no_loss_cases.json").write_bytes(canon(no_loss)+b"\n")
    (a.out/"checks.json").write_bytes(canon({"count":len(checks),"pass":checks})+b"\n")
    package=a.out/"git-only-rollback-package.zip"
    zip_deterministic(package,entries)
    (a.out/"package.sha256").write_text(digest(package.read_bytes())+"  git-only-rollback-package.zip\n")
    report={"state":"PASS_OFFLINE_ONLY","check_count":len(checks),
       "no_loss_cases":len(no_loss),"site_prod_sha":SITE,"frontend_sha":FRONT,
       "netlify_sha":NETLIFY,"generation":generation,"verified_cities":23,
       "git_file_count":5,"netlify_root_file_count":12,
       "casualty_tracked_count":len(casualty),
       "package_sha256":digest(package.read_bytes()),
       "manifest_sha256":digest((a.out/"manifest.json").read_bytes()),
       "ROLLBACK_OFFLINE_READY":"YES","ROLLBACK_OPERATIONAL_READY":"NO",
       "netlify_deploy_executed":False,"git_publication_executed":False}
    (a.out/"REPORT.json").write_bytes(canon(report)+b"\n")
    print(json.dumps(report,ensure_ascii=False,sort_keys=True))

if __name__=="__main__":
    main()
