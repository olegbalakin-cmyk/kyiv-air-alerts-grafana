#!/usr/bin/env python3
"""Prepare exact final C6 release bytes from immutable C2 + Work A artifacts.

This module has no network client, Git operation, writer, or deploy action.
An approved PREPARE ONLY receipt permits creating bytes, never publishing them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from scripts import c6_neon_git_candidate as candidate
from scripts import c6_neon_publication_gate as proof_gate
from scripts import c6_neon_release_binding as binding
from scripts.c2_shadow_bundle import verify_archive

SCHEMA = "c6-final-release-prepare-only-v1"
DECISION = "APPROVE_PREPARE_ONLY_NO_PUBLICATION"
REPORT_SCHEMA = "c6-final-release-prepare-report-v1"
REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
C2_WORKFLOW = ".github/workflows/update-netlify-site.yml"
WORK_A_WORKFLOW = ".github/workflows/c6-neon-shadow-isolated-proof.yml"
HEX40 = re.compile(r"^[a-f0-9]{40}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")


def require(ok, reason):
    if not ok:
        raise candidate.Blocked(reason)


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def extract(archive, destination):
    """Extract GitHub ZIP with explicit bounds; reject unsafe/duplicate entries."""
    names, total = set(), 0
    with zipfile.ZipFile(archive) as z:
        for item in z.infolist():
            path = Path(item.filename)
            mode = (item.external_attr >> 16) & 0o170000
            require(not path.is_absolute() and path.parts and
                    all(x not in ("", ".", "..") for x in path.parts) and
                    mode in (0, 0o100000, 0o040000) and
                    item.filename not in names, "UNSAFE_GITHUB_ZIP_MEMBER")
            names.add(item.filename)
            total += item.file_size
            require(item.file_size <= 128 * 1024 * 1024 and
                    total <= 256 * 1024 * 1024, "GITHUB_ZIP_SIZE_LIMIT")
        z.extractall(destination)


def exact_artifact(metadata, archive, receipt, prefix, *, run, expected_name):
    require(metadata.get("id") == receipt.get(prefix + "_artifact_id") and
            metadata.get("name") == expected_name and
            metadata.get("workflow_run", {}).get("id") == run["id"] and
            metadata.get("expired") is False and
            HEX64.fullmatch(str(receipt.get(prefix + "_artifact_sha256"))) and
            metadata.get("digest") == "sha256:" + receipt[prefix + "_artifact_sha256"] and
            sha(archive) == receipt[prefix + "_artifact_sha256"],
            "ARTIFACT_NOT_PINNED:" + prefix)


def validate_receipt(receipt, c2_run, work_a_run, *, actor, run_id,
                     run_attempt, code_sha, now):
    require(actor == "olegbalakin-cmyk" and
            receipt.get("schema") == SCHEMA and
            receipt.get("decision") == DECISION and
            receipt.get("repository") == REPO and
            receipt.get("publication_allowed") is False and
            receipt.get("global_cutover") == "NO" and
            receipt.get("dst_correction") == "OFF",
            "OWNER_PREPARE_ONLY_APPROVAL_REQUIRED")
    expires = proof_gate.utc(receipt.get("expires_at"))
    require(now.tzinfo is not None and now <= expires and
            0 <= (expires - now).total_seconds() <= 36 * 3600,
            "PREPARE_APPROVAL_EXPIRED")
    require(type(run_id) is int and run_id > 0 and
            type(run_attempt) is int and run_attempt > 0 and
            HEX40.fullmatch(str(code_sha)) and
            receipt.get("prepare_code_sha") == code_sha,
            "PREPARE_RUN_IDENTITY_MISMATCH")
    require(receipt.get("release_id") and
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,79}",
                         str(receipt.get("release_id"))),
            "RELEASE_ID_INVALID")
    for prefix, run, workflow in (
        ("c2", c2_run, C2_WORKFLOW),
        ("work_a", work_a_run, WORK_A_WORKFLOW),
    ):
        require(run.get("status") == "completed" and
                run.get("conclusion") == "success" and
                run.get("path") == workflow and
                run.get("id") == receipt.get(prefix + "_run_id") and
                run.get("run_attempt") == receipt.get(prefix + "_run_attempt") and
                run.get("head_sha") == receipt.get(prefix + "_head_sha") and
                HEX40.fullmatch(str(run.get("head_sha"))),
                "PINNED_RUN_IDENTITY_MISMATCH:" + prefix)
    require(c2_run["id"] != work_a_run["id"] and
            c2_run.get("event") in ("schedule", "workflow_dispatch") and
            work_a_run.get("event") == "workflow_dispatch",
            "INDEPENDENT_C2_AND_WORK_A_REQUIRED")
    require(HEX40.fullmatch(str(receipt.get("c2_input_sha"))) and
            HEX64.fullmatch(str(receipt.get("c2_corpus_sha256"))) and
            HEX64.fullmatch(str(receipt.get("c2_bundle_sha256"))) and
            re.fullmatch(r"br-[a-z0-9-]+", str(receipt.get("neon_branch", ""))) and
            receipt.get("expected_cities") == 23 and
            isinstance(receipt.get("generation"), str) and
            receipt["generation"],
            "PINNED_SOURCE_IDENTITY_MISSING")


def prepare(*, receipt, c2_run, work_a_run, artifacts, archives, output,
            audit, actor, run_id, run_attempt, code_sha, now=None):
    now = now or datetime.now(timezone.utc)
    output, audit = Path(output), Path(audit)
    require(not output.exists() and not audit.exists() and
            not output.is_relative_to(audit) and
            not audit.is_relative_to(output), "FINAL_OUTPUT_ALREADY_EXISTS")
    validate_receipt(receipt, c2_run, work_a_run, actor=actor,
                     run_id=run_id, run_attempt=run_attempt,
                     code_sha=code_sha, now=now)
    for prefix, run, name in (
        ("c2", c2_run, f"c6-neon-git-preparation-{c2_run['id']}-{c2_run['run_attempt']}"),
        ("c2_bundle", c2_run, f"c2-shadow-inputs-{c2_run['id']}-{c2_run['run_attempt']}"),
        ("work_a", work_a_run, f"isolated-neon-shadow-{work_a_run['id']}-{work_a_run['run_attempt']}"),
    ):
        exact_artifact(artifacts[prefix], archives[prefix], receipt, prefix,
                       run=run, expected_name=name)
    with tempfile.TemporaryDirectory(prefix="c6-final-prepare-") as d:
        root = Path(d)
        for prefix in ("c2", "c2_bundle", "work_a"):
            extract(archives[prefix], root / prefix)
        reports = list((root / "c2").rglob("REPORT.json"))
        require(len(reports) == 1, "C2_PREPARATION_REPORT_NOT_UNIQUE")
        prepared = reports[0].parent
        require(all((prepared / "candidate" / p).is_file()
                    for p in candidate.FILES.values()),
                "ORIGINAL_CANDIDATE_MISSING")
        report = load(reports[0])
        require(report.get("state") == candidate.STATE and
                report.get("publication_allowed") is False and
                report.get("production_git_push_executed") is False and
                report.get("prepared_files") == 6,
                "RESEARCH_PREPARATION_NOT_IMMUTABLE")
        proof_paths = list((root / "work_a").rglob("sha256_manifest.json"))
        require(len(proof_paths) == 1, "WORK_A_PROOF_NOT_UNIQUE")
        proof = proof_paths[0].parent
        physical = proof_gate.inspect(proof, as_of=now)
        require(physical["status"] == "PASS_SCOPED_PROOF_NO_PUBLICATION" and
                physical["production_publication_allowed"] is False and
                physical["city_count"] == 23,
                "WORK_A_NOT_PASS_OR_FRESH")
        bundles = list((root / "c2_bundle").rglob("c2-shadow-inputs.zip"))
        require(len(bundles) == 1, "C2_BUNDLE_NOT_UNIQUE")
        bundle = bundles[0]
        sidecar = bundle.with_name("c2-shadow-inputs.zip.sha256")
        require(sidecar.is_file() and
                sidecar.read_text().strip() ==
                receipt["c2_bundle_sha256"] + "  c2-shadow-inputs.zip",
                "C2_BUNDLE_SIDECAR_MISMATCH")
        c2_manifest = verify_archive(
            bundle, receipt["c2_bundle_sha256"], run_id=c2_run["id"],
            workflow_sha=c2_run["head_sha"], input_sha=receipt["c2_input_sha"],
            db_branch=receipt["neon_branch"])
        require(c2_manifest.get("github_run_attempt") == c2_run["run_attempt"] and
                c2_manifest.get("corpus_sha256") == receipt["c2_corpus_sha256"] and
                len(c2_manifest.get("historical_capture_receipts", {})
                    .get("complete_cities", [])) == 23,
                "C2_CORPUS_OR_23_RECEIPTS_MISMATCH")
        for key, want in (
            ("c2_run_id", c2_run["id"]),
            ("c2_run_attempt", c2_run["run_attempt"]),
            ("c2_workflow_sha", c2_run["head_sha"]),
            ("c2_input_sha", receipt["c2_input_sha"]),
            ("c2_corpus_sha256", receipt["c2_corpus_sha256"]),
            ("c2_bundle_sha256", receipt["c2_bundle_sha256"]),
            ("neon_branch", receipt["neon_branch"]),
        ):
            require(report.get(key) == want, "C2_PREPARATION_" + key.upper())
        readback = load(proof / "readback_proof.json")
        original_binding = load(proof / "historical_freshness_binding.json")
        identity = readback.get("capture_run_identity", {})
        require(identity.get("github_run_id") == c2_run["id"] and
                identity.get("github_run_attempt") == c2_run["run_attempt"] and
                identity.get("workflow_sha") == c2_run["head_sha"] and
                identity.get("input_sha") == receipt["c2_input_sha"] and
                readback.get("c2_corpus_sha256") == receipt["c2_corpus_sha256"] and
                original_binding.get("db_branch") == receipt["neon_branch"] and
                original_binding.get("corpus_sha256") == receipt["c2_corpus_sha256"],
                "WORK_A_C2_PROVENANCE_MISMATCH")
        files = report.get("files")
        require(isinstance(files, dict) and
                set(files) == set(candidate.FILES.values()),
                "RESEARCH_SIX_FILE_SET_INVALID")
        for name, path in candidate.FILES.items():
            require(files[path] == physical["candidate_files"][name] and
                    sha(prepared / "candidate" / path) == files[path],
                    "RESEARCH_VS_WORK_A_SHA_MISMATCH:" + name)
        dash = load(prepared / "candidate" / candidate.FILES["dashboard_data.json"])
        index = load(prepared / "candidate" / candidate.FILES["historical-daily-kpi.json"])
        cities = dash.get("multicity_meta", {}).get("production_city_keys")
        generation = dash.get("meta", {}).get("generated_at")
        require(generation == receipt["generation"] and
                index.get("meta", {}).get("source_dashboard_generated_at") == generation and
                isinstance(cities, list) and len(cities) == len(set(cities)) == 23 and
                set(cities) == set(index.get("cities", {})) and
                set(cities) == set(original_binding.get("city_keys", [])),
                "GENERATION_OR_23_CITIES_CHANGED")
        result = binding.release_candidate(
            prepared, report, repository=REPO,
            release_id=receipt["release_id"], output=output)
        require(result["generation"] == generation and
                len(result["files"]) == 6 and
                all(sha(output / "candidate" / p) == h
                    for p, h in result["files"].items()) and
                sha(output / "RELEASE_BINDING.json") ==
                    result["release_manifest_sha256"] and
                {p.relative_to(output).as_posix() for p in output.rglob("*")
                 if p.is_file()} == (
                    {"RELEASE_BINDING.json", "RELEASE_MANIFEST.json"} |
                    {"candidate/" + p for p in candidate.FILES.values()}),
                "FINAL_RELEASE_BYTES_INCOMPLETE")
        audit.parent.mkdir(parents=True, exist_ok=True)
        audit.write_text(json.dumps({
            "schema": REPORT_SCHEMA, "status": "FINAL_BYTES_PREPARED_NOT_PUBLISHED",
            "publication_allowed": False, "production_git_push_executed": False,
            "netlify_deployed": False, "owner_decision": DECISION,
            "prepare_run_id": run_id, "prepare_run_attempt": run_attempt,
            "prepare_code_sha": code_sha, "release_id": receipt["release_id"],
            "c2_run_id": c2_run["id"], "c2_run_attempt": c2_run["run_attempt"],
            "c2_workflow_sha": c2_run["head_sha"],
            "c2_bundle_sha256": receipt["c2_bundle_sha256"],
            "c2_corpus_sha256": receipt["c2_corpus_sha256"],
            "c2_input_sha": receipt["c2_input_sha"],
            "neon_branch": receipt["neon_branch"], "city_count": 23,
            "work_a_run_id": work_a_run["id"],
            "work_a_run_attempt": work_a_run["run_attempt"],
            "work_a_artifact_id": receipt["work_a_artifact_id"],
            "work_a_artifact_sha256": receipt["work_a_artifact_sha256"],
            "source_preparation_artifact_id": receipt["c2_artifact_id"],
            "source_preparation_artifact_sha256": receipt["c2_artifact_sha256"],
            "generation": generation,
            "release_binding_sha256": result["release_manifest_sha256"],
            "release_manifest_file_sha256": sha(output / "RELEASE_MANIFEST.json"),
            "final_files": result["files"],
        }, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return result


def main():
    p = argparse.ArgumentParser()
    for name in ("receipt", "c2-run", "work-a-run", "c2-artifact",
                 "c2-bundle-artifact", "work-a-artifact",
                 "c2-zip", "c2-bundle-zip", "work-a-zip",
                 "output", "audit", "actor", "run-id", "run-attempt", "code-sha"):
        p.add_argument("--" + name, required=True)
    args = p.parse_args()
    try:
        prepare(
            receipt=load(args.receipt), c2_run=load(args.c2_run),
            work_a_run=load(args.work_a_run),
            artifacts={"c2": load(args.c2_artifact),
                       "c2_bundle": load(args.c2_bundle_artifact),
                       "work_a": load(args.work_a_artifact)},
            archives={"c2": args.c2_zip, "c2_bundle": args.c2_bundle_zip,
                      "work_a": args.work_a_zip},
            output=args.output, audit=args.audit, actor=args.actor,
            run_id=int(args.run_id), run_attempt=int(args.run_attempt),
            code_sha=args.code_sha)
    except Exception as exc:
        # Never print approval, source content or database credentials.
        print("C6_FINAL_PREPARE_BLOCKED:" + type(exc).__name__)
        return 2
    print("FINAL_RELEASE_EIGHT_FILES_PREPARED; PUBLICATION_OFF")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
