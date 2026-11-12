#!/usr/bin/env python3
"""Deterministic, isolated C6 release binding; no Git, HTTP, or Neon access.

The research six JSON and Work A proof must remain immutable. Only the
separately gated one-shot publisher may consume the final release tree.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import tempfile
from pathlib import Path

from scripts import c6_neon_git_candidate as candidate

HEX64 = re.compile(r"^[a-f0-9]{64}$")
RELEASE_SCOPE = "PRODUCTION_NEON_GIT_RELEASE"
RELEASE_DELIVERY = "site-prod-git"


def require(ok, reason):
    if not ok:
        raise candidate.Blocked(reason)


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def release_candidate(prepared, report, *, repository, release_id, output):
    """Build exactly six final JSON; manifest binding does NOT hash final JSON.

    Final SHA values are recorded only in the separate RELEASE_MANIFEST.json.
    They must later be matched to independent owner-approval SHA values.
    """
    prepared, output = Path(prepared).resolve(), Path(output).resolve()
    require(not output.exists() and not output.is_relative_to(prepared)
            and not prepared.is_relative_to(output), "RELEASE_OUTPUT_NOT_ISOLATED")
    require(isinstance(release_id, str) and
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,79}", release_id),
            "RELEASE_ID_INVALID")
    require(report.get("state") == candidate.STATE
            and report.get("publication_allowed") is False
            and report.get("production_git_push_executed") is False
            and report.get("prepared_files") == 6, "RESEARCH_REPORT_NOT_FROZEN")
    source = prepared / "candidate"
    source_hashes = report.get("files")
    require(isinstance(source_hashes, dict) and
            set(source_hashes) == set(candidate.FILES.values()),
            "RESEARCH_FILE_SET_INVALID")
    for path, digest in source_hashes.items():
        p = source / path
        require(p.is_file() and not p.is_symlink() and
                HEX64.fullmatch(str(digest)) and
                candidate.sha(p.read_bytes()) == digest,
                "RESEARCH_FILE_SHA_MISMATCH")
    dashboard = load(source / candidate.FILES["dashboard_data.json"])
    index = load(source / candidate.FILES["historical-daily-kpi.json"])
    derived = load(source / candidate.FILES["site_derived.json"])
    original = dashboard.get("meta", {}).get("publication_authority", {})
    generation = dashboard.get("meta", {}).get("generated_at")
    freshness = original.get("historical_freshness", {}).get("binding_sha256")
    cities = dashboard.get("multicity_meta", {}).get("production_city_keys")
    require(original.get("publication_allowed") is False and
            original.get("scope") == "RESEARCH_CANDIDATE_NOT_CURRENT_DATA_CERTIFICATION"
            and original.get("branch_id") == report.get("neon_branch") and
            original.get("dst_simulation") is False and
            original.get("source_fallback") is False and
            original.get("active_status") == "UNKNOWN_UNCERTIFIED" and
            derived.get("meta", {}).get("publication_authority") == original,
            "RESEARCH_AUTHORITY_MISMATCH")
    require(HEX64.fullmatch(str(freshness)) and
            isinstance(generation, str) and generation and
            isinstance(cities, list) and len(cities) == len(set(cities)) == 23 and
            isinstance(index.get("cities"), dict) and
            set(index["cities"]) == set(cities) and
            all(index["cities"][city].get("status") == "verified" for city in cities) and
            index.get("schema") == "verified-historical-daily-start-counts-v1" and
            index.get("meta", {}).get("source_ref") == "neon:" + report["neon_branch"] and
            index["meta"].get("verified_count") == 23 and
            index["meta"].get("expected_cities") == 23 and
            index["meta"].get("source_dashboard_generated_at") == generation and
            dashboard.get("historical_daily_kpi") == index,
            "RESEARCH_INDEX_NOT_COMPATIBLE")
    binding = {
        "schema": "c6-neon-git-release-binding-v1",
        "repository": repository, "release_id": release_id,
        "c2_run_id": report["c2_run_id"],
        "c2_run_attempt": report["c2_run_attempt"],
        "c2_workflow_sha": report["c2_workflow_sha"],
        "c2_input_sha": report["c2_input_sha"],
        "c2_bundle_sha256": report["c2_bundle_sha256"],
        "c2_corpus_sha256": report["c2_corpus_sha256"],
        "neon_branch": report["neon_branch"],
        "source_files": source_hashes,
        "generation": generation,
        "historical_freshness_binding_sha256": freshness,
    }
    binding_bytes = json.dumps(
        binding, sort_keys=True, ensure_ascii=False,
        separators=(",", ":")).encode("utf-8")
    binding_hash = candidate.sha(binding_bytes)
    authority = copy.deepcopy(original)
    authority.update({
        "publication_allowed": True, "scope": RELEASE_SCOPE,
        "delivery": RELEASE_DELIVERY,
        "release_manifest_sha256": binding_hash,
    })
    index = copy.deepcopy(index)
    index["meta"]["release_manifest_sha256"] = binding_hash
    index["meta"]["verified_cities"] = list(cities)
    dashboard["historical_daily_kpi"] = index
    dashboard["meta"]["publication_authority"] = authority
    derived["meta"]["publication_authority"] = copy.deepcopy(authority)
    modified = {
        candidate.FILES["dashboard_data.json"]: dashboard,
        candidate.FILES["site_derived.json"]: derived,
        candidate.FILES["historical-daily-kpi.json"]: index,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c6-git-release-", dir=output.parent) as d:
        tmp = Path(d)
        final = tmp / "candidate"
        files = {}
        for path in candidate.FILES.values():
            dest = final / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            if path in modified:
                dest.write_text(json.dumps(modified[path], ensure_ascii=False,
                    sort_keys=True, indent=2) + "\n", encoding="utf-8")
            else:
                shutil.copyfile(source / path, dest)
            files[path] = candidate.sha(dest.read_bytes())
        manifest = {
            "schema": "c6-neon-git-release-manifest-v1",
            "binding": binding, "release_manifest_sha256": binding_hash,
            "source_files": source_hashes, "files": files,
        }
        # Exact file whose SHA-256 is embedded in the dashboard and KPI.
        # Final file hashes are stored in the adjacent release receipt instead,
        # avoiding a circular hash dependency.
        (tmp / "RELEASE_BINDING.json").write_bytes(binding_bytes)
        (tmp / "RELEASE_MANIFEST.json").write_text(json.dumps(
            manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8")
        shutil.move(str(tmp), str(output))
    return {"files": files, "source_files": source_hashes,
            "release_manifest_sha256": binding_hash, "generation": generation}


def verify_final(approval, final):
    """Require owner-pinned FINAL SHA values, not the Work A research SHA values."""
    files = approval.get("final_files")
    require(isinstance(files, dict) and set(files) == set(candidate.FILES.values())
            and all(HEX64.fullmatch(str(h)) for h in files.values())
            and files == final["files"], "FINAL_SIX_SHA_NOT_APPROVED")
    require(approval.get("release_manifest_sha256") ==
            final["release_manifest_sha256"] and
            approval.get("approved_generation") == final["generation"] and
            approval.get("approved_netlify_static_kpi_sha256") ==
                final["files"]["historical-daily-kpi.json"],
            "FINAL_MANIFEST_OR_NETLIFY_KPI_MISMATCH")
    return {"files": files, "release_manifest_sha256":
            final["release_manifest_sha256"]}
