#!/usr/bin/env python3
"""Strict offline check of the sanitized H2 receipt. Never connects to a database."""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SQL_BLOB = "dd3595f7402cdc6e44d3fce6c5632dd9cfb88052"
SQL_SHA = "3e8a8d62440ec30245f64da21a263d84793e7e77a8cf45806f60a656ba6a31ee"
ROUTE_BLOB = "0ea2e8688c5b5a5e3934704a29b2ad51195584b4"
HOST = "ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech"
FIELDS = "database_name|session_role|current_role|server_version_num|transaction_read_only|transaction_isolation|inspector_exists"
KEYS = set("""schema mode verdict role_existence provisional_inspector_exists sql_git_blob sql_sha256 route_template_git_blob project branch endpoint fqdn database port expected_role operator reviewed_by route_attestation_sha256 route_source_sha256 route_observed_at_utc client_version pg_sslmode pg_sslrootcert pg_gssencmode connect_timeout_seconds wall_budget_seconds elapsed_ms client_exit_code attempt_count sql_statement_count_expected select_count_expected stderr_status psql_arguments transcript transcript_sha256 observed_at_utc tls_handshake_independently_proven single_physical_session_independently_proven""".split())

def no_duplicates(pairs):
    d = {}
    for k, v in pairs:
        if k in d:
            raise ValueError("duplicate JSON key " + k)
        d[k] = v
    return d

def verify(receipt, synthetic_only=False):
    if not isinstance(receipt, dict) or set(receipt) != KEYS:
        raise ValueError("unexpected or absent receipt fields")
    def eq(key, value):
        if type(receipt[key]) is not type(value) or receipt[key] != value:
            raise ValueError("invalid " + key)
    for k, v in {
        "schema":"h2-role-existence-receipt-v1","verdict":"UNVERIFIED_PENDING_INDEPENDENT_REVIEW",
        "role_existence":"UNVERIFIED","sql_git_blob":SQL_BLOB,"sql_sha256":SQL_SHA,
        "route_template_git_blob":ROUTE_BLOB,"project":"green-cake-44216048",
        "branch":"br-bold-mode-b5rub8pq","database":"neondb",
        "port":5432,"expected_role":"neondb_owner","pg_sslmode":"verify-full",
        "pg_sslrootcert":"ISRG_ROOTS_PINNED.pem","pg_gssencmode":"disable","connect_timeout_seconds":5,
        "wall_budget_seconds":20,"client_exit_code":0,"attempt_count":1,
        "sql_statement_count_expected":7,"select_count_expected":1,
        "tls_handshake_independently_proven":False,
        "single_physical_session_independently_proven":False,
    }.items(): eq(k, v)
    mode = receipt["mode"]
    if mode not in ("SYNTHETIC", "OPERATOR_LOCAL"):
        raise ValueError("invalid mode")
    if synthetic_only and mode != "SYNTHETIC":
        raise ValueError("expected synthetic receipt")
    if mode == "SYNTHETIC":
        for k,v in {"fqdn":"synthetic.invalid","endpoint":"SYNTHETIC_ONLY",
                    "operator":"MOCK_OPERATOR","reviewed_by":"MOCK_NOT_REVIEWED",
                    "route_attestation_sha256":None,"route_source_sha256":None,
                    "route_observed_at_utc":None}.items(): eq(k,v)
    else:
        eq("fqdn", HOST)
        eq("endpoint","ep-calm-rice-b5073ypp")
        if receipt["operator"] == receipt["reviewed_by"]: raise ValueError("same reviewer")
        for k in ("operator","reviewed_by"):
            if not isinstance(receipt[k],str) or not re.fullmatch(r"[A-Za-z0-9_. -]{3,80}",receipt[k]):
                raise ValueError("invalid identity")
        for k in ("route_attestation_sha256","route_source_sha256"):
            if not isinstance(receipt[k],str) or not re.fullmatch(r"[0-9a-f]{64}",receipt[k]):
                raise ValueError("missing attestation digest")
        if not isinstance(receipt["route_observed_at_utc"],str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",receipt["route_observed_at_utc"]):
            raise ValueError("invalid route time")
    if not isinstance(receipt["client_version"],str) or not re.fullmatch(r"psql \(PostgreSQL\) 18\.\d+(?:\.\d+)?",receipt["client_version"]):
        raise ValueError("invalid version")
    if type(receipt["elapsed_ms"]) is not int or not 0 <= receipt["elapsed_ms"] <= 20000:
        raise ValueError("invalid elapsed")
    if receipt["stderr_status"] not in ("EMPTY","PROMPT_ONLY"): raise ValueError("stderr")
    args = receipt["psql_arguments"]
    expected = ['-X','-v','ON_ERROR_STOP=1','-v','ON_ERROR_ROLLBACK=off','-A','-F','|',
                '-P','footer=off','-P','pager=off','-P','tuples_only=off','-W','-h',
                receipt["fqdn"],'-p','5432','-U','neondb_owner','-d','neondb','-f','ROLE_EXISTENCE_PINNED.sql']
    if type(args) is not list or args != expected: raise ValueError("psql arguments changed")
    lines = receipt["transcript"]
    if type(lines) is not list or len(lines) != 8 or any(type(s) is not str or '\n' in s or '\r' in s for s in lines):
        raise ValueError("unexpected transcript shape")
    if lines[:5] != ["BEGIN","SET","SET","SET","SET"] or lines[5] != FIELDS or lines[7] != "ROLLBACK":
        raise ValueError("tags, header, or rollback invalid")
    if len(lines[6].encode("utf-8")) > 2048: raise ValueError("row too long")
    columns = lines[6].split("|")
    if len(columns) != 7 or columns[:3] != ["neondb","neondb_owner","neondb_owner"] or not re.fullmatch(r"18\d{4}",columns[3]) or columns[4:6] != ["on","repeatable read"] or columns[6] not in ("t","f"):
        raise ValueError("invalid row")
    eq("provisional_inspector_exists",columns[6] == "t")
    digest = hashlib.sha256(("\n".join(lines)+"\n").encode()).hexdigest()
    eq("transcript_sha256",digest)
    if not isinstance(receipt["observed_at_utc"],str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ",receipt["observed_at_utc"]):
        raise ValueError("invalid observation time")
    return "OFFLINE_RECEIPT_SHAPE_PASS / H2_ROLE_EXISTENCE=UNVERIFIED / INDEPENDENT_REVIEW_REQUIRED"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt",type=Path)
    parser.add_argument("--synthetic-only",action="store_true")
    args=parser.parse_args()
    try:
        raw=args.receipt.read_bytes()
        if len(raw)>8192: raise ValueError("receipt file too big")
        data=json.loads(raw.decode("utf-8-sig"),object_pairs_hook=no_duplicates)
        print(verify(data,args.synthetic_only))
    except (OSError,UnicodeError,ValueError,TypeError,KeyError) as ex:
        print("FAIL_CLOSED / H2_ROLE_EXISTENCE=UNVERIFIED / "+str(ex),file=sys.stderr)
        raise SystemExit(1)

if __name__=="__main__": main()
