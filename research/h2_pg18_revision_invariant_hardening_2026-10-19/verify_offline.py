#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
R=Path(__file__).resolve().parent
P={
"observed_partial_schema.sql":"09f9c5a2f0c4eeddaba63e7c9c5834cce85f7ab3",
"001_revision_invariants.sql":"339b9b44a90f8b5e8ba216576f63daac393a5eb3",
"002_synthetic_writer_grants.sql":"b4c1be395b0cfdc16086729ad903ef10e00b1fb0",
"test_pg18.py":"6bada34023f92ab567485907a911a41db2d84b33"}
if sys.argv[1]=="static":
 for name,expected in P.items():
  b=(R/name).read_bytes()
  actual=hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
  assert actual==expected,(name,actual,expected)
 print("PASS STATIC 4/4 source pins")
elif sys.argv[1]=="report":
 b=Path(sys.argv[2]).read_bytes()
 j=json.loads(b)
 assert j.get("verdict")=="PASS",j.get("error")
 assert j["assertions"]>=28 and j["assertions"]==j["passed"]
 assert j["pg_version"].startswith("18.")
 assert sorted(x["status"] for x in j["race"])==["committed","rejected"]
 print("PASS REPORT",j["assertions"],hashlib.sha256(b).hexdigest())
else:raise SystemExit(2)
