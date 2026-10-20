#!/usr/bin/env python3
"""Verify original ACL A/B PARTIAL evidence and reject attribution/byte tampering."""
import base64,hashlib,io,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent/"expanded_acl_original_ab"
EXPECTED={"A":(12273360123,118671676646,"be1b773f0c65f471f2754fe6f4776d403901a371fadff4e356daac9c252eb24c"),
"B":(12272300948,118671676273,"b3547c3cfdca910481f14c8b678ab5f81657c016215f225454295e9a769e3750")}
def sha(d):return hashlib.sha256(d).hexdigest()
def verify(copy,v,data=None):
    data=base64.b64decode((ROOT/v["zip_file"]).read_bytes()) if data is None else data
    assert len(data)==v["zip_bytes"] and sha(data)==v["zip_sha256"]
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert z.testzip() is None and z.namelist()==[v["member"]]
        body=z.read(v["member"])
    assert body==(ROOT/v["report_file"]).read_bytes()
    assert len(body)==v["report_bytes"] and sha(body)==v["report_sha256"]
    d=json.loads(body)
    assert d["tested_commit"]=="884ae6bfe91f271dfcb355ee8c5b25cdd0dfb18f"
    assert d["copy"]==copy and d["total"]==d["passed"]==v["total"]==20
    assert d["verdict"]==v["verdict"]=="PARTIAL"
    assert d["physical_catalog_residual"]==v["raw_residual"]==["relation"]
    assert len(d["cases"])==3 and all(x["status"]=="PASS" for x in d["cases"])
    assert not d["errors"]
m=json.loads((ROOT/"manifest.json").read_bytes())
assert m["source_run"]==39435605595 and m["tested_commit"]=="884ae6bfe91f271dfcb355ee8c5b25cdd0dfb18f"
assert set(m["records"])=={"A","B"}
n=0
for copy,v in m["records"].items():
    assert (v["artifact_id"],v["job_id"],v["zip_sha256"])==EXPECTED[copy]
    assert v["job_name"].endswith("("+copy+")")
    verify(copy,v)
    raw=base64.b64decode((ROOT/v["zip_file"]).read_bytes())
    for bad in (raw[:-1],raw[:-1]+bytes([raw[-1]^1])):
        try:verify(copy,v,bad)
        except (AssertionError,ValueError,zipfile.BadZipFile):n+=1
        else:raise AssertionError("corrupt ZIP undetected")
    f=ROOT/v["report_file"];orig=f.read_bytes()
    try:
        f.write_bytes(orig+b"x")
        try:verify(copy,v)
        except (AssertionError,ValueError,zipfile.BadZipFile):n+=1
        else:raise AssertionError("corrupt JSON undetected")
    finally:f.write_bytes(orig)
    for key,val in (("zip_sha256","0"*64),("report_sha256","f"*64),
                    ("verdict","PASS"),("raw_residual",[]),("job_id",-1)):
        changed=dict(v);changed[key]=val
        try:
            if key=="job_id":assert (changed["artifact_id"],changed["job_id"],changed["zip_sha256"])==EXPECTED[copy]
            else:verify(copy,changed)
        except (AssertionError,ValueError,zipfile.BadZipFile):n+=1
        else:raise AssertionError("metadata tamper undetected "+key)
assert n==16,n
print(json.dumps({"result":"PASS","ZIPs":2,"JSONs":2,"corruption_checks":n,
                  "checks_per_copy":20,"physical_acl_residual":"relation",
                  "verdict_preserved":"PARTIAL"}))
