#!/usr/bin/env python3
"""Package existing same-run C2 bytes. No network, database or publication code."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

class BundleBlocked(ValueError):
    pass


def require(ok, reason):
    if not ok:
        raise BundleBlocked(reason)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

SITE_DATA = ("dashboard_data.json", "site_derived.json", "alerts_combined.json",
             "kyiv_threat_mix.json", "sevastopol_events.json")
MEMBERS = {"receipt.json", "status.json", "payload.json"} | {
    "site_data/" + name for name in SITE_DATA}
SCHEMA = "existing-c2-shadow-inputs-v1"
REPOSITORY = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
SHA40 = re.compile(r"[0-9a-f]{40}")
SHA256 = re.compile(r"[0-9a-f]{64}")
ENDPOINT = re.compile(r"ep-[a-z0-9-]+(?:-pooler)?\.[a-z0-9.-]+\.neon\.tech")
SECRET_TEXT = re.compile(r"(?i)(postgres(?:ql)?://|\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_)|"
                         r"-----BEGIN [A-Z ]*PRIVATE KEY|[?&](?:token|api_key|password)=)")
SECRET_KEY = re.compile(r"(?i)(?:^|_)(?:password|passwd|secret|token|authorization|database_url|dsn)$")


def capture_validation_clock(rows, *, now=None):
    """Bound every response page by export time, not the oldest source capture.

    The separate freshness gate continues using each receipt's conservative
    last_checked_at (the first response page), never this validation clock.
    """
    from scripts.c6_history_freshness import utc
    captures = [utc(page["captured_at"]) for row in rows for page in row.get("pages", [])]
    require(bool(captures), "CAPTURE_RECEIPTS_EMPTY")
    at = utc(now if now is not None else datetime.now(timezone.utc))
    require(max(captures) <= at, "CAPTURE_PAGE_AFTER_EXPORT")
    return at


def safe_json(raw):
    """Only data JSON enters the archive; reject known credential forms, never echo it."""
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result
    value = json.loads(raw, object_pairs_hook=pairs,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError("NONFINITE_JSON")))
    def visit(obj):
        if isinstance(obj, dict):
            for key, item in obj.items():
                require(not SECRET_KEY.search(key), "CREDENTIAL_FIELD_REJECTED")
                visit(item)
        elif isinstance(obj, list):
            for item in obj:
                visit(item)
        elif isinstance(obj, str):
            require(not SECRET_TEXT.search(obj), "CREDENTIAL_TEXT_REJECTED")
    visit(value)
    return value


def validate_manifest(manifest, *, run_id=None, workflow_sha=None, input_sha=None,
                      db_branch=None, db_endpoint=None):
    require(manifest.get("schema") == SCHEMA and
                   manifest.get("repository") == REPOSITORY and
                   set(manifest.get("files", {})) == MEMBERS, "C2_MANIFEST_SCHEMA")
    for key in ("workflow_sha", "input_sha"):
        require(isinstance(manifest.get(key), str) and
                       SHA40.fullmatch(manifest[key]), "C2_MANIFEST_GIT_SHA")
    require(SHA256.fullmatch(str(manifest.get("corpus_sha256", ""))) and
                   all(SHA256.fullmatch(str(v)) for v in manifest["files"].values()),
                   "C2_MANIFEST_DIGEST")
    require(type(manifest.get("github_run_id")) is int and manifest["github_run_id"] > 0 and
                   type(manifest.get("github_run_attempt")) is int and manifest["github_run_attempt"] > 0,
                   "C2_MANIFEST_RUN")
    require(re.fullmatch(r"br-[a-z0-9-]+", str(manifest.get("db_branch", ""))) and
                   ENDPOINT.fullmatch(str(manifest.get("db_endpoint", ""))), "C2_MANIFEST_DB_IDENTITY")
    for key, expected in (("github_run_id", int(run_id) if run_id is not None else None),
                          ("workflow_sha", workflow_sha), ("input_sha", input_sha),
                          ("db_branch", db_branch), ("db_endpoint", db_endpoint)):
        require(expected is None or manifest.get(key) == expected, "C2_MANIFEST_IDENTITY_MISMATCH")


def verify_archive(bundle, expected_sha, *, destination=None, **identity):
    require(SHA256.fullmatch(expected_sha) and digest(bundle) == expected_sha,
                   "EXISTING_C2_BUNDLE_SHA_MISMATCH")
    with zipfile.ZipFile(bundle) as archive:
        names = archive.namelist()
        require(set(names) == MEMBERS | {"manifest.json"} and len(names) == len(MEMBERS) + 1,
                       "EXISTING_C2_BUNDLE_MEMBER_SET")
        require(all(i.file_size <= 128 * 1024 * 1024 and
                           (i.external_attr >> 16) & 0o170000 in (0, 0o100000)
                           for i in archive.infolist()), "EXISTING_C2_BUNDLE_LIMIT")
        manifest = safe_json(archive.read("manifest.json"))
        validate_manifest(manifest, **identity)
        for name, want in manifest["files"].items():
            raw = archive.read(name)
            require(hashlib.sha256(raw).hexdigest() == want, "EXISTING_C2_MEMBER_SHA")
            safe_json(raw)
        receipt = safe_json(archive.read("receipt.json"))
        status = safe_json(archive.read("status.json"))
        require(receipt.get("offline_fixture") is not True and
                       status.get("offline_fixture") is not True, "OFFLINE_FIXTURE_NOT_REAL_C2")
        for key in ("workflow_sha", "input_sha", "db_branch", "corpus_sha256"):
            require(receipt.get(key) == manifest[key], "C2_MANIFEST_RECEIPT_MISMATCH")
        require(manifest.get("canonical_run_id") == receipt.get("run_id"),
                       "C2_MANIFEST_CANONICAL_RUN_MISMATCH")
        if destination is not None:
            archive.extractall(destination)  # exact regular-file relative allowlist above
        return manifest


def verified_export_inputs(*, site, receipt_path, status_path, payload_path, dashboard_path, verifier=None):
    # The exact production verifier remains authoritative; no DB module is imported.
    if verifier is None:
        sys.path.insert(0, str(site / "scripts"))
        from verify_multicity_canonical_receipt import verify_receipt
        verifier = verify_receipt
    receipt = verifier(receipt_path)
    status = load(status_path)
    require(status.get("canonical_persistence_status") == "NEON_SUCCEEDED" and
            status.get("canonical_receipt_validated") is True and
            status.get("canonical_db_commit") == "CONFIRMED", "C2_GATE_NOT_CONFIRMED")
    require(all(status.get(k) == receipt.get(k) for k in ("workflow_sha", "input_sha")),
            "C2_STATUS_RECEIPT_MISMATCH")
    payload = load(payload_path)
    keys = load(dashboard_path).get("multicity_meta", {}).get("production_city_keys", [])
    require(isinstance(keys, list) and len(keys) == len(set(keys)) == 23,
            "CITY_BOUNDARY_NOT_23")
    version = "alert-canonicalization-v1"
    require(payload.get("format") == "multicity-canonical-same-run-v1" and
            payload.get("canonicalization_version") == version and
            set(payload.get("cities", {})) == set(keys), "SAME_RUN_FORMAT_OR_CITY_MISMATCH")
    rows = []
    for key in keys:
        block = payload["cities"][key]
        require(isinstance(block.get("episodes"), list) and len(block["episodes"]) > 0 and
                type(block.get("episode_count")) is int and
                block["episode_count"] == len(block["episodes"]), "SAME_RUN_COUNT_MISMATCH")
        rows.extend(block["episodes"])
    serial = {"canonicalization_version": version, "production_city_keys": keys, "episodes": rows}
    corpus = hashlib.sha256(json.dumps(serial, ensure_ascii=False, sort_keys=True,
                                      separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    require(corpus == receipt.get("corpus_sha256") and receipt.get("city_count") == 23 and
            receipt.get("canonical_episode_count") == len(rows), "C2_CORPUS_BINDING_MISMATCH")
    return receipt


def export_bundle(*, enabled, site, receipt_path, status_path, payload_path, output,
                  run_id, run_attempt, workflow_sha, input_sha, db_branch, writer_url,
                  verifier=None):
    if enabled != "true":
        return {"status": "OFF"}
    status = load(status_path)
    if status.get("canonical_persistence_status") == "NEON_FAILED":
        return {"status": "C2_FAILED_NO_ARTIFACT"}
    require(not output.exists(), "EXPORT_OUTPUT_ALREADY_EXISTS")
    require(not output.resolve().is_relative_to(site.resolve()), "EXPORT_OUTPUT_NOT_ISOLATED")
    # Freeze exactly the bytes that will be verified and archived. Never glob data/.
    sources = {"receipt.json": receipt_path, "status.json": status_path, "payload.json": payload_path}
    sources.update({"site_data/" + name: site / "data" / name for name in SITE_DATA})
    raw_files = {}
    for name, path in sources.items():
        require(path.is_file() and not path.is_symlink(), "EXPORT_MISSING_INPUT")
        raw_files[name] = path.read_bytes()
        safe_json(raw_files[name])
    host = urlsplit(writer_url).hostname or ""
    require(ENDPOINT.fullmatch(host), "EXPORT_WRITER_ENDPOINT_REQUIRED")
    host = host.replace("-pooler.", ".").lower()
    with tempfile.TemporaryDirectory(prefix="c2-export-verify-") as td:
        frozen = Path(td)
        for name, raw in raw_files.items():
            path = frozen / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        receipt = verified_export_inputs(
            site=site, receipt_path=frozen / "receipt.json", status_path=frozen / "status.json",
            payload_path=frozen / "payload.json", dashboard_path=frozen / "site_data/dashboard_data.json",
            verifier=verifier)
        manifest = {
            "schema": SCHEMA, "repository": REPOSITORY,
            "github_run_id": int(run_id), "github_run_attempt": int(run_attempt),
            "workflow_sha": workflow_sha, "input_sha": input_sha,
            "corpus_sha256": receipt["corpus_sha256"], "canonical_run_id": receipt.get("run_id"),
            "db_branch": db_branch, "db_endpoint": host,
            "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(raw_files.items())},
        }
        validate_manifest(manifest)
        payload = safe_json(raw_files["payload.json"])
        if "history_capture_contract" in payload or "historical_source_receipts" in payload:
            from scripts.c6_history_freshness import verified_capture_sources
            read_at = capture_validation_clock(payload["historical_source_receipts"].values())
            # Validate identity and raw bytes without a new source request.
            # Freshness is evaluated later against the actual readback clock.
            sources_checked = verified_capture_sources(payload, manifest, read_at=read_at)
            manifest["historical_capture_receipts"] = {
                "schema": "c2-history-capture-v1", "publication_allowed": False,
                "receipt_cities": sorted(sources_checked),
                "complete_cities": sorted(k for k,v in sources_checked.items() if v["full_receipt_verified"]),
                "receipts_sha256": hashlib.sha256(json.dumps(payload["historical_source_receipts"],
                    ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()}
        candidate = frozen / "c2-shadow-inputs.zip"
        with zipfile.ZipFile(candidate, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, raw in sorted(raw_files.items()):
                archive.writestr(name, raw)
            archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True, indent=2) + "\n")
        checksum = digest(candidate)
        verify_archive(candidate, checksum)
        # Expose nothing until every validation and independent archive read passes.
        output.mkdir(parents=True)
        try:
            (output / candidate.name).write_bytes(candidate.read_bytes())
            (output / "c2-shadow-inputs.zip.sha256").write_text(checksum + "  c2-shadow-inputs.zip\n")
        except Exception:
            import shutil
            shutil.rmtree(output)
            raise
    return {"status": "EXPORTED", "bundle_sha256": checksum,
            "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True, indent=2).encode() + b"\n").hexdigest()}

# Explicit allowlist: never echo exception messages, source contents or connection strings.
# Capture verification uses CODE:city errors; only CODE is eligible for display.
SAFE_BLOCK_REASONS = frozenset("""
CAPTURE_RECEIPTS_EMPTY CAPTURE_PAGE_AFTER_EXPORT DUPLICATE_JSON_KEY NONFINITE_JSON
CREDENTIAL_FIELD_REJECTED CREDENTIAL_TEXT_REJECTED C2_MANIFEST_SCHEMA
C2_MANIFEST_GIT_SHA C2_MANIFEST_DIGEST C2_MANIFEST_RUN C2_MANIFEST_DB_IDENTITY
C2_MANIFEST_IDENTITY_MISMATCH EXISTING_C2_BUNDLE_SHA_MISMATCH
EXISTING_C2_BUNDLE_MEMBER_SET EXISTING_C2_BUNDLE_LIMIT EXISTING_C2_MEMBER_SHA
OFFLINE_FIXTURE_NOT_REAL_C2 C2_MANIFEST_RECEIPT_MISMATCH
C2_MANIFEST_CANONICAL_RUN_MISMATCH C2_GATE_NOT_CONFIRMED
C2_STATUS_RECEIPT_MISMATCH CITY_BOUNDARY_NOT_23
SAME_RUN_FORMAT_OR_CITY_MISMATCH SAME_RUN_COUNT_MISMATCH C2_CORPUS_BINDING_MISMATCH
EXPORT_OUTPUT_ALREADY_EXISTS EXPORT_OUTPUT_NOT_ISOLATED EXPORT_MISSING_INPUT
EXPORT_WRITER_ENDPOINT_REQUIRED HISTORY_CAPTURE_CONTRACT_MISSING
HISTORY_CAPTURE_CITY_MISMATCH CAPTURE_SCHEMA CAPTURE_RUN_MISMATCH
CAPTURE_SOURCE_SHA CAPTURE_PAYLOAD_KIND CAPTURE_BODY_SHA CAPTURE_CLOCK
CAPTURE_SOURCE_IDENTITY CAPTURE_COMPLETED_SHA CAPTURE_REPLAY_MISMATCH
CAPTURE_OLDEST_COMPLETED CAPTURE_COMPLETED_INTERVAL CAPTURE_CHECKPOINT_SHA
CAPTURE_CHECKPOINT_CLOCK CAPTURE_FALSE_CONTINUITY CAPTURE_UNKNOWN_SOURCE
CAPTURE_NAIVE_TIMESTAMP
""".split())


def safe_block_diagnostic(exc):
    """Return only static codes and a Python exception type, never exception details."""
    code = str(exc).split(":", 1)[0]
    if code not in SAFE_BLOCK_REASONS:
        code = "UNCLASSIFIED"
    error_type = type(exc).__name__
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,63}", error_type):
        error_type = "Exception"
    return f"reason={code} error_type={error_type}"


def main():
    p = argparse.ArgumentParser()
    for name in ("site", "receipt", "status", "payload", "output"):
        p.add_argument("--" + name, required=True, type=Path)
    args = p.parse_args()
    try:
        result = export_bundle(
            enabled=os.environ.get("C2_SHADOW_BUNDLE_EXPORT_ENABLED", ""), site=args.site,
            receipt_path=args.receipt, status_path=args.status, payload_path=args.payload, output=args.output,
            run_id=os.environ.get("GITHUB_RUN_ID"), run_attempt=os.environ.get("GITHUB_RUN_ATTEMPT"),
            workflow_sha=os.environ.get("GITHUB_SHA"), input_sha=os.environ.get("PHASE1_INPUT_SHA"),
            db_branch=os.environ.get("MULTICITY_CANONICAL_DB_BRANCH"),
            writer_url=os.environ.get("MULTICITY_CANONICAL_DATABASE_URL", ""))
    except Exception as exc:
        print("C2_BUNDLE_BLOCKED " + safe_block_diagnostic(exc) + "; no artifact authorized")
        return 1
    print(json.dumps(result, sort_keys=True))
    if result["status"] == "EXPORTED" and os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as summary:
            summary.write("\nC2 bundle SHA-256: `" + result["bundle_sha256"] + "`\n\nManifest SHA-256: `" +
                          result["manifest_sha256"] + "`\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
