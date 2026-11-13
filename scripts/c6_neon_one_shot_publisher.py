#!/usr/bin/env python3
"""One-shot, owner-gated six-JSON Git publisher for the existing C2 workflow.

Nothing is published by the proof itself. The independent Work A physical proof,
an exact GitHub run/artifact identity, and a separate expiring owner grant are
ALL mandatory. No rebase/reset/force push; any changed site-prod HEAD blocks.
"""
from __future__ import annotations

import argparse
import json
import hashlib
import zipfile
import re
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from scripts import c6_neon_git_candidate as candidate
from scripts import c6_neon_publication_gate as proof_gate
from scripts import c6_neon_release_binding as release_binding
from scripts import c6_neon_final_prepare as work_m

HEX40 = re.compile(r"^[a-f0-9]{40}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
RECEIPT_SCHEMA = "c6-approved-one-shot-neon-git-v1"
APPROVAL = "APPROVE_ONE_SHOT_NEON_GIT_PUBLICATION"
GH_WORKFLOW = ".github/workflows/update-netlify-site.yml"
# A *separate* publication receipt. Work M's prepare-only receipt cannot grant a push.
WORK_N_SCHEMA = "c6-approved-one-shot-neon-git-work-m-v1"
WORK_M_RUN_ID = 43403595621
WORK_M_CODE_SHA = "9d846279b91b44b324a722ca00276a99956b4fca"
WORK_M_FINAL_ARTIFACT_ID = 14025629654
WORK_M_FINAL_SHA256 = "f2252da0014ce4ed28d5d52a7164e077b8fcd8c99380dd752ee0650412b051ed"
WORK_M_REPORT_ARTIFACT_ID = 14025729121
WORK_M_REPORT_SHA256 = "f4f786b168d28f37bdf6a333d4e514b503e402e4fda25553d99ffa0a8d6a8648"


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
            HEX64.fullmatch(str(approval.get("approved_netlify_static_kpi_sha256"))) and
            approval.get("release_id") and
            approval.get("netlify_http_static_verified") is True and
            approval.get("git_only_publisher_paused") is True,
            "NETLIFY_FIRST_OR_SINGLE_WRITER_NOT_APPROVED")
    require(dash.get("meta", {}).get("publication_authority", {}).get(
            "publication_allowed") is False,
            "RESEARCH_PROOF_MUST_NOT_SELF_AUTHORIZE")
    return {"status": "OWNER_AND_WORK_A_APPROVED_ONE_SHOT",
            "site_prod_head_sha": approval["site_prod_head_sha"],
            "files": files, "c2_run_id": c2_run["id"]}


def verify_pinned_final_zip(archive, released, final, approval, artifact, run):
    """Require the exact pre-Netlify immutable ZIP bytes before any Git write."""
    require(artifact.get("id") == approval.get("final_release_artifact_id") and
            artifact.get("expired") is False and
            artifact.get("workflow_run", {}).get("id") == run.get("id") and
            run.get("status") == "completed" and run.get("conclusion") == "success" and
            run.get("run_attempt") == approval.get("final_release_run_attempt") and
            run.get("head_sha") == approval.get("final_release_code_sha") and
            run.get("path") == GH_WORKFLOW and
            artifact.get("name") == f"c6-neon-final-release-{run.get('id')}-{run.get('run_attempt')}" and
            HEX64.fullmatch(str(approval.get("final_release_artifact_sha256"))) and
            artifact.get("digest") == "sha256:" + approval["final_release_artifact_sha256"] and
            hashlib.sha256(Path(archive).read_bytes()).hexdigest() ==
                approval["final_release_artifact_sha256"],
            "PINNED_FINAL_ZIP_NOT_VERIFIED")
    expected = {"RELEASE_BINDING.json", "RELEASE_MANIFEST.json"} | {
        "candidate/" + x for x in candidate.FILES.values()}
    with zipfile.ZipFile(archive) as z:
        require(set(z.namelist()) == expected and len(z.namelist()) == 8,
                "FINAL_ZIP_MEMBER_SET_MISMATCH")
        for name in expected:
            info = z.getinfo(name)
            require(info.file_size <= 64 * 1024 * 1024 and
                    z.read(name) == (Path(released) / name).read_bytes(),
                    "FINAL_RELEASE_NOT_BYTE_IDENTICAL:" + name)
    require(approval.get("release_manifest_sha256") == final["release_manifest_sha256"],
            "FINAL_RELEASE_BINDING_NOT_APPROVED")



def validate_work_m(approval, report, work_a_proof, released, *,
                    c2_run, work_a_run, final_run, c2_artifact,
                    work_a_artifact, final_artifact, report_artifact,
                    c2_jobs, repository, now=None):
    """Exact C2 failure-before-runner -> Work L -> Work M publication preflight.

    No original C2 preparation artifact is claimed. This path can be reached
    only with a NEW, expiring publication receipt; the Work M receipt is
    prepare-only. Nothing in this function writes to Git, Neon, or Netlify.
    """
    now = now or datetime.now(timezone.utc)
    pins = work_m.RECOVERY_PINS
    require(now.tzinfo is not None and
            approval.get("schema") == WORK_N_SCHEMA and
            approval.get("decision") == APPROVAL and
            approval.get("global_cutover") == "OWNER_SEPARATELY_APPROVED" and
            approval.get("dst_correction") == "OFF" and
            repository == work_m.REPO and approval.get("repository") == repository,
            "SEPARATE_WORK_N_PUBLICATION_OWNER_GRANT_REQUIRED")
    expiry = proof_gate.utc(approval.get("expires_at"))
    require(now <= expiry and 0 <= (expiry - now).total_seconds() <= 36 * 3600,
            "GRANT_EXPIRED_OR_TOO_LONG")
    require(approval.get("provenance_contract") == work_m.RECOVERY_CONTRACT and
            not approval.get("candidate_artifact_id") and
            not approval.get("candidate_artifact_sha256") and
            not approval.get("c2_preparation_artifact_id") and
            not report.get("source_preparation_artifact_id") and
            not report.get("source_preparation_artifact_sha256"),
            "MISSING_ORIGINAL_PREPARATION_MUST_REMAIN_ABSENT")
    for prefix, run, run_id, sha, conclusion, workflow in (
        ("c2", c2_run, pins["c2_run_id"], pins["c2_head_sha"],
         "failure", GH_WORKFLOW),
        ("work_a", work_a_run, pins["work_a_run_id"], pins["work_a_head_sha"],
         "success", work_m.WORK_A_WORKFLOW),
        ("final_release", final_run, WORK_M_RUN_ID, WORK_M_CODE_SHA,
         "success", GH_WORKFLOW),
    ):
        require(run.get("id") == run_id and run.get("head_sha") == sha and
                run.get("run_attempt") == 1 and
                run.get("status") == "completed" and
                run.get("conclusion") == conclusion and
                run.get("path") == workflow and
                approval.get(prefix + "_run_id") == run_id and
                approval.get(prefix + "_run_attempt") == 1 and
                approval.get(prefix + "_head_sha") == sha,
                "EXACT_WORK_N_RUN_NOT_PINNED:" + prefix)
    require(c2_run.get("event") == "workflow_dispatch" and
            c2_run.get("head_branch") == "main" and
            work_a_run.get("event") == "workflow_dispatch" and
            work_a_run.get("head_branch") ==
                "research-c6-work-l-recover-2026-11-13" and
            final_run.get("event") == "workflow_dispatch" and
            final_run.get("head_branch") ==
                "research-c6-work-m-release-recovery-2026-11-13" and
            len({c2_run["id"], work_a_run["id"], final_run["id"]}) == 3,
            "WORK_N_THREE_RUN_INDEPENDENCE_REQUIRED")
    require(isinstance(c2_jobs, dict) and c2_jobs.get("total_count") == 4 and
            isinstance(c2_jobs.get("jobs"), list) and
            len(c2_jobs["jobs"]) == 4, "C2_FOUR_JOBS_REQUIRED")
    jobs = {j.get("name"): j for j in c2_jobs["jobs"]}
    require(set(jobs) == set(work_m.RECOVERY_JOB_RESULTS),
            "C2_JOB_SET_CHANGED")
    for name, (job_id, conclusion) in work_m.RECOVERY_JOB_RESULTS.items():
        job = jobs[name]
        require(job.get("id") == job_id and
                job.get("run_id") == c2_run["id"] and
                job.get("status") == "completed" and
                job.get("conclusion") == conclusion,
                "C2_JOB_STATUS_NOT_EXACT:" + name)
    failed = jobs["c6-neon-six-json-prepare"]
    require(failed.get("runner_id") in (None, 0) and
            not failed.get("runner_name") and
            failed.get("steps") in ([], None) and
            failed.get("started_at") == failed.get("created_at") and
            len(jobs["update-site"].get("steps") or []) > 0 and
            all(jobs[k].get("steps") in ([], None) for k in
                ("c6-neon-final-prepare-only", "c6-neon-owner-gated-git-release")),
            "C2_FAILURE_NOT_KNOWN_PRERUN_ONLY")
    for art, a_id, digest, name, run_id in (
        (c2_artifact, pins["c2_bundle_artifact_id"],
         pins["c2_bundle_artifact_sha256"], "c2-shadow-inputs-43321997695-1",
         pins["c2_run_id"]),
        (work_a_artifact, pins["work_a_artifact_id"],
         pins["work_a_artifact_sha256"], "isolated-neon-shadow-43390770985-1",
         pins["work_a_run_id"]),
        (final_artifact, WORK_M_FINAL_ARTIFACT_ID, WORK_M_FINAL_SHA256,
         "c6-neon-final-release-43403595621-1", WORK_M_RUN_ID),
        (report_artifact, WORK_M_REPORT_ARTIFACT_ID, WORK_M_REPORT_SHA256,
         "c6-neon-final-prepare-report-43403595621-1", WORK_M_RUN_ID),
    ):
        require(art.get("id") == a_id and art.get("name") == name and
                art.get("digest") == "sha256:" + digest and
                art.get("expired") is False and
                art.get("workflow_run", {}).get("id") == run_id,
                "WORK_N_ARTIFACT_PROVENANCE_OR_SHA_MISMATCH:" + name)
    for key, want in (
        ("c2_artifact_id", pins["c2_bundle_artifact_id"]),
        ("c2_artifact_sha256", pins["c2_bundle_artifact_sha256"]),
        ("work_a_artifact_id", pins["work_a_artifact_id"]),
        ("work_a_artifact_sha256", pins["work_a_artifact_sha256"]),
        ("final_release_artifact_id", WORK_M_FINAL_ARTIFACT_ID),
        ("final_release_artifact_sha256", WORK_M_FINAL_SHA256),
        ("final_prepare_report_artifact_id", WORK_M_REPORT_ARTIFACT_ID),
        ("final_prepare_report_artifact_sha256", WORK_M_REPORT_SHA256),
        ("final_release_code_sha", WORK_M_CODE_SHA),
    ):
        require(approval.get(key) == want, "WORK_N_OWNER_NOT_EXACT:" + key)
    require(report.get("schema") == work_m.REPORT_SCHEMA and
            report.get("status") == "FINAL_BYTES_PREPARED_NOT_PUBLISHED" and
            report.get("owner_decision") == work_m.DECISION and
            report.get("provenance_contract") == work_m.RECOVERY_CONTRACT and
            report.get("publication_allowed") is False and
            report.get("production_git_push_executed") is False and
            report.get("netlify_deployed") is False and
            report.get("prepare_run_id") == WORK_M_RUN_ID and
            report.get("prepare_run_attempt") == 1 and
            report.get("prepare_code_sha") == WORK_M_CODE_SHA and
            report.get("release_id") == approval.get("release_id") and
            report.get("city_count") == 23 and
            report.get("work_a_run_id") == pins["work_a_run_id"] and
            report.get("work_a_run_attempt") == 1 and
            report.get("work_a_artifact_id") == pins["work_a_artifact_id"] and
            report.get("work_a_artifact_sha256") == pins["work_a_artifact_sha256"],
            "WORK_M_PREPARE_REPORT_NOT_PINNED")
    for key, want in (
        ("c2_run_id", pins["c2_run_id"]),
        ("c2_run_attempt", 1),
        ("c2_workflow_sha", pins["c2_head_sha"]),
        ("c2_input_sha", pins["c2_input_sha"]),
        ("c2_corpus_sha256", pins["c2_corpus_sha256"]),
        ("c2_bundle_sha256", pins["c2_bundle_sha256"]),
        ("neon_branch", pins["neon_branch"]),
    ):
        require(report.get(key) == want and approval.get(key) == want,
                "WORK_M_C2_IDENTITY_CHANGED:" + key)
    require(HEX40.fullmatch(str(approval.get("site_prod_head_sha"))) and
            approval.get("approved_netlify_deploy_id") and
            approval.get("netlify_http_static_verified") is True and
            approval.get("git_only_publisher_paused") is True and
            HEX64.fullmatch(str(approval.get("approved_netlify_static_kpi_sha256"))),
            "NETLIFY_FIRST_OR_SINGLE_WRITER_NOT_APPROVED")
    physical = proof_gate.inspect(Path(work_a_proof), as_of=now)
    require(physical["status"] == "PASS_SCOPED_PROOF_NO_PUBLICATION" and
            physical["production_publication_allowed"] is False and
            physical["city_count"] == 23 and
            physical["neon_branch"] == pins["neon_branch"] and
            physical["c2_corpus_sha256"] == pins["c2_corpus_sha256"],
            "WORK_L_PHYSICAL_PROOF_NOT_PASS")
    rb = load(Path(work_a_proof) / "readback_proof.json")
    identity = rb.get("capture_run_identity", {})
    require(identity.get("github_run_id") == pins["c2_run_id"] and
            identity.get("github_run_attempt") == 1 and
            identity.get("workflow_sha") == pins["c2_head_sha"] and
            identity.get("input_sha") == pins["c2_input_sha"] and
            rb.get("c2_corpus_sha256") == pins["c2_corpus_sha256"],
            "WORK_L_C2_READBACK_MISMATCH")
    binding = load(Path(released) / "RELEASE_BINDING.json")
    manifest = load(Path(released) / "RELEASE_MANIFEST.json")
    require(binding.get("schema") == "c6-neon-git-release-binding-v1" and
            binding.get("repository") == repository and
            binding.get("release_id") == approval.get("release_id") and
            manifest.get("schema") == "c6-neon-git-release-manifest-v1" and
            manifest.get("binding") == binding and
            manifest.get("release_manifest_sha256") ==
                candidate.sha((Path(released) / "RELEASE_BINDING.json").read_bytes()) and
            report.get("release_binding_sha256") ==
                manifest["release_manifest_sha256"] and
            report.get("release_manifest_file_sha256") ==
                candidate.sha((Path(released) / "RELEASE_MANIFEST.json").read_bytes()),
            "WORK_M_FINAL_BINDING_NOT_EXACT")
    for key, bkey in (
        ("c2_run_id", "c2_run_id"), ("c2_run_attempt", "c2_run_attempt"),
        ("c2_workflow_sha", "c2_workflow_sha"),
        ("c2_input_sha", "c2_input_sha"),
        ("c2_corpus_sha256", "c2_corpus_sha256"),
        ("c2_bundle_sha256", "c2_bundle_sha256"),
        ("neon_branch", "neon_branch"),
    ):
        require(binding.get(bkey) == report.get(key),
                "WORK_M_BINDING_C2_IDENTITY_MISMATCH:" + key)
    require(binding.get("generation") == report.get("generation") and
            binding.get("generation") == approval.get("approved_generation") and
            binding.get("source_files") == manifest.get("source_files"),
            "WORK_M_SOURCE_FILE_BINDING_MISMATCH")
    sources = {p: physical["candidate_files"][name]
               for name, p in candidate.FILES.items()}
    files = manifest.get("files")
    require(manifest.get("source_files") == sources and
            approval.get("files") == sources and
            isinstance(files, dict) and set(files) == set(candidate.FILES.values())
            and report.get("final_files") == files and
            approval.get("final_files") == files,
            "WORK_L_TO_WORK_M_SIX_FILES_MISMATCH")
    for path, expected in files.items():
        f = Path(released) / "candidate" / path
        require(f.is_file() and not f.is_symlink() and
                HEX64.fullmatch(str(expected)) and
                candidate.sha(f.read_bytes()) == expected,
                "WORK_M_FINAL_FILE_SHA_INVALID:" + path)
    dash = load(Path(released) / "candidate" / candidate.FILES["dashboard_data.json"])
    index = load(Path(released) / "candidate" / candidate.FILES["historical-daily-kpi.json"])
    authority = dash.get("meta", {}).get("publication_authority", {})
    cities = dash.get("multicity_meta", {}).get("production_city_keys", [])
    require(authority.get("scope") == release_binding.RELEASE_SCOPE and
            authority.get("publication_allowed") is True and
            authority.get("release_manifest_sha256") ==
                manifest["release_manifest_sha256"] and
            isinstance(cities, list) and len(cities) == len(set(cities)) == 23 and
            set(cities) == set(index.get("cities", {})) and
            all(row.get("status") == "verified" for row in index["cities"].values()) and
            index.get("meta", {}).get("source_ref") ==
                "neon:" + pins["neon_branch"] and
            index.get("meta", {}).get("verified_count") == 23 and
            index.get("meta", {}).get("source_dashboard_generated_at") ==
                approval.get("approved_generation") and
            index.get("meta", {}).get("release_manifest_sha256") ==
                manifest["release_manifest_sha256"] and
            dash.get("historical_daily_kpi") == index,
            "WORK_M_23_CITY_STATIC_GENERATION_MISMATCH")
    return {
        "status": "OWNER_AND_WORK_L_WORK_M_APPROVED_ONE_SHOT",
        "site_prod_head_sha": approval["site_prod_head_sha"],
        "release_manifest_sha256": manifest["release_manifest_sha256"],
        "generation": approval["approved_generation"], "files": files,
    }

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
    manifest = load(prepared / "RELEASE_MANIFEST.json")
    require(candidate.sha((prepared / "RELEASE_BINDING.json").read_bytes()) ==
            decision["release_manifest_sha256"],
            "RELEASE_MANIFEST_BINDING_SHA_INVALID")
    require(manifest.get("schema") == "c6-neon-git-release-manifest-v1"
            and manifest.get("files") == decision["files"]
            and manifest.get("release_manifest_sha256") ==
                decision["release_manifest_sha256"],
            "RELEASE_MANIFEST_INVALID")
    for path, expected in decision["files"].items():
        source = prepared / "candidate" / path
        require(source.is_file() and not source.is_symlink() and
                candidate.sha(source.read_bytes()) == expected,
                "RELEASE_SIX_SHA_INVALID:" + path)
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
                "c2-run", "work-a-run", "c2-artifact", "work-a-artifact",
                "final-artifact", "final-run", "final-zip", "repository"):
        parser.add_argument("--" + key, required=True)
    parser.add_argument("--work-m-report-artifact")
    parser.add_argument("--c2-jobs")
    p = parser.parse_args()
    try:
        approval, report = load(p.approval), load(p.report)
        with tempfile.TemporaryDirectory(prefix="c6-owner-release-") as temp:
            if approval.get("schema") == WORK_N_SCHEMA:
                require(p.work_m_report_artifact and p.c2_jobs,
                        "WORK_M_REPORT_AND_C2_JOBS_REQUIRED")
                release_root = Path(p.prepared)
                decision = validate_work_m(
                    approval, report, p.work_a_proof, release_root,
                    c2_run=load(p.c2_run), work_a_run=load(p.work_a_run),
                    final_run=load(p.final_run),
                    c2_artifact=load(p.c2_artifact),
                    work_a_artifact=load(p.work_a_artifact),
                    final_artifact=load(p.final_artifact),
                    report_artifact=load(p.work_m_report_artifact),
                    c2_jobs=load(p.c2_jobs), repository=p.repository)
                final = {"files": decision["files"],
                         "release_manifest_sha256": decision["release_manifest_sha256"],
                         "generation": decision["generation"]}
            else:
                decision = validate(
                    approval, report, p.work_a_proof, p.prepared,
                    c2_run=load(p.c2_run), work_a_run=load(p.work_a_run),
                    c2_artifact=load(p.c2_artifact),
                    work_a_artifact=load(p.work_a_artifact), repository=p.repository)
                release_root = Path(temp) / "release"
                final = release_binding.release_candidate(
                    p.prepared, report, repository=p.repository,
                    release_id=approval.get("release_id"), output=release_root)
            decision.update(release_binding.verify_final(approval, final))
            verify_pinned_final_zip(p.final_zip, release_root, final, approval,
                                    load(p.final_artifact), load(p.final_run))
            sha = publish(p.checkout, release_root, decision,
                          expected_head=decision["site_prod_head_sha"])
    except Exception as exc:
        # Never expose owner grant content or C2 raw source data in logs.
        print("C6_NEON_GIT_PUBLICATION_BLOCKED:" + type(exc).__name__)
        return 2
    print("C6_NEON_GIT_PUBLISHED_EXACT_SHA=" + sha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
