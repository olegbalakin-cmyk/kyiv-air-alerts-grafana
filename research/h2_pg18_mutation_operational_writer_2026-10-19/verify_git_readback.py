#!/usr/bin/env python3
"""Independent, no-DB Git readback: byte-perfect A/B and negative controls."""
from pathlib import Path
import subprocess, shutil, tempfile, hashlib, json, sys

ROOT=Path(__file__).resolve().parent
files=["original_A.json","original_A.zip","original_B.json","original_B.zip",
       "AB_original_evidence_manifest.json","verify_original_ab.py"]
def blob(p):
    b=p.read_bytes()
    return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
def run(target):
    r=subprocess.run([sys.executable,str(target/"verify_original_ab.py")],
        capture_output=True,text=True,timeout=20)
    return r.returncode,r.stdout,r.stderr

rc,stdout,stderr=run(ROOT)
assert rc==0,(stdout,stderr)
with tempfile.TemporaryDirectory(prefix="h2-git-verify-") as t:
    tmp=Path(t)
    for name in files: shutil.copyfile(ROOT/name,tmp/name)
    tested=0
    for name in ("original_A.json","original_A.zip",
                 "original_B.json","original_B.zip"):
        p=tmp/name;original=p.read_bytes()
        for transformation in ("flip","append"):
            mutated=bytearray(original)
            if transformation=="flip": mutated[len(mutated)//2]^=1
            else: mutated.extend(b"\\ncorrupt")
            p.write_bytes(mutated)
            code,_,_=run(tmp)
            assert code !=0,("corruption went undetected",name,transformation)
            tested+=1
        p.write_bytes(original)
    manifest=tmp/"AB_original_evidence_manifest.json"
    b=manifest.read_bytes()
    manifest.write_bytes(b.replace(b'"success"',b'"failed"',1))
    code,_,_=run(tmp)
    assert code!=0,"manifest corruption undetected"
    tested+=1
report={
    "verdict":"PASS_GIT_ONLY",
    "original_pairs":"2/2",
    "negative_control_corruptions_rejected":tested,
    "artifacts":{name:{"bytes":(ROOT/name).stat().st_size,"git_blob":blob(ROOT/name)}
                 for name in files}
}
print(json.dumps(report,sort_keys=True))
