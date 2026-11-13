#!/usr/bin/env python3
"""Fail-closed, read-only preflight for one immutable C2 job-success recovery.

This is NOT a C2 rerun, Git publication permission, or a workaround for
environment/owner approval. Only the exact 2026-11-12 attempt-1 bundle passes.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import tempfile
import zipfile
from pathlib import Path

from scripts.c2_shadow_bundle import verify_archive

REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
RUN = 43321997695
ATTEMPT = 1
WORKFLOW_ID = 360885782
WORKFLOW_PATH = ".github/workflows/update-netlify-site.yml"
WORKFLOW_SHA = "712c9e351fc3548325cf594cf0617bb33e70a002"
INPUT_SHA = "6648a11242fac16cf023114cd6e58a65c3b49968"
CORPUS_SHA = "f855be9c2cfb8617903666d0d898c223c6a91ac0fc56029b5b036dc153db84d4"
BRANCH = "br-bold-mode-b5rub8pq"
ENDPOINT = "ep-still-violet-b5bg6mhp.c-7.us-east-2.aws.neon.tech"
ARTIFACT_ID = 13991878472
ARTIFACT_NAME = "c2-shadow-inputs-43321997695-1"
OUTER_SHA = "2686f1c54e77e630fd7f8c920f4d88d05f6048b68be26f11f5e3fa03745bebde"
INNER_SHA = "3f53c7ca4a0bc1d0f25cd228dcde003cd45ac247ecab76747405f556f75e8030"
JOBS = {
    "update-site": (131544763676, "success"),
    "c6-neon-six-json-prepare": (131559447936, "failure"),
    "c6-neon-owner-gated-git-release": (131544765618, "skipped"),
    "c6-neon-final-prepare-only": (131544766010, "skipped"),
}
CITY_COUNT = 23

class RecoveryBlocked(ValueError):
    pass

def require(condition, reason):
    if not condition:
        raise RecoveryBlocked(reason)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def verify_metadata(run, jobs, artifact):
    require(run.get("id") == RUN and run.get("run_attempt") == ATTEMPT
            and run.get("workflow_id") == WORKFLOW_ID
            and run.get("path") == WORKFLOW_PATH
            and run.get("head_branch") == "main"
            and run.get("head_sha") == WORKFLOW_SHA
            and run.get("event") == "workflow_dispatch"
            and run.get("status") == "completed"
            and run.get("conclusion") == "failure"
            and run.get("repository", {}).get("full_name") == REPO,
            "PINNED_C2_RUN_IDENTITY_OR_RESULT")
    entries = jobs.get("jobs")
    require(isinstance(entries, list) and
            jobs.get("total_count") == len(JOBS) and len(entries) == len(JOBS)
            and {j.get("name") for j in entries} == set(JOBS),
            "UNEXPECTED_C2_JOB_SET")
    by_name = {j["name"]: j for j in entries}
    for name, (job_id, conclusion) in JOBS.items():
        j = by_name[name]
        require(j.get("id") == job_id and j.get("run_id") == RUN
                and j.get("run_attempt") == ATTEMPT
                and j.get("status") == "completed"
                and j.get("conclusion") == conclusion,
                "PINNED_JOB_NOT_ACCEPTABLE:" + name)
    updater = by_name["update-site"]
    require(type(updater.get("runner_id")) is int
            and updater["runner_id"] > 0
            and len(updater.get("steps") or []) >= 40
            and all(s.get("conclusion") == "success"
                    for s in updater["steps"]),
            "C2_UPDATER_DID_NOT_FINISH")
    failed = by_name["c6-neon-six-json-prepare"]
    require(failed.get("runner_id") == 0 and
            failed.get("runner_name") in ("", None) and
            failed.get("steps") == [] and
            failed.get("created_at") and failed.get("started_at") and
            failed.get("completed_at"),
            "C6_FAILURE_MAY_HAVE_EXECUTED_CODE")
    for name in ("c6-neon-owner-gated-git-release",
                 "c6-neon-final-prepare-only"):
        j = by_name[name]
        require(j.get("steps") == [] and j.get("runner_id") in (None, 0),
                "OTHER_JOB_MAY_HAVE_EXECUTED:" + name)
    require(artifact.get("id") == ARTIFACT_ID and
            artifact.get("name") == ARTIFACT_NAME and
            artifact.get("expired") is False and
            artifact.get("digest") == "sha256:" + OUTER_SHA and
            artifact.get("workflow_run", {}).get("id") == RUN and
            artifact.get("workflow_run", {}).get("head_sha") == WORKFLOW_SHA and
            artifact.get("workflow_run", {}).get("head_branch") == "main",
            "IMMUTABLE_C2_ARTIFACT_IDENTITY")
    return by_name

def verify_outer(outer):
    require(sha(outer) == OUTER_SHA, "OUTER_ZIP_SHA_MISMATCH")
    with zipfile.ZipFile(io.BytesIO(outer)) as z:
        require(set(z.namelist()) == {
            "c2-shadow-inputs.zip", "c2-shadow-inputs.zip.sha256"},
            "OUTER_ZIP_MEMBERS_INVALID")
        inner = z.read("c2-shadow-inputs.zip")
        sidecar = z.read("c2-shadow-inputs.zip.sha256").decode("ascii")
    require(sha(inner) == INNER_SHA and
            sidecar.strip() == INNER_SHA + "  c2-shadow-inputs.zip",
            "INNER_C2_SHA_OR_SIDECAR_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="work-l-c2-") as tmp:
        tmp_inner = Path(tmp) / "c2-shadow-inputs.zip"
        tmp_inner.write_bytes(inner)
        manifest = verify_archive(
            tmp_inner, INNER_SHA, destination=Path(tmp) / "validated",
            run_id=RUN, workflow_sha=WORKFLOW_SHA, input_sha=INPUT_SHA,
            db_branch=BRANCH, db_endpoint=ENDPOINT)
        rec = json.loads((Path(tmp) / "validated/receipt.json").read_text())
        status = json.loads((Path(tmp) / "validated/status.json").read_text())
    source = manifest.get("historical_capture_receipts", {})
    complete = source.get("complete_cities", [])
    receipt_cities = source.get("receipt_cities", [])
    require(manifest.get("github_run_id") == RUN
            and manifest.get("github_run_attempt") == ATTEMPT
            and manifest.get("corpus_sha256") == CORPUS_SHA
            and len(complete) == len(receipt_cities) == CITY_COUNT
            and len(set(complete)) == CITY_COUNT
            and set(complete) == set(receipt_cities)
            and source.get("publication_allowed") is False,
            "C2_ATTEMPT_CORPUS_OR_23_SOURCE_RECEIPTS")
    require(rec.get("status") == "succeeded" and
            rec.get("persistence_status") == "persisted" and
            rec.get("failure_policy") == "fail_closed" and
            rec.get("production_output_mutation") is False and
            rec.get("workflow_sha") == WORKFLOW_SHA and
            rec.get("input_sha") == INPUT_SHA and
            rec.get("corpus_sha256") == CORPUS_SHA and
            rec.get("db_branch") == BRANCH and
            rec.get("canonical_episode_count") == 33315 and
            rec.get("episodes_inserted") == 48 and
            rec.get("episodes_updated") == 0 and
            rec.get("city_count") == CITY_COUNT and
            status.get("canonical_persistence_status") == "NEON_SUCCEEDED" and
            status.get("canonical_db_commit") == "CONFIRMED" and
            status.get("canonical_receipt_validated") is True,
            "C2_WRITER_RECEIPT_OR_PERSISTENCE_INVALID")
    return inner, sidecar

def main():
    p = argparse.ArgumentParser()
    for k in ("run", "jobs", "artifact", "outer", "bundle-output"):
        p.add_argument("--" + k, type=Path, required=True)
    for k in ("run-id", "run-attempt", "workflow-sha", "input-sha",
              "corpus-sha", "bundle-sha256", "db-branch", "db-endpoint",
              "artifact-id", "artifact-name"):
        p.add_argument("--" + k, required=True)
    args = p.parse_args()
    pinned = {
        "run_id": str(RUN), "run_attempt": str(ATTEMPT),
        "workflow_sha": WORKFLOW_SHA, "input_sha": INPUT_SHA,
        "corpus_sha": CORPUS_SHA, "bundle_sha256": INNER_SHA,
        "db_branch": BRANCH, "db_endpoint": ENDPOINT,
        "artifact_id": str(ARTIFACT_ID), "artifact_name": ARTIFACT_NAME,
    }
    for key, want in pinned.items():
        require(getattr(args, key) == want, "OWNER_PIN_MISMATCH:" + key)
    verify_metadata(json.loads(args.run.read_text()),
                    json.loads(args.jobs.read_text()),
                    json.loads(args.artifact.read_text()))
    inner, sidecar = verify_outer(args.outer.read_bytes())
    require(not args.bundle_output.exists(), "RECOVERY_OUTPUT_EXISTS")
    args.bundle_output.parent.mkdir(parents=True, exist_ok=True)
    args.bundle_output.write_bytes(inner)
    args.bundle_output.with_name("c2-shadow-inputs.zip.sha256").write_text(
        sidecar, encoding="ascii")
    print("WORK_L_PINNED_C2_JOB_AND_BUNDLE_PASS; NO_PUBLICATION")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
