#!/usr/bin/env python3
"""Synthetic psql process emulator. Never imports network libraries or runs SQL."""
import argparse
import os
import sys
import time

p=argparse.ArgumentParser()
p.add_argument("--scenario",required=True)
p.add_argument("rest",nargs=argparse.REMAINDER)
a=p.parse_args()
if os.environ.get("H2_MOCK_ONLY")!="1": sys.exit(90)
required=["-X","ON_ERROR_STOP=1","ON_ERROR_ROLLBACK=off","-W","synthetic.invalid","ROLE_EXISTENCE_PINNED.sql"]
if any(x not in a.rest for x in required): sys.exit(91)
if any("neon.tech" in x for x in a.rest): sys.exit(92)
header="database_name|session_role|current_role|server_version_num|transaction_read_only|transaction_isolation|inspector_exists"
role="neondb_owner"
db="neondb"
guard="on"
if a.scenario=="wrong_role": role="postgres"
if a.scenario=="wrong_database": db="wrong"
if a.scenario=="wrong_guard": guard="off"
exists="t" if a.scenario=="exists" else "f"
row=f"{db}|{role}|{role}|180006|{guard}|repeatable read|{exists}"
lines=["BEGIN","SET","SET","SET","SET",header,row,"ROLLBACK"]
if a.scenario=="missing_rollback": lines.pop()
if a.scenario=="extra_statement": lines.insert(7,"SET")
if a.scenario=="multiple_rows": lines.insert(7,row)
if a.scenario=="malformed_header": lines[5]="bad|header"
if a.scenario=="sql_error":
    print("ERROR: synthetic query failure",file=sys.stderr)
    sys.exit(3)
if a.scenario=="exit_failure": sys.exit(1)
if a.scenario=="stderr_noise": print("NOTICE: extra",file=sys.stderr)
if a.scenario=="timeout": time.sleep(25)
print("\n".join(lines))
