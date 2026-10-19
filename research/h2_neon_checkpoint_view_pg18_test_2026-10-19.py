#!/usr/bin/env python3
"""Synthetic-only independent H2 checkpoint-view PostgreSQL 18 test.

Loads the Git-frozen partial schema unchanged, applies the separate exact
view supplement, executes the pinned site-prod Phase-1 query extracted
directly from its verified Git blob, and retains unresolved Neon gates.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import runpy
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"
DSN = os.environ["H2_PG18_DSN"]
COPY = os.environ.get("H2_PG18_COPY", "A")
OUTPUT = Path(os.environ.get("H2_PG18_OUTPUT", f"/tmp/h2_view_pg18_{COPY}.json"))
BASE = "research/h2_neon_catalog_reconciliation_2026-10-18/neon_observed_partial_schema_fixture_v1.sql"
SUPPLEMENT = "research/h2_neon_current_ingestion_checkpoints_view_reconstruction_2026-10-19.sql"
PINNED = "kyiv-air-alerts-grafana/scripts/db_phase1_persistence.py"
EXPECTED_BLOBS = {
    BASE: "09f9c5a2f0c4eeddaba63e7c9c5834cce85f7ab3",
    SUPPLEMENT: "d44eda04f20034b28125bf3e94d5881ab340db5a",
    "research/h2_neon_seven_contract_catalog_completion_2026-10-19.json": "46bc8ea60c682054873c3bbf76f576f7f9c6d8c7",
    "research/h2_neon_213_contract_matrix_v6_2026-10-19.json": "6f1269c7d3134f2c3bfce2373a01641c26f10fa6",
    "research/h2_neon_schema_contract_matrix_v5_runtime_2026-10-18.json": "810fa36d0064888587ec88a0ab1380b6ef7e2a1e",
    "research/h2_neon_catalog_reconciliation_2026-10-18/neon_catalog_verified.json": "60246ffa7a436eef830592c7999c9e7dc3941123",
    "research/h2_K1K2_full_AB_reports_2026-10-19.json.xz.b64": "620d195f16ce686f92f66b3da6d702e126bc66fe",
    "research/h2_K1K2_full_AB_retention_manifest_2026-10-19.json": "40b4d4e6d53b422e73b376bcd821ae7d999ab84d",
    "research/h2_verify_K1K2_full_AB_retention_2026-10-19.py": "a2333368b8acdb4b86fdc104fad064f03cc56a97",
}
PINNED_BLOB = "ed014e61fc6186fa9daf91c763c847e7df2f0306"
VIEW = "public.current_ingestion_checkpoints"
CHECK_COLS = [
    "checkpoint_id", "source_key", "city_key", "stream_key", "checkpoint_seq",
    "checkpoint_kind", "previous_checkpoint_id", "checked_at",
    "continuity_verified", "continuity_method", "continuity_anchor_at",
    "observed_oldest_start_at", "observed_latest_end_at",
    "observed_record_count", "cursor", "metadata", "created_by_run_id", "created_at",
]
UUID_RUN = uuid.uuid5(uuid.NAMESPACE_DNS, "h2-view-pg18-synthetic-only-run")
rows_expected: dict[tuple[str, str, str], dict] = {}
recorded: list[dict] = []
checks: dict[str, str] = {}


def byte_sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def blob_sha(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()


def checkpoint(name: str, ok: bool, detail: str = "") -> None:
    if not ok:
        raise AssertionError(f"{name}: {detail}")
    checks[name] = "PASS"
    print(f"PASS {name} {detail}", flush=True)


def checkpoint_id(source: str, city: str, stream: str, seq: int) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"synthetic:{source}:{city}:{stream}:{seq}")


def apply_and_count(conn: psycopg.Connection, path: str) -> None:
    with conn.cursor() as cur:
        cur.execute((ROOT / path).read_text(encoding="utf-8"))


def structural(conn: psycopg.Connection):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT c.relname,c.relkind FROM pg_class c JOIN pg_namespace n
              ON c.relnamespace=n.oid WHERE n.nspname='public'
              AND c.relkind IN ('r','v') ORDER BY c.relname
        """)
        relations = dict(cur.fetchall())
        cur.execute("""
            SELECT count(*) FROM pg_attribute a JOIN pg_class c ON a.attrelid=c.oid
            JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname='public'
            AND c.relkind='r' AND a.attnum>0 AND NOT a.attisdropped
        """)
        columns = cur.fetchone()[0]
        cur.execute("""
            SELECT count(*) FROM pg_constraint co JOIN pg_class c ON co.conrelid=c.oid
            JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname='public'
            AND c.relkind='r'
        """)
        constraints = cur.fetchone()[0]
        cur.execute("SELECT indexname,indexdef FROM pg_indexes WHERE schemaname='public' ORDER BY indexname")
        indexes = cur.fetchall()
        cur.execute("""
            SELECT count(*) FROM pg_trigger t JOIN pg_class c ON t.tgrelid=c.oid
            JOIN pg_namespace n ON c.relnamespace=n.oid
            WHERE n.nspname='public' AND NOT t.tgisinternal
        """)
        triggers = cur.fetchone()[0]
        cur.execute("""
            SELECT count(*) FROM pg_policies WHERE schemaname='public'
        """)
        policies = cur.fetchone()[0]
    return {"relations": relations, "table_columns": columns, "constraints": constraints,
            "indexes": indexes, "user_triggers": triggers, "policies": policies}


def read_checkpoint(conn: psycopg.Connection, sql: str, identity: tuple[str, str, str]):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(sql, identity)
        return cur.fetchone()


def add_cp(conn: psycopg.Connection, identity: tuple[str, str, str], seq: int,
           previous: uuid.UUID | None, dt: int, optional: bool = False):
    source, city, stream = identity
    uid = checkpoint_id(source, city, stream, seq)
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO public.ingestion_checkpoints
            (checkpoint_id,source_key,city_key,stream_key,checkpoint_seq,checkpoint_kind,
             previous_checkpoint_id,checked_at,continuity_verified,continuity_method,
             observed_record_count,cursor,metadata,created_by_run_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            RETURNING checkpoint_id
        """, (uid,source,city,stream,seq,"bootstrap" if seq==1 else "poll",
              previous,datetime(2026,1,dt,tzinfo=timezone.utc),
              not optional, None if optional else "synthetic",
              None if optional else seq,
              None if optional else Jsonb({"seq": seq}),Jsonb({"synthetic": True}),UUID_RUN))
        assert cur.fetchone()[0] == uid
    rows_expected[identity] = {"checkpoint_id": uid, "checkpoint_seq": seq}
    recorded.append({"source_key": source, "city_key": city, "stream_key": stream,
                     "checkpoint_seq": seq, "checkpoint_id": str(uid)})
    return uid


def check_expected(conn, sql):
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {VIEW}")
        assert cur.fetchone()[0] == len(rows_expected)
    for identity, expected in rows_expected.items():
        obj = read_checkpoint(conn, sql, identity)
        assert obj is not None, identity
        assert list(obj) == CHECK_COLS
        assert obj["checkpoint_id"] == expected["checkpoint_id"], identity
        assert obj["checkpoint_seq"] == expected["checkpoint_seq"], identity
        assert (obj["source_key"],obj["city_key"],obj["stream_key"]) == identity
    return True


def must_fail(conn, query, params=(), expected_codes=None):
    try:
        with conn.cursor() as cur:
            cur.execute(query, params)
            cur.fetchone() if cur.description else None
    except psycopg.Error as exc:
        if expected_codes and exc.sqlstate not in expected_codes:
            raise AssertionError(f"unexpected SQLSTATE {exc.sqlstate} for {query[:65]}") from exc
        return exc.sqlstate
    raise AssertionError(f"expected failure: {query[:120]}")


def main() -> None:
    outcome = {
        "kind": "H2_PG18_VIEW_SCHEMA_PARITY_SYNTHETIC_ONLY",
        "copy": COPY,
        "verdict": "IN_PROGRESS",
        "expected_predecessor": "b7d395a2363aa51fa283489738cdc7a88f5af252",
        "pinned_phase1_blob": PINNED_BLOB,
        "frozen_inputs": EXPECTED_BLOBS,
        "checks": checks,
        "neon_connections": 0, "neon_writes": 0, "production_writes": 0,
        "boundary": "Not actual Neon role, no operational run or cutover",
    }
    try:
        _run(outcome)
        outcome["verdict"] = "PASS_PG18_OFFLINE_TARGETED"
    except Exception as exc:
        outcome["verdict"] = "FAIL"
        outcome["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        outcome["synthetic_checkpoint_rows"] = recorded
        outcome["checks"] = checks
        OUTPUT.write_text(json.dumps(outcome, indent=2, sort_keys=True, default=str) + "\n")
        print("RESULT", outcome["verdict"], OUTPUT, flush=True)


def _run(o: dict) -> None:
    for path, sha in EXPECTED_BLOBS.items():
        raw = (ROOT/path).read_bytes()
        assert blob_sha(raw) == sha, (path, sha, blob_sha(raw))
    checkpoint("FROZEN_GIT_BLOBS", True, str(len(EXPECTED_BLOBS)))

    retention = runpy.run_path(str(RESEARCH/"h2_verify_K1K2_full_AB_retention_2026-10-19.py"))
    raw = (RESEARCH/"h2_K1K2_full_AB_reports_2026-10-19.json.xz.b64").read_bytes()
    manifest = json.loads((RESEARCH/"h2_K1K2_full_AB_retention_manifest_2026-10-19.json").read_bytes())
    members = retention["verify"](raw, manifest)
    neg = retention["negatives"](raw, manifest)
    checkpoint("K1K2_EIGHT_RAW_MEMBERS_AND_THREE_NEGATIVES", len(members)==8 and len(neg)==3)
    o["archive"] = {"verified_members": members, "negatives": neg,
                    "archive_sha256": byte_sha(raw), "source_run": 39212648444,
                    "source_commit": "edb3faa5e5e3fd303db357d5b2fd01b236fe255c",
                    "K2_limit": "DB UNIQUE plus ON CONFLICT DO NOTHING, not application rejection"}

    v5 = json.loads((ROOT/"research/h2_neon_schema_contract_matrix_v5_runtime_2026-10-18.json").read_text())
    v6 = json.loads((ROOT/"research/h2_neon_213_contract_matrix_v6_2026-10-19.json").read_text())
    pairs = list(zip(v5["matrix"],v6["matrix"]))
    assert len(pairs)==213 and len(v5["matrix"])==len(v6["matrix"])==213
    for i,(old,new) in enumerate(pairs, 1):
        assert old["original_ordinal"]==new["original_ordinal"]==i
        assert old["object"]==new["object"]
        assert old["application_requirement"]==new["application_requirement"]
        assert old["match_status"]==new["match_status"]
    counted = {s:sum(row["match_status"]==s for row in v6["matrix"])
               for s in ("MATCH","MISMATCH","UNVERIFIED")}
    checkpoint("V5_V6_ALL_213_UNCHANGED", counted=={"MATCH":203,"MISMATCH":3,"UNVERIFIED":7})
    o["matrix_counts"] = counted
    o["matrix_reconciliation"] = "v7 not justified by offline subclaim test; U1-U7 stay UNVERIFIED"

    capture = json.loads((ROOT/"research/h2_neon_seven_contract_catalog_completion_2026-10-19.json").read_text())
    catalog = json.loads((ROOT/"research/h2_neon_catalog_reconciliation_2026-10-18/neon_catalog_verified.json").read_text())
    supplemental = (ROOT/SUPPLEMENT).read_text()
    actual_body = supplemental.split("CREATE VIEW public.current_ingestion_checkpoints AS\n",1)[1].split("\n-- Catalog-specified owner",1)[0].strip()
    canonical_body = capture["contracts"]["U2"]["view_definition"].strip()
    checkpoint("VIEW_DDL_EQUALS_CAPTURED_DEFINITION",
               actual_body.replace("public.ingestion_checkpoints","ingestion_checkpoints") == canonical_body)
    expected_view = [x for x in catalog["catalog"]["columns"]
                     if x["table"]=="current_ingestion_checkpoints"]
    checkpoint("FROZEN_VIEW_CATALOG_18",len(expected_view)==18 and
               [x["name"] for x in expected_view]==CHECK_COLS)
    for key in ("U1","U2","U3","U4","U5","U6","U7"):
        assert capture["contracts"][key]["status"]=="UNVERIFIED"
    checkpoint("U1_U7_RUNTIME_REMAINS_UNVERIFIED", True)

    pinned = subprocess.check_output(["git","show", "origin/site-prod:"+PINNED], cwd=ROOT)
    checkpoint("PINNED_SITEPROD_PHASE1_SOURCE", blob_sha(pinned)==PINNED_BLOB)
    source = ast.parse(pinned.decode())
    fn = next(node for node in source.body if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef))
              and node.name=="read_current_checkpoint")
    call = next(node for node in ast.walk(fn) if isinstance(node, ast.Call)
                and isinstance(node.func,ast.Attribute) and node.func.attr=="execute"
                and node.args and isinstance(node.args[0],ast.Constant))
    sql = call.args[0].value
    checkpoint("ACTUAL_PINNED_SQL_EXTRACTED", "/* PHASE1:CHECKPOINT_REREAD */" in sql
               and "FROM current_ingestion_checkpoints" in sql and sql.count("%s")==3
               and all(k in sql for k in CHECK_COLS))
    o["phase1_sql_sha256"] = byte_sha(sql.encode())
    o["phase1_query_origin"] = "site-prod pinned db_phase1_persistence.py ast.FunctionDef read_current_checkpoint"

    with psycopg.connect(DSN,autocommit=True) as db:
        with db.cursor() as cur:
            cur.execute("SHOW server_version")
            vers = cur.fetchone()[0]
            cur.execute("SHOW server_version_num")
            vers_num = int(cur.fetchone()[0])
        checkpoint("REAL_POSTGRESQL_18", vers_num//10000==18, vers)
        o["postgres_version"] = vers
        apply_and_count(db,BASE)
        before = structural(db)
        checkpoint("SEVEN_TABLES_167_COLUMNS_221_CONSTRAINTS_30_INDEXES",
                   len(before["relations"])==7 and all(v=="r" for v in before["relations"].values())
                   and before["table_columns"]==167 and before["constraints"]==221
                   and len(before["indexes"])==30 and before["user_triggers"]==before["policies"]==0)
        checkpoint("EMPTY_BEFORE_VIEW", "current_ingestion_checkpoints" not in before["relations"])
        apply_and_count(db,SUPPLEMENT)
        after = structural(db)
        checkpoint("VIEW_ADDED_WITH_NO_SCHEMA_MUTATION",len(after["relations"])==8
                   and after["relations"].get("current_ingestion_checkpoints")=="v"
                   and len([v for v in after["relations"].values() if v=="r"])==7
                   and before["indexes"]==after["indexes"]
                   and before["constraints"]==after["constraints"]
                   and before["table_columns"]==after["table_columns"]
                   and after["user_triggers"]==after["policies"]==0)
        with db.cursor() as cur:
            cur.execute("""
                SELECT a.attname, format_type(a.atttypid,a.atttypmod)
                FROM pg_attribute a WHERE a.attrelid='public.current_ingestion_checkpoints'::regclass
                AND a.attnum>0 AND NOT a.attisdropped ORDER BY a.attnum
            """)
            actual = cur.fetchall()
            cur.execute("SELECT pg_get_viewdef('public.current_ingestion_checkpoints'::regclass,true)")
            view_def = cur.fetchone()[0]
        checkpoint("VIEW_18_EXACT_NAME_TYPES",actual==
                   [(x["name"],x["type"]) for x in expected_view])
        checkpoint("DISTINCT_ON_SEQ_DESC_VIEW", "DISTINCT ON" in view_def and
                   "checkpoint_seq DESC" in view_def)
        o["view_columns"] = [[name, typ] for name,typ in actual]
        checkpoint("PINNED_PHASE1_EMPTY_READ",read_checkpoint(db,sql,("s1","kyiv","alerts")) is None)

        with db.cursor() as cur:
            cur.execute("""INSERT INTO public.ingestion_runs
                (run_id,run_kind,schema_version,status,started_at)
                VALUES (%s,'synthetic_only','h2_pg18_test','running',%s)
            """, (UUID_RUN,datetime(2026,1,1,tzinfo=timezone.utc)))
        a=("source_a","kyiv","alerts")
        b=("source_a","lviv","alerts")
        c=("source_b","kyiv","alerts")
        d=("source_a","kyiv","explosions")
        e=("source_b","lviv","alerts")
        a1=add_cp(db,a,1,None,10)
        checkpoint("SINGLE_SOURCE_CITY_STREAM",check_expected(db,sql))
        a2=add_cp(db,a,2,a1,8)
        a3=add_cp(db,a,3,a2,1)
        checkpoint("LATEST_SEQ_NOT_LATEST_CHECKED_AT",check_expected(db,sql) and
                   read_checkpoint(db,sql,a)["checked_at"].day==1)
        b1=add_cp(db,b,1,None,2)
        b2=add_cp(db,b,2,b1,3)
        c1=add_cp(db,c,1,None,4)
        d1=add_cp(db,d,1,None,5)
        e1=add_cp(db,e,1,None,6,optional=True)
        checkpoint("CROSS_SOURCE_CITY_STREAM_ISOLATION",check_expected(db,sql))
        null_row=read_checkpoint(db,sql,e)
        checkpoint("PERMITTED_NULL_OPTIONAL_FIELDS",
                   null_row["cursor"] is None and null_row["continuity_method"] is None
                   and null_row["observed_record_count"] is None)

        with psycopg.connect(DSN,autocommit=True) as other:
            with other.cursor() as cur:
                cur.execute("BEGIN")
                state=must_fail(other,"""INSERT INTO public.ingestion_checkpoints
                    (checkpoint_id,source_key,city_key,stream_key,checkpoint_seq,
                     checkpoint_kind,previous_checkpoint_id,checked_at,created_by_run_id)
                    VALUES (%s,%s,%s,%s,3,'poll',%s,%s,%s)""",
                    (uuid.uuid5(uuid.NAMESPACE_DNS,"deliberate-duplicate"),*a,a2,
                     datetime(2026,1,20,tzinfo=timezone.utc),UUID_RUN),{"23505"})
                cur.execute("ROLLBACK")
        checkpoint("SEQ_TIES_FORBIDDEN_BY_ACTUAL_UNIQUE_INDEX",state=="23505"
                   and check_expected(db,sql))
        with db.cursor() as cur:
            cur.execute("CREATE ROLE h2_synthetic_app NOLOGIN")
            cur.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
            cur.execute("GRANT USAGE ON SCHEMA public TO h2_synthetic_app")
            cur.execute("GRANT SELECT ON public.current_ingestion_checkpoints TO h2_synthetic_app")
            cur.execute("SET ROLE h2_synthetic_app")
            cur.execute('SET search_path TO "$user", public')
            checkpoint("LEAST_PRIVILEGE_PINNED_VIEW_SELECT",check_expected(db,sql))
            state=must_fail(db,"SELECT count(*) FROM public.ingestion_checkpoints",expected_codes={"42501"})
            checkpoint("UNDERLYING_TABLE_DENIED_FOR_VIEW_READER",state=="42501")
            state=must_fail(db,"INSERT INTO public.ingestion_checkpoints DEFAULT VALUES",expected_codes={"42501"})
            checkpoint("UNGRANTED_INSERT_DENIED",state=="42501")
            cur.execute("SELECT pg_catalog.hashtextextended('only-synthetic',0), pg_catalog.gen_random_uuid()")
            checkpoint("BUILTIN_FUNCTION_RESOLUTION",cur.fetchone()[1] is not None)
            cur.execute("BEGIN")
            cur.execute("SELECT pg_catalog.pg_advisory_xact_lock(123456789)")
            cur.execute("ROLLBACK")
            checkpoint("LOCAL_ADVISORY_XACT_LOCK_BINDING",True)
            cur.execute("RESET ROLE")
            cur.execute("REVOKE SELECT ON public.current_ingestion_checkpoints FROM h2_synthetic_app")
            cur.execute("SET ROLE h2_synthetic_app")
            state=must_fail(db,"SELECT checkpoint_seq FROM public.current_ingestion_checkpoints",
                            expected_codes={"42501"})
            checkpoint("VIEW_SELECT_DENIED_WHEN_UNGRANTED",state=="42501")
            cur.execute("RESET ROLE")
            cur.execute("GRANT SELECT ON public.current_ingestion_checkpoints TO h2_synthetic_app")
            cur.execute("REVOKE USAGE ON SCHEMA public FROM h2_synthetic_app")
            cur.execute("SET ROLE h2_synthetic_app")
            state=must_fail(db,"SELECT checkpoint_seq FROM public.current_ingestion_checkpoints",
                            expected_codes={"42501","42P01"})
            checkpoint("SCHEMA_USAGE_REQUIRED",state in {"42501","42P01"})
            cur.execute("RESET ROLE")
            cur.execute("GRANT USAGE ON SCHEMA public TO h2_synthetic_app")
            checkpoint("GRANTS_RESTORED_SYNTHETIC_ONLY",check_expected(db,sql))

        with psycopg.connect(DSN,autocommit=True) as snap, psycopg.connect(DSN,autocommit=True) as writer:
            with snap.cursor() as cur:
                cur.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                seen=read_checkpoint(snap,sql,a)["checkpoint_seq"]
                a4=add_cp(writer,a,4,a3,11)
                same=read_checkpoint(snap,sql,a)["checkpoint_seq"]
                cur.execute("COMMIT")
                now=read_checkpoint(snap,sql,a)["checkpoint_seq"]
            checkpoint("REPEATABLE_READ_READ_ONLY_SNAPSHOT",seen==same==3 and now==4)
            with snap.cursor() as cur:
                cur.execute("BEGIN TRANSACTION ISOLATION LEVEL READ COMMITTED READ ONLY")
                first=read_checkpoint(snap,sql,a)["checkpoint_seq"]
                a5=add_cp(writer,a,5,a4,12)
                second=read_checkpoint(snap,sql,a)["checkpoint_seq"]
                cur.execute("COMMIT")
            checkpoint("READ_COMMITTED_READ_ONLY_REFRESH",first==4 and second==5)
            with writer.cursor() as cur:
                cur.execute("BEGIN")
                add_cp(writer,("rollback","test","stream"),1,None,13)
                cur.execute("ROLLBACK")
            rows_expected.pop(("rollback","test","stream"))
            checkpoint("ROLLBACK_NO_CHECKPOINT",read_checkpoint(db,sql,("rollback","test","stream")) is None)
        checkpoint("FINAL_PINNED_QUERY_ALL_IDENTITIES",check_expected(db,sql))

        final_schema=structural(db)
        checkpoint("NO_ADDITIONAL_TABLE_INDEX_CONSTRAINT_TRIGGER_POLICY",
                   after["relations"]==final_schema["relations"] and after["indexes"]==final_schema["indexes"]
                   and after["constraints"]==final_schema["constraints"]
                   and final_schema["user_triggers"]==final_schema["policies"]==0)
        index_names=[n for n,_ in after["indexes"]]
        checkpoint("THREE_DB_GUARANTEES_STILL_MISSING",
                   not any("supersedes_classification_uid" in definition and "UNIQUE INDEX" in definition
                           for _,definition in after["indexes"])
                   and not any("current_tip" in x for x in index_names)
                   and final_schema["user_triggers"]==0)
        o["schema"] = {"tables":7,"table_columns":167,"constraints":221,"indexes":30,
                        "views":1,"view_columns":18,"user_triggers":0,"policies":0,
                        "db_revision_enforcement_mismatches":3}
        o["synthetic_role"] = "Modeled least privilege only; actual Neon role unverified"
        o["transaction_scope"] = "Read-only snapshots and local rollback; not Neon durability"

if __name__=="__main__":
    main()
