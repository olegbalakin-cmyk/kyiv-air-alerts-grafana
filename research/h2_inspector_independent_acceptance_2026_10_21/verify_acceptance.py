#!/usr/bin/env python3
"""Independently pinned, offline-only acceptance audit for two H2 package candidates.
No database driver, network call, credential or Neon access. Python stdlib only.
Tests dangerous SQL as TEXT, never by sending it to a database.
"""
import copy
import hashlib
import importlib.util
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BROOT = ROOT / "_candidate_b_readonly"
SOURCE_A = "a4f30691d89a4206b910b8dfde5dac44aee0ed99"
SOURCE_B = "827e843b7fb40d84b79091ed0985bfc5091c0249"
A_BLOBS = {
    "H2_INSPECTOR_INDEPENDENT_REVIEW.json": "e970659e1657d51be028f26ea5b17a420ba456df",
    "H2_INSPECTOR_NEGATIVE_CONTROLS.json": "b43a535e153876fc76902455ec8c8411ba34151f",
    "H2_INSPECTOR_PREFLIGHT_VERIFICATION.md": "b46b3abe3de4ccb8c37f97ea1e87345503ab0851",
    "H2_INSPECTOR_TARGET_AND_ROLE.md": "82c4f02f165d1bd26efb0af17d51f6864c6fd2f3",
    "H2_READONLY_QUERY_MANIFEST.json": "c4d4f6174699cd64710a0157da3c1bf1c85cae8d",
    "H2_READONLY_SESSION_PROTOCOL.md": "0c3ce5ecbec6fbb11f3ef30b571323cc0761ab5e",
    "h2_independent_manifest_review.py": "60a7950e661ecb736cae2202a2b883549abdd8ad",
    "h2_readonly_offline_verifier.py": "36953f2ce7109a4bd03b64e8a7271bc56288a9ba",
}
B_BLOBS = {
    "H2_READONLY_QUERY_MANIFEST.json": "d405e5791c6b65ab15a3a111b8211452f4f24873",
    "research/h2_inspector_preflight_2026_10_21/verify_package.py": "da1488522fb7a7ee698f512d5b108321ac7f7ddb",
}
SQL_PINS = {
    "G01":"ce813119fd93e85000ed6fedd426eace5f3427f9b96e0580d4aa1b5e3626e061",
    "G02":"939aa087f3989273869a0ee8e0d1a4ce97fe090dccb19ef48d237aab1f4ecb80",
    "G03":"3935fdb92b3e4ec081b68ac204a2bd0af9419fe91ee4d880a64665470ce29e40",
    "G04":"ed9f526db60557e19d7a6f2b489f1afcd55cc877a57ce3af708082d17452d89a",
    "G05":"fbc7343ee2d7a011397526517bbaa1f4e401c1a58a6efbb62b1d5610b9d3bf8c",
    "G06":"a342759e5e4e889da12e96e7270b38421becb7601bb90f82f3db47632c779b4d",
    "G07":"3f74d91f46d32db0d40d65eba5cbd1c84b7c1fb757c741fd1692c7de1ecd240b",
    "G08":"01cde324fd932071fd682f1928e78a0dbfd2fd1d76c34ad8e142bb9e4fcd33ce",
    "G09":"e708c9fa96bc84b7003fd4798a8226c015dbee1b0c2dd7eace7a40c6f6899a38",
    "G10":"498be7a1b8fe07b87675d4624521e1aff35d965789623393ab00e4d1a05f0a19",
    "G11":"33a57845c359e82a6ba895a92eb94730756882eb791a270107bc0c2ecc4e0607",
    "G12":"1baf7cdfeb807ca2682de3ae2a5619db3681ce2c571e690855fae5a10db8e4b8",
    "G13":"cb4fe8636e72a1fce46a0c36da569061ef186e63ae20edaf3bddbf23ef84d738",
    "G14":"0d819ea8ce6e3de65b1e13eeeca8bd7d68b2bf33a990a25298a8ba0c1895c932",
}
OBJECTS = {
    "alert_episode_sources","alert_episodes","attack_event_classifications",
    "attack_event_sources","attack_events","current_ingestion_checkpoints",
    "ingestion_checkpoints","ingestion_runs",
}
HOLDS = {
    "H2_READONLY_NEON_PREFLIGHT_READINESS":"BLOCKED/NO-GO",
    "H2_DISPOSABLE_NEON_TEST_READINESS":"BLOCKED/NO-GO",
    "NEON_AUTHORITY_ACTIVE":"NO",
    "PRODUCTION_CUTOVER_EXECUTED":"NO",
    "WIP_ACTIVATION":"NO-GO",
    "H2_ACL_OPTION_B":"BLOCKED / PROPOSAL_ONLY",
}

def sha256(b):
    return hashlib.sha256(b).hexdigest()

def git_blob(b):
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()

def check_blobs(root, blobs):
    for path, digest in blobs.items():
        b = (root/path).read_bytes()
        assert git_blob(b)==digest, f"Git blob altered: {path}"
        print("PINNED_BLOB",path,git_blob(b),"SHA256",sha256(b),"BYTES",len(b))
    return len(blobs)

def check_a(m):
    assert m["kind"]=="H2_NEON_CATALOG_INSPECTOR_OFFLINE_PROPOSAL"
    assert m["authorization_state"]=="NOT_AUTHORIZED_NO_CONNECTION"
    t=m["target"]
    assert t=={"project_id":"green-cake-44216048","branch_id":"br-bold-mode-b5rub8pq",
               "database":"neondb","historical_endpoint_id":"ep-calm-rice-b5073ypp",
               "current_endpoint_id":None,"endpoint_hostname":None,
               "host_branch_mapping_verified":False,"control_plane_evidence_age_hours":None}
    assert m["inspector"]=={"proposed_role":"h2_catalog_inspector_ro",
             "actual_role_verified":False,"least_privilege_verified":False,
             "role_provisioned_here":False,"owner_role_alternative_approved":False}
    assert m["approval"]=={"operator":None,"independent_reviewer":None,
                           "route_scope_approval":None,"explicit_user_access_authorization":None}
    assert m["unchanged_hard_holds"]==HOLDS
    assert m["source"]["main_head"]=="b5e9b078f171a15ffcf1cb197b61018cd76ca611"
    assert m["source"]["accepted_coordination"]=="66fbabf20644797bd67d3790893b4103a5dcb8ef"
    assert m["source"]["accepted_eligibility_research"]=="576ac42b7734106ccc0edc858173c90f82537d85"
    lim=m["limits"]
    assert lim=={"connections":1,"transactions":1,"unique_selects":14,
                 "max_catalog_select_executions":15,"max_sql_statement_executions":21,
                 "max_result_rows_total":180,"max_sanitized_bytes_total":65536,
                 "max_cell_bytes":8192,"statement_timeout_ms":15000,
                 "lock_timeout_ms":5000,"idle_in_transaction_timeout_ms":30000,
                 "transaction_timeout_ms":45000,"client_wall_clock_ms":60000}
    assert m["session_sql_order"] == [
       "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;",
       "SET LOCAL statement_timeout = '15s';",
       "SET LOCAL lock_timeout = '5s';",
       "SET LOCAL idle_in_transaction_session_timeout = '30s';",
       "SET LOCAL transaction_timeout = '45s';",
       *[f"G{i:02d}" for i in range(1,15)],"G01","ROLLBACK;"]
    assert m["sql_policy"]["allow_user_defined_function_calls"] is False
    assert m["sql_policy"]["allow_application_row_selects"] is False
    assert m["sql_policy"]["allow_data_modification"] is False
    assert m["sql_policy"]["allow_role_switch"] is False
    assert m["sql_policy"]["ignore_or_normalize_raw_relacl"] is False
    assert m["receipt_contract"]["required_runtime_coverage"]==["I1","I2","I3","I4","I5","I6","I7"]
    qs=m["queries"]
    assert [q["id"] for q in qs]==list(SQL_PINS)
    assert len(qs)==14
    assert sum(q["max_rows"] for q in qs)+1<=lim["max_result_rows_total"]
    for q in qs:
        sql=q["sql"]
        assert sha256(sql.encode("utf-8"))==q["sha256"]==SQL_PINS[q["id"]],q["id"]
        assert sql.startswith("SELECT ") and sql.endswith(";") and sql.count(";")==1
        assert "/*" not in sql and "--" not in sql
        assert re.search(r"\bFROM\s+public\.|\bJOIN\s+public\.",sql,re.I) is None
        assert re.search(r"\b(WITH|UPDATE|INSERT|DELETE|MERGE|CREATE|DROP|CALL|DO|EXPLAIN|COPY|SET\s+ROLE)\b",re.sub(r"'(?:''|[^'])*'", "''", sql),re.I) is None
        assert q["id"]=="G01" or re.search(r"\bLIMIT\s+\d+;$",sql,re.I)
        assert 0<q["max_rows"]<=33
        assert q["max_cell_bytes"]==8192
        assert isinstance(q["columns"],list) and len(q["columns"])==len(set(q["columns"]))
        assert q["contract_ids"] and q["purpose"]
    g4=qs[3]["sql"]
    list_section=re.search(r"c\.relname IN \((.*?)\)\s*ORDER BY",g4,re.S)
    assert list_section, "G04 object restriction missing"
    obj=re.findall(r"'([^']+)'",list_section.group(1))
    assert len(obj)==8 and set(obj)==OBJECTS
    assert "c.relacl IS NULL" in g4 and "c.relacl::text" in g4
    assert "raw_relacl_is_null" in qs[3]["columns"] and "raw_relacl_text" in qs[3]["columns"]
    assert "neondb_owner" in qs[10]["sql"]  # default ACL name filter, not a login fallback
    manifest_text=json.dumps(m)
    assert not re.search(r"(?i)postgres(?:ql)?://|bearer\s+[A-Za-z0-9_-]{8,}|password\s*[:=]",manifest_text)
    return True

def load_module(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def rejected_manifest_tests(m):
    cases=[]
    def add(name, mutate):
        candidate=copy.deepcopy(m)
        mutate(candidate)
        try:
            check_a(candidate)
        except (AssertionError,KeyError,TypeError,ValueError):
            cases.append(name)
        else:
            raise AssertionError("A independent fail-open: "+name)
    def sql_replace(x,query_index,txt):
        x["queries"][query_index].update(sql=txt,sha256=sha256(txt.encode()))
    add("wrong_project",lambda x:x["target"].update(project_id="not-target"))
    add("wrong_branch",lambda x:x["target"].update(branch_id="br-wandering-sunset-b5835alw"))
    add("wrong_database",lambda x:x["target"].update(database="postgres"))
    add("writer_endpoint",lambda x:x["target"].update(historical_endpoint_id="ep-still-violet-b5bg6mhp"))
    add("forged_host_mapping",lambda x:x["target"].update(host_branch_mapping_verified=True))
    add("forged_inspector",lambda x:x["inspector"].update(actual_role_verified=True))
    add("owner_fallback",lambda x:x["inspector"].update(proposed_role="neondb_owner"))
    add("allowed_owner_alternative",lambda x:x["inspector"].update(owner_role_alternative_approved=True))
    add("forged_authorization",lambda x:x["approval"].update(explicit_user_access_authorization="YES"))
    add("claim_live",lambda x:x.update(authorization_state="LIVE_AUTHORIZED"))
    add("gate_promotion",lambda x:x["unchanged_hard_holds"].update(NEON_AUTHORITY_ACTIVE="YES"))
    add("lost_sql",lambda x:x["queries"].pop())
    add("extra_sql",lambda x:x["queries"].append(copy.deepcopy(x["queries"][3])))
    add("query_reorder",lambda x:x["queries"].reverse())
    add("sql_hash_drift",lambda x:x["queries"][0].update(sha256="0"*64))
    add("sql_rehashed_change",lambda x:sql_replace(x,0,"SELECT 1 AS ok;"))
    add("user_defined_function_rehashed",lambda x:sql_replace(x,0,"SELECT public.fn();"))
    add("advisory_lock_rehashed",lambda x:sql_replace(x,0,"SELECT pg_catalog.pg_try_advisory_lock(42) AS injected;"))
    add("server_filesystem_rehashed",lambda x:sql_replace(x,0,"SELECT pg_catalog.pg_ls_dir('/tmp') AS injected;"))
    add("application_select_rehashed",lambda x:sql_replace(x,3,"SELECT * FROM public.attack_events;"))
    add("nested_cte_rehashed",lambda x:sql_replace(x,3,"WITH t AS (DELETE FROM public.attack_events RETURNING *) SELECT * FROM t;"))
    add("sql_comment_rehashed",lambda x:sql_replace(x,0,x["queries"][0]["sql"]+" --tamper"))
    add("quoted_literal_rehashed",lambda x:sql_replace(x,0,"SELECT 'not; harmless' AS x;"))
    add("missing_raw_acl_null",lambda x:x["queries"][3]["columns"].remove("raw_relacl_is_null"))
    add("extra_catalog_object",lambda x:sql_replace(x,3,x["queries"][3]["sql"].replace("'attack_events'","'not_target'")))
    add("disable_readonly",lambda x:x["session_sql_order"].__setitem__(0,"BEGIN;"))
    add("wrong_isolation",lambda x:x["session_sql_order"].__setitem__(0,"BEGIN READ COMMITTED READ ONLY;"))
    add("missing_repeat_check",lambda x:x["session_sql_order"].pop(-2))
    add("rollback_to_commit",lambda x:x["session_sql_order"].__setitem__(-1,"COMMIT;"))
    add("no_statement_timeout",lambda x:x["session_sql_order"].__setitem__(1,"SET LOCAL statement_timeout = 0;"))
    add("extended_wall_clock",lambda x:x["limits"].update(client_wall_clock_ms=999999))
    add("over_rows",lambda x:x["limits"].update(max_result_rows_total=999999))
    add("over_bytes",lambda x:x["limits"].update(max_sanitized_bytes_total=999999))
    add("missing_results_column",lambda x:x["queries"][1].update(columns=[]))
    add("forged_I1_to_I7",lambda x:x["receipt_contract"].update(required_runtime_coverage=[]))
    add("leaked_DSN",lambda x:x["target"].update(dsn="postgresql://private"))
    return cases

def check_b_fail_open():
    check_blobs(BROOT,B_BLOBS)
    bmod=load_module(BROOT/"research/h2_inspector_preflight_2026_10_21/verify_package.py","h2_b_verifier")
    baseline=json.loads((BROOT/"H2_READONLY_QUERY_MANIFEST.json").read_text(encoding="utf-8"))
    bmod.check(baseline)  # original accepted as offline design
    cases=[
      ("persistent_advisory_lock","SELECT pg_catalog.pg_try_advisory_lock(42) AS db LIMIT 1;"),
      ("server_filesystem_listing","SELECT pg_catalog.pg_ls_dir('/tmp') AS db LIMIT 1;"),
    ]
    for name,unsafe_sql in cases:
        t=copy.deepcopy(baseline)
        query=t["queries"][0]
        query["sql"]=unsafe_sql
        query["sql_sha256"]=sha256(unsafe_sql.encode())
        query["expected_columns"]=["db"]
        receipt=t["receipt_template"]["query_results"][0]
        receipt["sql_sha256"]=query["sql_sha256"]
        receipt["columns"]=["db"]
        try:
            bmod.check(t)
        except ValueError as err:
            raise AssertionError(f"B bypass not reproduced ({name}): {err}")
        print("B_REGEX_FAIL_OPEN_CONFIRMED",name,query["sql_sha256"],"SQL_NOT_EXECUTED")
    return len(cases)

def main():
    assert check_blobs(ROOT,A_BLOBS)==8
    manifest=json.loads((ROOT/"H2_READONLY_QUERY_MANIFEST.json").read_text(encoding="utf-8"))
    assert check_a(manifest)
    orig=load_module(ROOT/"h2_readonly_offline_verifier.py","h2_a_verifier")
    assert orig.validate_manifest(manifest)
    recorded=json.loads((ROOT/"H2_INSPECTOR_NEGATIVE_CONTROLS.json").read_text())
    fresh=orig.execute_checks(manifest)
    assert fresh==recorded and fresh["negative_count"]==43
    second=load_module(ROOT/"h2_independent_manifest_review.py","h2_a_independent")
    assert second.review(manifest)
    assert len(second.negatives(manifest))==16
    review=json.loads((ROOT/"H2_INSPECTOR_INDEPENDENT_REVIEW.json").read_text())
    assert review["pinned_queries"]==14 and review["rejected_negative_controls"]==16
    own=rejected_manifest_tests(manifest)
    assert len(own)>=35
    print("A_SQL",len(manifest["queries"]),"A_PRIMARY_NEGATIVES",fresh["negative_count"],
          "A_SECONDARY_NEGATIVES",16,"A_NEW_INDEPENDENT_NEGATIVES",len(own))
    print("A_MANIFEST_CANONICAL_SHA256",sha256(orig.canonical_bytes(manifest)))
    b_bypasses=check_b_fail_open()
    assert b_bypasses==2
    print("VERDICT_A=OFFLINE_STATIC_AND_SYNTHETIC_PASS_BOUNDED")
    print("VERDICT_B=NOT_ACCEPTABLE_AS_IMMUTABLE_SQL_ALLOWLIST")
    print("LIVE_NEON_CONNECTIONS=0")
    print("LIVE_I1_TO_I7=UNVERIFIED")
    print("NO_ACCESS_AUTHORIZATION_ISSUED")
    print("SOURCE_A",SOURCE_A,"SOURCE_B",SOURCE_B)
if __name__=="__main__":
    main()
