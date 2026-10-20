#!/usr/bin/env python3
"""Archive original 31/31 Actions ZIP envelopes and unmodified JSON members."""
import base64
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
RUN = 39409226309
TESTED = "72c10b8e13edfc60f74f9a0ecd5c4142cfb1af1d"
EXPECTED = {
    "A": {"artifact_id": 12259111057, "job_id": 118582574943,
          "sha": "399cc1018ccb9e5235bf94ad5afab7e8204b6dfb0e0c03ae2dd58d033b07b820", "bytes": 4480},
    "B": {"artifact_id": 12258806396, "job_id": 118582575230,
          "sha": "3fd9d1892a59c37388451134928911bc431dc65239fb7285c6e1fe8c6532c3ce", "bytes": 4480},
}
OUT = Path(__file__).resolve().parent / "original_31_artifacts"
OUT.mkdir(exist_ok=True)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def api(endpoint, binary=False):
    cmd = ["gh", "api", "-H", "Accept: application/vnd.github+json",
           "repos/" + REPO + "/" + endpoint]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       timeout=120, check=True)
    return p.stdout if binary else json.loads(p.stdout)

run = api("actions/runs/" + str(RUN))
assert run["id"] == RUN and run["head_sha"] == TESTED and run["conclusion"] == "success"
jobs = api("actions/runs/" + str(RUN) + "/jobs?per_page=100")["jobs"]
manifest = {"schema": "h2-original-31-nonsuperuser-ab-v1", "source_run": RUN,
            "tested_commit": TESTED, "records": {}}
for copy, spec in EXPECTED.items():
    relevant = [j for j in jobs if j["id"] == spec["job_id"]]
    assert len(relevant) == 1
    job = relevant[0]
    assert job["run_id"] == RUN and job["conclusion"] == "success"
    assert job["name"].endswith("(" + copy + ")"), job["name"]

    a = api("actions/artifacts/" + str(spec["artifact_id"]))
    assert a["id"] == spec["artifact_id"] and a["name"] == "h2-nonsuperuser-acl-" + copy
    assert a["size_in_bytes"] == spec["bytes"] and not a["expired"]
    assert a["digest"] == "sha256:" + spec["sha"]
    assert a["workflow_run"]["id"] == RUN and a["workflow_run"]["head_sha"] == TESTED
    raw = api("actions/artifacts/" + str(spec["artifact_id"]) + "/zip", binary=True)
    assert len(raw) == spec["bytes"] and sha(raw) == spec["sha"], "ZIP envelope mismatch " + copy
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        assert z.testzip() is None, "ZIP CRC failure " + copy
        names = z.namelist()
        assert len(names) == 1 and names[0].endswith(".json"), names
        member = names[0]
        body = z.read(member)
    report = json.loads(body)
    assert report["copy"] == copy and report["sha"] == TESTED
    assert report["total"] == report["passed"] == 31 and report["skipped"] == 0
    assert report["verdict"] == "PARTIAL" and report["raw_residual"] == ["relations"]
    assert report["raw_catalog_equivalence"] == "PARTIAL"
    assert report["effective_privilege_equivalence"] == "PASS"
    assert not report["errors"] and len(report["cases"]) == 5
    assert all(c["pass"] for c in report["cases"])
    assert len(report["checks"]) == 31 and all(c["passed"] for c in report["checks"])

    zfile = copy + ".original.github.zip.b64"
    jfile = copy + ".original.json"
    (OUT / zfile).write_bytes(base64.b64encode(raw) + b"\n")
    (OUT / jfile).write_bytes(body)
    manifest["records"][copy] = {
        "artifact_id": spec["artifact_id"], "job_id": spec["job_id"],
        "artifact_name": a["name"], "job_name": job["name"],
        "zip_b64_file": zfile, "zip_bytes": len(raw), "zip_sha256": sha(raw),
        "member": member, "report_file": jfile, "report_bytes": len(body),
        "report_sha256": sha(body), "verdict": report["verdict"],
        "checks": report["total"], "raw_residual": report["raw_residual"],
    }
(OUT / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
print(json.dumps({"verdict": "ORIGINAL_31_AB_FROZEN", "tested_commit": TESTED,
                  "records": {k: {"zip_sha256": v["zip_sha256"],
                                  "json_sha256": v["report_sha256"],
                                  "zip_bytes": v["zip_bytes"]}
                              for k, v in manifest["records"].items()}}, sort_keys=True))
