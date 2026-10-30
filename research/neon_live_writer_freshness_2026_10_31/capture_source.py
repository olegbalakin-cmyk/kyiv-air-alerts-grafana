#!/usr/bin/env python3
"""One real Kyiv Digital HTTP response, pinned site-prod parser, no database writes."""
from __future__ import annotations
import hashlib
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
PROOF = ROOT / "proof"
SITE = Path("site") / "kyiv-air-alerts-grafana"
URL = "https://kyiv.digital/storage/air-alert/stats.html"
PINS = {
  "scripts/update_data.py":"cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833",
  "scripts/db_phase1_core.py":"dda23c268e08f74367f33b189a8bafc1358aadd2",
  "scripts/db_phase1_persistence.py":"ed014e61fc6186fa9daf91c763c847e7df2f0306",
}
SOURCE_KEY = "kyiv_digital_live_http_prospective"
SOURCE_VERSION = "c6-kyiv-digital-html-observation-v1"
UTC = timezone.utc

def iso(value):
    return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00","Z")

def digest(b):
    return hashlib.sha256(b).hexdigest()

def blob(b):
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def emit(path, body):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(body,sort_keys=True,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

def canonical(body):
    return json.dumps(body,ensure_ascii=False,separators=(",",":"),sort_keys=True).encode("utf-8")

def main():
    PROOF.mkdir(parents=True,exist_ok=True)
    report={"checkpoint":"C6-LIVE-WRITER-FRESHNESS-01","scope":"research_only_live_http_and_synthetic_freshness_gate",
            "source_pin":"site-prod@c6636e838cc5ca1da3f250091bb1c5c0ff08229e",
            "github_sha":os.getenv("GITHUB_SHA"),
            "physical_http":"NOT_RUN","physical_isolated_neon_write":"BLOCKED",
            "branch_create_error":"HTTP_422_BRANCHES_LIMIT_EXCEEDED",
            "independent_neon_readback":"NOT_EXECUTED",
            "real_site_json_after_new_write":"NOT_EXECUTED",
            "production_writer_ready":False,"global_cutover_allowed":False}
    http={"method":"GET","url":URL,"status":None,"captured_at_utc":None,
          "raw_sha256":None,"entity_bytes":None,"source_payload_cache_warning":True}
    capture=None
    stage="pins"
    try:
        for path,expected in PINS.items():
            got=blob((SITE/path).read_bytes())
            if got!=expected:
                raise RuntimeError("SITE_PROD_SOURCE_PIN_MISMATCH")
        report["site_prod_git_blobs_verified"]=True
        stage="http"
        session=requests.Session()
        session.mount("https://",requests.adapters.HTTPAdapter(max_retries=0))
        with session.get(URL,headers={"Accept":"text/html","Accept-Encoding":"identity",
                     "User-Agent":"kyiv-air-alerts-grafana/research-live-writer-freshness"},
                     stream=True,timeout=(10,25),allow_redirects=False) as r:
            http.update({"status":r.status_code,"content_type":r.headers.get("Content-Type"),
                         "server_date":r.headers.get("Date"),"last_modified":r.headers.get("Last-Modified"),
                         "cache_control":r.headers.get("Cache-Control")})
            body=r.raw.read(8*1024*1024+1,decode_content=True)
            http["captured_at_utc"]=iso(datetime.now(UTC))
        if len(body)>8*1024*1024 or not body:
            raise RuntimeError("HTTP_ENTITY_SIZE_INVALID")
        http["raw_sha256"]=digest(body)
        http["entity_bytes"]=len(body)
        (PROOF/"kyiv_digital_http_entity.bin").write_bytes(body)
        if http["status"]!=200:
            raise RuntimeError("HTTP_STATUS_NOT_200")
        if "html" not in str(http["content_type"]).lower():
            raise RuntimeError("HTTP_CONTENT_TYPE_NOT_HTML")
        report["physical_http"]="PASS"
        stage="parser"
        sys.path.insert(0,str((SITE/"scripts").resolve()))
        from update_data import parse_live_history
        from db_phase1_core import legacy_episode_id
        alerts,_events=parse_live_history(body.decode("utf-8",errors="strict"))
        capture_at=datetime.fromisoformat(http["captured_at_utc"].replace("Z","+00:00"))
        valid=sorted((a for a in alerts if a.start.tzinfo and a.end.tzinfo and
                a.start<a.end<=capture_at),key=lambda a:(a.start,a.end))
        if not valid:
            raise RuntimeError("NO_COMPLETED_EPISODE")
        a=valid[-1]
        start,end=iso(a.start),iso(a.end)
        record={"version":SOURCE_VERSION,"source_key":SOURCE_KEY,"city_key":"kyiv",
                "alert_type":"AIR","source_native_id":None,"source_start_at":start,"source_end_at":end}
        capture={"source_key":SOURCE_KEY,"source_version":SOURCE_VERSION,
                "canonical_record":record,
                "source_record_key":digest(canonical(record)),
                "legacy_episode_id":legacy_episode_id("kyiv",a.start,a.end),
                "start_at_utc":start,"end_at_utc":end,
                "captured_at_utc":http["captured_at_utc"],"raw_sha256":http["raw_sha256"],
                "parser_blob_sha":PINS["scripts/update_data.py"],
                "parsed_completed_count":len(valid),
                "identity_status":"PROSPECTIVE_NOT_APPROVED_FOR_PRODUCTION"}
        report["canonical_identity_prospective"]="PASS"
        report["physical_neon_uuid_from_this_run"]="NOT_PROVEN"
        report["result"]="PARTIAL_HTTP_IDENTITY_ONLY"
    except Exception as exc:
        report["result"]="BLOCKED_HTTP_OR_PARSER"
        report["failed_stage"]=stage
        report["error_class"]=type(exc).__name__
        if type(exc) is RuntimeError and str(exc) in {
            "SITE_PROD_SOURCE_PIN_MISMATCH","HTTP_ENTITY_SIZE_INVALID","HTTP_STATUS_NOT_200",
            "HTTP_CONTENT_TYPE_NOT_HTML","NO_COMPLETED_EPISODE"}:
            report["error_code"]=str(exc)
    finally:
        emit(PROOF/"http_capture.json",http)
        if capture:
            emit(PROOF/"canonical_candidate.json",capture)
        emit(PROOF/"machine_verdict.json",report)
        manifest={"schema":"c6-live-writer-freshness-v1","source_pin":report["source_pin"],"files":{}}
        for p in sorted(PROOF.glob("*")):
            if p.is_file() and p.name!="sha256_manifest.json":
                manifest["files"][p.name]=digest(p.read_bytes())
        emit(PROOF/"sha256_manifest.json",manifest)
    print("MACHINE_VERDICT="+json.dumps({k:v for k,v in report.items() if k not in {"error_details"}},sort_keys=True))
    return 0 if report["result"]=="PARTIAL_HTTP_IDENTITY_ONLY" else 2

if __name__=="__main__":
    sys.exit(main())
