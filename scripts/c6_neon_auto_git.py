#!/usr/bin/env python3
"""One existing-C2 -> verified-Neon -> Git-only cycle. Never touches Netlify.

Capture copies ONLY same-run C2 data/ and Grafana state into an Actions artifact.
Publish consumes the existing physical reader proof and release-binding helpers;
all checks finish before a single fast-forward commit to site-prod. Both commands
are inert until their separately guarded workflow steps run.
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

from scripts import c6_neon_git_candidate as candidate
from scripts import c6_neon_publication_gate as proof_gate
from scripts import c6_neon_release_binding as release

PREFIX = "kyiv-air-alerts-grafana/data/"
GRAFANA = "kyiv-air-alerts-grafana/grafana/dashboard.json"
DELIVERED = frozenset(p for n, p in candidate.FILES.items()
                      if n != "historical-daily-kpi.json")
SCHEMA = "c6-neon-auto-c2-delta-v1"
REPOSITORY = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
NEON_BRANCH = "br-bold-mode-b5rub8pq"

# One immutable, independently verified exception. No generic failed-run bypass.
RECOVERY_PINS = {
    "run_id": 43523629106,
    "run_attempt": 1,
    "workflow_sha": "5606147a955b64e17474688c6a13596b21d93580",
    "input_sha": "54079326ae2b4e691e2bfcf7cd1a51c9705404eb",
    "bundle_artifact_id": 14086255755,
    "bundle_outer_sha256": "b4af6197078ccb980dabc4e1c4fa3cd3c5ce9029599650ace727930a536847da",
    "bundle_inner_sha256": "9f4a7ccbb9f7468aa72b612cad512ecd0eb19ea8fd484146915ac07a08333493",
    "status_artifact_id": 14085756162,
    "status_outer_sha256": "59e684643489585cae1d52abf424aeb9f553d7417fa4d36ad24cfd5f5f49ad70",
    "corpus_sha256": "123c515db11e0a22ede051c7b638df0242404190f553fb2daf292585731e1f00",
    "writer_run_uuid": "90061757-b44b-4389-9fd0-8440d2af367d",
    "db_endpoint": "ep-still-violet-b5bg6mhp.c-7.us-east-2.aws.neon.tech",
}
RECOVERY_JOB_CONCLUSIONS = {
    "update-site": "failure",
    "c6-neon-six-json-prepare": "skipped",
    "c6-neon-auto-git-publish": "skipped",
    "c6-neon-final-prepare-only": "skipped",
    "c6-neon-owner-gated-git-release": "skipped",
}

# Fixed capture() guard identifiers only; never echo arbitrary exception text.
SAFE_CAPTURE_BLOCK_REASONS = frozenset({
    "CAPTURE_ARGS_MISSING",
    "C2_CHECKPOINTS_MISSING",
    "C2_DELTA_TOO_MANY_FILES",
    "C2_GENERATION_NOT_UPDATED",
    "C2_INPUT_HEAD_MISMATCH",
    "C2_WRITER_RECEIPT_NOT_PASS",
    "DELETIONS_RENAMES_OR_CONFLICTS_BLOCKED",
    "INVALID_C2_DELTA_FILE",
    "INVALID_GIT_STATUS",
    "OUTPUT_NOT_ISOLATED",
    "OUTSIDE_C2_DATA_ALLOWLIST",
    "UNEXPECTED_GIT_DATA_PATH",
})


class Blocked(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise Blocked(reason)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(repo, *args):
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True).strip()


def remote_head(repo):
    result = git(repo, "ls-remote", "origin", "refs/heads/site-prod").split()
    require(len(result) == 2 and result[1] == "refs/heads/site-prod",
            "REMOTE_SITE_PROD_MISSING")
    return result[0]


def allowed(path):
    return (path.startswith(PREFIX) and
            len(Path(path).parts) >= 3 and
            ".." not in Path(path).parts) or path == GRAFANA


def safe_file(root, path):
    require(allowed(path), "OUTSIDE_C2_DATA_ALLOWLIST")
    full = root / path
    require(full.is_file() and not full.is_symlink() and
            0 < full.stat().st_size <= 128 * 1024 * 1024,
            "INVALID_C2_DELTA_FILE")
    return full


def changed_paths(checkout):
    raw = subprocess.check_output(
        ["git", "-C", str(checkout), "status", "--porcelain=v1",
         "-z", "--untracked-files=all", "--",
         "kyiv-air-alerts-grafana/data", GRAFANA])
    paths = set()
    for item in raw.split(b"\0"):
        if not item:
            continue
        require(len(item) >= 4, "INVALID_GIT_STATUS")
        status, path = item[:2].decode("ascii"), item[3:].decode("utf-8")
        require(status in {" M", "M ", "MM", "??", " A", "A "},
                "DELETIONS_RENAMES_OR_CONFLICTS_BLOCKED")
        require(allowed(path) and path not in paths,
                "UNEXPECTED_GIT_DATA_PATH")
        paths.add(path)
    return paths


def capture(checkout, output, *, input_sha, workflow_sha, run_id,
            run_attempt, status_path):
    """Freeze C2's QA-complete changed files; no Git commit and no push."""
    checkout, output = Path(checkout).resolve(), Path(output).resolve()
    require(not output.exists() and not output.is_relative_to(checkout),
            "OUTPUT_NOT_ISOLATED")
    require(git(checkout, "rev-parse", "HEAD") == input_sha and
            git(checkout, "branch", "--show-current") == "site-prod",
            "C2_INPUT_HEAD_MISMATCH")
    status = load(status_path)
    require(status.get("canonical_persistence_status") == "NEON_SUCCEEDED"
            and status.get("canonical_receipt_validated") is True
            and status.get("workflow_sha") == workflow_sha
            and status.get("input_sha") == input_sha,
            "C2_WRITER_RECEIPT_NOT_PASS")
    require((checkout / PREFIX / "c2_history_capture_checkpoints.json").is_file(),
            "C2_CHECKPOINTS_MISSING")
    paths = sorted(changed_paths(checkout))
    require(candidate.FILES["dashboard_data.json"] in paths,
            "C2_GENERATION_NOT_UPDATED")
    require(len(paths) <= 256, "C2_DELTA_TOO_MANY_FILES")
    output.mkdir(parents=True)
    hashes = {}
    for path in paths:
        source = safe_file(checkout, path)
        dest = output / "files" / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        hashes[path] = sha(dest)
    manifest = {
        "schema": SCHEMA, "input_sha": input_sha,
        "workflow_sha": workflow_sha, "run_id": int(run_id),
        "run_attempt": int(run_attempt), "files": hashes,
        "netlify_deployments_per_update": 0,
        "git_publication_performed": False,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8")
    return manifest


def verify_capture(delta, report, *, workflow_sha, run_id, run_attempt):
    delta = Path(delta).resolve()
    m = load(delta / "manifest.json")
    require(m.get("schema") == SCHEMA
            and m.get("input_sha") == report.get("c2_input_sha")
            and m.get("workflow_sha") == workflow_sha
            and report.get("c2_workflow_sha") == workflow_sha
            and m.get("run_id") == report.get("c2_run_id") == int(run_id)
            and m.get("run_attempt") == report.get("c2_run_attempt")
            == int(run_attempt)
            and m.get("netlify_deployments_per_update") == 0
            and m.get("git_publication_performed") is False,
            "C2_DELTA_IDENTITY_MISMATCH")
    hashes = m.get("files")
    require(isinstance(hashes, dict) and hashes and len(hashes) <= 256
            and candidate.FILES["dashboard_data.json"] in hashes
            and all(isinstance(v, str) and len(v) == 64 for v in hashes.values()),
            "C2_DELTA_MANIFEST_INVALID")
    observed = set()
    for p in (delta / "files").rglob("*"):
        require(not p.is_symlink(), "C2_DELTA_SYMLINK")
        if p.is_file():
            observed.add(p.relative_to(delta / "files").as_posix())
    require(observed == set(hashes), "C2_DELTA_FILE_SET_CHANGED")
    for path, digest in hashes.items():
        require(sha(safe_file(delta / "files", path)) == digest,
                "C2_DELTA_SHA_MISMATCH")
    return hashes



def verify_exact_failed_c2_archive(run, jobs, artifacts, manifest, status, receipt):
    """Allow ONLY the fixed 43523629106 failed-run archive, never another.

    The real Neon proof and freshness gates remain separate and mandatory.
    A reconstructed delta is not evidence of the original lost Git status.
    This function does no HTTP, Neon, Git operation or publication.
    """
    p = RECOVERY_PINS
    require(isinstance(run, dict) and run.get("id") == p["run_id"]
            and run.get("run_attempt") == p["run_attempt"]
            and run.get("head_sha") == p["workflow_sha"]
            and run.get("head_branch") == "main"
            and run.get("path") == ".github/workflows/update-netlify-site.yml"
            and run.get("status") == "completed"
            and run.get("conclusion") == "failure"
            and run.get("repository", {}).get("full_name") == REPOSITORY,
            "UNAPPROVED_FAILED_C2_RUN")
    require(isinstance(jobs, dict) and
            jobs.get("total_count") == len(RECOVERY_JOB_CONCLUSIONS)
            and isinstance(jobs.get("jobs"), list)
            and len(jobs["jobs"]) == len(RECOVERY_JOB_CONCLUSIONS),
            "RECOVERY_JOB_COUNT_MISMATCH")
    indexed = {j.get("name"): j for j in jobs["jobs"]}
    require(len(indexed) == len(RECOVERY_JOB_CONCLUSIONS)
            and set(indexed) == set(RECOVERY_JOB_CONCLUSIONS),
            "RECOVERY_JOB_SET_MISMATCH")
    for name, expected in RECOVERY_JOB_CONCLUSIONS.items():
        job = indexed[name]
        require(job.get("run_id") == p["run_id"]
                and job.get("status") == "completed"
                and job.get("conclusion") == expected,
                "RECOVERY_JOB_CONCLUSION_MISMATCH")
    steps = {step.get("name"): step.get("conclusion")
             for step in indexed["update-site"].get("steps", [])}
    require(steps.get("Validate verified UkraineAlarm bridge checkpoint") == "success"
            and steps.get("Run multicity canonical DB shadow") == "success"
            and steps.get("Upload C2 canonical publication status") == "success"
            and steps.get("Export verified same-run C2 shadow bundle") == "success"
            and steps.get("Upload verified C2 shadow inputs") == "success"
            and steps.get("Freeze same-run C2 checkpoint delta (no commit/push)") == "failure"
            and steps.get("Upload same-run C2 delta for one Git-only commit") == "skipped"
            and steps.get("Commit updated production data and verified UkraineAlarm bridge checkpoint") == "skipped",
            "RECOVERY_WRITER_AND_CAPTURE_STEPS_NOT_PINNED")
    require(isinstance(artifacts, dict)
            and set(artifacts) == {"bundle", "status"},
            "RECOVERY_ARTIFACT_SET_MISMATCH")
    for key, artifact_id, name, digest in (
        ("bundle", p["bundle_artifact_id"],
         "c2-shadow-inputs-43523629106-1", p["bundle_outer_sha256"]),
        ("status", p["status_artifact_id"],
         "c2-publication-status-43523629106-1", p["status_outer_sha256"]),
    ):
        artifact = artifacts[key]
        require(artifact.get("id") == artifact_id
                and artifact.get("name") == name
                and artifact.get("digest") == "sha256:" + digest
                and artifact.get("expired") is False
                and artifact.get("workflow_run", {}).get("id") == p["run_id"],
                "RECOVERY_ARTIFACT_IDENTITY_MISMATCH")
    require(manifest.get("github_run_id") == p["run_id"]
            and manifest.get("github_run_attempt") == p["run_attempt"]
            and manifest.get("workflow_sha") == p["workflow_sha"]
            and manifest.get("input_sha") == p["input_sha"]
            and manifest.get("db_branch") == NEON_BRANCH
            and manifest.get("db_endpoint") == p["db_endpoint"]
            and manifest.get("canonical_run_id") == p["writer_run_uuid"]
            and manifest.get("corpus_sha256") == p["corpus_sha256"]
            and len(manifest.get("historical_capture_receipts", {})
                    .get("complete_cities", [])) == 23
            and len(set(manifest["historical_capture_receipts"]["complete_cities"])) == 23,
            "RECOVERY_C2_MANIFEST_NOT_PINNED")
    require(status.get("canonical_persistence_status") == "NEON_SUCCEEDED"
            and status.get("canonical_db_commit") == "CONFIRMED"
            and status.get("canonical_receipt_validated") is True
            and status.get("input_sha") == p["input_sha"]
            and status.get("workflow_sha") == p["workflow_sha"],
            "RECOVERY_WRITER_STATUS_NOT_PASS")
    require(receipt.get("run_id") == p["writer_run_uuid"]
            and receipt.get("status") == "succeeded"
            and receipt.get("persistence_status") == "persisted"
            and receipt.get("workflow_sha") == p["workflow_sha"]
            and receipt.get("input_sha") == p["input_sha"]
            and receipt.get("corpus_sha256") == p["corpus_sha256"]
            and receipt.get("db_branch") == NEON_BRANCH
            and receipt.get("canonical_episode_count") == 33450
            and receipt.get("episodes_inserted") == 6
            and receipt.get("episodes_updated") == 0
            and receipt.get("city_count") == 23
            and receipt.get("production_output_mutation") is False,
            "RECOVERY_WRITER_RECEIPT_NOT_PINNED")
    return {"status": "EXACT_FAILED_C2_ARCHIVE_PASS",
            "c2_run_id": p["run_id"], "c2_run_attempt": p["run_attempt"],
            "corpus_sha256": p["corpus_sha256"], "cities": 23,
            "episode_count": 33450, "publication_allowed": False}


def retains_keys(old, new):
    """Allow corrections to values, not silent deletion of existing records."""
    if isinstance(old, dict):
        return isinstance(new, dict) and set(old) <= set(new) and all(
            retains_keys(value, new[key]) for key, value in old.items())
    if isinstance(old, list):
        if not isinstance(new, list) or len(new) < len(old):
            return False
        # Exact old evidence must remain present; count alone is insufficient.
        from collections import Counter
        def fingerprint(value):
            return json.dumps(value, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"))
        return not (Counter(map(fingerprint, old))
                    - Counter(map(fingerprint, new)))
    return new is not None


def verify_embedded(dashboard, index, manifest):
    keys = dashboard.get("multicity_meta", {}).get("production_city_keys")
    auth = dashboard.get("meta", {}).get("publication_authority", {})
    require(isinstance(keys, list) and len(keys) == len(set(keys)) == 23
            and "kyiv" in keys and "sevastopol" in keys
            and dashboard.get("historical_daily_kpi") == index
            and index.get("schema") == "verified-historical-daily-start-counts-v1"
            and index.get("meta", {}).get("expected_cities") == 23
            and index["meta"].get("verified_count") == 23
            and set(index["meta"].get("verified_cities", [])) == set(keys)
            and set(index.get("cities", {})) == set(keys)
            and all(index["cities"][key].get("status") == "verified" for key in keys)
            and index["meta"].get("source_ref") == "neon:" + NEON_BRANCH
            and index["meta"].get("source_dashboard_generated_at")
                == dashboard.get("meta", {}).get("generated_at")
            and index["meta"].get("release_manifest_sha256")
                == manifest["release_manifest_sha256"]
            and auth.get("publication_allowed") is True
            and auth.get("scope") == release.RELEASE_SCOPE
            and auth.get("delivery") == "site-prod-git"
            and auth.get("branch_id") == NEON_BRANCH
            and auth.get("release_manifest_sha256")
                == manifest["release_manifest_sha256"]
            and auth.get("historical_freshness", {}).get("binding_sha256")
                == manifest["binding"]["historical_freshness_binding_sha256"]
            and auth.get("dst_simulation") is False
            and auth.get("source_fallback") is False
            and auth.get("active_status") == "UNKNOWN_UNCERTIFIED",
            "EMBEDDED_HISTORICAL_KPI_CONTRACT_FAIL")


def publish(checkout, delta, prepared, proof, *, repository,
            workflow_sha, run_id, run_attempt, enabled, zero_deploys):
    """Verify everything before touching a Git worktree or its remote."""
    require(enabled == "true" and zero_deploys == "0",
            "AUTO_MODE_DISABLED_OR_NETLIFY_NOT_ZERO")
    require(repository == REPOSITORY, "REPOSITORY_MISMATCH")
    checkout, prepared = Path(checkout).resolve(), Path(prepared).resolve()
    report = load(prepared / "REPORT.json")
    require(report.get("state") == candidate.STATE
            and report.get("publication_allowed") is False
            and report.get("prepared_files") == 6
            and report.get("production_git_push_executed") is False
            and report.get("neon_branch") == NEON_BRANCH,
            "RESEARCH_PREPARATION_UNVERIFIED")
    require(proof_gate.inspect(Path(proof), as_of=datetime.now(timezone.utc))
            ["status"] == "PASS_SCOPED_PROOF_NO_PUBLICATION",
            "LIVE_PHYSICAL_NEON_PROOF_FAIL")
    verdict = load(Path(proof) / "verdict.json")
    require(verdict.get("c2_corpus_sha256") == report.get("c2_corpus_sha256")
            and verdict.get("neon_branch") == NEON_BRANCH,
            "PHYSICAL_CORPUS_MISMATCH")
    hashes = verify_capture(delta, report, workflow_sha=workflow_sha,
                            run_id=run_id, run_attempt=run_attempt)
    input_sha = report["c2_input_sha"]
    require(git(checkout, "branch", "--show-current") == "site-prod"
            and git(checkout, "rev-parse", "HEAD") == input_sha
            and not git(checkout, "status", "--porcelain")
            and remote_head(checkout) == input_sha,
            "SITE_PROD_MOVED_OR_UNCLEAN")
    old = load(checkout / candidate.FILES["dashboard_data.json"])
    require(old.get("meta", {}).get("publication_authority", {})
            .get("scope") == release.RELEASE_SCOPE,
            "EXISTING_NEON_CUTOVER_NOT_PRESENT")
    c2 = load(Path(delta) / "files" / candidate.FILES["dashboard_data.json"])
    for field in candidate.CASUALTY_FIELDS:
        require(field in old and field in c2
                and retains_keys(old[field], c2[field]),
                "C2_CASUALTY_RECORD_LOSS")
    source_files = report.get("files", {})
    require(set(source_files) == set(candidate.FILES.values()), "SOURCE_FILE_SET")
    for name, path in candidate.FILES.items():
        file = prepared / "candidate" / path
        require(file.is_file() and not file.is_symlink()
                and sha(file) == source_files[path],
                "PREPARED_CANDIDATE_SHA_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="c6-neon-auto-") as temp:
        final_dir = Path(temp) / "final"
        result = release.release_candidate(
            prepared, report, repository=repository,
            release_id=f"auto-{run_id}-{run_attempt}", output=final_dir)
        manifest = load(final_dir / "RELEASE_MANIFEST.json")
        require(manifest.get("files") == result["files"]
                and manifest.get("release_manifest_sha256")
                    == result["release_manifest_sha256"],
                "RELEASE_BINDING_MANIFEST_INVALID")
        final_data = final_dir / "candidate"
        new = load(final_data / candidate.FILES["dashboard_data.json"])
        index = load(final_data / candidate.FILES["historical-daily-kpi.json"])
        verify_embedded(new, index, manifest)
        require(proof_gate.utc(new["meta"]["generated_at"])
                > proof_gate.utc(old["meta"]["generated_at"]),
                "GENERATION_NOT_NEWER")
        for field in candidate.CASUALTY_FIELDS:
            require(c2[field] == new.get(field), "SAME_RUN_CASUALTY_MISMATCH")
        for name in candidate.AUXILIARY:
            path = candidate.FILES[name]
            c2_file = (Path(delta) / "files" / path
                       if path in hashes else checkout / path)
            require(c2_file.read_bytes() == (final_data / path).read_bytes(),
                    "SAME_RUN_AUXILIARY_MISMATCH")
        old_kyiv = candidate.intervals(load(
            checkout / candidate.FILES["alerts_combined.json"]))
        c2_kyiv = (Path(delta) / "files" /
                   candidate.FILES["alerts_combined.json"]
                   if candidate.FILES["alerts_combined.json"] in hashes
                   else checkout / candidate.FILES["alerts_combined.json"])
        final_kyiv = candidate.intervals(load(
            final_data / candidate.FILES["alerts_combined.json"]))
        require(old_kyiv and old_kyiv <= final_kyiv
                and candidate.intervals(load(c2_kyiv)) <= final_kyiv,
                "KYIV_HISTORICAL_INTERVAL_LOSS")
        # Everything above is read-only. C2's same-run state and Neon JSON
        # now enter the *same* Git index; no separate C2 Git publisher runs.
        for path in sorted(hashes):
            target = checkout / path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(Path(delta) / "files" / path, target)
        for path in sorted(DELIVERED):
            dest = checkout / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(final_data / path, dest)
            require(sha(dest) == result["files"][path], "FINAL_SHA_MISMATCH")
        paths = sorted(set(hashes) | DELIVERED)
        subprocess.run(["git", "-C", str(checkout), "add", "--", *paths],
                       check=True)
        staged = set(git(checkout, "diff", "--cached", "--name-only").splitlines())
        require(staged and staged <= set(paths)
                and all(allowed(p) for p in staged)
                and "historical-daily-kpi.json" not in staged,
                "NETLIFY_TRIGGER_OR_OUTSIDE_DATA_PATH")
        require(remote_head(checkout) == input_sha, "PRE_PUSH_HEAD_MOVED")
        subprocess.run(["git", "-C", str(checkout), "-c",
                        "user.name=github-actions[bot]", "-c",
                        "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                        "commit", "-m",
                        "Publish verified Neon generation and same-run C2 checkpoints"],
                       check=True, stdout=subprocess.DEVNULL)
        commit = git(checkout, "rev-parse", "HEAD")
        require(git(checkout, "rev-parse", "HEAD^") == input_sha
                and remote_head(checkout) == input_sha,
                "FAST_FORWARD_PARENT_CHANGED")
        subprocess.run(["git", "-C", str(checkout), "push",
                        "origin", "HEAD:refs/heads/site-prod"], check=True)
        require(remote_head(checkout) == commit, "REMOTE_COMMIT_UNCONFIRMED")
        return {"status": "GIT_ONLY_PUBLISHED",
                "commit": commit, "changed_files": sorted(staged),
                "city_count": 23, "generation": result["generation"],
                "netlify_deployments_per_update": 0}



def safe_block_reason(error):
    """Expose only known capture guard identifiers, never raw exception data."""
    if isinstance(error, (Blocked, candidate.Blocked)):
        value = str(error)
        return value if value in SAFE_CAPTURE_BLOCK_REASONS else "VALIDATION_BLOCKED"
    if isinstance(error, subprocess.CalledProcessError):
        return "SUBPROCESS_FAILED"
    if isinstance(error, OSError):
        return "IO_FAILED"
    return "INVALID_INPUT"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("operation", choices=["capture", "publish"])
    p.add_argument("--checkout", type=Path, required=True)
    p.add_argument("--output", type=Path)
    p.add_argument("--status", type=Path)
    p.add_argument("--input-sha")
    p.add_argument("--workflow-sha", required=True)
    p.add_argument("--run-id", type=int, required=True)
    p.add_argument("--run-attempt", type=int, required=True)
    p.add_argument("--delta", type=Path)
    p.add_argument("--prepared", type=Path)
    p.add_argument("--proof", type=Path)
    p.add_argument("--repository", default=REPOSITORY)
    a = p.parse_args()
    try:
        if a.operation == "capture":
            require(a.output and a.status and a.input_sha,
                    "CAPTURE_ARGS_MISSING")
            result = capture(a.checkout, a.output, input_sha=a.input_sha,
                             workflow_sha=a.workflow_sha, run_id=a.run_id,
                             run_attempt=a.run_attempt, status_path=a.status)
        else:
            require(a.delta and a.prepared and a.proof, "PUBLISH_ARGS_MISSING")
            result = publish(
                a.checkout, a.delta, a.prepared, a.proof,
                repository=a.repository, workflow_sha=a.workflow_sha,
                run_id=a.run_id, run_attempt=a.run_attempt,
                enabled=os.getenv("C6_AUTO_NEON_GIT_ENABLED", ""),
                zero_deploys=os.getenv("NETLIFY_DEPLOYMENTS_PER_UPDATE", ""))
    except (Blocked, candidate.Blocked, OSError, KeyError, TypeError,
            ValueError, subprocess.CalledProcessError) as error:
        # The original pilot lost the exact guard reason. Do not log raw
        # exceptions, file paths, C2 bytes, environment or subprocess output.
        print("C6_AUTO_NEON_GIT_BLOCKED; ZERO_GIT_PUBLICATION_BY_THIS_RUN;"
              f" C6_BLOCK_REASON={safe_block_reason(error)}")
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
