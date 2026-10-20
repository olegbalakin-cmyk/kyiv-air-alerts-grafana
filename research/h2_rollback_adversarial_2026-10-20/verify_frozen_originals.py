#!/usr/bin/env python3
"""Independent Git-only verifier; does not run SQL or use network."""
import base64
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path
P=Path("research/h2_rollback_adversarial_2026-10-20/frozen_2026-10-20")
manifest=json.loads((P/"manifest.json").read_bytes())
def sha(x):return hashlib.sha256(x).hexdigest()
def blob(ref,path):
    return subprocess.check_output(["git","rev-parse",ref+":"+path],text=True).strip()
def check(m,z,label,modify=None):
    a=m["copies"][label]
    assert sha(z)==a["zip_sha256"]
    assert len(z)==a["size_zip"]
    with zipfile.ZipFile(io.BytesIO(z)) as zipf:
        assert zipf.testzip() is None
        assert zipf.namelist()==[a["json_member"]]
        raw=zipf.read(a["json_member"])
    assert sha(raw)==a["json_sha256"] and len(raw)==a["json_bytes"]
    r=json.loads(raw)
    assert r["tested_commit"]==m["tested_commit"] and r["copy"]==label
    assert r["verdict"]=="PARTIAL" and not r["errors"]
    assert r["totals"]==a["totals"]
    assert r["gates"]==a["gate_results"]
    assert r["gates"]["H2_FULL_SCHEMA_ACL_OWNERSHIP_ROLLBACK"]=="PARTIAL"
    assert r["gates"]["H2_READONLY_NEON_PREFLIGHT_READINESS"]=="BLOCKED"
    assert {x["id"] for x in r["records"] if x["section"]=="R"}=={f"R{i:02d}" for i in range(1,17)}
    assert {x["id"] for x in r["records"] if x["section"]=="H"}=={f"H{i:02d}" for i in range(1,13)}
    assert {x["id"] for x in r["records"] if x["section"]=="C"}=={f"C{i}" for i in range(1,9)}
    assert all(x["status"]=="PASS" for x in r["records"] if x["section"]=="C")
    return r

assert manifest["reported_verdict"]=="PARTIAL" and manifest["run_id"]==39446642675
assert manifest["tested_commit"]=="142bd18757a432fee57f5c3536e2a40a3ccdb072"
for path,expected in manifest["tested_executables"].items():
    assert blob(manifest["tested_commit"],path)==expected
    assert blob("HEAD",path)==expected,(path,"source changed")
for label in ("A","B"):
    raw=base64.b64decode((P/manifest["copies"][label]["original_b64_filename"]).read_bytes(),validate=False)
    check(manifest,raw,label)
    print("GIT_ONLY_ORIGINAL",label,sha(raw),len(raw))
# Deliberate corruption must be rejected, including metadata and verdict rewrites.
z=base64.b64decode((P/"A.original.zip.b64").read_bytes())
mutations=[]
mutations.append(("zip_flip",lambda m,z:(m,z[:-1]+bytes([z[-1]^1]))))
mutations.append(("zip_truncate",lambda m,z:(m,z[:-10])))
mutations.append(("zip_append",lambda m,z:(m,z+b"X")))
mutations.append(("wrong_zip_hash",lambda m,z:(dict(m,copies={**m["copies"],"A":{**m["copies"]["A"],"zip_sha256":"0"*64}}),z)))
mutations.append(("wrong_job",lambda m,z:(dict(m,copies={**m["copies"],"A":{**m["copies"]["A"],"json_sha256":"0"*64}}),z)))
mutations.append(("wrong_tested_sha",lambda m,z:(dict(m,tested_commit="0"*40),z)))
mutations.append(("wrong_copy",lambda m,z:(dict(m,copies={**m["copies"],"A":{**m["copies"]["A"],"json_member":"not-the-original.json"}}),z)))
mutations.append(("wrong_total",lambda m,z:(dict(m,copies={**m["copies"],"A":{**m["copies"]["A"],"totals":{}}}),z)))
mutations.append(("wrong_partial_gate",lambda m,z:(dict(m,copies={**m["copies"],"A":{**m["copies"]["A"],"gate_results":{**m["copies"]["A"]["gate_results"],"H2_FULL_SCHEMA_ACL_OWNERSHIP_ROLLBACK":"PASS"}}}),z)))
mutations.append(("wrong_verdict",lambda m,z:(dict(m,copies={**m["copies"],"A":{**m["copies"]["A"],"gate_results":{**m["copies"]["A"]["gate_results"],"H2_READONLY_NEON_PREFLIGHT_READINESS":"PASS"}}}),z)))
for name,make in mutations:
    m2,z2=make(manifest,z)
    try:check(m2,z2,"A")
    except (AssertionError,ValueError,zipfile.BadZipFile):print("REJECTED",name)
    else:raise AssertionError("CORRUPTION_ACCEPTED "+name)
print("GIT_ONLY_PASS originals=2 corruption_rejections="+str(len(mutations)))
