#!/usr/bin/env python3
"""Research-only fail-closed Neon projection. Never writes to database or publishes."""
import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import psycopg
from psycopg.rows import dict_row

EXPECTED_CROSSWALK_BLOB = "4066301d37a4fe41c6bf34570786afaf573cf027"
EXPECTED_SITE_PROD = "552de9cfc8ee7fff7e169caf0a928f4e17ca9cb2"
EXPECTED_INPUT_BLOB = "69d0c1d906fca6a81445e102fa4fce8b102d4073"
EXPECTED_BRANCH = "br-bold-mode-b5rub8pq"
EXPECTED_COMPUTE = "ep-calm-rice-b5073ypp"

class ReaderGateError(RuntimeError):
    pass

def fail(code):
    raise ReaderGateError(code)

def floor(value):
    return value.astimezone(timezone.utc).replace(second=0, microsecond=0)

def execute(conn, scope, *, crosswalk, pinned_sha, input_blob, mapping_blob,
            require_neon_identity=False, fail_stage=None, consumer=None):
    """One repeatable-read read-only transaction; no output until all assertions pass."""
    if pinned_sha != EXPECTED_SITE_PROD or input_blob != EXPECTED_INPUT_BLOB:
        fail("HARD_FAIL_STALE_SITE_PROD_SHA")
    if mapping_blob != EXPECTED_CROSSWALK_BLOB or len(crosswalk.get("rows", [])) != 9:
        fail("HARD_FAIL_MISSING_GIT_CROSSWALK_AUTHORITY")
    if scope not in ("september", "october"):
        fail("HARD_FAIL_UNKNOWN_SCOPE")
    if len({r["alias_uid"] for r in crosswalk["rows"]}) != 9 or len({r["canonical_uid"] for r in crosswalk["rows"]}) != 9:
        fail("HARD_FAIL_AMBIGUOUS_MAPPING")
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
                              FROM public.alert_episodes WHERE city_key='kyiv'
                              AND alert_type='AIR' AND episode_state='closed'""")
                all_rows = {r["uid"]:r for r in cur.fetchall()}
                aliases = set()
                for rec in crosswalk["rows"]:
                    a,b = all_rows.get(rec["alias_uid"]), all_rows.get(rec["canonical_uid"])
                    if a is None: fail("HARD_FAIL_MISSING_ALIAS_PARENT")
                    if b is None: fail("HARD_FAIL_MISSING_CANONICAL_PARENT")
                    if a["city_key"] != "kyiv" or b["city_key"] != "kyiv": fail("HARD_FAIL_SOURCE_IDENTITY_MISMATCH")
                    if a["canonicalization_version"] != b["canonicalization_version"]: fail("HARD_FAIL_VERSION_MISMATCH")
                    if (a["start_at"],a["end_at"]) != (floor(b["start_at"]),floor(b["end_at"])):
                        fail("HARD_FAIL_MINUTE_BOUNDARY")
                    if a["start_at"].isoformat() != datetime.fromisoformat(rec["alias_start_utc"].replace("Z","+00:00")).isoformat():
                        fail("HARD_FAIL_GIT_LINEAGE_CONFLICT")
                    if b["start_at"] != datetime.fromisoformat(rec["canonical_start"]):
                        fail("HARD_FAIL_GIT_LINEAGE_CONFLICT")
                    aliases.add(a["uid"])
                lo, hi = (("2026-09-01","2026-10-01") if scope=="september" else ("2026-10-01","2026-11-01"))
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
                known={(r["alias_uid"],r["canonical_uid"]) for r in crosswalk["rows"]}
                unknown=[x for x in candidates if (x["alias_uid"],x["canonical_uid"]) not in known]
                if unknown:
                    fail("HARD_FAIL_UNCERTIFIED_OCTOBER_ALIASES" if scope=="october" else "HARD_FAIL_UNKNOWN_ALIAS_CANDIDATES")
                if fail_stage == "projection": fail("HARD_FAIL_PROJECTION")
                physical=[r for r in scoped if r["uid"] not in aliases]
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
                if fail_stage == "relations": fail("HARD_FAIL_RELATIONSHIP_VALIDATION")
                a5={r["a5_classification_uid"] for r in crosswalk["rows"]}
                clsids={c["uid"] for c in classes if c["parent_uid"] in aliases and c["binding_state"]=="BOUND"}
                if require_neon_identity and a5!=clsids: fail("HARD_FAIL_A5_PRESERVATION")
                result={"status":"PASS","scope":scope,"physical_intervals":len(physical),
                        "physical_uids":[r["uid"] for r in physical],
                        "classification_count":len(classes),"source_count":len(sources),"event_count":len(events),
                        "unbound_without_parent":len(unbound),"a5_classifications":len(a5 & clsids),
                        "snapshot":meta["snapshot"],"isolation":meta["isolation"]}
        if consumer is not None: consumer(result)
        return result
    except ReaderGateError: raise
    except (psycopg.Error, KeyError, TypeError, ValueError) as e:
        fail("HARD_FAIL_DATABASE_OR_READER_ERROR:"+type(e).__name__)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--scope", choices=["september","october"],required=True)
    p.add_argument("--crosswalk",type=Path,required=True)
    p.add_argument("--site-prod-sha",default=EXPECTED_SITE_PROD)
    p.add_argument("--input-blob-sha",default=EXPECTED_INPUT_BLOB)
    p.add_argument("--crosswalk-blob-sha",default=EXPECTED_CROSSWALK_BLOB)
    p.add_argument("--require-neon-identity", action="store_true")
    args=p.parse_args()
    if not os.getenv("DATABASE_URL"): raise SystemExit("HARD_FAIL_DB_CONNECTION: DATABASE_URL missing")
    try:
        with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
            result=execute(conn,args.scope,crosswalk=json.loads(args.crosswalk.read_text()),
                           pinned_sha=args.site_prod_sha,input_blob=args.input_blob_sha,
                           mapping_blob=args.crosswalk_blob_sha,require_neon_identity=args.require_neon_identity)
        print(json.dumps(result,sort_keys=True))
    except ReaderGateError as e:
        print(json.dumps({"status":"HARD_FAIL","reason":str(e),"published":False}))
        raise SystemExit(2)
if __name__=="__main__": main()
