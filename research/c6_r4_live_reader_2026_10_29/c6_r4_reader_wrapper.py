#!/usr/bin/env python3
"""C6-R4 research-only, fail-closed Python Neon reader. No database or publication writes."""
import argparse
import json
import os
import hashlib
import subprocess
import urllib.request
from collections import Counter
from zoneinfo import ZoneInfo
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

EXPECTED_CROSSWALK_BLOB = "4066301d37a4fe41c6bf34570786afaf573cf027"
EXPECTED_SITE_PROD = "e08cc7da8cf29fc8603f199c85f0964610a850a7"
EXPECTED_INPUT_BLOB = "e39dfc6fdbdb90863b5bfb595e12cadf8c20b068"
EXPECTED_BRANCH = "br-bold-mode-b5rub8pq"
EXPECTED_COMPUTE = "ep-calm-rice-b5073ypp"
EXPECTED_PROJECT = "green-cake-44216048"
R3_SOURCE_COMMIT = "0cc4d4b56c547ff0b1b0ccc75c0fd0c7e4027c1e"
FROZEN_JSON_PATH = "kyiv-air-alerts-grafana/data/alerts_combined.json"
CROSSWALK_GIT_PATH = "research/c6_r3_october_lineage_reader_2026_10_29/exact_nine_uuid_crosswalk.json"
UTC = timezone.utc
KYIV = ZoneInfo("Europe/Kyiv")


def _utc(value):
    return value.astimezone(UTC).isoformat(timespec="microseconds")

def _interval_digest(rows):
    payload = "\n".join(sorted(_utc(r["start_at"]) + "|" + _utc(r["end_at"]) for r in rows))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def _verify_full_parity(rows, expected_intervals, *, require_190):
    expected = []
    for record in expected_intervals:
        start = datetime.fromisoformat(record["start"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(record["end"].replace("Z", "+00:00"))
        if start.astimezone(KYIV).strftime("%Y-%m") != "2026-09":
            continue
        if end <= start:
            fail("HARD_FAIL_SOURCE_INTERVAL")
        duration = (end-start).total_seconds() / 60.0
        if not isinstance(record.get("duration_minutes"), (float,int)) or abs(duration-record["duration_minutes"]) > 0.00051:
            fail("HARD_FAIL_SOURCE_DURATION")
        expected.append((_utc(start),_utc(end)))
    actual = [(_utc(r["start_at"]),_utc(r["end_at"])) for r in rows]
    if require_190 and (len(expected)!=190 or len(actual)!=190):
        fail("HARD_FAIL_SEPTEMBER_COUNT")
    if len(actual)!=len(set(actual)) or len(expected)!=len(set(expected)):
        fail("HARD_FAIL_AMBIGUOUS_PHYSICAL_ROWS")
    if Counter(actual) != Counter(expected):
        fail("HARD_FAIL_SEPTEMBER_ROW_PARITY")
    for r in rows:
        if r["end_at"] <= r["start_at"] or r["start_at"].astimezone(KYIV).strftime("%Y-%m") != "2026-09":
            fail("HARD_FAIL_PHYSICAL_DURATION_OR_MONTH")

class ReaderGateError(RuntimeError):
    pass

def fail(code):
    raise ReaderGateError(code)

def floor(value):
    return value.astimezone(timezone.utc).replace(second=0, microsecond=0)

def execute(conn, scope, *, crosswalk, pinned_sha, input_blob, mapping_blob,
            require_neon_identity=False, fail_stage=None, consumer=None,
            expected_intervals=None, identity_verified=False):
    """One repeatable-read read-only transaction; no output until all assertions pass."""
    if pinned_sha != EXPECTED_SITE_PROD or input_blob != EXPECTED_INPUT_BLOB:
        fail("HARD_FAIL_STALE_SITE_PROD_SHA")
    if mapping_blob != EXPECTED_CROSSWALK_BLOB or len(crosswalk.get("rows", [])) != 9:
        fail("HARD_FAIL_MISSING_GIT_CROSSWALK_AUTHORITY")
    if scope not in ("september", "october", "fixture_empty"):
        fail("HARD_FAIL_UNKNOWN_SCOPE")
    if len({r["alias_uid"] for r in crosswalk["rows"]}) != 9 or len({r["canonical_uid"] for r in crosswalk["rows"]}) != 9:
        fail("HARD_FAIL_AMBIGUOUS_MAPPING")
    if set(r["alias_uid"] for r in crosswalk["rows"]) & set(r["canonical_uid"] for r in crosswalk["rows"]):
        fail("HARD_FAIL_AMBIGUOUS_MAPPING")
    if require_neon_identity and not identity_verified:
        fail("IDENTITY_NOT_PROVEN")
    if require_neon_identity and scope == "fixture_empty":
        fail("HARD_FAIL_UNSUPPORTED_LIVE_SCOPE")
    if require_neon_identity and scope == "september" and expected_intervals is None:
        fail("HARD_FAIL_MISSING_SOURCE_AUTHORITY")
    if fail_stage == "connection":
        fail("HARD_FAIL_DB_CONNECTION")
    try:
        with conn.transaction():
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                cur.execute("""SELECT current_database() AS db, current_setting('transaction_isolation') AS isolation,
                          current_setting('transaction_read_only') AS ro, pg_is_in_recovery() AS recovery,
                          txid_current_snapshot()::text AS snapshot""")
                meta = cur.fetchone()
                if meta["isolation"] != "repeatable read" or meta["ro"] != "on":
                    fail("HARD_FAIL_NOT_SINGLE_READONLY_TRANSACTION")
                if require_neon_identity and (meta["db"] != "neondb" or meta["recovery"] is not True):
                    fail("HARD_FAIL_DATABASE_IDENTITY")
                if fail_stage == "metadata":
                    fail("HARD_FAIL_METADATA_FAULT")
                cur.execute("""SELECT episode_uid::text AS uid,city_key,alert_type,episode_state,
                              canonicalization_version,start_at,end_at
                              FROM public.alert_episodes WHERE episode_uid::text=ANY(%s::text[])""",
                            ([u for rec in crosswalk["rows"] for u in (rec["alias_uid"],rec["canonical_uid"])],))
                all_rows = {r["uid"]:r for r in cur.fetchall()}
                aliases = set()
                for rec in crosswalk["rows"]:
                    a,b = all_rows.get(rec["alias_uid"]), all_rows.get(rec["canonical_uid"])
                    if a is None: fail("HARD_FAIL_MISSING_ALIAS_PARENT")
                    if b is None: fail("HARD_FAIL_MISSING_CANONICAL_PARENT")
                    if any(r["city_key"]!="kyiv" or r["alert_type"]!="AIR" or r["episode_state"]!="closed" for r in (a,b)):
                        fail("HARD_FAIL_SOURCE_IDENTITY_MISMATCH")
                    if (a["canonicalization_version"] != b["canonicalization_version"] or
                        a["canonicalization_version"] != "alert-canonicalization-v1"):
                        fail("HARD_FAIL_VERSION_MISMATCH")
                    if (a["start_at"],a["end_at"]) != (floor(b["start_at"]),floor(b["end_at"])):
                        fail("HARD_FAIL_MINUTE_BOUNDARY")
                    if a["start_at"].isoformat() != datetime.fromisoformat(rec["alias_start_utc"].replace("Z","+00:00")).isoformat():
                        fail("HARD_FAIL_GIT_LINEAGE_CONFLICT")
                    if b["start_at"] != datetime.fromisoformat(rec["canonical_start"]):
                        fail("HARD_FAIL_GIT_LINEAGE_CONFLICT")
                    if a["end_at"] != datetime.fromisoformat(rec["alias_end_utc"].replace("Z","+00:00")):
                        fail("HARD_FAIL_GIT_LINEAGE_CONFLICT")
                    if b["end_at"] != datetime.fromisoformat(rec["canonical_end"]):
                        fail("HARD_FAIL_GIT_LINEAGE_CONFLICT")
                    if rec["alias_duration_seconds"] != int((a["end_at"]-a["start_at"]).total_seconds()):
                        fail("HARD_FAIL_GIT_LINEAGE_CONFLICT")
                    if rec["canonical_duration_seconds"] != int((b["end_at"]-b["start_at"]).total_seconds()):
                        fail("HARD_FAIL_GIT_LINEAGE_CONFLICT")
                    aliases.add(a["uid"])
                lo, hi = {"september":("2026-09-01","2026-10-01"),
                          "october":("2026-10-01","2026-11-01"),
                          "fixture_empty":("2035-01-01","2035-01-02")}[scope]
                cur.execute("""SELECT episode_uid::text AS uid, start_at,end_at FROM public.alert_episodes
                               WHERE city_key='kyiv' AND alert_type='AIR' AND episode_state='closed'
                               AND (start_at AT TIME ZONE 'Europe/Kyiv') >= %s::timestamp
                               AND (start_at AT TIME ZONE 'Europe/Kyiv') < %s::timestamp
                               ORDER BY start_at,episode_uid""",(lo,hi))
                scoped=cur.fetchall()
                if fail_stage == "candidate_read": fail("HARD_FAIL_CANDIDATE_READ")
                cur.execute("""WITH e AS (SELECT * FROM public.alert_episodes WHERE city_key='kyiv'
                                AND alert_type='AIR' AND episode_state='closed'
                                AND (start_at AT TIME ZONE 'Europe/Kyiv') >= %s::timestamp
                                AND (start_at AT TIME ZONE 'Europe/Kyiv') < %s::timestamp)
                                SELECT a.episode_uid::text AS alias_uid,b.episode_uid::text AS canonical_uid
                                FROM e a JOIN e b ON a.episode_uid<>b.episode_uid
                                AND a.start_at=date_trunc('minute',b.start_at)
                                AND a.end_at=date_trunc('minute',b.end_at)
                                AND a.canonicalization_version=b.canonicalization_version
                                AND (a.start_at<>b.start_at OR a.end_at<>b.end_at)
                                ORDER BY a.episode_uid,b.episode_uid""",(lo,hi))
                candidates=cur.fetchall()
                if (len({r["alias_uid"] for r in candidates}) != len(candidates) or
                    len({r["canonical_uid"] for r in candidates}) != len(candidates)):
                    fail("HARD_FAIL_AMBIGUOUS_CANDIDATES")
                known={(r["alias_uid"],r["canonical_uid"]) for r in crosswalk["rows"]}
                unknown=[x for x in candidates if (x["alias_uid"],x["canonical_uid"]) not in known]
                if unknown:
                    fail("HARD_FAIL_UNCERTIFIED_OCTOBER_ALIASES" if scope=="october" else "HARD_FAIL_UNKNOWN_ALIAS_CANDIDATES")
                if fail_stage == "projection": fail("HARD_FAIL_PROJECTION")
                physical=[r for r in scoped if r["uid"] not in aliases]
                interval_digest = _interval_digest(physical)
                if scope=="september" and expected_intervals is not None:
                    _verify_full_parity(physical,expected_intervals,require_190=require_neon_identity)
                cur.execute("""SELECT classification_uid::text AS uid,alert_episode_uid::text AS parent_uid,binding_state,verdict
                               FROM public.attack_event_classifications ORDER BY classification_uid""")
                classes=cur.fetchall()
                if fail_stage == "classifications": fail("HARD_FAIL_RELATIONSHIP_READ")
                cur.execute("""SELECT attack_event_source_uid::text AS uid,classification_uid::text AS classification_uid,
                                      source_link_key FROM public.attack_event_sources ORDER BY attack_event_source_uid""")
                sources=cur.fetchall()
                cur.execute("""SELECT attack_event_uid::text AS uid,current_classification_uid::text AS current_classification_uid,
                                     alert_episode_uid::text AS parent_uid,event_status FROM public.attack_events ORDER BY attack_event_uid""")
                events=cur.fetchall()
                if fail_stage == "after_projection": fail("HARD_FAIL_AFTER_PROJECTION")
                cids={c["uid"] for c in classes}
                if any(s["classification_uid"] not in cids for s in sources) or any(e["current_classification_uid"] not in cids for e in events if e["current_classification_uid"]):
                    fail("HARD_FAIL_INCOMPLETE_RELATIONSHIP_SNAPSHOT")
                unbound=[c for c in classes if c["binding_state"]=="UNBOUND" and c["parent_uid"] is None]
                if require_neon_identity and len(unbound)!=25:
                    fail("HARD_FAIL_UNBOUND_PRESERVATION")
                ub_ids = {c["uid"] for c in unbound}
                unbound_source_count=sum(s["classification_uid"] in ub_ids for s in sources)
                active_unbound_events=sum(e["current_classification_uid"] in ub_ids and e["event_status"]=="ACTIVE" for e in events)
                if require_neon_identity and (unbound_source_count!=14 or active_unbound_events!=2):
                    fail("HARD_FAIL_UNBOUND_RELATIONSHIP_PRESERVATION")
                if fail_stage == "relations": fail("HARD_FAIL_RELATIONSHIP_VALIDATION")
                a5={r["a5_classification_uid"] for r in crosswalk["rows"]}
                clsids={c["uid"] for c in classes if c["parent_uid"] in aliases and c["binding_state"]=="BOUND"}
                if require_neon_identity and a5!=clsids: fail("HARD_FAIL_A5_PRESERVATION")
                result={"status":"PASS","scope":scope,"physical_intervals":len(physical),
                        "physical_uids":[r["uid"] for r in physical],
                        "classification_count":len(classes),"source_count":len(sources),"event_count":len(events),
                        "unbound_without_parent":len(unbound),"unbound_sources":unbound_source_count,
                        "unbound_active_events":active_unbound_events,
                        "a5_classifications":len(a5 & clsids),"interval_sha256":interval_digest,
                        "source_row_parity":"PASS" if scope=="september" and expected_intervals is not None else "NOT_EXECUTED",
                        "snapshot":meta["snapshot"],"isolation":meta["isolation"]}
        if consumer is not None: consumer(result)
        return result
    except ReaderGateError: raise
    except (psycopg.Error, KeyError, TypeError, ValueError) as e:
        fail("HARD_FAIL_DATABASE_OR_READER_ERROR:"+type(e).__name__)



def _git(repo,*args):
    try:
        return subprocess.run(["git","-C",str(repo),*args],check=True,
                              stdout=subprocess.PIPE,stderr=subprocess.PIPE).stdout
    except (OSError,subprocess.CalledProcessError):
        fail("HARD_FAIL_GIT_OBJECT_UNAVAILABLE")

def _blob_sha(raw):
    # Git SHA-1 object identity, independent of caller-supplied --blob-sha.
    return hashlib.sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()

def verify_git_authority(repo,*, require_current=True):
    repo=Path(repo)
    if _git(repo,"cat-file","-t",EXPECTED_SITE_PROD).strip()!=b"commit":
        fail("HARD_FAIL_SOURCE_COMMIT_NOT_OBJECT")
    if require_current and _git(repo,"rev-parse","--verify","refs/remotes/origin/site-prod").decode().strip()!=EXPECTED_SITE_PROD:
        fail("HARD_FAIL_STALE_SITE_PROD_SHA")
    frozen=_git(repo,"show",EXPECTED_SITE_PROD+":"+FROZEN_JSON_PATH)
    if _blob_sha(frozen)!=EXPECTED_INPUT_BLOB:
        fail("HARD_FAIL_SOURCE_BLOB_MISMATCH")
    if _git(repo,"cat-file","-t",R3_SOURCE_COMMIT).strip()!=b"commit":
        fail("HARD_FAIL_CROSSWALK_COMMIT_NOT_OBJECT")
    mapping=_git(repo,"show",R3_SOURCE_COMMIT+":"+CROSSWALK_GIT_PATH)
    if _blob_sha(mapping)!=EXPECTED_CROSSWALK_BLOB:
        fail("HARD_FAIL_CROSSWALK_BLOB_MISMATCH")
    try:
        intervals=json.loads(frozen)
        crosswalk=json.loads(mapping)
    except (ValueError,TypeError):
        fail("HARD_FAIL_INVALID_FROZEN_JSON")
    if not isinstance(intervals,list) or not isinstance(crosswalk,dict):
        fail("HARD_FAIL_INVALID_FROZEN_JSON")
    return {"intervals":intervals,"crosswalk":crosswalk,
            "source_sha":EXPECTED_SITE_PROD,"source_blob":_blob_sha(frozen),
            "crosswalk_blob":_blob_sha(mapping),"current_site_prod_verified":require_current}

def verify_control_plane_metadata(branch, endpoint, *, conn_host):
    if (branch.get("id")!=EXPECTED_BRANCH or branch.get("project_id")!=EXPECTED_PROJECT or
        endpoint.get("id")!=EXPECTED_COMPUTE or endpoint.get("project_id")!=EXPECTED_PROJECT or
        endpoint.get("branch_id")!=EXPECTED_BRANCH or endpoint.get("type")!="read_only"):
        fail("IDENTITY_NOT_PROVEN")
    hosts={endpoint.get("host"),(endpoint.get("hosts") or {}).get("read_only_host")}
    if conn_host not in hosts:
        fail("IDENTITY_NOT_PROVEN")
    return True

def _neon_api(path):
    key=os.environ.get("NEON_API_KEY")
    if not key:
        fail("IDENTITY_NOT_PROVEN")
    req=urllib.request.Request("https://console.neon.tech/api/v2"+path,
                               headers={"Authorization":"Bearer "+key,"Accept":"application/json"})
    try:
        with urllib.request.urlopen(req,timeout=15) as response:
            return json.loads(response.read())
    except Exception:
        # Never include HTTP bodies, URL query strings, headers or credentials in logs.
        fail("IDENTITY_NOT_PROVEN")

def verify_live_neon_control_plane(conn):
    b=_neon_api("/projects/"+EXPECTED_PROJECT+"/branches/"+EXPECTED_BRANCH)
    e=_neon_api("/projects/"+EXPECTED_PROJECT+"/endpoints/"+EXPECTED_COMPUTE)
    return verify_control_plane_metadata(b.get("branch",{}),e.get("endpoint",{}),
                                         conn_host=conn.info.host)

def execute_r4(conn,scope,*,authority,neon_identity_verified=False,consumer=None,fail_stage=None):
    """The only public R4 execution entry; no callback before all gates pass."""
    if not isinstance(authority,dict) or authority.get("source_blob")!=EXPECTED_INPUT_BLOB or authority.get("crosswalk_blob")!=EXPECTED_CROSSWALK_BLOB:
        fail("HARD_FAIL_MISSING_GIT_SOURCE_AUTHORITY")
    return execute(conn,scope,crosswalk=authority["crosswalk"],pinned_sha=authority["source_sha"],
                   input_blob=authority["source_blob"],mapping_blob=authority["crosswalk_blob"],
                   expected_intervals=authority["intervals"],require_neon_identity=neon_identity_verified,
                   identity_verified=neon_identity_verified,consumer=consumer,fail_stage=fail_stage)

def main():
    parser=argparse.ArgumentParser(description="C6-R4 research-only; no publisher")
    parser.add_argument("--scope",required=True,choices=["september","october"])
    parser.add_argument("--git-repo",type=Path,required=True)
    parser.add_argument("--frozen-only",action="store_true",help="Check pinned tree only; do NOT certify current site-prod ref")
    args=parser.parse_args()
    try:
        authority=verify_git_authority(args.git_repo,require_current=not args.frozen_only)
        database_url=os.environ.get("C6_R4_READONLY_DATABASE_URL")
        if not database_url:
            fail("HARD_FAIL_READONLY_CONNECTION_UNAVAILABLE")
        with psycopg.connect(database_url,connect_timeout=15) as conn:
            verify_live_neon_control_plane(conn)
            result=execute_r4(conn,args.scope,authority=authority,neon_identity_verified=True)
        # Redacted output; no UID or raw source/classification payloads on stdout.
        safe={k:v for k,v in result.items() if k!="physical_uids"}
        safe.update({"live_python_wrapper":True,"consumer_invocations":0,
                     "publication_artifacts":0,"current_site_prod_verified":authority["current_site_prod_verified"]})
        print(json.dumps(safe,sort_keys=True))
    except ReaderGateError as error:
        print(json.dumps({"status":"HARD_FAIL","reason":str(error),"published":False,
                          "consumer_invocations":0,"publication_artifacts":0},sort_keys=True))
        raise SystemExit(2)

if __name__=="__main__":
    main()
