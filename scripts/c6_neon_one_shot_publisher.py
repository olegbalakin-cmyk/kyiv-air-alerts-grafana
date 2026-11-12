#!/usr/bin/env python3
"""One-shot, owner-gated six-JSON Git publisher for the existing C2 workflow.

Nothing is published by the proof itself. The independent Work A physical proof,
an exact GitHub run/artifact identity, and a separate expiring owner grant are
ALL mandatory. No rebase/reset/force push; any changed site-prod HEAD blocks.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from scripts import c6_neon_git_candidate as candidate
from scripts import c6_neon_publication_gate as proof_gate

HEX40 = re.compile(r"^[a-f0-9]{40}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
RECEIPT_SCHEMA = "c6-approved-one-shot-neon-git-v1"
APPROVAL = "APPROVE_ONE_SHOT_NEON_GIT_PUBLICATION"
GH_WORKFLOW = ".github/workflows/update-netlify-site.yml"


def require(value, reason):
    if not value:
        raise candidate.Blocked(reason)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()


def validate(approval, report, work_a_proof, site, *,
             c2_run, work_a_run, c2_artifact, work_a_artifact,
             now=None, repository=None):
    now = now or datetime.now(timezone.utc)
    require(now.tzinfo is not None, "TIME_NAIVE")
    require(approval.get("schema") == RECEIPT_SCHEMA
            and approval.get("decision") == APPROVAL
            and approval.get("global_cutover") == "OWNER_SEPARATELY_APPROVED"
            and approval.get("dst_correction") == "OFF",
            "EXPLICIT_OWNER_GRANT_MISSING")
    require(repository and approval.get("repository") == repository,
            "REPOSITORY_GRANT_MISMATCH")
    expiry = proof_gate.utc(approval.get("expires_at"))
    require(now <= expiry and (expiry - now).total_seconds() <= 36 * 3600,
            "GRANT_EXPIRED_OR_TOO_LONG")
    require(report.get("state") == candidate.STATE and
            report.get("publication_allowed") is False and
            report.get("production_git_push_executed") is False and
            report.get("prepared_files") == 6,
            "PREPARED_REPORT_INVALID")
    require(c2_run.get("conclusion") == "success" and
            c2_run.get("status") == "completed" and
            c2_run.get("path") == GH_WORKFLOW and
            c2_run.get("event") in ("schedule", "workflow_dispatch"),
            "C2_WORKFLOW_NOT_SUCCESSFUL")
    require(work_a_run.get("conclusion") == "success" and
            work_a_run.get("status") == "completed" and
            work_a_run.get("id") != c2_run.get("id"),
            "INDEPENDENT_WORK_A_SUCCESS_REQUIRED")
    for name, run, prefix in (("C2", c2_run, "c2"),
                              ("WORK_A", work_a_run, "work_a")):
        require(type(approval.get(prefix + "_run_id")) is int and
                approval[prefix + "_run_id"] == run.get("id") and
                approval.get(prefix + "_run_attempt") == run.get("run_attempt") and
                approval.get(prefix + "_head_sha") == run.get("head_sha") and
                HEX40.fullmatch(str(run.get("head_sha"))),
                name + "_EXACT_RUN_MISMATCH")
    require(report.get("c2_run_id") == c2_run["id"] and
            report.get("c2_run_attempt") == c2_run["run_attempt"] and
            report.get("c2_workflow_sha") == c2_run["head_sha"] and
            approval.get("c2_workflow_sha") == c2_run["head_sha"],
            "C2_REPORT_IDENTITY_MISMATCH")
    for key in ("c2_input_sha", "c2_bundle_sha256", "c2_corpus_sha256",
                "neon_branch"):
        require(approval.get(key) == report.get(key), "C2_REPORT_" + key)
    require(HEX40.fullmatch(str(report["c2_input_sha"])) and
            all(HEX64.fullmatch(str(report[k])) for k in
                ("c2_bundle_sha256", "c2_corpus_sha256")) and
            HEX40.fullmatch(str(approval.get("site_prod_head_sha"))),
            "RELEASE_HASH_INVALID")
    for info, prefix, run in ((c2_artifact, "candidate", c2_run),
                              (work_a_artifact, "work_a", work_a_run)):
        require(info.get("id") == approval.get(prefix + "_artifact_id") and
                info.get("digest") == "sha256:" + str(approval.get(prefix + "_artifact_sha256")) and
                HEX64.fullmatch(str(approval.get(prefix + "_artifact_sha256"))) and
                info.get("workflow_run", {}).get("id") == run["id"] and
                info.get("expired") is False,
                prefix.upper() + "_ARTIFACT_NOT_PINNED")
    require(c2_artifact.get("name") ==
            "c6-neon-git-preparation-" + str(c2_run["id"]) +
            "-" + str(c2_run["run_attempt"]),
            "CANDIDATE_ARTIFACT_NAME_MISMATCH")
    work_a = proof_gate.inspect(Path(work_a_proof), as_of=now)
    require(work_a["status"] == "PASS_SCOPED_PROOF_NO_PUBLICATION" and
            work_a["production_publication_allowed"] is False and
            work_a["city_count"] == 23,
            "WORK_A_PHYSICAL_PROOF_NOT_PASS")
    readback = load(Path(work_a_proof) / "readback_proof.json")
    identity = readback.get("capture_run_identity", {})
    require(identity.get("github_run_id") == c2_run["id"] and
            identity.get("github_run_attempt") == c2_run["run_attempt"] and
            identity.get("workflow_sha") == c2_run["head_sha"] and
            identity.get("input_sha") == report["c2_input_sha"] and
            readback.get("c2_corpus_sha256") == report["c2_corpus_sha256"],
            "WORK_A_SAME_RUN_PROOF_MISMATCH")
    require(work_a["neon_branch"] == report["neon_branch"] and
            work_a["c2_corpus_sha256"] == report["c2_corpus_sha256"],
            "WORK_A_CORPUS_OR_BRANCH_MISMATCH")
    files = report.get("files")
    require(isinstance(files, dict) and set(files) == set(candidate.FILES.values())
            and approval.get("files") == files,
            "APPROVED_SIX_FILES_MISMATCH")
    root = Path(site)
    src = root / "candidate"
    for name, path in candidate.FILES.items():
        dest = src / path
        require(dest.is_file() and not dest.is_symlink() and
                HEX64.fullmatch(str(files[path])) and
                candidate.sha(dest.read_bytes()) == files[path] and
                work_a["candidate_files"][name] == files[path],
                "SIX_FILE_HASH_OR_WORK_A_MISMATCH:" + name)
    dash = load(src / candidate.FILES["dashboard_data.json"])
    index = load(src / candidate.FILES["historical-daily-kpi.json"])
    generation = dash.get("meta", {}).get("generated_at")
    require(isinstance(generation, str) and generation and
            index.get("meta", {}).get("source_dashboard_generated_at") == generation and
            index.get("meta", {}).get("source_ref") == "neon:" + report["neon_branch"] and
            index.get("meta", {}).get("verified_count") == 23 and
            len(index.get("cities", {})) == 23 and
            dash.get("historical_daily_kpi") == index and
            generation == approval.get("approved_generation"),
            "RELEASE_INDEX_SOURCE_OR_GENERATION_MISMATCH")
    require(approval.get("approved_netlify_deploy_id") and
            approval.get("approved_netlify_static_kpi_sha256") ==
            files["historical-daily-kpi.json"] and
            approval.get("netlify_http_static_verified") is True and
            approval.get("git_only_publisher_paused") is True,
            "NETLIFY_FIRST_OR_SINGLE_WRITER_NOT_APPROVED")
    require(dash.get("meta", {}).get("publication_authority", {}).get(
            "publication_allowed") is False,
            "RESEARCH_PROOF_MUST_NOT_SELF_AUTHORIZE")
    return {"status": "OWNER_AND_WORK_A_APPROVED_ONE_SHOT",
            "site_prod_head_sha": approval["site_prod_head_sha"],
            "files": files, "c2_run_id": c2_run["id"]}


def publish(checkout, prepared, decision, *, expected_head):
    """An atomic allowlisted Git commit; no remote changes until all guards PASS."""
    checkout, prepared = Path(checkout), Path(prepared)
    require(HEX40.fullmatch(str(expected_head)) and
            git(checkout, "rev-parse", "HEAD") == expected_head and
            not git(checkout, "status", "--porcelain") and
            git(checkout, "branch", "--show-current") == "site-prod",
            "GIT_CHECKOUT_NOT_PINNED_AND_CLEAN")
    require(git(checkout, "ls-remote", "origin", "refs/heads/site-prod").split()[0]
            == expected_head, "SITE_PROD_HEAD_MOVED")
    before = checkout / "kyiv-air-alerts-grafana/data"
    new = prepared / "candidate/kyiv-air-alerts-grafana/data"
    old_dashboard = load(before / "dashboard_data.json")
    new_dashboard = load(new / "dashboard_data.json")
    for key in candidate.CASUALTY_FIELDS:
        require(old_dashboard.get(key) == new_dashboard.get(key) and
                key in old_dashboard and key in new_dashboard,
                "NEWER_CASUALTY_WOULD_BE_LOST:" + key)
    for key in candidate.AUXILIARY:
        require((before / key).read_bytes() == (new / key).read_bytes(),
                "NEWER_AUXILIARY_WOULD_BE_LOST:" + key)
    old_kyiv = candidate.intervals(load(before / "alerts_combined.json"))
    new_kyiv = candidate.intervals(load(new / "alerts_combined.json"))
    require(old_kyiv and old_kyiv <= new_kyiv,
            "NEWER_KYIV_INTERVAL_WOULD_BE_LOST")
    for name, path in candidate.FILES.items():
        dest = checkout / path
        source = prepared / "candidate" / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, dest)
        require(candidate.sha(dest.read_bytes()) == decision["files"][path],
                "COPY_SHA_MISMATCH:" + name)
    subprocess.run(["git", "-C", str(checkout), "add", "--",
                    *candidate.FILES.values()], check=True)
    changed = set(git(checkout, "diff", "--cached", "--name-only").splitlines())
    require(changed and changed <= set(candidate.FILES.values()),
            "OUTSIDE_SIX_FILES_OR_EMPTY_GIT_DIFF")
    require(git(checkout, "ls-remote", "origin", "refs/heads/site-prod").split()[0]
            == expected_head, "SITE_PROD_MOVED_BEFORE_COMMIT")
    subprocess.run(["git", "-C", str(checkout), "-c",
                    "user.name=github-actions[bot]", "-c",
                    "user.email=41898282+github-actions[bot]@users.noreply.github.com",
                    "commit", "-m", "Publish owner-approved exact C6 Neon six-JSON snapshot"],
                   check=True)
    commit_sha = git(checkout, "rev-parse", "HEAD")
    require(git(checkout, "rev-parse", "HEAD^") == expected_head,
            "GIT_PARENT_CHANGED")
    require(git(checkout, "ls-remote", "origin", "refs/heads/site-prod").split()[0]
            == expected_head, "SITE_PROD_MOVED_BEFORE_PUSH")
    subprocess.run(["git", "-C", str(checkout), "push", "origin",
                    "HEAD:refs/heads/site-prod"], check=True)
    require(git(checkout, "ls-remote", "origin", "refs/heads/site-prod").split()[0]
            == commit_sha, "REMOTE_COMMIT_UNCONFIRMED")
    return commit_sha


def main():
    parser = argparse.ArgumentParser()
    for key in ("approval", "report", "work-a-proof", "prepared", "checkout",
                "c2-run", "work-a-run", "c2-artifact", "work-a-artifact", "repository"):
        parser.add_argument("--" + key, required=True)
    p = parser.parse_args()
    try:
        decision = validate(
            load(p.approval), load(p.report), p.work_a_proof, p.prepared,
            c2_run=load(p.c2_run), work_a_run=load(p.work_a_run),
            c2_artifact=load(p.c2_artifact),
            work_a_artifact=load(p.work_a_artifact), repository=p.repository)
        sha = publish(p.checkout, p.prepared, decision,
                      expected_head=decision["site_prod_head_sha"])
    except Exception as exc:
        # Never expose owner grant content or C2 raw source data in logs.
        print("C6_NEON_GIT_PUBLICATION_BLOCKED:" + type(exc).__name__)
        return 2
    print("C6_NEON_GIT_PUBLISHED_EXACT_SHA=" + sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
