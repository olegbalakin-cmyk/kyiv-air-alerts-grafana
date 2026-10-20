#!/usr/bin/env python3
"""Freeze byte-exact original A/B Actions ZIPs without replacing earlier proofs.

Only downloads artifacts of a pinned synthetic PG18 run, verifies original
artifact digests/CRC/JSON verdicts, creates versioned ZIP.b64 and manifest.
No Neon, external polling, prod, secret reads, or runtime code execution.
"""
import base64
import hashlib
import io
import json
import os
import subprocess
import urllib.request
import zipfile
from pathlib import Path

RUN = 39446642675
TESTED = "142bd18757a432fee57f5c3536e2a40a3ccdb072"
REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
ARTS = {
    "A": {"id":12276507122, "job":118710199075,
          "digest":"c46a42ef4b579aad9235b4d5080d24abfa387d9de9746312640ca058d68d0203"},
    "B": {"id":12275672717, "job":118710199384,
          "digest":"865e577087eea0835a66520b70d21c8762eb2fc41add54a1608ff5401a5d4b60"}
}
DIR = Path("research/h2_rollback_adversarial_2026-10-20/frozen_2026-10-20")
token=os.environ["GITHUB_TOKEN"]
def api(path):
    url=f"https://api.github.com/repos/{REPO}/{path}"
    request=urllib.request.Request(url,headers={"Authorization":"Bearer "+token,
        "Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28",
        "User-Agent":"h2-synthetic-original-freeze"})
    # GitHub Actions artifact ZIP is served by a signed cross-host redirect.
    # Never propagate the GitHub Bearer token to the presigned storage URL.
    class SignedZipRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            redirected=super().redirect_request(req,fp,code,msg,headers,newurl)
            if redirected is not None:
                from urllib.parse import urlsplit
                if urlsplit(req.full_url).netloc!=urlsplit(newurl).netloc:
                    redirected.remove_header("Authorization")
                    redirected.remove_header("X-GitHub-Api-Version")
            return redirected
    opener=urllib.request.build_opener(SignedZipRedirect())
    with opener.open(request,timeout=90) as r:return r.read()
def sha(b):return hashlib.sha256(b).hexdigest()
def git_blob(path,at=TESTED):
    return subprocess.check_output(["git","rev-parse",at+":"+path]).decode().strip()
def verified_run():
    x=json.loads(api(f"actions/runs/{RUN}"))
    assert x["head_sha"]==TESTED and x["conclusion"]=="success"
    assert x["head_branch"]=="research-h2-rollback-adversarial-pg18-2026-10-20-gpt6"
    return x
def main():
    verified_run()
    DIR.mkdir(parents=True,exist_ok=True)
    manifest={"version":"h2-adversarial-original-ab-v1","scope":"SYNTHETIC_POSTGRES_ONLY",
              "run_id":RUN,"tested_commit":TESTED,"reported_verdict":"PARTIAL",
              "copies":{},"original_files":[],"tested_executables":{},
              "limitations":["Git-only integrity is not executable SQL proof",
                             "physical relation ACL residual not accepted",
                             "H11 already-migrated registry contract remains PARTIAL",
                             "R09 inherited privileges require external role hygiene"]}
    for path in ["research/h2_rollback_adversarial_2026-10-20/"+x for x in
                 ["harness.py","rollback_matrix.py","history_matrix.py","security_matrix.py","acl_residual.py","run_all.py"]]:
        manifest["tested_executables"][path]=git_blob(path)
    for label,a in ARTS.items():
        info=json.loads(api(f"actions/artifacts/{a['id']}"))
        assert info["workflow_run"]["id"]==RUN and info["expired"] is False,info
        assert info["name"]==f"h2-adversarial-{label}",info
        assert info["digest"]=="sha256:"+a["digest"],info
        z=api(f"actions/artifacts/{a['id']}/zip")
        assert sha(z)==a["digest"],(label,sha(z))
        assert len(z)==info["size_in_bytes"]
        with zipfile.ZipFile(io.BytesIO(z)) as arc:
            assert arc.testzip() is None
            names=arc.namelist()
            assert len(names)==1,names
            raw=arc.read(names[0])
        report=json.loads(raw)
        assert report["copy"]==label and report["tested_commit"]==TESTED
        assert report["pg_version"].startswith("18.6")
        assert report["verdict"]=="PARTIAL" and not report["errors"]
        assert {r["id"] for r in report["records"] if r["section"]=="R"}=={f"R{i:02d}" for i in range(1,17)}
        assert {r["id"] for r in report["records"] if r["section"]=="H"}=={f"H{i:02d}" for i in range(1,13)}
        assert {r["id"] for r in report["records"] if r["section"]=="C"}=={f"C{i}" for i in range(1,9)}
        assert report["gates"]["H2_ACL_RAW_CATALOG_EQUIVALENCE"]=="PARTIAL"
        name=f"{label}.original.zip.b64"
        (DIR/name).write_text(base64.b64encode(z).decode()+"\n")
        manifest["copies"][label]={"job":a["job"],"artifact_id":a["id"],
              "size_zip":len(z),"zip_sha256":sha(z),
              "json_member":names[0],"json_bytes":len(raw),"json_sha256":sha(raw),
              "verdict":report["verdict"],"totals":report["totals"],
              "race_timelines":report["race_timelines"],
              "gate_results":report["gates"],"original_b64_filename":name}
        print(label,"ORIGINAL_BYTES_VERIFIED",len(z),"JSON",len(raw),"SHA",sha(z))
    (DIR/"manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    print("FROZEN_MANIFEST_SHA256",sha((DIR/"manifest.json").read_bytes()))
if __name__=="__main__":main()
