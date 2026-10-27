#!/usr/bin/env python3
"""Fail-closed snapshot verification across Git fetch/rebase/rejected-push retries.

Snapshot generated once after successful PostgreSQL receipt and 23-city QA.
Any mutation to selected generated output bytes after rebase aborts publication.
No remote access, secrets, or database connection.
"""
import argparse
import hashlib
import json
from pathlib import Path

FILES = (
    "data/ukrainealarm_bridge.json",
    "data/dashboard_data.json",
    "data/dashboard_qa.json",
    "grafana/dashboard.json",
)


def digest(root):
    base = Path(root).resolve()
    out = {}
    files = [base / name for name in FILES]
    files.extend((base / "data").rglob("*"))
    for f in files:
        if not f.is_file():
            continue
        f = f.resolve()
        if not f.is_relative_to(base):
            raise ValueError("output outside root")
        name = f.relative_to(base).as_posix()
        out[name] = hashlib.sha256(f.read_bytes()).hexdigest()
    if not set(FILES).issubset(out):
        raise ValueError("required verified output file missing")
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("command", choices=("capture", "verify"))
    p.add_argument("--root", required=True)
    p.add_argument("--manifest", required=True)
    args = p.parse_args()
    path = Path(args.manifest)
    result = digest(args.root)
    if args.command == "capture":
        if path.exists():
            raise SystemExit("manifest already exists; refusing overwrite")
        path.write_text(json.dumps({"kind": "c2-verified-output-snapshot-v1",
                                    "files": result}, indent=2, sort_keys=True) + "\n")
    else:
        data = json.loads(path.read_text())
        if data.get("kind") != "c2-verified-output-snapshot-v1" or data.get("files") != result:
            raise SystemExit("verified output changed during Git rebase/retry")
    print("C2 publication output snapshot " + args.command + " PASS")


if __name__ == "__main__":
    main()
