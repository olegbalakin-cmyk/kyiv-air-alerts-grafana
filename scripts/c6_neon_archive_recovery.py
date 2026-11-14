#!/usr/bin/env python3
"""Restore only archived C2 data into an isolated exact Git checkout; no network/writes.

Never claim to reconstruct the original lost runner worktree or unarchived paths.
The existing C6 physical proof and publication gates still decide release eligibility.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path
from scripts import c6_neon_auto_git as auto
from scripts.c2_shadow_bundle import verify_archive

NAMES = ("alerts_combined.json", "dashboard_data.json", "site_derived.json",
         "kyiv_threat_mix.json", "sevastopol_events.json")


def require(ok, reason):
    auto.require(ok, reason)


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def read_zip(path, members):
    require(Path(path).is_file(), "RECOVERY_ZIP_MISSING")
    with zipfile.ZipFile(path) as archive:
        require(set(archive.namelist()) == set(members)
                and len(archive.namelist()) == len(members),
                "RECOVERY_OUTER_MEMBER_SET")
        for info in archive.infolist():
            require(info.file_size <= 128 * 1024 * 1024 and
                    (info.external_attr >> 16) & 0o170000 in (0, 0o100000),
                    "RECOVERY_UNSAFE_ZIP_MEMBER")
        return {name: archive.read(name) for name in members}


def restore(*, outer, status_outer, run, jobs, artifact_metadata, checkout,
            delta, receipt_output):
    pins = auto.RECOVERY_PINS
    require(sha_bytes(Path(outer).read_bytes()) == pins["bundle_outer_sha256"]
            and sha_bytes(Path(status_outer).read_bytes()) == pins["status_outer_sha256"],
            "RECOVERY_OUTER_SHA_MISMATCH")
    outer_files = read_zip(outer, ("c2-shadow-inputs.zip",
                                   "c2-shadow-inputs.zip.sha256"))
    nested = outer_files["c2-shadow-inputs.zip"]
    require(sha_bytes(nested) == pins["bundle_inner_sha256"]
            and outer_files["c2-shadow-inputs.zip.sha256"].decode().strip()
            == pins["bundle_inner_sha256"] + "  c2-shadow-inputs.zip",
            "RECOVERY_NESTED_BUNDLE_SHA_MISMATCH")
    status_bytes = read_zip(status_outer, ("c2_publication_status.json",))[
        "c2_publication_status.json"]
    require(not Path(delta).exists() and not Path(receipt_output).exists(),
            "RECOVERY_OUTPUT_EXISTS")
    require(not Path(delta).resolve().is_relative_to(Path(checkout).resolve())
            and not Path(receipt_output).resolve().is_relative_to(
                Path(checkout).resolve()), "RECOVERY_OUTPUT_NOT_ISOLATED")
    import tempfile
    with tempfile.TemporaryDirectory(prefix="c6-archive-verified-") as temp:
        inner = Path(temp) / "c2-shadow-inputs.zip"
        inner.write_bytes(nested)
        m = verify_archive(inner, pins["bundle_inner_sha256"],
            run_id=pins["run_id"], workflow_sha=pins["workflow_sha"],
            input_sha=pins["input_sha"], db_branch=auto.NEON_BRANCH,
            db_endpoint=pins["db_endpoint"])
    with zipfile.ZipFile(__import__("io").BytesIO(nested)) as z:
        manifest = json.loads(z.read("manifest.json"))
        status = json.loads(z.read("status.json"))
        receipt = json.loads(z.read("receipt.json"))
        archived_data = {n: z.read("site_data/" + n) for n in NAMES}
    require(m == manifest and json.loads(status_bytes) == status,
            "RECOVERY_EXTERNAL_STATUS_MISMATCH")
    auto.verify_exact_failed_c2_archive(
        run, jobs, artifact_metadata, manifest, status, receipt)
    checkout = Path(checkout).resolve()
    require(auto.git(checkout, "rev-parse", "HEAD") == pins["input_sha"]
            and auto.git(checkout, "branch", "--show-current") == "site-prod"
            and not auto.git(checkout, "status", "--porcelain")
            and (checkout / auto.PREFIX /
                 "c2_history_capture_checkpoints.json").is_file(),
            "RECOVERY_BASELINE_NOT_EXACT_AND_CLEAN")
    copied = {}
    for name, raw in sorted(archived_data.items()):
        path = auto.PREFIX + name
        target = auto.safe_file(checkout, path)
        require(raw and len(raw) <= 128 * 1024 * 1024,
                "RECOVERY_ARCHIVED_DATA_INVALID")
        require(sha_bytes(raw) == manifest["files"]["site_data/" + name],
                "RECOVERY_ARCHIVED_DATA_SHA_MISMATCH")
        target.write_bytes(raw)
        copied[path] = sha_bytes(raw)
    actual_changed = auto.changed_paths(checkout)
    require(actual_changed == {p for p in copied
                if auto.git(checkout, "status", "--porcelain", "--", p)},
            "RECOVERY_UNARCHIVED_PATH_CHANGE")
    require(auto.PREFIX + "dashboard_data.json" in actual_changed,
            "RECOVERY_DASHBOARD_UNCHANGED")
    frozen = auto.capture(checkout, delta, input_sha=pins["input_sha"],
        workflow_sha=pins["workflow_sha"], run_id=pins["run_id"],
        run_attempt=pins["run_attempt"], status_path=write_status(
            Path(receipt_output).parent, status_bytes))
    require(set(frozen["files"]) == actual_changed,
            "RECOVERY_DELTA_FILE_SET_MISMATCH")
    for path in frozen["files"]:
        require(frozen["files"][path] == copied[path],
                "RECOVERY_DELTA_ARCHIVE_SHA_MISMATCH")
    receipt_output = Path(receipt_output)
    receipt_output.parent.mkdir(parents=True, exist_ok=True)
    info = {
        "schema": "c6-archived-c2-reconstruction-v1",
        "provenance": "ARCHIVED_FIVE_JSON_ONLY_NOT_ORIGINAL_RUNNER_STATUS",
        "c2_run_id": pins["run_id"], "c2_run_attempt": pins["run_attempt"],
        "c2_corpus_sha256": pins["corpus_sha256"],
        "bundle_sha256": pins["bundle_inner_sha256"],
        "delta_manifest_sha256": auto.sha(Path(delta) / "manifest.json"),
        "files": frozen["files"], "unarchived_original_changes_certified": False,
        "publication_allowed": False, "neon_writes": 0,
        "source_http_gets": 0, "git_pushes": 0, "netlify_deployments": 0,
    }
    receipt_output.write_text(json.dumps(info, sort_keys=True, indent=2) + "\n")
    return info


def write_status(output_dir, data):
    target = output_dir / "c6-recovery-status.json"
    require(not target.exists(), "RECOVERY_STATUS_EXISTS")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def main():
    p = argparse.ArgumentParser()
    for field in ("outer", "status-outer", "run", "jobs", "artifacts",
                  "checkout", "delta", "receipt-output"):
        p.add_argument("--" + field, required=True)
    a = p.parse_args()
    try:
        result = restore(
            outer=a.outer, status_outer=a.status_outer,
            run=json.loads(Path(a.run).read_text()),
            jobs=json.loads(Path(a.jobs).read_text()),
            artifact_metadata=json.loads(Path(a.artifacts).read_text()),
            checkout=a.checkout, delta=a.delta, receipt_output=a.receipt_output)
        print("RECOVERED_ARCHIVED_C2_DELTA_ONLY; NO_PUBLICATION; "
              "manifest_sha256=" + result["delta_manifest_sha256"])
        return 0
    except (auto.Blocked, ValueError, OSError, KeyError, TypeError,
            subprocess.CalledProcessError, zipfile.BadZipFile):
        print("RECOVERY_FAIL_CLOSED; NO_GIT_PUBLICATION")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
