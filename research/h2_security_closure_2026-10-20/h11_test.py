#!/usr/bin/env python3
"""Bounded real PG18.6 H11 A/B. No Neon. Snapshot contract only."""
import sys,json,os,traceback
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"h2_rollback_adversarial_2026-10-20"))
from harness import *
SQL=Path(__file__).with_name("h11_head_history_check.sql").read_text()
report={"copy":COPY,"commit":os.environ.get("GITHUB_SHA"),"postgres":query("postgres","SHOW server_version")[0][0],"cases":[]}
assert report["postgres"].startswith("18.6")
def check(db):
 with conn(db,autocommit=False) as c:
  c.execute("BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY")
  out=c.execute(SQL).fetchall()
  c.commit()
 return sorted(set(x[0] for x in out))
def one(id,expect,setup):
 d=new("h11v2"+id)
 setup(d)
 before=truth(d)
 actual=check(d)
 after=truth(d)
 case={"id":id,"expected":expect,"actual":actual,"history_before":before["history_md5"],"history_after":after["history_md5"],"status":"PASS" if actual==sorted(expect) and before==after else "FAIL"}
 report["cases"].append(case)
 print(json.dumps(case),flush=True)
 if case["status"]!="PASS":raise AssertionError(id)
def build(d):return put(d,"h11_"+d)
def chain(d):
 a=build(d)
 b=put(d,"second_"+d,parent=a)
 return a,b
try:
 one("empty",[],lambda d:None)
 one("root",[],lambda d:build(d))
 one("chain",[],lambda d:chain(d))
 one("three",[],lambda d:(lambda a,b:put(d,"third_"+d,parent=b))(*chain(d)))
 one("independent",[],lambda d:(put(d,"id1"+d),put(d,"id2"+d,identity=2,city="kharkiv")))
 one("stale_tip",["HEAD_NOT_CANONICAL_TIP"],lambda d:(lambda a,b:query(d,"UPDATE public.h2_classification_heads SET tip_classification_uid=%s",(a,)))(*chain(d)))
 one("missing_head",["MISSING_HEAD"],lambda d:(build(d),query(d,"DELETE FROM public.h2_classification_heads")))
 one("wrong_identity",["HEAD_NOT_CANONICAL_TIP"],lambda d:(lambda a,b:query(d,"UPDATE public.h2_classification_heads SET tip_classification_uid=%s WHERE city_key='kyiv'",(b,)))(build(d),put(d,"secondid"+d,identity=2,city="kharkiv")))
 one("repeated",[],lambda d:(chain(d),check(d),check(d)))
except Exception as e:
 report["error"]=repr(e);report["trace"]=traceback.format_exc()[-1200:]
finally:
 report["verdict"]="PARTIAL" if report.get("error") else "PASS_BOUNDED_SNAPSHOT"
 Path("/tmp/h2_h11_"+COPY+".json").write_text(json.dumps(report,indent=2)+"\n")
 print(report["verdict"],flush=True)
if report["verdict"]!="PASS_BOUNDED_SNAPSHOT":raise SystemExit(1)
