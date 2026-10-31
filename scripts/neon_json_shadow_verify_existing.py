#!/usr/bin/env python3
"""Verify recovered six-file output without rerunning the generator or connecting."""
from __future__ import annotations

import argparse
import json
import re
import tempfile
from pathlib import Path

from scripts import neon_json_shadow_offline_proof as proof
from scripts import neon_json_shadow_generator as generator


def verify(output, negatives, unit_log):
    manifest = json.loads((output / "sha256_manifest.json").read_text())["files"]
    actual = proof.file_hashes(output)
    actual.pop("sha256_manifest.json")
    assert actual == manifest, "RECOVERED_MANIFEST_MISMATCH"
    with tempfile.TemporaryDirectory(prefix="verify-existing-shadow-") as td:
        site, _, snapshot, provenance = proof.prepare_fixture(Path(td))
        before = proof.file_hashes(site)
        with proof.no_network() as attempts:
            checks = proof.validate_candidate(output, snapshot, site)
        assert attempts == [] and before == proof.file_hashes(site)
        readback = json.loads((output / "readback_proof.json").read_text())
        assert all(generator.fingerprint(snapshot[k]) == v
                   for k, v in readback["table_sha256"].items()), "READBACK_TABLE_DIGEST"
        assert readback["physical_neon_readback_run"] is False
    gates = json.loads((output / "source_gates.json").read_text())
    assert len(gates) == 23
    assert all(g["source_capture_verified"] is False and g["source_captured_at_utc"] is None
               and g["publication_verdict"] == "BLOCKED" for g in gates.values())
    verdict = json.loads((output / "verdict.json").read_text())
    assert verdict["dst_repair_certified"] is False and verdict["kyiv_current_provenance_certified"] is False
    scenarios = json.loads(negatives.read_text())["scenarios"]
    assert len(scenarios) == 19 and len({s["test"] for s in scenarios}) == 19
    log = unit_log.read_text()
    assert re.search(r"Ran 30 tests in [0-9.]+s\s+OK\s*$", log)
    for scenario in scenarios:
        assert scenario["status"] == "PASS" and scenario["accepted_candidate"] is False
        assert scenario["publication_allowed"] is False and scenario["network_or_sql_attempts"] == 0
        assert re.search(re.escape(scenario["test"]) + r" \([^\n]+\) \.\.\. ok", log)
    return {"status": "PASS", "machine_verdict": "OFFLINE_EXISTING_RESULT_VERIFIED",
            "full_generation_repeated": False, "manifest_hashes_verified": len(manifest),
            "candidate_files": verdict["candidate_files"], "checks": checks,
            "negative_scenarios_verified_from_retained_log": len(scenarios),
            "prior_generation_exit_code": "NOT_RETAINED; NO EXIT CODE INFERRED",
            "original_snapshot_sha256": provenance["snapshot_sha256"],
            "fixture_member_hashes_verified": sum(map(len, provenance["members"].values())),
            "network_or_sql_attempts": 0, "production_publication": "PRODUCTION_PUBLICATION_NOT_AUTHORIZED",
            "physical_readback": "PHYSICAL_NEON_READBACK_NOT_RUN",
            "freshness": "CURRENT_FRESHNESS_NOT_CERTIFIED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "negatives", "unit-log"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.output, args.negatives, args.unit_log), sort_keys=True))


if __name__ == "__main__":
    main()
