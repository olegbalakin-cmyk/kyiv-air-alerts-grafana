#!/usr/bin/env python3
"""Restore local fixture members from immutable Git objects. Never fetch or connect.

The full accepted evidence archive and production checkout already exist in Git.
No derived archive of 31,977 episodes needs to be added to the research branch.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "research/neon_json_shadow_frontend_2026_10_31/fixtures"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_bytes(repo, ref, path):
    result = subprocess.run(["git", "-C", str(repo), "show", ref + ":" + path],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError("IMMUTABLE_GIT_OBJECT_MISSING:" + ref + ":" + path)
    return result.stdout


def restore(output, git_repo=ROOT):
    provenance = json.loads((FIXTURES / "provenance.json").read_text())
    if output.exists():
        raise ValueError("FIXTURE_CACHE_ALREADY_EXISTS")
    raw = git_bytes(git_repo, provenance["archive_git_commit"], provenance["archive_git_path"])
    assert digest(raw) == provenance["archive_sha256"], "IMMUTABLE_ARCHIVE_SHA"
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        manifest = json.loads(archive.read("sha256_manifest.json"))["files"]
        assert len(manifest) == provenance["archive_verified_members"] == 85
        for name, expected in manifest.items():
            assert digest(archive.read(name)) == expected, "IMMUTABLE_ARCHIVE_MEMBER_SHA"
        snapshot_raw = archive.read(provenance["snapshot_member"])
    assert digest(snapshot_raw) == provenance["snapshot_sha256"], "ORIGINAL_READBACK_SHA"
    snap = json.loads(snapshot_raw)
    site_members = {
        name: git_bytes(git_repo, provenance["site_input_sha"], "kyiv-air-alerts-grafana/" + name)
        for name in provenance["members"]["site-inputs.zip"]}
    overlay_raw = (FIXTURES / "contracts/snapshot_overlay.json").read_bytes()
    overlay = json.loads(overlay_raw)
    version = overlay["canonicalization_version"]
    fields = ("alert_type", "city_key", "end_at", "episode_state", "legacy_episode_id", "start_at")
    cities = {}
    for row in snap["episodes"]:
        block = cities.setdefault(row["city_key"], {"episodes": [], "episode_count": 0})
        block["episodes"].append({**{field: row[field] for field in fields},
                                  "canonicalization_version": version})
        block["episode_count"] += 1
    payload = {"canonicalization_version": version, "cities": cities,
               "format": "multicity-canonical-same-run-v1"}
    payload_raw = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False).encode()
    input_members = {"neon_readback.original.json": snapshot_raw, "payload.json": payload_raw,
                     "snapshot_overlay.json": overlay_raw,
                     **{name: (FIXTURES / "contracts" / name).read_bytes()
                        for name in ("receipt.json", "status.json")}}
    groups = {"site-inputs.zip": site_members, "readback-c2-fixture.zip": input_members}
    # Verify every member before writing a cache; no timestamps or source rows change.
    for group, members in groups.items():
        expected = provenance["members"][group]
        assert set(members) == set(expected), "RESTORED_FIXTURE_MEMBER_SET"
        for name, content in members.items():
            assert digest(content) == expected[name], "RESTORED_FIXTURE_MEMBER_SHA:" + name
    output.mkdir(parents=True)
    for group, members in groups.items():
        for name, content in members.items():
            path = output / group.removesuffix(".zip") / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return {"status": "PASS", "network_or_sql_calls": 0,
            "archive_sha256": provenance["archive_sha256"],
            "original_manifest_hashes_verified": 85,
            "restored_member_count": sum(map(len, groups.values())),
            "snapshot_sha256": digest(snapshot_raw), "payload_sha256": digest(payload_raw),
            "synthetic_contract_only": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=FIXTURES / "cache")
    parser.add_argument("--git-repo", type=Path, default=ROOT)
    args = parser.parse_args()
    print(json.dumps(restore(args.output, args.git_repo), sort_keys=True))


if __name__ == "__main__":
    main()
