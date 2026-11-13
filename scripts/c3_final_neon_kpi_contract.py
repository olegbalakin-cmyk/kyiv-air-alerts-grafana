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



# WORK R: immutable, exact-pair recovery. The legacy C2-preparation path above
# is intentionally unchanged. This is NOT a substitute C2 preparation artifact.
RECOVERY_PINS = {
    "c2_run_id": 43321997695,
    "c2_head_sha": "712c9e351fc3548325cf594cf0617bb33e70a002",
    "c2_input_sha": "6648a11242fac16cf023114cd6e58a65c3b49968",
    "c2_corpus_sha256": "f855be9c2cfb8617903666d0d898c223c6a91ac0fc56029b5b036dc153db84d4",
    "c2_bundle_sha256": "3f53c7ca4a0bc1d0f25cd228dcde003cd45ac247ecab76747405f556f75e8030",
    "c2_artifact_id": 13991878472,
    "c2_artifact_sha256": "2686f1c54e77e630fd7f8c920f4d88d05f6048b68be26f11f5e3fa03745bebde",
    "work_l_run_id": 43390770985,
    "work_l_head_sha": "325669a4441f5cfaeed8327f08032c0ecf4449b9",
    "work_l_artifact_id": 14020616892,
    "work_l_artifact_sha256": "79acb3017dccefdf19def7fe15bdaf2033b27d8c8a6d41f146d7b0e903bd3954",
    "work_m_run_id": 43403595621,
    "work_m_head_sha": "9d846279b91b44b324a722ca00276a99956b4fca",
    "work_m_artifact_id": 14025629654,
    "work_m_artifact_sha256": "f2252da0014ce4ed28d5d52a7164e077b8fcd8c99380dd752ee0650412b051ed",
    "work_m_report_artifact_id": 14025729121,
    "work_m_report_artifact_sha256": "f4f786b168d28f37bdf6a333d4e514b503e402e4fda25553d99ffa0a8d6a8648",
}
RECOVERY_JOBS = {
    "update-site": (131544763676, "success"),
    "c6-neon-six-json-prepare": (131559447936, "failure"),
    "c6-neon-final-prepare-only": (131544766010, "skipped"),
    "c6-neon-owner-gated-git-release": (131544765618, "skipped"),
}
RECOVERY_PROVENANCE = "C2_FAILED_PRERUN_C6_WORKL_PHYSICAL_PROOF_V1"
RECOVERY_REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"


def recovery_json(root, filename):
    return json.loads((root / filename).read_text(encoding="utf-8"))


def validate_recovery_identity(root, env, *, now=None):
    """Owner grant, immutable GitHub metadata, job results and outer ZIPs.

    Requires a new expiring *production* grant. A Work M prepare-only grant
    or a research publication_allowed=false flag can never satisfy it.
    """
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    p = RECOVERY_PINS
    require(env.get("C6_WORK_L_RECOVERY_MODE") == "true" and
            env.get("C6_WORK_L_RECOVERY_ENABLED") == "true" and
            env.get("C6_RELEASE_OWNER_APPROVED") == "true" and
            env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and
            env.get("GITHUB_ACTOR") == "olegbalakin-cmyk" and
            env.get("GITHUB_REPOSITORY") == RECOVERY_REPO,
            "SEPARATE_OWNER_RECOVERY_APPROVAL_REQUIRED")
    try:
        grant = json.loads(env.get("C6_RECOVERY_OWNER_RELEASE_GRANT_JSON", "null"))
    except (ValueError, TypeError):
        raise ValueError("INVALID_RECOVERY_OWNER_GRANT")
    require(isinstance(grant, dict) and
            grant.get("schema") == "c3-work-l-work-m-netlify-release-v1" and
            grant.get("decision") == "APPROVE_EXACT_NEON_NETLIFY_RELEASE" and
            grant.get("repository") == RECOVERY_REPO and
            grant.get("publication_allowed") is True and
            grant.get("dst_correction") == "OFF" and
            grant.get("c2_run_id") == p["c2_run_id"] and
            grant.get("work_l_run_id") == p["work_l_run_id"] and
            grant.get("work_m_run_id") == p["work_m_run_id"] and
            grant.get("final_artifact_id") == p["work_m_artifact_id"] and
            grant.get("final_artifact_sha256") == p["work_m_artifact_sha256"] and
            grant.get("binding_sha256") == env.get("APPROVED_BINDING_SHA") and
            grant.get("kpi_sha256") == env.get("APPROVED_KPI_SHA") and
            grant.get("generation") == env.get("APPROVED_GENERATION"),
            "NEW_EXACT_OWNER_RELEASE_GRANT_REQUIRED")
    expires = utc(grant.get("expires_at"))
    require(now.tzinfo is not None and now <= expires and
            0 <= (expires - now).total_seconds() <= 36 * 3600,
            "OWNER_RELEASE_GRANT_EXPIRED_OR_TOO_LONG")
    for field, pinned in (
        ("C6_RUN_ID", p["c2_run_id"]),
        ("C6_ATTEMPT", 1),
        ("C6_ARTIFACT_ID", p["c2_artifact_id"]),
        ("WORK_A_RUN_ID", p["work_l_run_id"]),
        ("WORK_A_ARTIFACT_ID", p["work_l_artifact_id"]),
        ("FINAL_RUN_ID", p["work_m_run_id"]),
        ("FINAL_ATTEMPT", 1),
        ("FINAL_ARTIFACT_ID", p["work_m_artifact_id"]),
    ):
        require(str(env.get(field)) == str(pinned), "EXACT_RECOVERY_INPUT_CHANGED:" + field)
    for field, pinned in (
        ("C6_ARTIFACT_SHA", p["c2_artifact_sha256"]),
        ("WORK_A_ARTIFACT_SHA", p["work_l_artifact_sha256"]),
        ("FINAL_ARTIFACT_SHA", p["work_m_artifact_sha256"]),
        ("OWNER_FINAL_ARTIFACT_SHA", p["work_m_artifact_sha256"]),
        ("OWNER_WORK_A_ARTIFACT_SHA", p["work_l_artifact_sha256"]),
        ("C6_APPROVED_WORK_A_RUN", str(p["work_l_run_id"])),
        ("C6_APPROVED_FINAL_RUN", str(p["work_m_run_id"])),
        ("C6_APPROVED_FINAL_ATTEMPT", "1"),
        ("C6_APPROVED_FINAL_ARTIFACT_ID", str(p["work_m_artifact_id"])),
        ("C6_APPROVED_FINAL_HEAD_SHA", p["work_m_head_sha"]),
        ("C6_APPROVED_FINAL_WORKFLOW", ".github/workflows/update-netlify-site.yml"),
        ("C6_APPROVED_FINAL_NAME", "c6-neon-final-release-43403595621-1"),
        ("OWNER_BINDING_SHA", env.get("APPROVED_BINDING_SHA")),
    ):
        require(env.get(field) == pinned, "RECOVERY_OWNER_PIN_CHANGED:" + field)
    require(bool(HEX64.fullmatch(str(env.get("APPROVED_BINDING_SHA", "")))) and
            bool(HEX64.fullmatch(str(env.get("APPROVED_KPI_SHA", "")))) and
            bool(env.get("APPROVED_GENERATION")),
            "APPROVED_STATIC_HASH_OR_GENERATION_MISSING")

    runs = (
        ("run.json", "c2", "failure", "main",
         ".github/workflows/update-netlify-site.yml"),
        ("work-a-run.json", "work_l", "success",
         "research-c6-work-l-recover-2026-11-13",
         ".github/workflows/c6-neon-shadow-isolated-proof.yml"),
        ("final-run.json", "work_m", "success",
         "research-c6-work-m-release-recovery-2026-11-13",
         ".github/workflows/update-netlify-site.yml"),
    )
    for file, prefix, conclusion, branch, workflow in runs:
        r = recovery_json(root, file)
        require(r.get("id") == p[prefix + "_run_id"] and
                r.get("run_attempt") == 1 and
                r.get("head_sha") == p[prefix + "_head_sha"] and
                r.get("head_branch") == branch and
                r.get("path") == workflow and
                r.get("event") == "workflow_dispatch" and
                r.get("status") == "completed" and
                r.get("conclusion") == conclusion,
                "RECOVERY_GITHUB_RUN_IDENTITY_CHANGED:" + prefix)
    jobs = recovery_json(root, "c2-jobs.json")
    require(jobs.get("total_count") == 4 and
            isinstance(jobs.get("jobs"), list) and len(jobs["jobs"]) == 4,
            "C2_FOUR_JOBS_REQUIRED")
    by_name = {j.get("name"): j for j in jobs["jobs"]}
    require(set(by_name) == set(RECOVERY_JOBS), "C2_JOB_SET_CHANGED")
    for name, (job_id, status) in RECOVERY_JOBS.items():
        j = by_name[name]
        require(j.get("id") == job_id and
                j.get("run_id") == p["c2_run_id"] and
                j.get("status") == "completed" and
                j.get("conclusion") == status,
                "C2_EXACT_JOB_STATUS_CHANGED:" + name)
    failed = by_name["c6-neon-six-json-prepare"]
    require(failed.get("runner_id") in (None, 0) and
            not failed.get("runner_name") and
            failed.get("steps") in (None, []) and
            failed.get("created_at") == failed.get("started_at") and
            bool(by_name["update-site"].get("steps")) and
            all(by_name[k].get("steps") in (None, []) for k in
                ("c6-neon-final-prepare-only", "c6-neon-owner-gated-git-release")),
            "C2_KNOWN_PRERUN_FAILURE_ONLY")

    artifacts = (
        ("artifact.json", "artifact.zip", "c2",
         "c2-shadow-inputs-43321997695-1"),
        ("work-a-artifact.json", "work-a-artifact.zip", "work_l",
         "isolated-neon-shadow-43390770985-1"),
        ("final-artifact.json", "final-release-artifact.zip", "work_m",
         "c6-neon-final-release-43403595621-1"),
        ("work-m-report-artifact.json", "work-m-report-artifact.zip", "work_m_report",
         "c6-neon-final-prepare-report-43403595621-1"),
    )
    for metadata_file, zip_file, prefix, name in artifacts:
        art = recovery_json(root, metadata_file)
        run_id = p["work_m_run_id"] if prefix == "work_m_report" else p[prefix + "_run_id"]
        require(art.get("id") == p[prefix + "_artifact_id"] and
                art.get("name") == name and
                art.get("workflow_run", {}).get("id") == run_id and
                art.get("expired") is False and
                art.get("digest") == "sha256:" + p[prefix + "_artifact_sha256"] and
                digest((root / zip_file).read_bytes()) == p[prefix + "_artifact_sha256"],
                "RECOVERY_ARTIFACT_CHANGED:" + prefix)
    return grant


def run_recovery(root, environ=None, *, now=None):
    """Physically validate C2 bundle -> Work L original -> Work M final bytes."""
    from io import BytesIO
    env = os.environ if environ is None else environ
    now = now or datetime.now(timezone.utc)
    root = Path(root)
    validate_recovery_identity(root, env, now=now)
    p = RECOVERY_PINS
    c2 = CheckedZip(root / "artifact.zip")  # real C2 bundle, never "prep"
    physical = CheckedZip(root / "work-a-artifact.zip")
    released = CheckedZip(root / "final-release-artifact.zip")
    report_zip = CheckedZip(root / "work-m-report-artifact.zip")
    try:
        require(len(physical.names) == 19 and
                set(released.names) == (
                    {"RELEASE_BINDING.json", "RELEASE_MANIFEST.json"} |
                    {"candidate/" + path for path in SET}) and
                len(released.names) == 8,
                "RECOVERY_FINAL_OR_PHYSICAL_FILE_SET_CHANGED")
        raw_bundle = c2.read("c2-shadow-inputs.zip")
        require(digest(raw_bundle) == p["c2_bundle_sha256"] and
                c2.read("c2-shadow-inputs.zip.sha256").decode("utf-8").strip()
                == p["c2_bundle_sha256"] + "  c2-shadow-inputs.zip",
                "C2_INNER_BUNDLE_OR_SIDECAR_MISMATCH")
        with zipfile.ZipFile(BytesIO(raw_bundle)) as inner:
            require(len(set(inner.namelist())) == len(inner.namelist()) and
                    "receipt.json" in inner.namelist(), "C2_BUNDLE_UNSAFE_OR_INCOMPLETE")
            writer = json_bytes(inner.read("receipt.json"))
        require(writer.get("status") == "succeeded" and
                writer.get("persistence_status") == "persisted" and
                writer.get("canonical_episode_count") == 33315 and
                writer.get("episodes_inserted") == 48 and
                writer.get("episodes_updated") == 0 and
                writer.get("city_count") == 23 and
                writer.get("corpus_sha256") == p["c2_corpus_sha256"] and
                writer.get("input_sha") == p["c2_input_sha"] and
                writer.get("workflow_sha") == p["c2_head_sha"] and
                writer.get("production_output_mutation") is False,
                "C2_PHYSICAL_WRITER_RECEIPT_CHANGED")

        manifest_l = json_bytes(physical.read("sha256_manifest.json"))
        require(manifest_l.get("schema") == "isolated-neon-shadow-proof-v1" and
                set(manifest_l.get("files", {})) == (
                    WORK_A_EVIDENCE | {"candidate/" + n for n in NAMES}),
                "WORK_L_MANIFEST_OR_18_MEMBERS_CHANGED")
        for member, expected in manifest_l["files"].items():
            require(bool(HEX64.fullmatch(str(expected))) and
                    digest(physical.read(member)) == expected,
                    "WORK_L_PHYSICAL_MEMBER_CHANGED:" + member)
        verdict = json_bytes(physical.read("verdict.json"))
        readback = json_bytes(physical.read("readback_proof.json"))
        binding_l = json_bytes(physical.read("historical_freshness_binding.json"))
        freshness = json_bytes(physical.read("historical_freshness_gate.json"))
        source_gates = json_bytes(physical.read("source_gates.json"))
        sources = binding_l.get("sources")
        keys = binding_l.get("city_keys")
        source_files = {PATHS[n]: digest(physical.read("candidate/" + n))
                        for n in NAMES}
        require(verdict.get("status") == "PASS" and
                verdict.get("neon_readback_verified") is True and
                verdict.get("physical_neon_readback_run") is True and
                verdict.get("readback_mode") == "physical" and
                verdict.get("publication_allowed") is False and
                verdict.get("neon_writes") == 0 and
                verdict.get("upstream_http_gets") == 0 and
                verdict.get("production_file_writes") == 0 and
                verdict.get("city_count") == 23 and
                verdict.get("neon_branch") == BRANCH and
                verdict.get("episode_count") == 33315 and
                verdict.get("c2_corpus_sha256") == p["c2_corpus_sha256"] and
                verdict.get("candidate_files") == {
                    name: source_files[PATHS[name]] for name in NAMES},
                "WORK_L_PHYSICAL_READBACK_OR_SIX_FILES_CHANGED")
        identity = readback.get("capture_run_identity", {})
        require(identity.get("github_run_id") == p["c2_run_id"] and
                identity.get("github_run_attempt") == 1 and
                identity.get("workflow_sha") == p["c2_head_sha"] and
                identity.get("input_sha") == p["c2_input_sha"] and
                readback.get("c2_corpus_sha256") == p["c2_corpus_sha256"] and
                readback.get("physical_neon_readback_run") is True and
                readback.get("meta", {}).get("read_only") == "on" and
                readback.get("meta", {}).get("isolation") == "repeatable read" and
                utc(readback.get("meta", {}).get("read_at")) <= now and
                binding_l.get("db_branch") == BRANCH and
                binding_l.get("corpus_sha256") == p["c2_corpus_sha256"] and
                binding_l.get("bundle_sha256") == p["c2_bundle_sha256"] and
                binding_l.get("github_run_id") == p["c2_run_id"] and
                binding_l.get("github_run_attempt") == 1 and
                binding_l.get("input_sha") == p["c2_input_sha"],
                "WORK_L_C2_EXACT_RUN_PROVENANCE_CHANGED")
        require(isinstance(keys, list) and len(keys) == len(set(keys)) == 23 and
                set(keys) == set(sources or {}) == set(source_gates) and
                {"kyiv", "sevastopol"} <= set(keys) and
                freshness.get("status") == "FRESHNESS_READY_FOR_INTEGRATION" and
                freshness.get("publication_allowed") is False and
                freshness.get("freshness_ceiling_hours") == 36.0 and
                all(freshness.get(k) == 23 for k in
                    ("fresh_cities", "full_receipt_cities", "historically_bound_cities")) and
                set(freshness.get("cities", {})) == set(keys),
                "WORK_L_23_CITY_HISTORICAL_FRESHNESS_CHANGED")
        for city in keys:
            row, receipt = freshness["cities"][city], sources[city]
            require(row.get("reasons") == [] and
                    row.get("continuity_verified") is True and
                    row.get("full_receipt_verified") is True and
                    row.get("historical_binding_verified") is True and
                    receipt.get("continuity_verified") is True and
                    source_gates[city].get("full_historical_receipt_verified") is True and
                    0 <= (now - utc(receipt.get("last_checked_at"))).total_seconds()
                         <= 36 * 3600,
                    "WORK_L_HISTORICAL_CITY_STALE_OR_INCOMPLETE:" + city)

        report = json_bytes(report_zip.read("PREPARE_REPORT.json"))
        require(report.get("schema") == "c6-final-release-prepare-report-v1" and
                report.get("status") == "FINAL_BYTES_PREPARED_NOT_PUBLISHED" and
                report.get("provenance_contract") == RECOVERY_PROVENANCE and
                report.get("publication_allowed") is False and
                report.get("production_git_push_executed") is False and
                report.get("netlify_deployed") is False and
                not report.get("source_preparation_artifact_id") and
                not report.get("source_preparation_artifact_sha256") and
                report.get("city_count") == 23 and
                report.get("prepare_run_id") == p["work_m_run_id"] and
                report.get("prepare_run_attempt") == 1 and
                report.get("prepare_code_sha") == p["work_m_head_sha"] and
                report.get("work_a_run_id") == p["work_l_run_id"] and
                report.get("work_a_run_attempt") == 1 and
                report.get("work_a_artifact_id") == p["work_l_artifact_id"] and
                report.get("work_a_artifact_sha256") == p["work_l_artifact_sha256"],
                "WORK_M_REPORT_NOT_EXACT_PREPARE_ONLY")
        for key, expected in (
            ("c2_run_id", p["c2_run_id"]), ("c2_run_attempt", 1),
            ("c2_workflow_sha", p["c2_head_sha"]),
            ("c2_input_sha", p["c2_input_sha"]),
            ("c2_corpus_sha256", p["c2_corpus_sha256"]),
            ("c2_bundle_sha256", p["c2_bundle_sha256"]),
            ("neon_branch", BRANCH),
        ):
            require(report.get(key) == expected, "WORK_M_REPORT_C2_MISMATCH:" + key)

        raw_binding = released.read("RELEASE_BINDING.json")
        binding = json_bytes(raw_binding)
        manifest = json_bytes(released.read("RELEASE_MANIFEST.json"))
        binding_sha = digest(raw_binding)
        approved = json.loads(env.get("OWNER_FINAL_FILES_JSON", "null"))
        require(isinstance(approved, dict) and set(approved) == SET and
                all(isinstance(h, str) and HEX64.fullmatch(h)
                    for h in approved.values()) and
                env.get("APPROVED_KPI_SHA") == approved[ROOT] and
                env.get("APPROVED_BINDING_SHA") == binding_sha and
                binding_sha == env.get("OWNER_BINDING_SHA") and
                binding.get("schema") == "c6-neon-git-release-binding-v1" and
                binding.get("repository") == RECOVERY_REPO and
                manifest.get("schema") == "c6-neon-git-release-manifest-v1" and
                manifest.get("release_manifest_sha256") == binding_sha and
                manifest.get("binding") == binding and
                binding.get("source_files") == source_files and
                manifest.get("source_files") == source_files and
                manifest.get("files") == approved and
                report.get("final_files") == approved and
                report.get("release_binding_sha256") == binding_sha and
                report.get("release_manifest_file_sha256") ==
                    digest(released.read("RELEASE_MANIFEST.json")) and
                report.get("generation") == binding.get("generation") ==
                    env.get("APPROVED_GENERATION") and
                utc(binding.get("generation")) <= now,
                "WORK_M_FINAL_BINDING_SHA_OR_LINEAGE_INVALID")
        for key, expected in (
            ("c2_run_id", p["c2_run_id"]), ("c2_run_attempt", 1),
            ("c2_workflow_sha", p["c2_head_sha"]),
            ("c2_input_sha", p["c2_input_sha"]),
            ("c2_bundle_sha256", p["c2_bundle_sha256"]),
            ("c2_corpus_sha256", p["c2_corpus_sha256"]),
            ("neon_branch", BRANCH),
        ):
            require(binding.get(key) == expected,
                    "WORK_M_RELEASE_SOURCE_MISMATCH:" + key)
        require(binding.get("historical_freshness_binding_sha256") ==
                binding_l.get("binding_sha256") and
                binding.get("release_id") == report.get("release_id") and
                isinstance(binding.get("release_id"), str) and
                bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{7,79}",
                                  binding["release_id"])),
                "WORK_M_SOURCE_BINDING_OR_RELEASE_ID_INVALID")

        final = {name: json_bytes(released.read("candidate/" + path))
                 for name, path in PATHS.items()}
        source = {name: json_bytes(physical.read("candidate/" + name))
                  for name in NAMES}
        for name, path in PATHS.items():
            require(digest(released.read("candidate/" + path)) == approved[path],
                    "WORK_M_FINAL_JSON_BYTES_CHANGED:" + path)
        for name in ("alerts_combined.json", "kyiv_threat_mix.json", "sevastopol_events.json"):
            require(final[name] == source[name] and
                    approved[PATHS[name]] == source_files[PATHS[name]],
                    "WORK_M_AUXILIARY_OR_KYIV_LOSS:" + name)
        source_index, source_dash, source_derived = (
            source[ROOT], source["dashboard_data.json"], source["site_derived.json"])
        auth0 = source_dash.get("meta", {}).get("publication_authority", {})
        require(auth0.get("publication_allowed") is False and
                auth0.get("scope") == "RESEARCH_CANDIDATE_NOT_CURRENT_DATA_CERTIFICATION" and
                auth0.get("branch_id") == BRANCH and
                auth0.get("historical_freshness", {}).get("binding_sha256") ==
                    binding["historical_freshness_binding_sha256"] and
                auth0.get("dst_simulation") is False and
                auth0.get("source_fallback") is False and
                auth0.get("active_status") == "UNKNOWN_UNCERTIFIED" and
                source_derived.get("meta", {}).get("publication_authority") == auth0,
                "WORK_L_RESEARCH_AUTHORITY_MUTATED")
        auth = copy.deepcopy(auth0)
        auth.update({"publication_allowed": True, "scope": "PRODUCTION_NEON_GIT_RELEASE",
                     "delivery": "site-prod-git", "release_manifest_sha256": binding_sha})
        index = copy.deepcopy(source_index)
        index["meta"].update({
            "release_manifest_sha256": binding_sha,
            "verified_cities": source_dash["multicity_meta"]["production_city_keys"]})
        dash = copy.deepcopy(source_dash)
        dash["historical_daily_kpi"] = index
        dash["meta"]["publication_authority"] = auth
        derived = copy.deepcopy(source_derived)
        derived["meta"]["publication_authority"] = auth
        require(final[ROOT] == index and
                final["dashboard_data.json"] == dash and
                final["site_derived.json"] == derived,
                "WORK_M_NOT_EXACT_FINAL_RELEASE_TRANSFORMATION")
        cities = dash["multicity_meta"]["production_city_keys"]
        require(isinstance(cities, list) and len(cities) == len(set(cities)) == 23 and
                set(cities) == set(keys) == set(index.get("cities", {})) and
                all(index["cities"][c].get("status") == "verified" for c in cities) and
                index.get("schema") == "verified-historical-daily-start-counts-v1" and
                index["meta"].get("source_ref") == "neon:" + BRANCH and
                index["meta"].get("verified_count") == 23 and
                index["meta"].get("expected_cities") == 23 and
                index["meta"].get("source_dashboard_generated_at") ==
                    dash["meta"].get("generated_at") == env["APPROVED_GENERATION"] and
                set(dash.get("cities", {})) == set(cities),
                "WORK_M_FINAL_23_CITY_KPI_MISMATCH")
        # No production writes here: the separate Netlify step remains gated.
        target = root.parent / ROOT
        target.write_bytes(released.read("candidate/" + ROOT))
        require(digest(target.read_bytes()) == env["APPROVED_KPI_SHA"],
                "RECOVERY_KPI_OUTPUT_SHA_MISMATCH")
        print("EXACT_WORK_L_TO_WORK_M_NETLIFY_KPI_PASS; 23_CITIES; SIX_JSON; OWNER_GRANT")
        return final
    finally:
        c2.close()
        physical.close()
        released.close()
        report_zip.close()


if __name__ == "__main__":
    try:
        target = sys.argv[1] if len(sys.argv) > 1 else "_approved_c6"
        if os.environ.get("C6_WORK_L_RECOVERY_MODE") == "true":
            run_recovery(target)
        else:
            run(target)
    except Exception as exc:
        print("FINAL_NEON_KPI_RELEASE_CONTRACT_BLOCKED:" + str(exc), file=sys.stderr)
        raise SystemExit(2)
