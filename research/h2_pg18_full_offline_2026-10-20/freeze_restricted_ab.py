#!/usr/bin/env python3
"""Preserve byte-identical ORIGINAL GitHub Actions A/B receipts in Git, research only."""
import base64,hashlib,io,json,subprocess,zipfile
from pathlib import Path
REPO="olegbalakin-cmyk/kyiv-air-alerts-grafana"
TESTED="1a1a63e61eef1e43bb7eefbb5a736bf920e56071"
RUN=39403057471
EXPECTED={
 "A":{"artifact_id":12255266791,"job_id":118562242581,"zip_sha256":"0a69658981b022cd20e6b9a3161ed5b30038ff01c69993274535b8c9294af887"},
 "B":{"artifact_id":12255171980,"job_id":118562242600,"zip_sha256":"927ab91176e15385d5ccc72179e9aba15535cc90902ca9b5159ebf6df127fe7c"}}
OUT=Path(__file__).resolve().parent/"new_original_artifacts"
OUT.mkdir(exist_ok=True)
def sha(v):return hashlib.sha256(v).hexdigest()
manifest={"schema":"h2-restricted-cas-full-rollback-original-ab-v1",
  "source_run":RUN,"tested_commit":TESTED,"records":{}}
for copy,spec in EXPECTED.items():
 cmd=["gh","api","-H","Accept: application/vnd.github+json",
  f"repos/{REPO}/actions/artifacts/{spec['artifact_id']}/zip"]
 res=subprocess.run(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True,timeout=90)
 raw=res.stdout
 assert sha(raw)==spec["zip_sha256"],"original Github artifact ZIP mismatch "+copy
 zname=copy+".github_original.zip.b64"
 (OUT/zname).write_bytes(base64.b64encode(raw)+b"\n")
 items={}
 with zipfile.ZipFile(io.BytesIO(raw)) as archive:
  assert archive.testzip() is None and len(archive.namelist())==2
  for member in archive.namelist():
   original=archive.read(member)
   obj=json.loads(original)
   assert obj["copy"]==copy
   assert obj["tested_commit"]==TESTED
   if obj.get("schema")=="h2-restricted-real-cas-pg18-v1": typ="cas"; verdict="PASS"; count=77
   elif "acl_physical_residual" in obj: typ="rollback"; verdict="PARTIAL"; count=17
   else:raise AssertionError("unexpected report schema "+member)
   assert obj["total"]==obj["passed"]==count
   assert obj["verdict"]==verdict and not obj["errors"]
   filename=copy+"."+typ+".original.json"
   (OUT/filename).write_bytes(original)
   items[typ]={"member":member,"file":filename,"bytes":len(original),
      "sha256":sha(original),"total":count,"verdict":verdict}
 assert set(items)=={"cas","rollback"}
 manifest["records"][copy]={"artifact_id":spec["artifact_id"],"job_id":spec["job_id"],
   "zip_b64_file":zname,"zip_bytes":len(raw),"zip_sha256":sha(raw),"reports":items}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
print(json.dumps({"status":"FROZEN_ORIGINALS","run":RUN,"tested":TESTED,
 "copies":{k:{t:v["sha256"] for t,v in x["reports"].items()} for k,x in manifest["records"].items()}},sort_keys=True))
