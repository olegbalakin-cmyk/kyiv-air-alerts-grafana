#!/usr/bin/env python3
"""Redacted, read-only Git status of the exact site checkout before C6 capture.

No network, Git writes, raw paths, file content, environment or secrets in logs.
A diagnostic failure cannot change capture's existing fail-closed behavior.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import stat
import subprocess

DATA = "kyiv-air-alerts-grafana/data"
DASHBOARD = DATA + "/dashboard_data.json"
CHECKPOINTS = DATA + "/c2_history_capture_checkpoints.json"
GRAFANA = "kyiv-air-alerts-grafana/grafana/dashboard.json"
PATHSPECS = (DATA, GRAFANA)
MAX_SAMPLE = 32
MAX_BYTES = 128 * 1024 * 1024
SCHEMA = "c6-pre-capture-status-v1"
KINDS = ("modified", "added", "untracked", "deleted", "renamed",
         "copied", "unmerged", "other")


def git_read(checkout: Path, *args: str) -> bytes:
    # Disable optional index-refresh locks/writes. Suppress raw stderr paths.
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(checkout), *args],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL, timeout=20,
    ).stdout


def parse_status(raw: bytes) -> list[tuple[str, str, str | None]]:
    """Decode porcelain-v1 -z; rename/copy has an extra NUL-delimited path."""
    if not raw:
        return []
    if not raw.endswith(b"\0"):
        raise ValueError("BAD_PORCELAIN")
    parts = raw[:-1].split(b"\0")
    rows = []
    i = 0
    while i < len(parts):
        record = parts[i]
        i += 1
        if len(record) < 4 or record[2:3] != b" ":
            raise ValueError("BAD_PORCELAIN")
        xy = record[:2].decode("ascii")
        path = record[3:].decode("utf-8", errors="surrogateescape")
        if not path:
            raise ValueError("BAD_PORCELAIN")
        previous = None
        if "R" in xy or "C" in xy:
            if i == len(parts) or not parts[i]:
                raise ValueError("BAD_PORCELAIN_PAIR")
            previous = parts[i].decode("utf-8", errors="surrogateescape")
            i += 1
        rows.append((xy, path, previous))
    return rows


def kind(xy: str) -> str:
    if xy == "??":
        return "untracked"
    if xy in {"DD", "AU", "UD", "UA", "DU", "AA", "UU"} or "U" in xy:
        return "unmerged"
    for code, name in (("R", "renamed"), ("C", "copied"),
                       ("D", "deleted"), ("A", "added"), ("M", "modified")):
        if code in xy:
            return name
    return "other"


def path_id(path: str) -> str:
    return hashlib.sha256(path.encode("utf-8", errors="surrogateescape")).hexdigest()[:16]


def file_flags(root: Path, relative: str) -> dict[str, bool]:
    absent = {"regular": False, "nonempty": False, "size_ok": False}
    parts = relative.split("/")
    if not parts or any(p in ("", ".", "..") for p in parts):
        return absent
    current = root
    try:
        # lstat parent directories too: never follow symlinked parents.
        for component in parts[:-1]:
            current = current / component
            if not stat.S_ISDIR(current.lstat().st_mode):
                return absent
        info = (current / parts[-1]).lstat()
    except (OSError, ValueError):
        return absent
    regular = stat.S_ISREG(info.st_mode)
    return {
        "regular": regular,
        "nonempty": regular and info.st_size > 0,
        "size_ok": regular and 0 < info.st_size <= MAX_BYTES,
    }


def inspect(checkout: Path, expected_head: str) -> dict:
    head = git_read(checkout, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", head):
        raise ValueError("BAD_HEAD")
    raw_branch = git_read(checkout, "branch", "--show-current").decode(
        "utf-8", errors="surrogateescape").strip()
    branch = "site-prod" if raw_branch == "site-prod" else (
        "detached" if not raw_branch else "other")
    raw = git_read(checkout, "status", "--porcelain=v1", "-z",
                   "--untracked-files=all", "--", *PATHSPECS)
    rows = parse_status(raw)
    xy_counts = Counter(xy for xy, _, _ in rows)
    types = Counter(kind(xy) for xy, _, _ in rows)
    checked = [(xy, path, old, file_flags(checkout, path))
               for xy, path, old in rows]
    checks = {
        field: sum(int(item[3][field]) for item in checked)
        for field in ("regular", "nonempty", "size_ok")
    }
    samples = []
    for xy, path, old, flags in sorted(checked, key=lambda item: path_id(item[1]))[:MAX_SAMPLE]:
        item = {"id": path_id(path), "xy": xy, "type": kind(xy),
                "file": flags}
        if old is not None:
            item["paired_from_id"] = path_id(old)
        samples.append(item)
    return {
        "schema": SCHEMA, "status": "ok", "head": head,
        "head_matches_expected": head == expected_head,
        "branch": branch, "scoped_changes": len(rows),
        "xy_counts": dict(sorted(xy_counts.items())),
        "types": {key: types[key] for key in KINDS},
        "file_check_counts": checks,
        "checkpoint_file_regular": file_flags(checkout, CHECKPOINTS)["regular"],
        "dashboard_changed": any(path == DASHBOARD for _, path, _ in rows),
        "path_ids": samples,
        "path_ids_truncated": max(0, len(rows) - len(samples)),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--expected-head", required=True)
    args = parser.parse_args(argv)
    try:
        result = inspect(Path(args.checkout), args.expected_head)
    except Exception:
        # Never print exception, path, traceback, subprocess stderr or secrets.
        result = {"schema": SCHEMA, "status": "unavailable"}
    print("C6_PRECAPTURE_DIAG=" + json.dumps(
        result, sort_keys=True, separators=(",", ":"), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
