#!/usr/bin/env python3
"""Fail-closed C3 verification of PR95's *final* authorized six-JSON release.

Reads immutable, pinned artifacts only. Does not make a publication decision,
call Git/Netlify/Neon, or mutate the original Work A/research artifacts.
The owner-approved exact final SHA values must come from outside the ZIP.
"""
import copy
import hashlib
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = "historical-daily-kpi.json"
DATA = "kyiv-air-alerts-grafana/data/"
NAMES = ("dashboard_data.json", "site_derived.json", "alerts_combined.json",
         "kyiv_threat_mix.json", "sevastopol_events.json", ROOT)
PATHS = {n: ROOT if n == ROOT else DATA + n for n in NAMES}
SET = set(PATHS.values())
BRANCH = "br-bold-mode-b5rub8pq"
HEX64 = re.compile(r"^[a-f0-9]{64}$")
HEX40 = re.compile(r"^[a-f0-9]{40}$")
WORK_A_EVIDENCE = {
    "active_rows_unmodified.json", "canonical_selection.json", "git_dependencies.json",
    "historical_freshness_binding.json", "historical_freshness_gate.json",
    "historical_source_receipts.json", "kyiv_selection.json", "projection_lineage.json",
    "readback_proof.json", "source_gates.json", "utc_union_diagnostics.json", "verdict.json",
}


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(raw):
    return json.loads(raw.decode("utf-8"))


def utc(value):
    require(isinstance(value, str), "INVALID_TIMESTAMP")
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(t.tzinfo is not None, "INVALID_TIMESTAMP")
    return t.astimezone(timezone.utc)


class CheckedZip:
    """Reject duplicate/traversal members, and retrieve by unambiguous suffix."""
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        members = [i for i in self.z.infolist() if not i.is_dir()]
        self.names = [i.filename for i in members]
        require(len(set(self.names)) == len(self.names), "DUPLICATE_ZIP_MEMBER")
        for i in members:
            p = i.filename.split("/")
            require(i.filename and not i.filename.startswith("/") and
                    ".." not in p and "" not in p and
                    ((i.external_attr >> 16) & 0o170000) != 0o120000,
                    "UNSAFE_ZIP_MEMBER")

    def read(self, suffix):
        matches = [n for n in self.names if n == suffix or n.endswith("/" + suffix)]
        require(len(matches) == 1, "MISSING_OR_AMBIGUOUS_MEMBER:" + suffix)
        return self.z.read(matches[0])

    def close(self):
        self.z.close()


def run(root, environ=None, *, now=None):
    env = os.environ if environ is None else environ
    now = now or datetime.now(timezone.utc)
    require(now.tzinfo is not None, "CLOCK_NAIVE")
    root = Path(root)
    original = CheckedZip(root / "artifact.zip")
    physical = CheckedZip(root / "work-a-artifact.zip")
    released = CheckedZip(root / "final-release-artifact.zip")
    try:
        require(len(released.names) == 8 and len(physical.names) == 19,
                "FINAL_OR_ORIGINAL_PROOF_FILE_SET_CHANGED")
        # External owner gate: the final ZIP and every final file hash must be
        # approved independently of the release generator's self-declared manifest.
        require(env.get("C6_RELEASE_OWNER_APPROVED") == "true",
                "OWNER_APPROVAL_REQUIRED")
        require(env.get("FINAL_ARTIFACT_SHA") == env.get("OWNER_FINAL_ARTIFACT_SHA") and
                HEX64.fullmatch(env.get("FINAL_ARTIFACT_SHA", "")),
                "FINAL_ARTIFACT_NOT_OWNER_PINNED")
        require(digest((root / "final-release-artifact.zip").read_bytes()) ==
                env["FINAL_ARTIFACT_SHA"], "FINAL_ZIP_SHA_MISMATCH")
        require(env.get("WORK_A_ARTIFACT_SHA") == env.get("OWNER_WORK_A_ARTIFACT_SHA") and
                HEX64.fullmatch(env.get("WORK_A_ARTIFACT_SHA", "")),
                "WORK_A_NOT_OWNER_PINNED")
        require(digest((root / "work-a-artifact.zip").read_bytes()) ==
                env["WORK_A_ARTIFACT_SHA"], "WORK_A_ZIP_SHA_MISMATCH")
        require(digest((root / "artifact.zip").read_bytes()) ==
                env.get("C6_ARTIFACT_SHA"), "RESEARCH_ZIP_SHA_MISMATCH")
        approved = json.loads(env.get("OWNER_FINAL_FILES_JSON", "null"))
        require(isinstance(approved, dict) and set(approved) == SET and
                all(isinstance(v, str) and HEX64.fullmatch(v)
                    for v in approved.values()), "SIX_FINAL_SHAS_NOT_OWNER_PINNED")
        require(env.get("APPROVED_KPI_SHA") == approved[ROOT],
                "OWNER_STATIC_KPI_SHA_MISMATCH")
        require(HEX64.fullmatch(env.get("APPROVED_BINDING_SHA", "")) and
                env["APPROVED_BINDING_SHA"] == env.get("OWNER_BINDING_SHA"),
                "RELEASE_BINDING_NOT_OWNER_PINNED")
        require(utc(env.get("APPROVED_GENERATION")) <= now,
                "GENERATION_IN_FUTURE")

        report = json_bytes(original.read("REPORT.json"))
        source_files = report.get("files")
        require(report.get("state") == "INTEGRATION_PREPARED_PUBLICATION_OFF"
                and report.get("publication_allowed") is False
                and report.get("production_git_push_executed") is False
                and report.get("prepared_files") == 6
                and isinstance(source_files, dict)
                and set(source_files) == SET,
                "ORIGINAL_RESEARCH_NOT_FROZEN")
        require(report.get("neon_branch") == BRANCH, "RESEARCH_BRANCH_CHANGED")
        for path in SET:
            require(HEX64.fullmatch(str(source_files[path])) and
                    digest(original.read("candidate/" + path)) == source_files[path],
                    "RESEARCH_SIX_SHA_MISMATCH:" + path)

        # All 18 Work A evidence files must still match their immutable SHA list,
        # and its candidate SHA list is the *original* six, NOT the final six.
        work_manifest = json_bytes(physical.read("sha256_manifest.json"))
        expected_proof = WORK_A_EVIDENCE | {"candidate/" + n for n in NAMES}
        require(work_manifest.get("schema") == "isolated-neon-shadow-proof-v1"
                and set(work_manifest.get("files", {})) == expected_proof,
                "WORK_A_MANIFEST_INVALID")
        for name, value in work_manifest["files"].items():
            require(HEX64.fullmatch(str(value)) and
                    digest(physical.read(name)) == value,
                    "WORK_A_PROOF_SHA_MISMATCH:" + name)
        verdict = json_bytes(physical.read("verdict.json"))
        readback = json_bytes(physical.read("readback_proof.json"))
        original_binding = json_bytes(physical.read("historical_freshness_binding.json"))
        freshness = json_bytes(physical.read("historical_freshness_gate.json"))
        source_gates = json_bytes(physical.read("source_gates.json"))
        expected_original = {n: source_files[PATHS[n]] for n in NAMES}
        require(verdict.get("status") == "PASS"
                and verdict.get("frontend_compatible") is True
                and verdict.get("neon_readback_verified") is True
                and verdict.get("physical_neon_readback_run") is True
                and verdict.get("physical_readback_verdict") == "PHYSICAL_NEON_READBACK_RUN"
                and verdict.get("generation_verdict") == "PHYSICAL_GENERATION_PASS"
                and verdict.get("readback_mode") == "physical"
                and verdict.get("publication_allowed") is False
                and verdict.get("production_publication") == "PRODUCTION_PUBLICATION_NOT_AUTHORIZED"
                and verdict.get("neon_writes") == 0
                and verdict.get("upstream_http_gets") == 0
                and verdict.get("production_file_writes") == 0
                and verdict.get("city_count") == 23
                and verdict.get("neon_branch") == BRANCH
                and verdict.get("candidate_files") == expected_original,
                "WORK_A_NOT_IMMUTABLE_PHYSICAL_PROOF")
        capture = readback.get("capture_run_identity", {})
        require(capture.get("github_run_id") == int(env["C6_RUN_ID"])
                and capture.get("github_run_attempt") == int(env["C6_ATTEMPT"])
                and capture.get("workflow_sha") == report.get("c2_workflow_sha")
                and capture.get("input_sha") == report.get("c2_input_sha")
                and report.get("c2_run_id") == capture.get("github_run_id")
                and report.get("c2_run_attempt") == capture.get("github_run_attempt")
                and readback.get("c2_corpus_sha256") == report.get("c2_corpus_sha256")
                and verdict.get("c2_corpus_sha256") == report.get("c2_corpus_sha256")
                and original_binding.get("corpus_sha256") == report.get("c2_corpus_sha256")
                and original_binding.get("db_branch") == BRANCH
                and original_binding.get("input_sha") == report.get("c2_input_sha")
                and original_binding.get("readback") == readback
                and original_binding.get("publication_allowed") is False,
                "WORK_A_C2_RUN_ATTEMPT_OR_CORPUS_MISMATCH")
        identity = json_bytes((root / "run.json").read_bytes())
        require(identity.get("id") == capture["github_run_id"]
                and identity.get("run_attempt") == capture["github_run_attempt"]
                and identity.get("head_sha") == capture["workflow_sha"],
                "C2_GITHUB_IDENTITY_MISMATCH")
        keys = original_binding.get("city_keys")
        sources = original_binding.get("sources")
        require(isinstance(keys, list) and len(keys) == len(set(keys)) == 23 and
                set(keys) == set(sources or {}) == set(source_gates) and
                {"kyiv", "sevastopol"} <= set(keys), "ORIGINAL_23_CITIES_MISSING")
        require(freshness.get("status") == "FRESHNESS_READY_FOR_INTEGRATION"
                and freshness.get("publication_allowed") is False
                and all(freshness.get(k) == 23 for k in
                        ("fresh_cities", "full_receipt_cities", "historically_bound_cities"))
                and freshness.get("freshness_ceiling_hours") == 36.0
                and set(freshness.get("cities", {})) == set(keys),
                "HISTORICAL_FRESHNESS_NOT_READY")
        require(readback.get("physical_neon_readback_run") is True
                and readback.get("meta", {}).get("read_only") == "on"
                and readback.get("meta", {}).get("isolation") == "repeatable read"
                and now >= utc(readback.get("meta", {}).get("read_at")),
                "WORK_A_PHYSICAL_READBACK_INVALID")
        for city in keys:
            row, receipt = freshness["cities"][city], sources[city]
            require(row.get("reasons") == [] and row.get("continuity_verified") is True
                    and row.get("full_receipt_verified") is True
                    and row.get("historical_binding_verified") is True
                    and receipt.get("continuity_verified") is True
                    and source_gates[city].get("full_historical_receipt_verified") is True,
                    "HISTORICAL_RECEIPT_UNVERIFIED:" + city)
            age = (now - utc(receipt.get("last_checked_at"))).total_seconds()
            require(0 <= age <= 36 * 3600, "HISTORICAL_SOURCE_STALE:" + city)

        # Match the final PR95 binding and manifest independently of Work A.
        raw_binding = released.read("RELEASE_BINDING.json")
        binding = json_bytes(raw_binding)
        manifest = json_bytes(released.read("RELEASE_MANIFEST.json"))
        binding_sha = digest(raw_binding)  # PR95 calls this release_manifest_sha256.
        require(binding_sha == env["APPROVED_BINDING_SHA"]
                and binding.get("schema") == "c6-neon-git-release-binding-v1"
                and manifest.get("schema") == "c6-neon-git-release-manifest-v1"
                and manifest.get("release_manifest_sha256") == binding_sha
                and manifest.get("binding") == binding
                and manifest.get("source_files") == source_files
                and manifest.get("files") == approved
                and binding.get("source_files") == source_files
                and binding.get("repository") == env.get("GITHUB_REPOSITORY")
                and isinstance(binding.get("release_id"), str)
                and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,79}",
                                 binding["release_id"]),
                "FINAL_BINDING_OR_MANIFEST_MISMATCH")
        for key in ("c2_run_id", "c2_run_attempt", "c2_workflow_sha",
                    "c2_input_sha", "c2_bundle_sha256", "c2_corpus_sha256",
                    "neon_branch"):
            require(binding.get(key) == report.get(key),
                    "FINAL_RESEARCH_LINEAGE_MISMATCH:" + key)
        require(HEX40.fullmatch(str(binding["c2_workflow_sha"]))
                and HEX40.fullmatch(str(binding["c2_input_sha"]))
                and HEX64.fullmatch(str(binding["c2_bundle_sha256"]))
                and HEX64.fullmatch(str(binding["c2_corpus_sha256"]))
                and binding.get("generation") == env["APPROVED_GENERATION"]
                and binding.get("historical_freshness_binding_sha256") ==
                    original_binding.get("binding_sha256"),
                "FINAL_SOURCE_OR_GENERATION_MISMATCH")
        # Verify all six final bytes (including the distinct authorized KPI).
        final = {}
        for name, path in PATHS.items():
            raw = released.read("candidate/" + path)
            require(digest(raw) == approved[path], "FINAL_SIX_SHA_MISMATCH:" + path)
            final[name] = json_bytes(raw)
        original_json = {n: json_bytes(original.read("candidate/" + p))
                         for n, p in PATHS.items()}
        for n in ("alerts_combined.json", "kyiv_threat_mix.json", "sevastopol_events.json"):
            require(final[n] == original_json[n] and approved[PATHS[n]] == source_files[PATHS[n]],
                    "UNCHANGED_AUXILIARY_OR_KYIV_BYTES_MISMATCH:" + n)
        source_index = original_json[ROOT]
        source_dash = original_json["dashboard_data.json"]
        source_derived = original_json["site_derived.json"]
        auth0 = source_dash.get("meta", {}).get("publication_authority", {})
        require(auth0.get("publication_allowed") is False
                and auth0.get("scope") == "RESEARCH_CANDIDATE_NOT_CURRENT_DATA_CERTIFICATION"
                and auth0.get("branch_id") == BRANCH
                and auth0.get("historical_freshness", {}).get("binding_sha256") ==
                    binding["historical_freshness_binding_sha256"]
                and auth0.get("dst_simulation") is False
                and auth0.get("source_fallback") is False
                and auth0.get("active_status") == "UNKNOWN_UNCERTIFIED"
                and source_derived.get("meta", {}).get("publication_authority") == auth0,
                "RESEARCH_AUTHORITY_WAS_MUTATED")
        auth = copy.deepcopy(auth0)
        auth.update({"publication_allowed": True, "scope": "PRODUCTION_NEON_GIT_RELEASE",
                     "delivery": "site-prod-git", "release_manifest_sha256": binding_sha})
        index = copy.deepcopy(source_index)
        index["meta"].update({"release_manifest_sha256": binding_sha,
                              "verified_cities": source_dash["multicity_meta"]["production_city_keys"]})
        dash = copy.deepcopy(source_dash)
        dash["historical_daily_kpi"] = index
        dash["meta"]["publication_authority"] = auth
        derived = copy.deepcopy(source_derived)
        derived["meta"]["publication_authority"] = auth
        require(final[ROOT] == index
                and final["dashboard_data.json"] == dash
                and final["site_derived.json"] == derived,
                "FINAL_NOT_EXACT_PR95_RELEASE_TRANSFORMATION")
        city_keys = dash["multicity_meta"]["production_city_keys"]
        require(index.get("schema") == "verified-historical-daily-start-counts-v1"
                and isinstance(city_keys, list)
                and len(city_keys) == len(set(city_keys)) == 23
                and set(city_keys) == set(keys)
                and set(index.get("cities", {})) == set(city_keys)
                and all(index["cities"][k].get("status") == "verified" for k in city_keys)
                and index["meta"].get("source_ref") == "neon:" + BRANCH
                and index["meta"].get("source_dashboard_generated_at") ==
                    dash["meta"].get("generated_at") == env["APPROVED_GENERATION"]
                and index["meta"].get("expected_cities") == 23
                and index["meta"].get("verified_count") == 23
                and set(dash.get("cities", {})) == set(city_keys),
                "FRONTEND_NEON_KPI_CONTRACT_MISMATCH")
        # Do not place an unauthorized or an unmatched KPI in Netlify's root.
        final_raw = released.read("candidate/" + ROOT)
        (root.parent / ROOT).write_bytes(final_raw)
        require((root.parent / ROOT).read_bytes() == final_raw and
                digest(final_raw) == env["APPROVED_KPI_SHA"],
                "ROOT_KPI_NOT_BYTE_IDENTICAL")
        print("FINAL_PR95_BINDING_TO_NETLIFY_KPI_PASS; SIX_FINAL_SHA_PASS; WORK_A_ORIGINAL_IMMUTABLE")
        return final
    finally:
        original.close()
        physical.close()
        released.close()


if __name__ == "__main__":
    try:
        run(sys.argv[1] if len(sys.argv) > 1 else "_approved_c6")
    except Exception as exc:
        print("FINAL_NEON_KPI_RELEASE_CONTRACT_BLOCKED:" + str(exc), file=sys.stderr)
        raise SystemExit(2)
