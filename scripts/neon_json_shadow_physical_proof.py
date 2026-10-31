#!/usr/bin/env python3
"""Manual protected proof using an existing owner-pinned C2 artifact. NEVER publish.

No credential creation, capture HTTP, writer, Git push or update-site workflow.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch

from scripts import neon_json_shadow as shadow

SITE_DATA = ("dashboard_data.json", "site_derived.json", "alerts_combined.json",
             "kyiv_threat_mix.json", "sevastopol_events.json")


def prepare_bundle(bundle, expected_sha, destination):
    shadow.require(re.fullmatch(r"[0-9a-f]{64}", expected_sha) is not None and
                   shadow.digest(bundle) == expected_sha, "EXISTING_C2_BUNDLE_SHA_MISMATCH")
    expected = {"receipt.json", "status.json", "payload.json", "manifest.json"} | {
        "site_data/" + name for name in SITE_DATA}
    with zipfile.ZipFile(bundle) as z:
        shadow.require(set(z.namelist()) == expected and len(z.namelist()) == len(expected),
                       "EXISTING_C2_BUNDLE_MEMBER_SET")
        manifest = json.loads(z.read("manifest.json"))
        shadow.require(manifest.get("schema") == "existing-c2-shadow-inputs-v1" and
                       set(manifest["files"]) == expected - {"manifest.json"}, "EXISTING_C2_MANIFEST")
        for name, want in manifest["files"].items():
            shadow.require(hashlib.sha256(z.read(name)).hexdigest() == want,
                           "EXISTING_C2_MEMBER_SHA")
        receipt = json.loads(z.read("receipt.json"))
        shadow.require(receipt.get("offline_fixture") is not True,
                       "OFFLINE_FIXTURE_CANNOT_AUTHORIZE_PHYSICAL_READBACK")
        z.extractall(destination)  # exact allowlisted relative names above


@contextlib.contextmanager
def no_source_http():
    import requests

    def blocked(*args, **kwargs):
        raise shadow.ShadowBlocked("SOURCE_HTTP_NOT_AUTHORIZED")

    # libpq owns the sole TLS database connection; Python source clients cannot connect.
    with contextlib.ExitStack() as stack:
        for obj, name in ((requests.sessions.Session, "request"), (urllib.request, "urlopen"),
                          (socket.socket, "connect"), (socket.socket, "connect_ex"),
                          (socket, "create_connection")):
            stack.enter_context(patch.object(obj, name, blocked))
        yield


def main():
    p = argparse.ArgumentParser()
    for flag in ("site", "bundle", "output"):
        p.add_argument("--" + flag, required=True, type=Path)
    for flag in ("bundle-sha256", "workflow-sha", "input-sha", "db-branch", "db-endpoint"):
        p.add_argument("--" + flag, required=True)
    args = p.parse_args()
    try:
        shadow.require(re.fullmatch(r"[0-9a-f]{40}", args.workflow_sha) is not None and
                       re.fullmatch(r"[0-9a-f]{40}", args.input_sha) is not None, "FULL_SHA_REQUIRED")
        shadow.require(re.fullmatch(r"ep-[a-z0-9.-]+\.neon\.tech", args.db_endpoint) is not None,
                       "APPROVED_NEON_ENDPOINT_REQUIRED")
        with tempfile.TemporaryDirectory(prefix="isolated-neon-proof-") as td:
            work = Path(td)
            prepare_bundle(args.bundle, args.bundle_sha256, work / "inputs")
            site = work / "site"
            shutil.copytree(args.site / "scripts", site / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
            shutil.copytree(work / "inputs/site_data", site / "data")
            with no_source_http():
                result = shadow.execute(
                    site=site, receipt_path=work / "inputs/receipt.json",
                    status_path=work / "inputs/status.json", payload_path=work / "inputs/payload.json",
                    dashboard_path=site / "data/dashboard_data.json", output=args.output,
                    database_url=os.environ.get("NEON_JSON_SHADOW_READONLY_DATABASE_URL", ""),
                    writer_database_url="postgresql://" + args.db_endpoint + "/neondb",
                    expected_branch=args.db_branch, workflow_sha=args.workflow_sha, input_sha=args.input_sha)
            assert result["publication_allowed"] is False and len(result["candidate_files"]) == 6
    except Exception:
        args.output.mkdir(parents=True, exist_ok=True)
        if not (args.output / "verdict.json").exists():
            shadow.write(args.output / "verdict.json", {
                "status": "BLOCKED", "reason": "PHYSICAL_PREFLIGHT_OR_INPUT_FAILURE",
                "publication_allowed": False, "candidate_files": {},
                "production_publication": "PRODUCTION_PUBLICATION_NOT_AUTHORIZED"})
        print("Physical shadow BLOCKED; inspect credential-free verdict", file=sys.stderr)
        return 1
    finally:
        if args.output.is_dir():
            shadow.write(args.output / "sha256_manifest.json", {
                "schema": "isolated-neon-shadow-proof-v1", "files": {
                    str(f.relative_to(args.output)): shadow.digest(f)
                    for f in sorted(args.output.rglob("*"))
                    if f.is_file() and f.name != "sha256_manifest.json"}})
    print("PHYSICAL_GENERATION_PASS; PRODUCTION_PUBLICATION_NOT_AUTHORIZED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
