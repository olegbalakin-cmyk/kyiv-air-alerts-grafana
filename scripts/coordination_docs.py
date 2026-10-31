#!/usr/bin/env python3
"""Lossless, standard-library-only coordination document maintenance.

Archive only explicit history regions; never infer whether live blockers are old.
Sizes are UTF-8 bytes. 1 KiB = 1024 bytes; boundaries themselves are inclusive.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

FILES = ("PROJECT_STATE.md", "CHANGELOG.md")
WARN = 12 * 1024
FAIL = 16 * 1024
TARGET = 8 * 1024
ARCHIVE = Path("docs/coordination-archive")
MANIFEST = ARCHIVE / "manifest.json"
START = b"<!-- coordination:history:start -->\n"
END = b"<!-- coordination:history:end -->"
ENTRY = re.compile(rb"(?m)^#{2,3} ([A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+)[^\r\n]*")
LEGACY = {
    "PROJECT_STATE_full_before_compaction_2026-10-30.md": "ebcc286b3bfc93372a61567f1de5fe1d3e49bc2a",
    "CHANGELOG_full_before_compaction_2026-10-30.md": "732e7a07f3e92e1138aafe311bff5561f56d60ee",
}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def read(root: Path, name: str | Path) -> bytes:
    data = (root / name).read_bytes()
    data.decode("utf-8")  # Do not silently normalize or replace invalid UTF-8.
    return data


def region(data: bytes) -> tuple[int, int]:
    if data.count(START) != 1 or data.count(END) != 1:
        raise ValueError("Require exactly one coordination:history:start/end pair")
    a, b = data.index(START) + len(START), data.index(END)
    if a > b:
        raise ValueError("History markers are reversed")
    return a, b


def records(data: bytes, marked: bool = True) -> list[dict]:
    a, b = region(data) if marked else (0, len(data))
    matches = list(ENTRY.finditer(data, a, b))
    result = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else b
        result.append({"id": m.group(1).decode(), "start": m.start(), "end": end,
                       "sha256": sha(data[m.start():end])})
    return result


def status(size: int) -> str:
    return "FAIL" if size > FAIL else "WARNING" if size > WARN else "PASS"


def check(root: Path) -> list[dict]:
    return [{"file": name, "bytes": len(read(root, name)),
             "status": status(len(read(root, name)))} for name in FILES]


def manifest(root: Path) -> dict:
    path = root / MANIFEST
    return json.loads(path.read_text()) if path.exists() else {"version": 1, "snapshots": []}


def snapshot(root: Path, name: str, data: bytes, date: str, source_ref: str,
             index: dict, pending: dict[Path, bytes], removed: list[dict]) -> str:
    path = ARCHIVE / f"{date}_{Path(name).stem}_{sha(data)[:16]}.md"
    item = {"path": path.as_posix(), "source_file": name, "source_ref": source_ref,
            "bytes": len(data), "sha256": sha(data), "git_blob_sha1": blob(data),
            "removed_records": removed}
    same = next((s for s in index["snapshots"] if s["path"] == str(path)), None)
    if same and same != item:
        raise ValueError(f"Snapshot metadata conflict: {path}")
    if (root / path).exists() and read(root, path) != data:
        raise ValueError(f"Refusing to overwrite immutable archive: {path}")
    if not same:
        index["snapshots"].append(item)
    pending[path] = data
    return str(path)


def verify(root: Path, base_ref: str | None = None, strict_layout: bool = True) -> dict:
    index = manifest(root)
    if index.get("version") != 1:
        raise ValueError("Unsupported archive manifest version")
    paths = set()
    archives = []
    for item in index["snapshots"]:
        path = item["path"]
        if path in paths or not path.startswith(str(ARCHIVE) + "/") or ".." in Path(path).parts:
            raise ValueError(f"Unsafe or duplicate archive path: {path}")
        paths.add(path)
        data = read(root, path)
        if (len(data), sha(data), blob(data)) != (item["bytes"], item["sha256"], item["git_blob_sha1"]):
            raise ValueError(f"Archive integrity mismatch: {path}")
        for rec in item.get("removed_records", []):
            part = data[rec["start"]:rec["end"]]
            if not part or sha(part) != rec["sha256"] or rec["id"].encode() not in part.split(b"\n", 1)[0]:
                raise ValueError(f"Lost or changed historical record: {path}: {rec['id']}")
        archives.append(data)
    for name, expected in LEGACY.items():
        path = str(ARCHIVE / name)
        if path not in paths or blob(read(root, path)) != expected:
            raise ValueError(f"Original historical Git blob missing or modified: {path}")
    # Every markdown archive must be inventoried; orphan snapshots are not accepted.
    for path in (root / ARCHIVE).glob("*.md"):
        if path.name != "README.md" and str(path.relative_to(root)) not in paths:
            raise ValueError(f"Untracked archive snapshot: {path}")
    for name in FILES:
        data = read(root, name)
        entries = records(data)
        if not entries or (name == FILES[1] and (len(entries) < 5 or (strict_layout and len(entries) > 10))):
            raise ValueError(f"{name}: keep one latest state checkpoint and 5–10 changelog transitions")
        if len({r['id'] for r in entries}) != len(entries):
            raise ValueError(f"Duplicate checkpoint IDs in {name}")
        if str(ARCHIVE / "README.md").encode() not in data:
            raise ValueError(f"{name}: missing stable archive index link")
    if base_ref:
        def old(path: str) -> bytes:
            return subprocess.check_output(["git", "show", f"{base_ref}:{path}"], cwd=root)
        # Inventories and prior snapshots are append-only across a PR/push.
        proc = subprocess.run(["git", "show", f"{base_ref}:{MANIFEST}"], cwd=root, capture_output=True)
        if proc.returncode == 0:
            prior = json.loads(proc.stdout)
            for item in prior["snapshots"]:
                if item not in index["snapshots"] or old(item["path"]) != read(root, item["path"]):
                    raise ValueError(f"Previously accepted archive removed or rewritten: {item['path']}")
        for name in FILES:
            before = old(name)
            after = read(root, name)
            for rec in records(before, marked=START in before):
                part = before[rec["start"]:rec["end"]]
                if part not in after and not any(part in data for data in archives):
                    raise ValueError(f"Historical record lost: {name}: {rec['id']}; run archive before editing")
    return {"snapshots_verified": len(paths), "removed_records_verified": sum(
        len(s.get("removed_records", [])) for s in index["snapshots"]), "history_integrity": "PASS"}


def archive(root: Path, date: str, source_ref: str, dry_run: bool = True) -> dict:
    dt.date.fromisoformat(date)
    verify(root, strict_layout=False)  # Permit >10 entries before reducing them.
    index = manifest(root)
    pending: dict[Path, bytes] = {}
    summary = []
    for name in FILES:
        data = read(root, name)
        entries = records(data)
        keep = 1 if name == FILES[0] else 5
        removed = entries[keep:]
        if not removed:
            if len(data) > WARN:
                raise ValueError(f"{name}: {len(data)} bytes; active text/retained checkpoints cannot be safely reduced. "
                                 "Keep live blockers, shorten the current snapshot manually after saving an exact snapshot; see docs/coordination-maintenance.md")
            continue
        a, b = region(data)
        cut = removed[0]["start"]
        new = data[:cut] + data[b:]
        if len(new) > WARN:
            raise ValueError(f"{name}: {len(new)} bytes after archive; live text remains too large; no files written")
        # All bytes removed from the roots are present in the complete exact snapshot.
        path = snapshot(root, name, data, date, source_ref, index, pending, removed)
        assert data[cut:b] in pending[Path(path)]
        assert new[:a] == data[:a] and new[new.index(END):] == data[b:]
        assert records(new)[0]["sha256"] == entries[0]["sha256"]
        pending[Path(name)] = new
        summary.append({"file": name, "before_bytes": len(data), "after_bytes": len(new),
                        "removed_records": len(removed), "archive": path})
    if pending:
        pending[MANIFEST] = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode()
    if not dry_run:
        # Prepare the complete plan before writing; interrupted writes are recoverable
        # because immutable source snapshots are persisted before roots are replaced.
        for path in sorted(pending, key=lambda p: (p in map(Path, FILES), p == MANIFEST, str(p))):
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(target.suffix + ".tmp")
            tmp.write_bytes(pending[path])
            tmp.replace(target)
        verify(root)
    return {"dry_run": dry_run, "changes": summary}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=("check", "verify", "archive"))
    p.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    p.add_argument("--source-ref", default="WORKTREE")
    p.add_argument("--base-ref")
    p.add_argument("--json-output", type=Path)
    args = p.parse_args()
    try:
        if args.command == "check":
            report = {"files": check(args.root), "warning_above_bytes": WARN, "failure_above_bytes": FAIL}
            for item in report["files"]:
                if item["status"] != "PASS":
                    level = "error" if item["status"] == "FAIL" else "warning"
                    print(f"::{level} file={item['file']}::{item['file']}: {item['bytes']} UTF-8 bytes; "
                          f"{item['status']} (warning > {WARN}, fail > {FAIL}). Run: "
                          "python scripts/coordination_docs.py archive --dry-run ; "
                          "python scripts/coordination_docs.py archive", file=sys.stderr)
            code = int(any(i["status"] == "FAIL" for i in report["files"]))
        elif args.command == "verify":
            report, code = verify(args.root, args.base_ref), 0
        else:
            report, code = archive(args.root, args.date, args.source_ref, args.dry_run), 0
        if args.json_output:
            args.json_output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return code
    except (ValueError, OSError, subprocess.CalledProcessError) as e:
        print(f"::error::Coordination docs: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
