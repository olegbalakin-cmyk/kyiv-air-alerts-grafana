#!/usr/bin/env python3
"""Stage a C6 six-file candidate in an ISOLATED directory. Never push or deploy.

A signed-off proof authorizes only creation of a local Git candidate snapshot.
The gate deliberately returns production_publication_allowed=False. Any FAIL
leaves the input site, existing Git worktree and remote unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scripts import c6_neon_publication_gate as gate

FILES = {
    "dashboard_data.json": "kyiv-air-alerts-grafana/data/dashboard_data.json",
    "site_derived.json": "kyiv-air-alerts-grafana/data/site_derived.json",
    "alerts_combined.json": "kyiv-air-alerts-grafana/data/alerts_combined.json",
    "kyiv_threat_mix.json": "kyiv-air-alerts-grafana/data/kyiv_threat_mix.json",
    "sevastopol_events.json": "kyiv-air-alerts-grafana/data/sevastopol_events.json",
    "historical-daily-kpi.json": "historical-daily-kpi.json",
}
AUXILIARY = {"kyiv_threat_mix.json", "sevastopol_events.json"}
CASUALTY_FIELDS = ("casualties", "casualties_by_city")
STATE = "INTEGRATION_PREPARED_PUBLICATION_OFF"


class Blocked(ValueError):
    pass


def require(value, reason):
    if not value:
        raise Blocked(reason)


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(raw: bytes):
    return hashlib.sha256(raw).hexdigest()


def intervals(rows):
    require(isinstance(rows, list), "KYIV_INTERVAL_FORMAT")
    return {(r["start"], r["end"]) for r in rows}


def validate(proof: Path, site: Path, *, as_of: datetime,
             expected_c2_corpus: str, expected_branch: str,
             expected_input_sha: str, expected_workflow_sha: str,
             expected_run_id: int, expected_run_attempt: int,
             expected_bundle_sha256: str):
    result = gate.inspect(proof, as_of=as_of)
    require(result["status"] == "PASS_SCOPED_PROOF_NO_PUBLICATION"
            and result["production_publication_allowed"] is False,
            "RESEARCH_NOT_A_PUBLICATION_GRANT")
    verdict = read(proof / "verdict.json")
    binding = read(proof / "historical_freshness_binding.json")
    readback = read(proof / "readback_proof.json")
    manifest = read(proof / "sha256_manifest.json")
    run = readback.get("capture_run_identity")
    require(isinstance(run, dict), "SAME_RUN_CAPTURE_IDENTITY_MISSING")
    require(run.get("github_run_id") == expected_run_id
            and run.get("github_run_attempt") == expected_run_attempt
            and run.get("workflow_sha") == expected_workflow_sha
            and run.get("input_sha") == expected_input_sha,
            "SAME_RUN_CAPTURE_IDENTITY_MISMATCH")
    require(verdict.get("c2_corpus_sha256") == expected_c2_corpus
            and binding.get("corpus_sha256") == expected_c2_corpus
            and readback.get("c2_corpus_sha256") == expected_c2_corpus,
            "SAME_RUN_CORPUS_MISMATCH")
    require(verdict.get("neon_branch") == expected_branch
            and binding.get("db_branch") == expected_branch
            and binding.get("input_sha") == expected_input_sha,
            "SAME_RUN_BRANCH_OR_INPUT_MISMATCH")
    require(sha((proof / "candidate/dashboard_data.json").read_bytes())
            == manifest["files"]["candidate/dashboard_data.json"],
            "DASHBOARD_BYTES_CHANGED")
    # The current C2 exporter is the only source of these bytes; the
    # caller must independently validate its ZIP sidecar before readback.
    require(len(expected_bundle_sha256) == 64
            and all(c in "0123456789abcdef" for c in expected_bundle_sha256),
            "C2_BUNDLE_SHA_MISSING")
    require(site.is_dir() and (site / "data").is_dir(), "SITE_ROOT_MISSING")
    before = {n: (site / "data" / n).read_bytes() for n in
              FILES if n != "historical-daily-kpi.json"}
    for name in AUXILIARY:
        require((proof / "candidate" / name).read_bytes() == before[name],
                "AUXILIARY_CHANGED:" + name)
    old = json.loads(before["dashboard_data.json"])
    new = read(proof / "candidate/dashboard_data.json")
    for field in CASUALTY_FIELDS:
        require(field in old and field in new and old[field] == new[field],
                "CASUALTY_METADATA_CHANGED:" + field)
    old_kyiv = intervals(json.loads(before["alerts_combined.json"]))
    new_kyiv = intervals(read(proof / "candidate/alerts_combined.json"))
    require(bool(old_kyiv) and old_kyiv <= new_kyiv,
            "KYIV_INTERVAL_CONTINUITY_LOST")
    index = read(proof / "candidate/historical-daily-kpi.json")
    require(new.get("historical_daily_kpi") == index,
            "HISTORICAL_KPI_INDEX_MISMATCH")
    require(index.get("meta", {}).get("source_ref") == "neon:" + expected_branch
            and index.get("meta", {}).get("source_dashboard_generated_at")
                == new.get("meta", {}).get("generated_at"),
            "KPI_INDEX_RELEASE_MISMATCH")
    # Even successful candidates retain explicit no-publish metadata.
    require(new.get("meta", {}).get("publication_authority", {}).get("publication_allowed")
            is False and verdict.get("publication_allowed") is False,
            "PUBLICATION_AUTHORITY_FORGED")
    return {
        "state": STATE, "publication_allowed": False,
        "production_git_push_executed": False,
        "production_netlify_deployed": False,
        "c2_run_id": expected_run_id, "c2_run_attempt": expected_run_attempt,
        "c2_workflow_sha": expected_workflow_sha,
        "c2_input_sha": expected_input_sha, "c2_bundle_sha256": expected_bundle_sha256,
        "c2_corpus_sha256": expected_c2_corpus, "neon_branch": expected_branch,
        "files": {FILES[n]: result["candidate_files"][n] for n in sorted(FILES)},
        "runtime_static_kpi_two_plane_activation_proven": False,
        "rollback_baseline_approved": False,
    }


def prepare(*, proof: Path, site: Path, output: Path, **bindings):
    # No file inside the production site is ever mutated, including on failure.
    require(not output.exists(), "OUTPUT_ALREADY_EXISTS")
    require(not output.resolve().is_relative_to(site.resolve())
            and not site.resolve().is_relative_to(output.resolve()),
            "OUTPUT_NOT_ISOLATED")
    report = validate(proof, site, **bindings)
    with tempfile.TemporaryDirectory(prefix="c6-stage-") as tmp:
        temp = Path(tmp)
        snapshot = temp / "candidate"
        for name, destination in FILES.items():
            src = proof / "candidate" / name
            dest = snapshot / destination
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dest)
            require(sha(dest.read_bytes()) == report["files"][destination],
                    "STAGED_SHA_MISMATCH:" + name)
        report["prepared_files"] = len(FILES)
        # Purely local Git tree; remote URL, deploy, and Git credentials never used.
        (temp / "REPORT.json").write_text(
            json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp), str(output))
    return report


def local_commit(snapshot: Path, checkout: Path, report: dict):
    """Create exactly one local Git commit in an already detached isolated worktree.

    No remote is configured by this function. Caller MUST use a credential-free
    detached worktree. This is a candidate tree only, never a production commit.
    """
    require(subprocess.check_output(["git", "-C", str(checkout), "rev-parse",
                                    "--abbrev-ref", "HEAD"], text=True).strip() == "HEAD",
            "DETACHED_CHECKOUT_REQUIRED")
    require(not subprocess.check_output(["git", "-C", str(checkout), "remote"]).strip(),
            "REMOTE_NOT_REMOVED")
    for name, relative in FILES.items():
        source = snapshot / "candidate" / relative
        target = checkout / relative
        require(source.is_file() and not source.is_symlink(),
                "STAGED_FILE_MISSING:" + name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        require(sha(target.read_bytes()) == report["files"][relative],
                "LOCAL_GIT_SHA_MISMATCH:" + name)
    subprocess.run(["git", "-C", str(checkout), "add", "--", *FILES.values()], check=True)
    staged = subprocess.check_output(
        ["git", "-C", str(checkout), "diff", "--cached", "--name-only", "-z"])
    paths = {s.decode("utf-8") for s in staged.split(b"\0") if s}
    require(paths <= set(FILES.values()), "UNEXPECTED_GIT_CHANGE")
    require(paths, "NO_CANDIDATE_DELTA")
    subprocess.run(["git", "-C", str(checkout), "-c", "user.name=C6 offline proof",
                    "-c", "user.email=c6-offline@example.invalid",
                    "commit", "-m", "C6 local six-file candidate (publication OFF)"],
                   check=True, stdout=subprocess.DEVNULL)
    commit = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True).strip()
    return commit


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--proof", type=Path, required=True)
    p.add_argument("--site", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--c2-corpus", required=True)
    p.add_argument("--db-branch", required=True)
    p.add_argument("--input-sha", required=True)
    p.add_argument("--workflow-sha", required=True)
    p.add_argument("--run-id", required=True, type=int)
    p.add_argument("--run-attempt", required=True, type=int)
    p.add_argument("--bundle-sha256", required=True)
    p.add_argument("--as-of", help="Offline test override; live defaults to UTC now")
    a = p.parse_args()
    try:
        report = prepare(
            proof=a.proof, site=a.site, output=a.output,
            as_of=gate.utc(a.as_of) if a.as_of else datetime.now(timezone.utc),
            expected_c2_corpus=a.c2_corpus,
            expected_branch=a.db_branch,
            expected_input_sha=a.input_sha, expected_workflow_sha=a.workflow_sha,
            expected_run_id=a.run_id, expected_run_attempt=a.run_attempt,
            expected_bundle_sha256=a.bundle_sha256)
    except Exception:
        # Do not log secrets, database URLs, or data. Never modify output on FAIL.
        print("C6_CANDIDATE_BLOCKED; PRODUCTION_PUBLICATION_OFF")
        return 2
    print(json.dumps({"state": report["state"], "publication_allowed": False,
                      "prepared_files": 6}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
