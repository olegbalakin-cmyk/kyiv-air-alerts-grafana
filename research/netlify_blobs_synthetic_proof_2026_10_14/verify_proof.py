#!/usr/bin/env python3
"""Offline, no-network integrity check of blocked Netlify synthetic proof."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILES = {"preflight.json", "authorization_scope.json", "access_precheck.json",
         "expected_manifest.json", "write_result.json", "readback_result.json",
         "adjudication.json", "verify_proof.py"}

def load(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))

def verify():
    rows = load("sha256_manifest.json")["members"]
    assert len(rows) == len(FILES)
    assert {row["path"] for row in rows} == FILES
    for row in rows:
        name = row["path"]
        assert Path(name).name == name
        data = (ROOT / name).read_bytes()
        assert len(data) == row["size_bytes"], name
        assert hashlib.sha256(data).hexdigest() == row["sha256"], name
    expected = load("expected_manifest.json")
    assert expected["state"] == "OFFLINE_CANDIDATE_ONLY__NOT_FROZEN_FOR_UPLOAD"
    b = bytes(range(256)) * 256
    assert len(b) == expected["expected_byte_length"] == 65536
    assert hashlib.sha256(b).hexdigest() == expected["expected_sha256"]
    assert load("access_precheck.json")["status"] == "BLOCKED"
    assert load("write_result.json")["logical_creation_attempts"] == 0
    assert load("readback_result.json")["read_requests"] == 0
    assert load("adjudication.json")["NETLIFY NONPROD STORAGE ACCESS PRECHECK"] == "BLOCKED"
    assert not list(ROOT.glob("*.bin"))
    print(f"PASS: {len(rows)} members, SHA-256, fixture, blocked verdict; zero storage I/O")

if __name__ == "__main__":
    verify()
