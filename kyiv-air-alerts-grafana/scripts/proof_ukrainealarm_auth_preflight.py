#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import apply_ukrainealarm_bridge as ua

REGION_ID = "1293"
REGION_NAME = "proof-auth-preflight"


def status_from_exception(exc: Exception) -> int:
    text = str(exc)
    marker = "HTTP "
    if marker in text:
        tail = text.split(marker, 1)[1]
        code = tail.split(None, 1)[0]
        if code.isdigit():
            return int(code)
    return 0


def probe_once() -> int:
    token = os.environ.get("UKRAINEALARM_API_TOKEN", "").strip()
    if not token:
        return 0
    client = ua.UkraineAlarmClient(token)
    sink = io.StringIO()
    try:
        with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            response = client.get(
                ua.HISTORY_URL,
                params={"regionId": REGION_ID},
                context=REGION_NAME,
            )
        return int(response.status_code)
    except Exception as exc:
        return status_from_exception(exc)


def child_main() -> int:
    print(json.dumps({"status": probe_once()}))
    return 0


def run_child(extra_env: dict[str, str] | None = None) -> int:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    proc = subprocess.run(
        [sys.executable, __file__, "--child"],
        cwd=str(ROOT),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    try:
        row = json.loads(proc.stdout.strip().splitlines()[-1])
        return int(row.get("status") or 0)
    except Exception:
        return 0


def main() -> int:
    token_present = bool(os.environ.get("UKRAINEALARM_API_TOKEN", "").strip())
    print(f"token_present = {'true' if token_present else 'false'}")
    if not token_present:
        return 2

    direct = probe_once()
    print(f"direct_probe_status = {direct}")
    if direct != 200:
        return 3

    child_env = dict(os.environ)
    child_env.pop("PYTHONPATH", None)
    proc = subprocess.run(
        [sys.executable, __file__, "--child"],
        cwd=str(ROOT),
        env=child_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    try:
        subprocess_status = int(json.loads(proc.stdout.strip().splitlines()[-1]).get("status") or 0)
    except Exception:
        subprocess_status = 0
    print(f"subprocess_probe_status = {subprocess_status}")
    if subprocess_status != 200:
        return 4

    import proof_differentiated_alert_siteprod_equivalence as proof

    proof.write_sitecustomize()
    shim_env = dict(os.environ)
    shim_env["PYTHONPATH"] = str(proof.SHIM_DIR)
    shim_env["PROOF_HTTP_MODE"] = "capture"
    shim_env["PROOF_HTTP_DIR"] = str(proof.CAPTURE_DIR)
    shim_env["UKRAINEALARM_MIN_INTERVAL_SECONDS"] = "0"

    capture_status = run_child(shim_env)
    capture_written = any(proof.CAPTURE_DIR.glob("*.json"))
    if capture_status == 200 and not capture_written:
        capture_status = 0
    print(f"capture_probe_status = {capture_status}")
    if capture_status != 200:
        return 5
    return 0


if __name__ == "__main__":
    if "--child" in sys.argv:
        raise SystemExit(child_main())
    raise SystemExit(main())
