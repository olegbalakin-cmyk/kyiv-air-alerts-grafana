#!/usr/bin/env python3
"""Freeze downloaded original Actions envelope ZIPs and their exact JSON members."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile
from verify_original_ab import KNOWN, SCHEMA, OUT, digest, verify, negative_controls

REPO="olegbalakin-cmyk/kyiv-air-alerts-grafana"
OUT.mkdir(parents=True,exist_ok=True)
records={}
for identity, expected in KNOWN.items():
    zip_path=OUT/(identity+".download.zip")
    subprocess.run(["gh","api","-H","Accept: application/vnd.github+json",
        f"repos/{REPO}/actions/artifacts/{expected['artifact_id']}/zip"],
        stdout=zip_path.open("wb"),check=True,timeout=90)
    raw=zip_path.read_bytes()
    assert digest(raw)==expected["zip_sha256"],identity+": GitHub ZIP digest mismatch"
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.testzip() is None,identity+": CRC corruption"
        names=z.namelist()
        assert len(names)==1,identity+": multiple artifact members"
        member=names[0]
        original=z.read(member)
    js=json.loads(original)
    assert js["copy"]==expected["copy"],identity+": copy mismatch"
    assert js["git_commit"]==expected["head_sha"],identity+": commit mismatch"
    assert js["verdict"]==expected["verdict"],identity+": verdict mismatch"
    assert js["total"]==expected["total"] and js["passed"]==expected["passed"], identity+": incorrect count"
    zip_b64=identity+".github_original_zip.b64"
    json_name=identity+".original.json"
    (OUT/zip_b64).write_bytes(base64.b64encode(raw)+b"\n")
    (OUT/json_name).write_bytes(original)
    rec=dict(expected,zip_b64_path=zip_b64,json_path=json_name,zip_length=len(raw),
             json_sha256=digest(original),json_length=len(original),member=member)
    records[identity]=rec
    zip_path.unlink()
manifest={"schema":SCHEMA,"origin_repository":REPO,
    "artifact_download":"direct authenticated GitHub Actions ZIP bytes",
    "records":records}
(OUT/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
assert verify(manifest)
controls=negative_controls(manifest)
assert len(controls)==11
(OUT/"original_validation_receipt.json").write_text(json.dumps(
    {"verdict":"PASS","records":len(records),"zip_crc_pass":len(records),
     "corruption_rejections":controls,"manifest_sha256":digest((OUT/"manifest.json").read_bytes())},
     indent=2,sort_keys=True)+"\n")
print("H2 ORIGINAL EVIDENCE VERIFIED",len(records),"ZIPs; corruption controls",len(controls))
