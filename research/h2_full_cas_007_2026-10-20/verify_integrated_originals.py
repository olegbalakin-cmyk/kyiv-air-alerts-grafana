#!/usr/bin/env python3
"""Independent Git-only original A/B CAS 007 byte, scope, attribution and corruption checks."""
import base64,hashlib,io,json,zipfile
from collections import Counter
from pathlib import Path
P=Path(__file__).resolve().parent
ROOT=P/"integrated_original_ab"
ORIG=P.parents[0]/"h2_pg18_full_offline_2026-10-20/new_original_artifacts"
def sha(s):return hashlib.sha256(s).hexdigest()
def verify(copy,item,raw=None):
    raw=base64.b64decode((ROOT/item["zip_file"]).read_bytes()) if raw is None else raw
    assert len(raw)==item["zip_bytes"] and sha(raw)==item["zip_sha256"]
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.testzip() is None and z.namelist()==[item["member"]]
        report=z.read(item["member"])
    assert len(report)==item["json_bytes"] and sha(report)==item["json_sha256"]
    assert report==(ROOT/item["json_file"]).read_bytes()
    p=json.loads(report)
    assert p["copy"]==copy and p["tested_commit"]=="00563b1eb5cb597fe0d3492ad12ae9c0645b2c6e"
    assert p["verdict"]==item["verdict"]=="PASS"
    assert p["total"]==p["passed"]==item["checks"]==144
    assert p["accepted_original_77_executed"]==item["accepted_original"]==77
    assert p["topology_additions"]==item["topology_additions"]==67
    assert len(p["assertions"])==144 and all(x["pass"] for x in p["assertions"])
    assert not p["errors"]
    old=json.loads((ORIG/(copy+".cas.original.json")).read_bytes())
    assert old["verdict"]=="PASS" and old["passed"]==77
    assert Counter(x["name"] for x in p["assertions"] if not x["name"].startswith("007_")) == Counter(x["name"] for x in old["assertions"])
    return p
manifest=json.loads((ROOT/"manifest.json").read_bytes())
assert manifest["source_run"]==39434358306
assert manifest["tested_commit"]=="00563b1eb5cb597fe0d3492ad12ae9c0645b2c6e"
assert set(manifest["records"])=={"A","B"}
expected={
"A":(12268903364,118667337877,"5852fef340d2da9af7b09c3607ff6f73cd6a920a68e846aacb718e61136e56d7"),
"B":(12269851414,118667338105,"e33cab4ac64d58ce82a3c7f063d46756ea84b34f9cb4fa27b27af9073987341c")}
corruptions=0
for copy,item in manifest["records"].items():
    assert (item["artifact_id"],item["job_id"],item["zip_sha256"])==expected[copy]
    assert item["job_name"].endswith("("+copy+")")
    p=verify(copy,item)
    raw=base64.b64decode((ROOT/item["zip_file"]).read_bytes())
    for bad in (raw[:-1],raw[:-1]+bytes([raw[-1]^1])):
        try:verify(copy,item,bad)
        except (AssertionError,ValueError,zipfile.BadZipFile):corruptions+=1
        else:raise AssertionError("zip corruption not detected")
    f=ROOT/item["json_file"];before=f.read_bytes()
    try:
        f.write_bytes(before+b"!")
        try:verify(copy,item)
        except (AssertionError,ValueError,zipfile.BadZipFile):corruptions+=1
        else:raise AssertionError("json corruption not detected")
    finally:f.write_bytes(before)
    for k,v in (("zip_sha256","0"*64),("json_sha256","f"*64),
                ("verdict","PARTIAL"),("checks",143),("job_id",-1)):
        m=dict(item);m[k]=v
        try:
            if k=="job_id":assert (m["artifact_id"],m["job_id"],m["zip_sha256"])==expected[copy]
            else:verify(copy,m)
        except (AssertionError,ValueError,zipfile.BadZipFile):corruptions+=1
        else:raise AssertionError("metadata corruption not detected "+k)
assert corruptions==16,corruptions
print(json.dumps({"status":"PASS","original_zip":2,"original_json":2,
                  "original_assertions_per_copy":77,"new_total_per_copy":144,
                  "rejected_corruptions":corruptions},sort_keys=True))
