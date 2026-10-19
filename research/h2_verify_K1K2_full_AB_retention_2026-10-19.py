#!/usr/bin/env python3
"""Independent Git-only K1/K2 A/B original-byte retention verifier."""
import argparse
import base64
import hashlib
import json
import lzma
from pathlib import Path

NAMES = (
    "h2_legacy_main_report.json",
    "h2_legacy_caller_report.json",
    "h2_observed_result.json",
    "h2_mutation_result.json",
)
VERDICTS = ("PASS", "PARTIAL", "PASS_OFFLINE_PARTIAL_OBSERVED_SCHEMA", "PASS_MUTATION_CONTROLS_BOUNDED_PG18")
sha = lambda b: hashlib.sha256(b).hexdigest()

def verify(data, manifest):
    meta = manifest["archive"]
    assert len(data) == meta["byte_size"] and sha(data) == meta["sha256"], "archive"
    xz = base64.b64decode(data.strip(), validate=True)
    assert len(xz) == meta["xz_byte_size"] and sha(xz) == meta["xz_sha256"], "xz"
    payload = lzma.decompress(xz, format=lzma.FORMAT_XZ)
    assert len(payload) == meta["map_byte_size"] and sha(payload) == meta["map_sha256"], "json-map"
    members = json.loads(payload)
    assert set(members) == {f"{label}/{n}" for label in ("A", "B") for n in NAMES}
    assert manifest["member_count"] == 8 and set(manifest["artifacts"]) == {"A", "B"}
    verified = []
    for label, artifact in manifest["artifacts"].items():
        assert artifact["run_id"] == 39212648444
        assert artifact["tested_commit"] == manifest["tested_commit"]
        assert set(artifact["members"]) == set(NAMES)
        for name, info in artifact["members"].items():
            raw = base64.b64decode(members[f"{label}/{name}"], validate=True)
            assert len(raw) == info["size"] and sha(raw) == info["sha256"], "source member"
            obj = json.loads(raw)
            assert obj["verdict"] == info["verdict"] == VERDICTS[NAMES.index(name)]
            if name == "h2_mutation_result.json":
                assert set(obj["cases"]) == {"K1", "K2"}
                assert obj["writer_restored"] is True
                assert obj["network_live_calls"] == obj["neon_calls"] == 0
            verified.append(label + "/" + name)
    return verified

def negatives(data, manifest):
    def rejected(a, b):
        try:
            verify(a, b)
            return False
        except (ValueError, AssertionError, TypeError, KeyError, EOFError, lzma.LZMAError):
            return True
    flip = bytearray(data)
    i = len(flip) // 2
    flip[i] = ord("B") if flip[i] == ord("A") else ord("A")
    assert rejected(bytes(flip), manifest)
    bad = json.loads(json.dumps(manifest))
    bad["artifacts"]["A"]["members"]["h2_mutation_result.json"]["sha256"] = "0"*64
    assert rejected(data, bad)
    bad = json.loads(json.dumps(manifest))
    bad["archive"]["map_sha256"] = "0"*64
    assert rejected(data, bad)
    return ["tampered archive", "tampered raw member hash", "tampered map hash"]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    opt = parser.parse_args()
    archive = (opt.root / "h2_K1K2_full_AB_reports_2026-10-19.json.xz.b64").read_bytes()
    manifest = json.loads((opt.root / "h2_K1K2_full_AB_retention_manifest_2026-10-19.json").read_bytes())
    print(json.dumps({"status": "PASS", "members": verify(archive, manifest), "negative_controls_rejected": negatives(archive, manifest)}, indent=2))

if __name__ == "__main__":
    main()
