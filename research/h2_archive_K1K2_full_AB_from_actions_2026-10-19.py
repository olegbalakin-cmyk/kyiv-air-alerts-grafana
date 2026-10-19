#!/usr/bin/env python3
"""Download two exact GitHub Actions ZIPs and retain all eight original JSON bytes.
Runs only in an explicitly isolated GitHub Actions research job; no Neon access."""
import base64
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import re
import subprocess
import zipfile

DEST = Path("research")
IDS = {
    "A": (12168038465, 13056, "1b98ea776474088b20c5551646b5447d11ab70d2b149ba7a000ae56abbb64217", "142e6ed4940fde6e42327d5710ca9319795f0625b0a3e691eefa11bb8320887c"),
    "B": (12167869611, 13051, "e21506972e57393892b50be263c72084e72504245c2498f06a873ef976078a29", "c1515afd66b7abf4894129152b10f76dbeb0a210a475d712977eadfdf2b7e3e4"),
}
NAMES = {"h2_legacy_main_report.json", "h2_legacy_caller_report.json", "h2_observed_result.json", "h2_mutation_result.json"}
VERDICTS = {
    "h2_legacy_main_report.json": "PASS",
    "h2_legacy_caller_report.json": "PARTIAL",
    "h2_observed_result.json": "PASS_OFFLINE_PARTIAL_OBSERVED_SCHEMA",
    "h2_mutation_result.json": "PASS_MUTATION_CONTROLS_BOUNDED_PG18",
}
sha = lambda b: hashlib.sha256(b).hexdigest()
head = "edb3faa5e5e3fd303db357d5b2fd01b236fe255c"
assert os.environ["GITHUB_REPOSITORY"] == "olegbalakin-cmyk/kyiv-air-alerts-grafana"
assert os.environ["GITHUB_REF_NAME"] == "research-h2-neon-seven-contract-catalog-completion-2026-10-19"
assert os.environ.get("GH_TOKEN") and os.environ.get("GITHUB_ACTIONS") == "true"

artifacts = {}
members = {}
for label, (aid, size, expected_zip_sha, mutation_hash) in IDS.items():
    url = f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/artifacts/{aid}/zip"
    result = subprocess.run(["gh", "api", "-H", "Accept: application/vnd.github+json", url], capture_output=True, check=False)
    assert result.returncode == 0, f"authorized GitHub API artifact download failed ({label}, code {result.returncode})"
    content = result.stdout
    assert len(content) == size and sha(content) == expected_zip_sha, f"source ZIP differs: {label}"
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        assert z.testzip() is None and set(z.namelist()) == NAMES and len(z.namelist()) == 4
        records = {}
        for name in sorted(NAMES):
            raw = z.read(name)
            assert not re.search(rb"(?i)(password|private_key|api[_-]?token|postgres(?:ql)?://|connection[_-]?string|PGPASSWORD)", raw)
            doc = json.loads(raw)
            assert doc["verdict"] == VERDICTS[name]
            if name == "h2_mutation_result.json":
                assert len(raw) == 42716 and sha(raw) == mutation_hash
                assert set(doc["cases"]) == {"K1", "K2"}
                assert doc["writer_restored"] is True
                assert doc["network_live_calls"] == doc["neon_calls"] == 0
            if name == "h2_legacy_main_report.json":
                assert doc["network"]["live_calls"] == 0
            members[f"{label}/{name}"] = base64.b64encode(raw).decode("ascii")
            records[name] = {"size": len(raw), "sha256": sha(raw), "verdict": doc["verdict"]}
        artifacts[label] = {
            "artifact_id": aid, "run_id": 39212648444, "tested_commit": head,
            "zip_size": size, "zip_sha256": expected_zip_sha,
            "zip_crc": "PASS", "members": records,
        }
payload = (json.dumps(members, sort_keys=True, separators=(",",":"), ensure_ascii=True) + "\n").encode()
compressed = lzma.compress(payload, format=lzma.FORMAT_XZ, preset=9)
encoded = base64.b64encode(compressed) + b"\n"
manifest = {
    "format": "H2-K1K2-full-AB-v1",
    "source": "exact original ZIP member bytes; original JSON never reserialized",
    "tested_commit": head,
    "previous_run": {"run_id": 39212435057, "tested_commit": "5a872f9f4b034433a5481620acd8f11bba700394", "retained": False},
    "artifacts": artifacts,
    "member_count": 8,
    "archive": {
        "path": "research/h2_K1K2_full_AB_reports_2026-10-19.json.xz.b64",
        "byte_size": len(encoded), "sha256": sha(encoded),
        "xz_byte_size": len(compressed), "xz_sha256": sha(compressed),
        "map_byte_size": len(payload), "map_sha256": sha(payload),
    },
    "acceptance_limits": {
        "K1": "intentional stale CAS bypass detected offline",
        "K2": "duplicate insert ATTEMPT; UNIQUE(classification_key) and ON CONFLICT DO NOTHING suppress committed duplicate; application-level duplicate rejection unproven",
        "Neon": "no live Neon SQL or writes",
    },
}
archive_name = "h2_K1K2_full_AB_reports_2026-10-19.json.xz.b64"
manifest_name = "h2_K1K2_full_AB_retention_manifest_2026-10-19.json"
receipt_name = "h2_K1K2_full_AB_retention_receipt_2026-10-19.json"
DEST.joinpath(archive_name).write_bytes(encoded)
DEST.joinpath(manifest_name).write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
receipt = {
    "result": "PASS_BEFORE_GIT_READBACK",
    "run_id": 39212648444,
    "source_zip_identity": {"A": IDS["A"][2], "B": IDS["B"][2]},
    "source_members_verified": len(members),
    "source_git_branch": os.environ["GITHUB_REF_NAME"],
    "source_workflow_sha": os.environ["GITHUB_SHA"],
    "archive_sha256": sha(encoded),
    "manifest_sha256": sha(DEST.joinpath(manifest_name).read_bytes()),
    "zip_crcs": ["A:PASS", "B:PASS"],
    "execution_limits": ["No Neon calls", "No application data rows", "No production or WIP changes"],
}
DEST.joinpath(receipt_name).write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"verdict": "PASS", "members": len(members), "archive_bytes": len(encoded), "archive_sha256": sha(encoded), "map_sha256": sha(payload)}))
