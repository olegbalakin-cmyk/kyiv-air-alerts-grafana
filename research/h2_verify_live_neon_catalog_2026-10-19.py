#!/usr/bin/env python3
"""Git-only H2 Neon catalog byte/invariant verification. No database or network calls."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAW = "h2_live_neon_catalog_readonly_response_2026-10-19.json"
SQL = "h2_neon_catalog_queries_2026-10-19.sql"
V5 = "h2_neon_schema_contract_matrix_v5_runtime_2026-10-18.json"
V6 = "h2_neon_213_contract_matrix_v6_2026-10-19.json"
ROLE = "h2_live_neon_runtime_role_attribution_2026-10-19.json"
MAP = "h2_live_neon_catalog_statement_map_2026-10-19.json"
VIEW = "h2_neon_current_ingestion_checkpoints_view_reconstruction_2026-10-19.sql"
RAW_SHA256 = "60d829053bb7d7e9a734c12c154b6db5552cdc558b60105babbecdbec0d3e624"
RAW_SHA1 = "e550b35578283b2af4e0e8fba956e98c4bcc0f03"
SQL_SHA256 = "eac52ff8dd6628d322dfc71e94a1ec0a053ed4c55ac3867dd85228d233be1d26"
EXPECTED_COUNTS = {"MATCH": 203, "MISMATCH": 3, "UNVERIFIED": 7}
OPEN = {183, 190, 206, 210, 211, 212, 213}
GAPS = {193, 196, 197}


def ensure(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def check_hashes(raw: bytes, sql: bytes | None) -> None:
    ensure(len(raw) == 60689 and digest(raw) == RAW_SHA256, "raw SHA-256/length")
    ensure(
        hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        == RAW_SHA1,
        "Git blob SHA-1",
    )
    if sql is not None:
        ensure(len(sql) == 10389 and digest(sql) == SQL_SHA256, "SQL SHA-256/length")
        ensure(sql.endswith(b"\n"), "SQL final newline")
    lower = raw.lower()
    for marker in (b"postgresql://", b"postgres://", b"password=", b"bearer ", b"begin private key", b"token="):
        ensure(marker not in lower, "raw unexpected credential marker")


def statements(sql: str) -> list[str]:
    chunks = re.split(r";\s*\n", sql)
    output = []
    for chunk in chunks:
        no_comments = re.sub(r"(?m)^\s*--[^\n]*(?:\n|$)", "", chunk).strip()
        if no_comments:
            output.append(no_comments)
    return output


def check_semantics(
    response: list, sql_text: str | None, original: dict, candidate: dict, role: dict, view_sql: str
) -> dict:
    ensure(isinstance(response, list) and len(response) == 19, "19-result outer array")
    qs = statements(sql_text) if sql_text is not None else None
    if qs is not None:
        ensure(len(qs) == 19, "19 exact SQL statements")
    if qs is not None:
        ensure(qs[:3] == [
        "SET TRANSACTION READ ONLY",
        "SET LOCAL statement_timeout = '15s'",
        "SET LOCAL lock_timeout = '5s'",
    ], "read-only SET sequence")
        ensure(all(re.match(r"(?is)^SELECT\b", q) for q in qs[3:]), "16 SELECT-only statements")
    ensure(all(response[i] == [] for i in range(3)), "three empty SET results")

    # Independently identify all 16 SELECTs by catalog target and returned schema.
    required_tokens = [
        ("current_database()",),
        ("pg_constraint", "alert_episodes"),
        ("pg_index", "alert_episodes"),
        ("pg_get_viewdef", "current_ingestion_checkpoints"),
        ("pg_depend", "current_ingestion_checkpoints"),
        ("pg_roles",),
        ("pg_auth_members",),
        ("has_table_privilege",),
        ("has_function_privilege",),
        ("pg_settings",),
        ("pg_constraint", "condeferrable"),
        ("pg_extension",),
        ("current_schemas(true)",),
        ("pg_db_role_setting",),
        ("pg_index", "attack_event_classifications"),
        ("pg_constraint", "attack_event_classifications"),
    ]
    # SQL spellings are stable in the original hash-bound source.
    if qs is not None:
        for i, tokens in enumerate(required_tokens, 3):
            for token in tokens:
                ensure(token.lower() in qs[i].lower(), f"SQL select mapping {i + 1}: {token}")
    expected_fields = [
        {"database_name", "effective_role", "session_role", "transaction_read_only", "transaction_isolation", "statement_timeout", "lock_timeout", "server_version"},
        {"conname", "contype", "condeferrable", "definition"},
        {"index_name", "indisunique", "index_definition", "predicate"},
        {"relname", "view_definition", "view_columns", "view_owner"},
        {"dependent_schema", "dependent_relation", "dependent_column_number"},
        {"rolname", "rolcanlogin", "rolinherit"},
        {"member_role", "granted_role", "inherit_option"},
        {"rolname", "object_name", "schema_usage", "can_select", "can_insert"},
        {"rolname", "function_schema", "proname", "identity_arguments", "can_execute"},
        {"name", "setting", "source"},
        {"nspname", "relname", "conname", "condeferrable"},
        {"extname", "extversion", "extension_schema"},
        {"configured_session_search_path", "effective_session_schemas"},
        set(),  # zero role/database overrides, identified from hash-bound SQL
        {"index_name", "indisunique", "index_definition"},
        {"conname", "contype", "definition"},
    ]
    for i, keys in enumerate(expected_fields, 3):
        ensure(isinstance(response[i], list), f"SELECT result {i + 1} array")
        if keys:
            ensure(response[i] and keys.issubset(response[i][0]), f"SELECT result {i + 1} field mapping")
        else:
            ensure(response[i] == [], "role/database overrides absent")
    ensure(all(isinstance(row, dict) for part in response[3:] for row in part), "catalog rows only")
    s = response[3][0]
    ensure(s["database_name"] == "neondb", "database identity")
    ensure(s["effective_role"] == s["session_role"] == "neondb_owner", "catalog role identity")
    ensure(s["transaction_read_only"] == "on" and s["transaction_isolation"] == "read committed", "tx identity")
    ensure(s["statement_timeout"] == "15s" and s["lock_timeout"] == "5s", "tx timeouts")
    ensure(s["server_version"].startswith("18.6"), "PostgreSQL 18.6")

    constraints = response[4]
    indexes = response[5]
    ensure(any(x["contype"] == "p" and "episode_uid" in x["definition"] for x in constraints), "U1 episode PK")
    ensure(any(x["contype"] == "u" and "legacy_episode_id" in x["definition"] for x in constraints), "U1 legacy unique")
    ensure(any(x["contype"] == "u" and "city_key, alert_type, start_at, end_at" in x["definition"] for x in constraints), "U1 interval unique")
    ensure(any(x["indisunique"] and "WHERE (end_at IS NULL)" in x["index_definition"] for x in indexes), "U1 open interval partial unique")
    ensure(not any(x["contype"] == "x" for x in constraints), "U1 no observed exclusion constraint")

    view = response[6][0]
    cols = view["view_columns"]
    ensure(view["relkind"] == "v" and view["view_owner"] == "neondb_owner", "U2 view owner")
    ensure(len(cols) == 18 and [x["position"] for x in cols] == list(range(1, 19)), "U2 18 ordered columns")
    ensure([x["name"] for x in cols] == [
        "checkpoint_id", "source_key", "city_key", "stream_key", "checkpoint_seq",
        "checkpoint_kind", "previous_checkpoint_id", "checked_at",
        "continuity_verified", "continuity_method", "continuity_anchor_at",
        "observed_oldest_start_at", "observed_latest_end_at",
        "observed_record_count", "cursor", "metadata", "created_by_run_id", "created_at",
    ], "U2 exact column names")
    actual = view["view_definition"]
    ensure("DISTINCT ON (source_key, city_key, stream_key)" in actual and
           "checkpoint_seq DESC" in actual, "U2 view selection and ordering")
    ensure(len(response[7]) == 18 and
           all(x["dependent_relation"] == "ingestion_checkpoints" for x in response[7]), "U2 18 underlying column dependencies")
    match = re.search(r"(?is)\bCREATE VIEW\s+public\.current_ingestion_checkpoints\s+AS\s*(SELECT.*?;)", view_sql)
    ensure(match is not None, "U2 synthetic reconstructed view")
    norm = lambda x: re.sub(r"\s+", " ", x.replace("public.ingestion_checkpoints", "ingestion_checkpoints")).strip().lower()
    ensure(norm(actual) == norm(match.group(1)), "U2 actual vs synthetic SQL semantic text")
    ensure("public.ingestion_checkpoints" in match.group(1) and
           "FROM ingestion_checkpoints" in actual, "U2 explicit qualification difference")

    roles = {x["rolname"]: x for x in response[8]}
    ensure("neondb_owner" in roles and roles["neondb_owner"]["rolcanlogin"], "U3 owner role")
    ensure(any(x["member_role"] == "neondb_owner" and x["granted_role"] == "neon_superuser" for x in response[9]), "U3 role inheritance")
    grants = response[10]
    ensure(len(grants) == 24 and
           all(x["schema_usage"] and x["can_select"] for x in grants), "U3 observed grants")
    ensure(all(x["object_owner"] == "neondb_owner" for x in grants), "U3 observed object owner")
    ensure(role["verdict"] == "H2 ACTUAL RUNTIME SQL ROLE = UNVERIFIED", "U3 actual runtime role NOT established")
    ensure(role["catalog_session_role"] == "neondb_owner" and
           role["credential_inspection_performed"] is False, "U3 role evidence boundary")

    functions = response[11]
    for name, args in (("gen_random_uuid", ""), ("hashtextextended", "text, bigint"),
                       ("pg_advisory_xact_lock", "bigint")):
        ensure(any(x["rolname"] == "neondb_owner" and
                   x["function_schema"] == "pg_catalog" and
                   x["proname"] == name and
                   x["identity_arguments"] == args and x["can_execute"]
                   for x in functions), f"U4 function {name}")
    ensure(not any(x["condeferrable"] or x["condeferred"] for x in response[13]), "U5 observed non-deferrable constraints")
    ensure(len(response[13]) == 134, "U5 full constraint deferrability result count")
    setting = {x["name"]: x["setting"] for x in response[12]}
    ensure(setting["default_transaction_read_only"] == "off" and
           setting["transaction_read_only"] == "on", "U5 session versus database default")
    ensure(setting["statement_timeout"] == "15000" and setting["lock_timeout"] == "5000", "U5 millisecond timeouts")
    ensure(len(response[14]) == 1 and response[14][0]["extname"] == "plpgsql", "U6 installed extension")
    ensure(response[15][0]["configured_session_search_path"] == '"$user", public', "U6 session path")
    ensure(response[15][0]["effective_session_schemas"] == "{pg_catalog,public}", "U6 schemas")
    ensure(response[16] == [], "U6 no catalog role/database overrides")

    ux = response[17]
    uc = response[18]
    ensure(any(x["indisunique"] and "(classification_key)" in x["index_definition"] for x in ux), "U7 classification key unique")
    ensure(not any(x["indisunique"] and "(supersedes_classification_uid)" in x["index_definition"] for x in ux), "U7 missing unique successor")
    ensure(any(x["contype"] == "f" and "supersedes_classification_uid" in x["definition"] for x in uc), "U7 supersedes FK not UNIQUE")
    ensure(not any(x["contype"] == "u" and "supersedes_classification_uid" in x["definition"] for x in uc), "U7 no successor constraint")
    ensure(any(x["can_update"] and x["can_delete"] and
               x["rolname"] == "neondb_owner" and x["object_name"] == "attack_event_classifications"
               for x in grants), "U7 owner can update/delete")
    ensure(len(ux) == 5 and len(uc) == 5, "U7 exactly observed indexes and constraints")

    a, b = original["matrix"], candidate["matrix"]
    ensure(len(a) == len(b) == 213, "matrix 213 original rows")
    ensure([x["original_ordinal"] for x in a] == list(range(1, 214)), "matrix exact ordinals")
    for x, y in zip(a, b):
        ensure(all(x[k] == y[k] for k in
            ("original_ordinal", "object", "application_requirement", "match_status")), "matrix identity/status frozen")
    count = {t: sum(x["match_status"] == t for x in a) for t in EXPECTED_COUNTS}
    ensure(count == EXPECTED_COUNTS, "203/3/7 matrix counts")
    ensure({x["original_ordinal"] for x in a if x["match_status"] == "UNVERIFIED"} == OPEN, "seven open contract ordinals")
    ensure({x["original_ordinal"] for x in a if x["match_status"] == "MISMATCH"} == GAPS, "three original DB invariant gaps")
    ensure(candidate["source_v5_blob"] == "810fa36d0064888587ec88a0ab1380b6ef7e2a1e", "v6 original matrix provenance")
    return {"raw_sha256": RAW_SHA256, "sql_sha256": SQL_SHA256,
            "catalog_statements": 19, "selects": 16, "contracts": "7 catalog-inspected; runtime open",
            "matrix": count, "app_role": "UNVERIFIED", "db_gaps": sorted(GAPS)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    raw = (BASE / RAW).read_bytes()
    # The exact source SQL was independently hash-verified from the Project Library.
    # Its raw bytes could not be materialized for this Git-only archive.
    sql = (BASE / SQL).read_bytes() if (BASE / SQL).exists() else None
    check_hashes(raw, sql)
    response = json.loads(raw)
    sql_text = sql.decode("utf-8") if sql is not None else None
    original = json.loads((BASE / V5).read_bytes())
    candidate = json.loads((BASE / V6).read_bytes())
    role = json.loads((BASE / ROLE).read_bytes())
    source_map = json.loads((BASE / MAP).read_bytes())
    ensure(source_map["source_sql"]["sha256"] == SQL_SHA256, "statement map source SQL digest")
    ensure(source_map["response"]["sha256"] == RAW_SHA256, "statement map source response digest")
    ensure(len(source_map["mapping"]) == 19, "statement map 19 slots")
    for i, row in enumerate(source_map["mapping"]):
        ensure(row["statement_ordinal"] == i + 1, "statement map ordinal")
        ensure(row["type"] == ("SET" if i < 3 else "SELECT"), "statement map query type")
        ensure(row["returned_rows"] == len(response[i]), "statement map row count")
        ensure(row["returned_fieldnames"] == sorted(set().union(*(set(rec) for rec in response[i]))), "statement map field signature")
    view_sql = (BASE / VIEW).read_text("utf-8")
    report = check_semantics(response, sql_text, original, candidate, role, view_sql)
    report["source_sql_byte_check_in_this_run"] = "PASS" if sql is not None else "NOT REPEATABLE: source SQL not Git-retained"
    if args.self_test:
        # The following negative tests intentionally corrupt in-memory inputs;
        # they cannot mutate the committed source bytes or database.
        failures_rejected = []
        def rejects(label, func):
            try:
                func()
            except (AssertionError, ValueError, UnicodeDecodeError):
                failures_rejected.append(label)
            else:
                raise AssertionError("tampering undetected: " + label)
        rejects("raw flipped byte", lambda: check_hashes(raw[:-2] + b"X" + raw[-1:], sql))
        if sql is not None:
            rejects("SQL changed byte", lambda: check_hashes(raw, sql[:-1] + b"X"))
        else:
            rejects("raw truncated", lambda: check_hashes(raw[:-1], None))
        t = copy.deepcopy(response)
        t[3][0]["transaction_read_only"] = "off"
        rejects("forged writable session", lambda: check_semantics(t, sql_text, original, candidate, role, view_sql))
        t = copy.deepcopy(response)
        t[6][0]["view_definition"] = t[6][0]["view_definition"].replace("checkpoint_seq DESC", "checked_at DESC")
        rejects("forged checkpoint view ordering", lambda: check_semantics(t, sql_text, original, candidate, role, view_sql))
        t = copy.deepcopy(response)
        t[17] = [x for x in t[17] if "classification_key_key" not in x["index_name"]]
        rejects("missing classification unique", lambda: check_semantics(t, sql_text, original, candidate, role, view_sql))
        t = copy.deepcopy(candidate)
        t["matrix"][192]["match_status"] = "MATCH"
        rejects("forged database invariant status", lambda: check_semantics(response, sql_text, original, t, role, view_sql))
        t = copy.deepcopy(role)
        t["verdict"] = "H2 ACTUAL RUNTIME SQL ROLE = VERIFIED"
        rejects("unsupported runtime role attribution", lambda: check_semantics(response, sql_text, original, candidate, t, view_sql))
        report["corruption_controls_rejected"] = failures_rejected
        ensure(len(failures_rejected) == 7, "all seven tampering controls")
    print(json.dumps({"verdict": "PASS GIT-ONLY", **report}, sort_keys=True))


if __name__ == "__main__":
    main()
