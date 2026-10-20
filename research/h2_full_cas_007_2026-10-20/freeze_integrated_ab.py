#!/usr/bin/env python3
"""Freeze original integrated 007 CAS A/B GitHub Actions artifact ZIPs without recreating ZIPs."""
import base64,hashlib,io,json,subprocess,zipfile
from pathlib import Path
REPO="olegbalakin-cmyk/kyiv-air-alerts-grafana"
RUN=39434358306
TESTED="00563b1eb5cb597fe0d3492ad12ae9c0645b2c6e"
EXPECTED={
"A":{"artifact_id":12268903364,"job_id":118667337877,"sha":"5852fef340d2da9af7b09c3607ff6f73cd6a920a68e846aacb718e61136e56d7","size":2889},
"B":{"artifact_id":12269851414,"job_id":118667338105,"sha":"e33cab4ac64d58ce82a3c7f063d46756ea84b34f9cb4fa27b27af9073987341c","size":2888}}
OUT=Path(__file__).resolve().parent/"integrated_original_ab"
OUT.mkdir(exist_ok=True)
def sha(data):return hashlib.sha256(data).hexdigest()
def api(path,binary=False):
 p=subprocess.run(["gh","api","-H","Accept: application/vnd.github+json","repos/"+REPO+"/"+path],
                  check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
 return p.stdout if binary else json.loads(p.stdout)
run=api("actions/runs/"+str(RUN))
assert run["conclusion"]=="success" and run["head_sha"]==TESTED
jobs=api("actions/runs/"+str(RUN)+"/jobs?per_page=100")["jobs"]
manifest={"schema":"h2-full-007-cas-original-ab-v1","source_run":RUN,"tested_commit":TESTED,"records":{}}
for copy,sp in EXPECTED.items():
 j=[x for x in jobs if x["id"]==sp["job_id"]]
 assert len(j)==1 and j[0]["name"].endswith("("+copy+")") and j[0]["conclusion"]=="success"
 a=api("actions/artifacts/"+str(sp["artifact_id"]))
 assert a["name"]=="h2-integrated-007-cas-"+copy and a["size_in_bytes"]==sp["size"]
 assert a["digest"]=="sha256:"+sp["sha"] and not a["expired"]
 assert a["workflow_run"]["head_sha"]==TESTED and a["workflow_run"]["id"]==RUN
 raw=api("actions/artifacts/"+str(sp["artifact_id"])+"/zip",binary=True)
 assert len(raw)==sp["size"] and sha(raw)==sp["sha"]
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  assert z.testzip() is None and len(z.namelist())==1
  member=z.namelist()[0]
  body=z.read(member)
 rep=json.loads(body)
 assert rep["copy"]==copy and rep["tested_commit"]==TESTED
 assert rep["schema"]=="h2-integrated-non-superuser-007-full-cas-v1"
 assert rep["verdict"]=="PASS" and rep["total"]==rep["passed"]==144
 assert rep["accepted_original_77_executed"]==77 and rep["topology_additions"]==67
 assert not rep["errors"] and len(rep["assertions"])==144
 assert all(x["pass"] for x in rep["assertions"])
 zname=copy+".github_original.zip.b64"
 jname=copy+".original.json"
 (OUT/zname).write_bytes(base64.b64encode(raw)+b"\n")
 (OUT/jname).write_bytes(body)
 manifest["records"][copy]={"artifact_id":sp["artifact_id"],"job_id":sp["job_id"],
     "job_name":j[0]["name"],"artifact_name":a["name"],"zip_file":zname,
     "zip_bytes":len(raw),"zip_sha256":sha(raw),"member":member,
     "json_file":jname,"json_bytes":len(body),"json_sha256":sha(body),
     "checks":144,"accepted_original":77,"topology_additions":67,"verdict":"PASS"}
(OUT/"manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n")
print(json.dumps({"status":"FROZEN_ORIGINAL_GITHUB_ZIPS","source_run":RUN,
 "sha256":{c:{"zip":sp["zip_sha256"],"json":sp["json_sha256"]} for c,sp in manifest["records"].items()}},sort_keys=True))
