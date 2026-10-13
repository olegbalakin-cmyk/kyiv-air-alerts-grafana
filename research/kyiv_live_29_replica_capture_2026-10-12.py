#!/usr/bin/env python3
"""One read-only PostgreSQL snapshot of the accepted 29 Kyiv identities. Never write to database."""
import collections
import csv
import datetime as dt
import hashlib
import io
import json
import os
import pathlib
import re
import subprocess
import sys
from urllib.parse import parse_qs, unquote, urlsplit

import psycopg

OUT = pathlib.Path("replica_audit_results")
OUT.mkdir(exist_ok=True)
PROJECT = "green-cake-44216048"
BRANCH = "br-bold-mode-b5rub8pq"
DB = "neondb"
REPLICA = "ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech"
ORIGINAL_HOSTS = {
    "ep-still-violet-b5bg6mhp.c-7.us-east-2.aws.neon.tech",
    "ep-still-violet-b5bg6mhp-pooler.c-7.us-east-2.aws.neon.tech",
}
RECEIPT_COMMIT = "2648aea950f489e5547869ca422e463dda84648d"
RECEIPT_BLOB = "9df9e451b852a882f065e98bbb188f878eda6646"
RECEIPT_PATH = "research/kyiv_live_29_semantic_audit_verified_receipt_2026-10-12.json"
TABLES = ("alert_episodes", "attack_event_classifications", "attack_event_sources", "attack_events")
FIELDS = {
    "alert_episodes": ("episode_uid", "legacy_episode_id", "city_key", "alert_type", "episode_state", "canonicalization_version", "start_at", "end_at", "created_at"),
    "attack_event_classifications": ("classification_uid", "classification_key_version", "classification_key", "alert_episode_uid", "city_key", "historical_episode_id", "alert_type", "alert_start_at", "alert_end_at", "verdict", "is_event", "positive_tier", "created_at", "classified_at", "supersedes_classification_uid", "revision_reason", "evidence_set_sha256", "review_provenance_sha256", "origin_provenance", "origin_provenance_sha256", "classifier_blob_sha", "classifier_methodology_version", "normalization_version"),
    "attack_event_sources": ("attack_event_source_uid", "source_link_key", "source_link_key_version", "classification_uid", "observation_id", "source_family", "source_type", "source_timestamp", "event_timestamp_if_stated", "content_sha256", "created_at"),
    "attack_events": ("attack_event_uid", "attack_event_key", "attack_event_key_version", "alert_episode_uid", "city_key", "historical_episode_id", "alert_type", "alert_start_at", "alert_end_at", "event_status", "current_classification_uid", "binding_state", "created_at", "updated_at"),
}
REQUIRED = {
    "alert_episodes": ("episode_uid", "legacy_episode_id", "city_key", "alert_type", "episode_state", "canonicalization_version", "start_at", "end_at"),
    "attack_event_classifications": ("classification_uid", "classification_key", "historical_episode_id", "city_key", "alert_start_at", "alert_end_at", "verdict", "supersedes_classification_uid"),
    "attack_event_sources": ("attack_event_source_uid", "source_link_key", "classification_uid"),
    "attack_events": ("attack_event_uid", "attack_event_key", "historical_episode_id", "city_key", "event_status", "current_classification_uid"),
}
CAPS = {"alert_episodes": 500, "attack_event_classifications": 1000, "attack_event_sources": 2500, "attack_events": 500}

def canonical(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")

def hash_bytes(x):
    return hashlib.sha256(x).hexdigest()

def put(name, obj):
    p = OUT / name
    p.write_bytes(json.dumps(obj, sort_keys=True, ensure_ascii=False, indent=2, default=str).encode("utf-8") + b"\n")

def fmt(v):
    if isinstance(v, dt.datetime):
        return v.astimezone(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z") if v.tzinfo else v.isoformat(timespec="microseconds")
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    if isinstance(v, (tuple, list)):
        return [fmt(x) for x in v]
    if isinstance(v, dict):
        return {str(k):fmt(x) for k,x in v.items()}
    return str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v

def utc(x):
    if not x:
        return ""
    s = str(x)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    z = dt.datetime.fromisoformat(s)
    if z.tzinfo is None:
        return "INVALID_NAIVE:" + s
    return z.astimezone(dt.timezone.utc).isoformat(timespec="microseconds")

def fail(msg):
    raise RuntimeError(msg)

def freeze_receipt():
    subprocess.run(["git", "fetch", "--no-tags", "--depth=1", "origin", RECEIPT_COMMIT], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    raw = subprocess.check_output(["git", "show", RECEIPT_COMMIT + ":" + RECEIPT_PATH])
    blob = subprocess.check_output(["git", "hash-object", "--stdin"], input=raw).decode().strip()
    if blob != RECEIPT_BLOB:
        fail("FROZEN_RECEIPT_BLOB_MISMATCH")
    x = json.loads(raw)
    if x.get("status") != "KYIV LIVE 29 CANDIDATE-BINDING SEMANTIC AUDIT = PASS" or x.get("frozen_original_commit") != "92d57bbbfad60e6c09bb92372b1e84f38fa6ced4":
        fail("FROZEN_RECEIPT_AUTHORITY_MISMATCH")
    rows = x.get("episode_rows") or []
    if len(rows) != 29 or len({r.get("episode_id") for r in rows}) != 29:
        fail("FROZEN_RECEIPT_COUNT_OR_DUPLICATE")
    identities = [{"city_key":"kyiv", "episode_id":str(r["episode_id"]), "alert_start":r["alert_start"], "alert_end":r["alert_end"], "git": {"unique_candidates_with_stored_match_or_classifier":r.get("unique_candidates_with_stored_match_or_classifier"), "unique_candidates_with_final_classifier_binding":r.get("unique_candidates_with_final_classifier_binding"), "followups_scheduled":r.get("followups_scheduled"), "followups_marked_checked":r.get("followups_marked_checked"), "source_coverage":r.get("all_required_source_coverage")}} for r in rows]
    if any(utc(r["alert_start"]).startswith("INVALID") or utc(r["alert_end"]).startswith("INVALID") for r in identities):
        fail("FROZEN_RECEIPT_TIMESTAMP_NOT_AWARE")
    return identities, hash_bytes(raw)

def parse_credential():
    raw = os.environ.get("AUDIT_SOURCE_SECRET") or ""
    if not raw:
        fail("EXISTING_AUTHORIZED_SECRET_UNAVAILABLE")
    try:
        q = urlsplit(raw)
        params = parse_qs(q.query, keep_blank_values=True)
        if q.scheme not in ("postgres", "postgresql") or q.hostname not in ORIGINAL_HOSTS:
            fail("SECRET_ORIGINAL_HOST_NOT_ATTESTED_PRIMARY")
        if unquote(q.path.lstrip("/")) != DB or not q.username or q.password is None:
            fail("SECRET_DATABASE_OR_ROLE_MISMATCH")
        if os.getenv("AUDIT_WRITER_BRANCH") != BRANCH:
            fail("SECRET_RUNTIME_BRANCH_MISMATCH")
        if q.port not in (None, 5432):
            fail("UNEXPECTED_SECRET_PORT")
        if any(k.lower() in ("host", "hostaddr", "service", "options", "dbname", "database", "user", "password", "port") for k in params):
            fail("FORBIDDEN_DSN_OVERRIDE_PARAM")
        ssl = params.get("sslmode", ["require"])[0]
        if ssl not in ("require", "verify-ca", "verify-full"):
            fail("SECRET_SSLMODE_NOT_SECURE")
        if os.getenv("AUDIT_EXPECTED_REPLICA") != REPLICA:
            fail("EXECUTION_REPLICA_ALLOWLIST_MISMATCH")
        return {"host":REPLICA, "port":5432, "user":unquote(q.username), "password":unquote(q.password), "dbname":DB, "sslmode":ssl, "connect_timeout":15, "application_name":"kyiv_live_29_replica_readonly_audit"}
    finally:
        del raw

def execute(cur, name, query, args, ledger, cap=None):
    ledger.append({"name": name, "sql_sha256": hash_bytes(query.encode()), "parameter_identity_hash":hash_bytes(canonical(args))})
    cur.execute(query, args)
    if cur.description:
        cols = [c.name for c in cur.description]
        arr = [dict(zip(cols, row)) for row in cur.fetchall()]
        if cap is not None and len(arr) > cap:
            fail("BOUNDED_QUERY_CAP_EXCEEDED:" + name)
        return arr
    return []

def sanitize(table, rows):
    result = []
    for row in rows:
        out = {}
        for k,v in row.items():
            if k == "origin_provenance":
                out["origin_kind"] = v.get("kind") if isinstance(v,dict) and isinstance(v.get("kind"),str) else None
                out["origin_provenance_content_sha256"] = hash_bytes(canonical(fmt(v)))
            else:
                out[k] = fmt(v)
        result.append(out)
    return sorted(result, key=lambda q: canonical(q))

def reconcile(data):
    identities = data["frozen_identities"]
    tables = data["tables"]
    parents, clss, links, events = [tables[name] for name in TABLES]
    results=[]
    for identity in identities:
        eid=identity["episode_id"]; start=utc(identity["alert_start"]); end=utc(identity["alert_end"])
        p=[x for x in parents if x.get("city_key")=="kyiv" and str(x.get("legacy_episode_id"))==eid]
        pe=[x for x in p if x.get("alert_type")=="AIR" and x.get("episode_state")=="closed" and x.get("canonicalization_version")=="alert-canonicalization-v1" and utc(x.get("start_at"))==start and utc(x.get("end_at"))==end]
        c0=[x for x in clss if x.get("city_key")=="kyiv" and str(x.get("historical_episode_id"))==eid]
        c=[x for x in c0 if utc(x.get("alert_start_at"))==start and utc(x.get("alert_end_at"))==end and x.get("alert_type") in (None, "AIR")]
        ids={str(x["classification_uid"]) for x in c}
        superseded={str(x.get("supersedes_classification_uid")) for x in c if x.get("supersedes_classification_uid")}
        tips=[x for x in c if str(x["classification_uid"]) not in superseded]
        l=[x for x in links if str(x.get("classification_uid")) in ids]
        ev=[x for x in events if x.get("city_key")=="kyiv" and str(x.get("historical_episode_id"))==eid]
        issues=[]
        if len(p)!=1 or len(pe)!=1:
            issues.append("CANONICAL_PARENT_CARDINALITY_OR_IDENTITY")
        if len(c)!=len(c0):
            issues.append("OUTSIDE_EXACT_CLASSIFICATION_IDENTITY")
        if len(c) and len(tips)!=1:
            issues.append("NONUNIQUE_OR_MISSING_CURRENT_TIP")
        if len({x["classification_key"] for x in c})!=len(c):
            issues.append("DUPLICATE_CLASSIFICATION_KEY")
        if any(x.get("supersedes_classification_uid") and (str(x.get("supersedes_classification_uid")) not in ids or str(x["classification_uid"])==str(x.get("supersedes_classification_uid"))) for x in c):
            issues.append("BROKEN_SUPERSESSION_CHAIN")
        if pe and any(x.get("alert_episode_uid") and str(x.get("alert_episode_uid")) != str(pe[0]["episode_uid"]) for x in c):
            issues.append("CLASSIFICATION_PARENT_UID_MISMATCH")
        if len({str(x["source_link_key"]) for x in l})!=len(l) or len({str(x["attack_event_source_uid"]) for x in l})!=len(l):
            issues.append("DUPLICATE_SOURCE_LINK")
        if any(str(x.get("classification_uid")) not in ids for x in l):
            issues.append("ORPHAN_SOURCE_LINK")
        if len(ev)>1 or len({str(x.get("attack_event_key")) for x in ev})!=len(ev):
            issues.append("MULTIPLE_OR_DUPLICATE_EVENT")
        if ev and (utc(ev[0].get("alert_start_at"))!=start or utc(ev[0].get("alert_end_at"))!=end):
            issues.append("EVENT_IDENTITY_INTERVAL_CONFLICT")
        if tips:
            tip=tips[0]
            if ev and str(ev[0].get("current_classification_uid"))!=str(tip["classification_uid"]):
                issues.append("EVENT_NOT_POINTING_AT_CURRENT_TIP")
            if bool(tip.get("is_event")) and (len(ev)!=1 or ev[0].get("event_status")!="ACTIVE"):
                issues.append("POSITIVE_TIP_EVENT_MISSING_OR_INACTIVE")
            if ev and not bool(tip.get("is_event")) and ev[0].get("event_status")!="WITHDRAWN":
                issues.append("NEGATIVE_TIP_EVENT_NOT_WITHDRAWN")
        elif ev:
            issues.append("EVENT_WITHOUT_CURRENT_CLASSIFICATION")
        if issues and "CANONICAL_PARENT_CARDINALITY_OR_IDENTITY" in issues:
            disposition="BLOCKED_IDENTITY_CONFLICT"
        elif issues:
            disposition="BLOCKED_CANONICAL_AUTHORITY_UNVERIFIED"
        elif tips:
            disposition="ALREADY_COMMITTED_EXACT"
        elif identity["git"]["source_coverage"]!="COMPLETE":
            disposition="PENDING_SOURCE_COVERAGE_RECOVERY"
        else:
            disposition="BLOCKED_EVIDENCE_INCOMPLETE"
        results.append({
            "city_key":"kyiv", "episode_id":eid, "alert_start":identity["alert_start"], "alert_end":identity["alert_end"],
            "canonical_parent_count_for_episode_id":len(p), "canonical_exact_parent_count":len(pe),
            "canonical_parent_uids":[str(x["episode_uid"]) for x in pe],
            "classification_revisions":len(c), "classification_outside_exact_tuple":len(c0)-len(c),
            "current_tip_count":len(tips), "current_tip_uids":[str(x["classification_uid"]) for x in tips],
            "current_tip_verdicts":[str(x.get("verdict")) for x in tips],
            "classification_keys":[str(x.get("classification_key")) for x in c],
            "supersession_edges":[[str(x["classification_uid"]),str(x.get("supersedes_classification_uid"))] for x in c if x.get("supersedes_classification_uid")],
            "source_links_count":len(l),"source_link_keys":[str(x["source_link_key"]) for x in l],
            "event_count":len(ev),"event_uids":[str(x["attack_event_uid"]) for x in ev],
            "event_statuses":[x.get("event_status") for x in ev],
            "event_current_classification_uids":[x.get("current_classification_uid") for x in ev],
            "git_source_coverage":identity["git"]["source_coverage"],
            "git_matched_candidates":identity["git"]["unique_candidates_with_stored_match_or_classifier"],
            "git_final_classifier_bindings":identity["git"]["unique_candidates_with_final_classifier_binding"],
            "issues":sorted(set(issues)), "disposition":disposition
        })
    return results

def main():
    code_head = os.getenv("GITHUB_SHA") or "UNKNOWN"
    artifact_01 = {"neon_project":PROJECT,"branch_id":BRANCH,"database":DB,"approved_replica_host":REPLICA,"approved_replica_endpoint_id":"ep-calm-rice-b5073ypp","verified_endpoint_type":"read_only","separate_writer_endpoint_id":"ep-still-violet-b5bg6mhp","metadata_reverified_prior_to_execution":True,"original_writer_secret_used_only_in_memory":True,"executed_code_head":code_head,"actual_connection_verified":False}
    put("01_replica_identity_and_access.json",artifact_01)
    identities,receipt_sha = freeze_receipt()
    conn_kwargs = parse_credential()
    if conn_kwargs["host"] != REPLICA:
        fail("SOCKET_DESTINATION_NOT_ALLOWLISTED")
    import psycopg.rows
    with psycopg.connect(**conn_kwargs, autocommit=True) as conn:
        if conn.info.host != REPLICA:
            fail("ACTUAL_DRIVER_DESTINATION_NOT_REPLICA")
        with conn.cursor() as cur:
            cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            try:
                cur.execute("SET LOCAL statement_timeout = '15000ms'")
                cur.execute("SET LOCAL lock_timeout = '3000ms'")
                cur.execute("""SELECT current_database(),current_user,
                current_setting('transaction_read_only'),current_setting('default_transaction_read_only'),
                current_setting('transaction_isolation'),current_setting('statement_timeout'),
                current_setting('lock_timeout'),txid_current_snapshot()::text,
                clock_timestamp(),transaction_timestamp(),inet_server_addr()::text,inet_server_port()""")
                z=cur.fetchone()
                if z[0]!=DB or z[2]!="on" or z[4]!="repeatable read":
                    fail("READONLY_TRANSACTION_IDENTITY_GATE_FAILED")
                # Neon proxy can terminate TLS before pg_stat_ssl sees the connection.
                # Verify actual libpq client transport, not PostgreSQL backend SSL state.
                if not bool(conn.pgconn.ssl_in_use):
                    fail("REPLICA_CLIENT_TLS_NOT_PROVEN")
                artifact_01.update({"actual_connection_verified":True,"driver_actual_host":conn.info.host,"driver_port":conn.info.port,"connected_database":z[0],"connected_user":z[1],"server_address":z[10],"server_port":z[11],"ssl_in_use":True})
                put("01_replica_identity_and_access.json",artifact_01)
                a2={"snapshot_id":z[7],"utc_observed_at":fmt(z[8]),"transaction_started_at_utc":fmt(z[9]),"transaction_read_only":z[2],"default_transaction_read_only":z[3],"isolation":z[4],"statement_timeout":z[5],"lock_timeout":z[6],"query_scope":"29 frozen Kyiv identities only","sql_statement_kind":"SELECT and transaction/session controls only"}
                put("02_readonly_transaction_attestation.json",a2)
                ledger=[]
                schemaq="SELECT table_name,column_name,data_type,udt_name,is_nullable FROM information_schema.columns WHERE table_schema=%s AND table_name = ANY(%s::text[]) ORDER BY table_name, ordinal_position"
                info=execute(cur,"schema",schemaq,("public",list(TABLES)),ledger,300)
                available={t:{x["column_name"] for x in info if x["table_name"]==t} for t in TABLES}
                missing={t:sorted(set(REQUIRED[t])-available[t]) for t in TABLES if set(REQUIRED[t])-available[t]}
                if missing:
                    put("03_sql_schema_and_query_contract.json",{"columns":info,"missing_required_columns":missing,"queries":ledger})
                    fail("ACCEPTED_CANONICAL_SCHEMA_REQUIRED_COLUMNS_MISSING")
                input_ids=[x["episode_id"] for x in identities]
                tables={}
                for table in TABLES:
                    sel=[c for c in FIELDS[table] if c in available[table]]
                    if not sel:
                        fail("EMPTY_SCHEMA_SELECTION:" + table)
                    select_clause=", ".join('"' + c + '"' for c in sel)
                    if table=="alert_episodes":
                        where='city_key=%s AND legacy_episode_id::text = ANY(%s::text[])'
                        params=("kyiv",input_ids)
                    elif table=="attack_event_classifications":
                        where='city_key=%s AND historical_episode_id::text = ANY(%s::text[])'
                        params=("kyiv",input_ids)
                    elif table=="attack_events":
                        where='city_key=%s AND historical_episode_id::text = ANY(%s::text[])'
                        params=("kyiv",input_ids)
                    else:
                        cs=[x.get("classification_uid") for x in tables["attack_event_classifications"]]
                        where='classification_uid::text = ANY(%s::text[])'
                        params=(cs,)
                    query=f'SELECT {select_clause} FROM public."{table}" WHERE {where} LIMIT {CAPS[table]+1}'
                    rows=execute(cur,table,query,params,ledger,CAPS[table])
                    tables[table]=sanitize(table,rows)
                cur.execute("COMMIT")
            except BaseException:
                cur.execute("ROLLBACK")
                raise
    a3={"schema_observed":info,"selected_columns":{t:[c for c in FIELDS[t] if c in available[t]] for t in TABLES},"query_contract":ledger,"frozen_receipt_commit":RECEIPT_COMMIT,"frozen_receipt_git_blob":RECEIPT_BLOB,"frozen_receipt_sha256":receipt_sha,"source_original_commit":"92d57bbbfad60e6c09bb92372b1e84f38fa6ced4","query_caps":CAPS}
    put("03_sql_schema_and_query_contract.json",a3)
    raw={"frozen_identities":identities,"frozen_receipt_sha256":receipt_sha,"frozen_receipt_git_blob":RECEIPT_BLOB,"code_head":code_head,"neon_read_replica":REPLICA,"snapshot":a2,"tables":tables,"query_sql_hashes":ledger,"complete":True}
    put("04_canonical_readback_redacted.json",raw)
    res=reconcile(raw)
    if len(res)!=29:fail("RECONCILIATION_ROW_COUNT_INVALID")
    counts=dict(sorted(collections.Counter(x["disposition"] for x in res).items()))
    verdicts=dict(sorted(collections.Counter(v for x in res for v in x["current_tip_verdicts"]).items()))
    summary={"input_count":29,"exact_parent_count":sum(x["canonical_exact_parent_count"]==1 for x in res),"missing_exact_parent":sum(x["canonical_exact_parent_count"]==0 for x in res),"conflicted_exact_parent":sum(x["canonical_exact_parent_count"]>1 or x["canonical_parent_count_for_episode_id"]>1 for x in res),"episodes_with_classification":sum(x["classification_revisions"]>0 for x in res),"classification_revisions":sum(x["classification_revisions"] for x in res),"episodes_with_unique_current_tip":sum(x["current_tip_count"]==1 for x in res),"current_tip_verdicts":verdicts,"source_links":sum(x["source_links_count"] for x in res),"event_records":sum(x["event_count"] for x in res),"dispositions":counts}
    put("05_kyiv_29_reconciliation.json",{"summary":summary,"episodes":res})
    with (OUT/"06_kyiv_29_reconciliation.csv").open("w",newline="",encoding="utf-8") as f:
        fields=["city_key","episode_id","alert_start","alert_end","canonical_parent_count_for_episode_id","canonical_exact_parent_count","classification_revisions","current_tip_count","current_tip_verdicts","source_links_count","event_count","disposition","issues"]
        writer=csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        for row in res:
            writer.writerow({c:json.dumps(row[c],ensure_ascii=False) if isinstance(row.get(c),(list,dict)) else row.get(c) for c in fields})
    put("07_historical_vs_current.json",{"frozen_capture_at":"2026-10-11T05:56:28.255150Z","historical_diagnostic_reported":"1 classified / 28 unclassified","historical_canonical_as_of":"AS_OF_CANONICAL_STATUS_NOT_PROVEN","current_observation_utc":a2["utc_observed_at"],"current_summary":summary,"warning":"A current Neon read replica is not a historical snapshot; database creation timestamps alone do not establish absence of deleted/superseded historical rows."})
    put("08_canonical_conflicts_and_gaps.json",{"episodes_with_issues":[{"episode_id":x["episode_id"],"issues":x["issues"]} for x in res if x["issues"]],"unresolved_source_completeness":sum(x["git_source_coverage"]!="COMPLETE" for x in res),"orphan_links_audited_scope":"only linked to classifications returned for these 29 IDs; global orphan scan not authorized","remaining_gates":["independent verifier A/B","source completeness for uncommitted cases","23-city regression","queue code safety deployment acceptance"],"overall_queue_integration":"PARTIAL"})
    print("AUDIT_READBACK_COMPLETE " + json.dumps(summary,sort_keys=True))
    print("FROZEN_READBACK_SHA256 " + hash_bytes((OUT/"04_canonical_readback_redacted.json").read_bytes()))
    return summary

if __name__=="__main__":
    try:
        main()
    except BaseException as exc:
        if not (OUT/"02_readonly_transaction_attestation.json").exists():
            put("02_readonly_transaction_attestation.json",{"transaction_proven":False})
        safe_type=type(exc).__name__
        err=str(exc)
        # Never emit any credential or full database URL, even in exception strings.
        original=os.environ.get("AUDIT_SOURCE_SECRET") or ""
        if original:
            err=err.replace(original,"[REDACTED]")
            try:
                u=urlsplit(original)
                if u.password: err=err.replace(unquote(u.password),"[REDACTED]")
            except Exception:pass
        if len(err)>280:err=err[:280]
        put("00_execution_blocker.json",{"status":"KYIV LIVE REPLICA ACCESS = BLOCKED" if not (OUT/"04_canonical_readback_redacted.json").exists() else "AUDIT_INCOMPLETE","exception_class":safe_type,"reason":err,"database_writes":0,"primary_connection_attempts":0})
        print("KYIV_LIVE_29_AUDIT_BLOCKED "+safe_type+" "+err, file=sys.stderr)
        sys.exit(2)
