#!/usr/bin/env python3
"""RESEARCH ONLY. Reuses site-prod Phase-1 persistence on a NEW, verified Neon child.
Never run on production, the existing production shadow, or another team's branch.
Two invocations: first-commit-crash, then retry-readback. Not run while branch limit blocks.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse

PARENT="br-bold-mode-b5rub8pq"
FORBIDDEN={"br-wandering-sunset-b5835alw",PARENT,"br-misty-darkness-b5wkoiyk"}
PREFIX="c6-live-writer-freshness-isolated-"
SOURCE_KEY="kyiv_digital_live_http_prospective"
SOURCE_VERSION="c6-kyiv-digital-html-observation-v1"

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def save(path,obj):
    p=Path(path);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,sort_keys=True,indent=2,default=str)+"\n",encoding="utf-8")

def sha(b):
    return hashlib.sha256(b).hexdigest()

def git_blob(b):
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def fail(message):
    raise RuntimeError(message)

def guard(meta,url):
    # Metadata must have been fetched independently from Neon AFTER child creation.
    if meta.get("parent_id")!=PARENT or meta.get("id") in FORBIDDEN:
        fail("NOT_A_NEW_PROOF_CHILD_OF_SHADOW")
    if not str(meta.get("name","")).startswith(PREFIX) or not str(meta.get("id","")).startswith("br-"):
        fail("CHILD_ID_OR_NAME_NOT_APPROVED")
    if meta.get("default") is not False or meta.get("protected") is not False:
        fail("CHILD_NOT_NONDEFAULT_UNPROTECTED")
    if meta.get("current_state")!="ready":
        fail("CHILD_NOT_READY")
    host=urlparse(url).hostname
    # Paste from the child's fresh Neon get_connection_string; never infer the
    # child's hostname from its parent. No credential material in metadata.
    if not host or not meta.get("approved_connection_hostname") or host!=meta["approved_connection_hostname"]:
        fail("CHILD_CONNECTION_HOST_MISMATCH")
    if meta.get("connection_role_scope")!="new_child_only":
        fail("CHILD_ROLE_SCOPE_NOT_ATTESTED")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--site",required=True,help="immutable pinned site-prod checkout root")
    ap.add_argument("--capture",required=True,help="Actions-produced canonical_candidate.json")
    ap.add_argument("--branch-attestation",required=True,help="independently fetched child metadata plus child connection host")
    ap.add_argument("--proof-dir",required=True)
    ap.add_argument("--phase",choices=["first-commit-crash","retry-readback"],required=True)
    args=ap.parse_args()
    url=os.getenv("NEON_ISOLATED_PROOF_DATABASE_URL")
    if not url:
        fail("MISSING_ISOLATED_BRANCH_URL")
    meta=load(args.branch_attestation)
    guard(meta,url)
    source=load(args.capture)
    if source.get("source_key")!=SOURCE_KEY or source.get("source_version")!=SOURCE_VERSION:
        fail("SOURCE_CONTRACT_NOT_PROSPECTIVE_PINNED")
    if source.get("identity_status")!="PROSPECTIVE_NOT_APPROVED_FOR_PRODUCTION":
        fail("SOURCE_IDENTITY_STATUS_MISMATCH")
    expected=sha(json.dumps(source["canonical_record"],ensure_ascii=False,sort_keys=True,
                       separators=(",",":")).encode("utf-8"))
    if expected!=source["source_record_key"]:
        fail("SOURCE_RECORD_HASH_CONFLICT")
    src=Path(args.site)/"scripts"
    for path,known in {"db_phase1_persistence.py":"ed014e61fc6186fa9daf91c763c847e7df2f0306",
                       "db_phase1_core.py":"dda23c268e08f74367f33b189a8bafc1358aadd2"}.items():
        if git_blob((src/path).read_bytes())!=known:
            fail("PINNED_DB_CODE_CHANGED")
    sys.path.insert(0,str(src.resolve()))
    from db_phase1_persistence import persist_phase1_payload
    from db_phase1_core import CANONICALIZATION_VERSION,legacy_episode_id
    import psycopg
    from psycopg.rows import dict_row
    if legacy_episode_id("kyiv",source["start_at_utc"],source["end_at_utc"])!=source["legacy_episode_id"]:
        fail("LEGACY_CANONICAL_EPISODE_CONFLICT")
    ts=lambda x:datetime.fromisoformat(x.replace("Z","+00:00"))
    captured=ts(source["captured_at_utc"])
    started=ts(source["start_at_utc"])
    ended=ts(source["end_at_utc"])
    if not started<ended<=captured:
        fail("NOT_A_COMPLETED_EPISODE")
    ck={
      "source_key":SOURCE_KEY,"city_key":"kyiv","stream_key":"proof:kyiv_digital_html",
      "checkpoint_seq":1,"checkpoint_kind":"bootstrap","previous_checkpoint_id":None,
      "checked_at":captured,"continuity_verified":False,"continuity_method":"single_html_response_no_continuity_claim",
      "continuity_anchor_at":None,"observed_oldest_start_at":started,"observed_latest_end_at":ended,
      "observed_record_count":1,"cursor":None,
      "metadata":{"source_record_key":source["source_record_key"],"http_sha256":source["raw_sha256"],
                  "proof":"research_only_one_response_not_history_coverage"}}
    provenance={"run_kind":"shadow_poll","schema_version":"001_phase1_core",
      "canonicalization_version":CANONICALIZATION_VERSION,
      "workflow_repository":"olegbalakin-cmyk/kyiv-air-alerts-grafana",
      "workflow_name":"C6 live writer research-only",
      "workflow_ref":"research-neon-live-writer-freshness-2026-10-31",
      "workflow_sha":os.environ.get("GITHUB_SHA"),
      "input_repository":"olegbalakin-cmyk/kyiv-air-alerts-grafana",
      "input_ref":"site-prod","input_sha":"c6636e838cc5ca1da3f250091bb1c5c0ff08229e",
      "parameters":{"scope":"isolated_research_single_episode","source_key_contract":"PROSPECTIVE"}}
    episodes=[{"legacy_episode_id":source["legacy_episode_id"],"city_key":"kyiv",
        "alert_type":"AIR","start_at":started,"end_at":ended,
        "episode_state":"closed","canonicalization_version":CANONICALIZATION_VERSION}]
    observations=[{"episode_legacy_id":source["legacy_episode_id"],
        "source_key":SOURCE_KEY,"source_record_key_version":SOURCE_VERSION,
        "source_record_key":source["source_record_key"],
        "source_native_id":None,"city_key":"kyiv","alert_type":"AIR",
        "source_start_at":started,"source_end_at":ended,"source_retrieved_at":captured,
        "binding_state":"bound","canonicalization_role":"canonical_input",
        "contributes_start_boundary":True,"contributes_end_boundary":True,
        "raw_sha256":source["raw_sha256"],
        "provenance":{"scope":"research_isolated","source_sha256":source["raw_sha256"],
                      "not_certified_for_live_production":True}}]
    proof=Path(args.proof_dir)
    with psycopg.connect(url,row_factory=dict_row) as cn:
        result=persist_phase1_payload(cn,source_key=SOURCE_KEY,city_key="kyiv",
            stream_key="proof:kyiv_digital_html",db_branch=meta["id"],
            run_provenance=provenance,episodes=episodes,
            source_observations=observations,checkpoint_candidate=ck)
    if args.phase=="first-commit-crash":
        if result["stats"]["checkpoints_inserted"]!=1:
            fail("UNEXPECTED_FIRST_CHECKPOINT")
        save(proof/"first_commit_receipt.json",{"run_id":result["run_id"],
             "stats":result["stats"],"branch_id":meta["id"],
             "source_record_key":source["source_record_key"],
             "crash_after_commit_exit_code":86})
        # Intentionally die after a real COMMIT. Must run retry as a separate process.
        os._exit(86)

    if not result["stats"]["exact_retry"]:
        fail("RETRY_NOT_IDEMPOTENT")
    first=load(proof/"first_commit_receipt.json")
    with psycopg.connect(url,autocommit=True,row_factory=dict_row) as rd:
        with rd.cursor() as c:
            c.execute("SET default_transaction_read_only = on")
            c.execute("""SELECT e.episode_uid::text AS episode_uuid,
                         s.source_observation_id::text AS observation_uuid,
                         s.source_record_key,
                         i.status AS ingestion_status, i.ingest_committed_at AS committed_at,
                         k.checkpoint_seq
                         FROM public.alert_episodes e
                         JOIN public.alert_episode_sources s ON s.episode_uid=e.episode_uid
                         JOIN public.ingestion_runs i ON i.run_id=e.created_by_run_id
                         JOIN public.current_ingestion_checkpoints k
                           ON k.source_key=s.source_key AND k.city_key=s.city_key
                         WHERE e.legacy_episode_id=%s AND s.source_key=%s
                           AND s.source_record_key_version=%s AND s.source_record_key=%s
                           AND k.stream_key='proof:kyiv_digital_html'
                         """,(source["legacy_episode_id"],SOURCE_KEY,
                              SOURCE_VERSION,source["source_record_key"]))
            rows=c.fetchall()
    if len(rows)!=1 or rows[0]["ingestion_status"]!="succeeded" or rows[0]["checkpoint_seq"]!=1:
        fail("INDEPENDENT_READBACK_NOT_EXACT")
    save(proof/"independent_readback.json",{
      "verdict":"PASS_BOUNDED_CHILD_WRITE_READBACK_IDEMPOTENCY",
      "phase1_original_code_used":True,"source_contract":"PROSPECTIVE_NOT_PRODUCTION",
      "branch_id":meta["id"],"first":first,"retry":result,
      "physical_ids":rows[0],"readback_at_utc":datetime.now(timezone.utc),
      "site_json_after_write":"NOT_EXECUTED_SEPARATE_GENERATOR_GATE",
      "release_authorized":False})
    print("ISOLATED_CHILD_READBACK_PASS")
    return 0

if __name__=="__main__":
    sys.exit(main())
