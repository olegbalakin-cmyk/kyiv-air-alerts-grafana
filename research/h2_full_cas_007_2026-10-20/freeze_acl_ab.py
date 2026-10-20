#!/usr/bin/env python3
"""Freeze original expanded ACL A/B ZIP and original report bytes, preserving PARTIAL."""
import base64,hashlib,io,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent/"expanded_acl_original_ab"
ROOT.mkdir(exist_ok=True)
REPO="olegbalakin-cmyk/kyiv-air-alerts-grafana"
RUN=39435605595
TESTED="884ae6bfe91f271dfcb355ee8c5b25cdd0dfb18f"
EXPECTED={
"A":(12273360123,118671676646,3584,"be1b773f0c65f471f2754fe6f4776d403901a371fadff4e356daac9c252eb24c"),
"B":(12272300948,118671676273,3586,"b3547c3cfdca910481f14c8b678ab5f81657c016215f225454295e9a769e3750")}
def sha(b):return hashlib.sha256(b).hexdigest()
def api(url,binary=False):
 p=subprocess.run(["gh","api","-H","Accept: application/vnd.github+json","repos/"+REPO+"/"+url],
                  stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,check=True)
 return p.stdout if binary else json.loads(p.stdout)
run=api("actions/runs/"+str(RUN))
assert run["conclusion"]=="success" and run["head_sha"]==TESTED
jobs=api("actions/runs/"+str(RUN)+"/jobs?per_page=100")["jobs"]
m={"schema":"h2-007-expanded-acl-original-v1","source_run":RUN,"tested_commit":TESTED,"records":{}}
for copy,(aid,jid,size,digest) in EXPECTED.items():
 j=[x for x in jobs if x["id"]==jid]
 assert len(j)==1 and j[0]["conclusion"]=="success" and j[0]["name"].endswith("("+copy+")")
 a=api("actions/artifacts/"+str(aid))
 assert a["name"]=="h2-007-expanded-acl-"+copy
 assert a["size_in_bytes"]==size and a["digest"]=="sha256:"+digest and not a["expired"]
 assert a["workflow_run"]["id"]==RUN and a["workflow_run"]["head_sha"]==TESTED
 raw=api("actions/artifacts/"+str(aid)+"/zip",True)
 assert len(raw)==size and sha(raw)==digest
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  assert z.testzip() is None and len(z.namelist())==1
  member=z.namelist()[0]
  body=z.read(member)
 p=json.loads(body)
 assert p["copy"]==copy and p["tested_commit"]==TESTED
 assert p["verdict"]=="PARTIAL" and p["passed"]==p["total"]==20
 assert p["physical_catalog_residual"]==["relation"] and not p["errors"]
 assert len(p["checks"])==20 and all(z["pass"] for z in p["checks"])
 assert len(p["cases"])==3 and all(z["status"]=="PASS" for z in p["cases"])
 zfile=copy+".original.zip.b64";jfile=copy+".original.json"
 (ROOT/zfile).write_bytes(base64.b64encode(raw)+b"\n")
 (ROOT/jfile).write_bytes(body)
 m["records"][copy]={"artifact_id":aid,"job_id":jid,"job_name":j[0]["name"],
  "zip_file":zfile,"zip_bytes":len(raw),"zip_sha256":sha(raw),"member":member,
  "report_file":jfile,"report_bytes":len(body),"report_sha256":sha(body),
  "total":20,"verdict":"PARTIAL","raw_residual":["relation"]}
(ROOT/"manifest.json").write_text(json.dumps(m,sort_keys=True,indent=2)+"\n")
print(json.dumps({"result":"FROZEN_ORIGINAL_ACL_A_B","records":m["records"]},sort_keys=True))
