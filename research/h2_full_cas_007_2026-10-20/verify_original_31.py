#!/usr/bin/env python3
"""Independent Git-only verifier for original nonsuperuser 31 A/B artifact envelopes."""
import base64, hashlib, io, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent/"original_31_artifacts"
def sha(raw):return hashlib.sha256(raw).hexdigest()
def verify(c,s,raw=None):
    raw=base64.b64decode((ROOT/s["zip_b64_file"]).read_bytes()) if raw is None else raw
    assert len(raw)==s["zip_bytes"] and sha(raw)==s["zip_sha256"]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.testzip() is None
        assert z.namelist()==[s["member"]]
        body=z.read(s["member"])
    assert body==(ROOT/s["report_file"]).read_bytes()
    assert len(body)==s["report_bytes"] and sha(body)==s["report_sha256"]
    p=json.loads(body)
    assert p["copy"]==c and p["sha"]=="72c10b8e13edfc60f74f9a0ecd5c4142cfb1af1d"
    assert p["total"]==p["passed"]==31 and p["skipped"]==0
    assert p["verdict"]==s["verdict"]=="PARTIAL"
    assert p["raw_residual"]==s["raw_residual"]==["relations"]
    assert p["effective_privilege_equivalence"]=="PASS"
    assert p["raw_catalog_equivalence"]=="PARTIAL"
    assert len(p["checks"])==31 and all(i["passed"] for i in p["checks"])
    assert len(p["cases"])==5 and all(i["pass"] for i in p["cases"])
    assert not p["errors"]
m=json.loads((ROOT/"manifest.json").read_bytes())
assert m["source_run"]==39409226309
assert m["tested_commit"]=="72c10b8e13edfc60f74f9a0ecd5c4142cfb1af1d"
assert set(m["records"])=={"A","B"}
expected={"A":(12259111057,118582574943,"399cc1018ccb9e5235bf94ad5afab7e8204b6dfb0e0c03ae2dd58d033b07b820"),
          "B":(12258806396,118582575230,"3fd9d1892a59c37388451134928911bc431dc65239fb7285c6e1fe8c6532c3ce")}
controls=0
for c,s in m["records"].items():
    aid,jid,digest=expected[c]
    assert (s["artifact_id"],s["job_id"],s["zip_sha256"])==(aid,jid,digest)
    assert s["job_name"].endswith("("+c+")")
    verify(c,s)
    raw=base64.b64decode((ROOT/s["zip_b64_file"]).read_bytes())
    for corrupt in (raw[:-1]+bytes([raw[-1]^1]),raw[:-1]):
        try:verify(c,s,corrupt)
        except (AssertionError,ValueError,zipfile.BadZipFile):controls+=1
        else:raise AssertionError("undetected ZIP corruption")
    p=ROOT/s["report_file"]; original=p.read_bytes()
    try:
        p.write_bytes(original+b"X")
        try:verify(c,s)
        except (AssertionError,ValueError,zipfile.BadZipFile):controls+=1
        else:raise AssertionError("undetected JSON corruption")
    finally:p.write_bytes(original)
    for key,bad in (("zip_sha256","f"*64),("verdict","PASS"),("raw_residual",[]),("job_id",0)):
        changed=dict(s,key_not_present="no") if False else dict(s)
        changed[key]=bad
        try:
            if key=="job_id":
                assert (changed["artifact_id"],changed["job_id"],changed["zip_sha256"])==expected[c]
            else:verify(c,changed)
        except (AssertionError,ValueError,zipfile.BadZipFile):controls+=1
        else:raise AssertionError("undetected metadata corruption "+key)
assert controls==14,controls
print(json.dumps({"verdict":"PASS","original_zips":2,"original_json":2,"corruptions_rejected":controls,
"manifest_git_blob_expected":"31fcf9f59c9e6e369b30bdc61e394db1f86b217d"}))
