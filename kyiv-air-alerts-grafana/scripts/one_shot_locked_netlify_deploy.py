#!/usr/bin/env python3
"""One owner-approved Netlify release, never leave automatic publishing unlocked.

This is only invoked after all existing offline frontend and Neon data gates.
It uses the existing Netlify CLI and token, and changes no C2/Neon/Git state.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import urllib.request

SITE = "b5aafc46-7468-4070-baf1-db80a4d30501"
API = "https://api.netlify.com/api/v1"


def request(token: str, path: str, method: str = "GET") -> dict:
    req = urllib.request.Request(
        API + path,
        data=b"" if method == "POST" else None,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def current_id(token: str) -> str:
    current = request(token, "/sites/" + SITE)
    value = (current.get("published_deploy") or {}).get("id")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{24}", value):
        raise RuntimeError("NETLIFY_CURRENT_DEPLOY_UNVERIFIABLE")
    return value


def is_locked(token: str, deploy_id: str) -> bool:
    deploy = request(token, "/deploys/" + deploy_id)
    if deploy.get("id") != deploy_id or deploy.get("site_id") != SITE:
        raise RuntimeError("NETLIFY_DEPLOY_IDENTITY_MISMATCH")
    return deploy.get("locked") is True


def verify_published_locked(token: str, deploy_id: str) -> bool:
    return current_id(token) == deploy_id and is_locked(token, deploy_id)


def release(cli, token: str, output: Path) -> str:
    if output.exists():
        raise RuntimeError("NETLIFY_OUTPUT_EXISTS")
    previous = current_id(token)
    if not is_locked(token, previous):
        raise RuntimeError("NETLIFY_PREVIOUS_DEPLOY_NOT_LOCKED")
    # Unlock only the exact currently published deploy, then relock the exact
    # newly published one before this process can finish successfully.
    request(token, "/deploys/" + previous + "/unlock", "POST")
    try:
        result = cli([
            "npx", "-y", "netlify-cli@latest", "deploy",
            "--prod", "--dir=_site", "--site=" + SITE,
            "--auth=" + token, "--json",
        ], capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError("NETLIFY_CLI_DEPLOY_FAILED")
        try:
            meta = json.loads(result.stdout)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("NETLIFY_CLI_RECEIPT_INVALID") from exc
        deployed = meta.get("deploy_id") or meta.get("id")
        if not isinstance(deployed, str) or not re.fullmatch(r"[0-9a-f]{24}", deployed):
            raise RuntimeError("NETLIFY_NEW_DEPLOY_ID_INVALID")
        info = request(token, "/deploys/" + deployed)
        if info.get("site_id") != SITE or info.get("state") != "ready":
            raise RuntimeError("NETLIFY_NEW_DEPLOY_NOT_READY")
        request(token, "/deploys/" + deployed + "/lock", "POST")
        if not verify_published_locked(token, deployed):
            raise RuntimeError("NETLIFY_PUBLISHED_LOCK_READBACK_FAILED")
        output.write_text(json.dumps(meta, sort_keys=True) + "\n", encoding="utf-8")
        print("NETLIFY_NEW_PRODUCTION_DEPLOY_PUBLISHED_LOCKED", deployed)
        return deployed
    except Exception:
        # Even if the publish succeeded and a later check failed, relock the
        # *actual current* published deploy. Never replay an old deploy blindly.
        try:
            observed = current_id(token)
            if not is_locked(token, observed):
                request(token, "/deploys/" + observed + "/lock", "POST")
            if not verify_published_locked(token, observed):
                raise RuntimeError("NETLIFY_RECOVERY_LOCK_NOT_CONFIRMED")
            print("NETLIFY_FAILURE_SAFE_RELOCK_CONFIRMED", observed)
        except Exception as lock_error:
            raise RuntimeError("CRITICAL_NETLIFY_AUTO_PUBLISH_LOCK_UNCONFIRMED") from lock_error
        raise


def main() -> None:
    token = os.environ.get("NETLIFY_AUTH_TOKEN", "")
    if not token:
        raise RuntimeError("NETLIFY_AUTH_TOKEN_MISSING")
    release(subprocess.run, token, Path("netlify-production-deploy.json"))


if __name__ == "__main__":
    main()
