#!/usr/bin/env python3
"""Freeze original GitHub Actions ZIP files, not re-packed JSON."""
import os,io,json,hashlib,zipfile,urllib.request,subprocess
from pathlib import Path
R="olegbalakin-cmyk/kyiv-air-alerts-grafana"
RUN=39504096121
TESTED="5213a91ae593a3ef80f4936d55c7ec08c4a5737e"
BASE=Path(__file__).resolve().parents[2]
OUT=Path(__file__).resolve().parent/"original_ab"
def request(path):
    req=urllib.request.Request("https://api.github.com/repos/"+R+"/"+path,
        headers={"Authorization":"Bearer "+os.environ["GITHUB_TOKEN"],"User-Agent":"h2-008-proof"})
    with urllib.request.urlopen(req,timeout=75) as x:return x.read()
def get(path):return json.loads(request(path))
def digest(b):return hashlib.sha256(b).hexdigest()
def git(commit,path):return subprocess.check_output(["git","rev-parse",commit+":"+path],cwd=BASE,text=True).strip()
run=get("actions/runs/"+str(RUN))
assert run["status"]=="completed" and run["conclusion"]=="success" and run["head_sha"]==TESTED
jobs=get("actions/runs/"+str(RUN)+"/jobs?per_page=100")["jobs"]
arts=get("actions/runs/"+str(RUN)+"/artifacts?per_page=100")["artifacts"]
paths=["research/h2_non_superuser_guard_acl_2026-10-20/008_non_superuser_acl_rollback.sql",
       "research/h2_008_late_acl_2026_10_21/008_late_fault_instrumented.sql",
       "research/h2_008_late_acl_2026_10_21/test_late_acl.py",
       ".github/workflows/h2-actual-008-late-acl-2026-10-21.yml"]
blobs={p:git(TESTED,p) for p in paths}
assert blobs[paths[0]]=="59eab59235f8aee14837ce7494649edba674e1ce"
assert all(git("HEAD",p)==b for p,b in blobs.items())
OUT.mkdir(exist_ok=True)
m={"run":RUN,"tested_sha":TESTED,"source_blobs":blobs,"copies":{}}
for copy in ["A","B"]:
    j,=[x for x in jobs if x["name"]=="pg18 ("+copy+")"]
    a,=[x for x in arts if x["name"]=="h2-008-late-acl-"+copy]
    assert j["conclusion"]=="success" and j["head_sha"]==TESTED
    assert a["workflow_run"]["id"]==RUN and a["workflow_run"]["head_sha"]==TESTED
    data=request("actions/artifacts/"+str(a["id"])+"/zip")
    assert len(data)==a["size_in_bytes"] and "sha256:"+digest(data)==a["digest"]
    z=zipfile.ZipFile(io.BytesIO(data));assert z.testzip() is None
    members={}
    for x in z.infolist():
        if x.is_dir():continue
        b=z.read(x.filename)
        members[x.filename]={"size":len(b),"sha256":digest(b),"crc32":x.CRC}
        if x.filename.endswith(".json"):
            report=json.loads(b)
            assert report["copy"]==copy and report["commit"]==TESTED
            assert report["verdict"]=="PARTIAL" and not report["errors"]
            assert report["tests_passed"]==report["tests_total"] and report["tests_total"]>=14
            assert report["original_008_git_blob"]==blobs[paths[0]]
            assert len(report["observations"]["physical_relacl_delta"])==7
    assert len(members)==1,members
    (OUT/(copy+".zip")).write_bytes(data)
    m["copies"][copy]={"job":j["id"],"artifact":a["id"],"file":copy+".zip",
      "size":len(data),"sha256":digest(data),"members":members}
    print("ORIGINAL_ZIP_PASS",copy,j["id"],a["id"],digest(data))
(OUT/"manifest.json").write_text(json.dumps(m,sort_keys=True,indent=2)+"\n")
print("ORIGINAL_AB_ZIP_FREEZE_PASS")
