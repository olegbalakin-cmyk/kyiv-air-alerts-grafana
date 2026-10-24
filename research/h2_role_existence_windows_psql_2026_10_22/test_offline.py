#!/usr/bin/env python3
"""Pure stdlib verifier negative fixtures; Windows mock-process tests run through .ps1."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from verify_receipt import verify, no_duplicates, SQL_BLOB, SQL_SHA, ROUTE_BLOB

HEADER="database_name|session_role|current_role|server_version_num|transaction_read_only|transaction_isolation|inspector_exists"
ARGS=['-X','-v','ON_ERROR_STOP=1','-v','ON_ERROR_ROLLBACK=off','-A','-F','|','-P','footer=off',
      '-P','pager=off','-P','tuples_only=off','-W','-h','synthetic.invalid','-p','5432',
      '-U','neondb_owner','-d','neondb','-f','ROLE_EXISTENCE_PINNED.sql']
def fixture():
    lines=['BEGIN','SET','SET','SET','SET',HEADER,'neondb|neondb_owner|neondb_owner|180006|on|repeatable read|f','ROLLBACK']
    r=dict(schema='h2-role-existence-receipt-v1',mode='SYNTHETIC',verdict='UNVERIFIED_PENDING_INDEPENDENT_REVIEW',
    role_existence='UNVERIFIED',provisional_inspector_exists=False,sql_git_blob=SQL_BLOB,sql_sha256=SQL_SHA,
    route_template_git_blob=ROUTE_BLOB,project='green-cake-44216048',branch='br-bold-mode-b5rub8pq',
    endpoint='SYNTHETIC_ONLY',fqdn='synthetic.invalid',database='neondb',port=5432,
    expected_role='neondb_owner',operator='MOCK_OPERATOR',reviewed_by='MOCK_NOT_REVIEWED',
    route_attestation_sha256=None,route_source_sha256=None,route_observed_at_utc=None,
    client_version='psql (PostgreSQL) 18.6',pg_sslmode='verify-full',pg_sslrootcert='ISRG_ROOTS_PINNED.pem',
    pg_gssencmode='disable',connect_timeout_seconds=5,wall_budget_seconds=20,elapsed_ms=2,
    client_exit_code=0,attempt_count=1,sql_statement_count_expected=7,select_count_expected=1,
    stderr_status='EMPTY',psql_arguments=ARGS,transcript=lines,
    transcript_sha256=hashlib.sha256(('\n'.join(lines)+'\n').encode()).hexdigest(),
    observed_at_utc='2026-10-23T10:00:00Z',tls_handshake_independently_proven=False,
    single_physical_session_independently_proven=False)
    return r
def run():
    cases={}
    def case(name, mutate, valid=False):
        r=copy.deepcopy(fixture())
        mutate(r)
        if valid and r["transcript"]:
            r["transcript_sha256"]=hashlib.sha256(('\n'.join(r["transcript"])+'\n').encode()).hexdigest()
        try:
            verify(r,synthetic_only=True)
            ok=True
        except (ValueError,TypeError,KeyError): ok=False
        assert ok==valid,f"case {name}: got {ok}, expected {valid}"
        cases[name]="PASS"
    case("valid_absent",lambda r:None,True)
    def exists(r):
        r["transcript"][6]=r["transcript"][6][:-1]+"t"
        r["provisional_inspector_exists"]=True
    case("valid_exists",exists,True)
    case("missing_rollback",lambda r:r["transcript"].pop())
    case("extra_statement",lambda r:r["transcript"].insert(7,"SET"))
    case("second_row",lambda r:r["transcript"].insert(7,r["transcript"][6]))
    case("wrong_role",lambda r:r["transcript"].__setitem__(6,r["transcript"][6].replace("neondb_owner","postgres")))
    case("bad_server_major",lambda r:r["transcript"].__setitem__(6,r["transcript"][6].replace("180006","170000")))
    case("read_only_off",lambda r:r["transcript"].__setitem__(6,r["transcript"][6].replace("|on|","|off|")))
    case("bad_header",lambda r:r["transcript"].__setitem__(5,"header"))
    case("bad_exit",lambda r:r.__setitem__("client_exit_code",1))
    case("timeout",lambda r:r.__setitem__("elapsed_ms",20001))
    case("extra_attempt",lambda r:r.__setitem__("attempt_count",2))
    case("relaxed_tls",lambda r:r.__setitem__("pg_sslmode","require"))
    case("untrusted_ca_fallback",lambda r:r.__setitem__("pg_sslrootcert","system"))
    case("wrong_ca_file",lambda r:r.__setitem__("pg_sslrootcert","pgAdmin/cacert.pem"))
    case("wrong_host",lambda r:r.__setitem__("fqdn","some.neon.tech"))
    case("rollback_only_wrong_case",lambda r:r["transcript"].__setitem__(7,"rollback"))
    case("wrong_hash",lambda r:r.__setitem__("sql_git_blob","0"*40))
    case("false_tls_claim",lambda r:r.__setitem__("tls_handshake_independently_proven",True))
    case("mutated_arguments",lambda r:r["psql_arguments"].append("--set=foo"))
    case("injected_row",lambda r:r["transcript"].__setitem__(6,r["transcript"][6]+"\nDROP TABLE x;"))
    case("absent_changed_to_confirmed",lambda r:r.__setitem__("role_existence","ABSENT_CONFIRMED"))
    case("trailing_unexpected_field",lambda r:r.__setitem__("unexpected","x"))
    case("bool_instead_of_port",lambda r:r.__setitem__("port",True))
    try:
        json.loads('{"schema":"a","schema":"b"}',object_pairs_hook=no_duplicates)
        raise AssertionError("duplicate keys accepted")
    except ValueError: cases["duplicate_json_key"]="PASS"
    print(json.dumps({"suite":"H2 offline verifier fixtures","tests":len(cases),"passed":len(cases),
                     "status":"PASS_OFFLINE_ONLY","cases":cases},indent=2))
if __name__=="__main__":run()
