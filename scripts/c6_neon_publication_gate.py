#!/usr/bin/env python3
"""Read-only, fail-closed preflight for physical C6 six-JSON evidence.

This script has NO Git push, publication, database, or source network path.
A passing research proof is NEVER a production publication authorization.
"""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

FILES = {"dashboard_data.json", "site_derived.json", "alerts_combined.json",
         "historical-daily-kpi.json", "kyiv_threat_mix.json", "sevastopol_events.json"}
EVIDENCE = {"active_rows_unmodified.json", "canonical_selection.json",
            "git_dependencies.json", "historical_freshness_binding.json",
            "historical_freshness_gate.json", "historical_source_receipts.json",
            "kyiv_selection.json", "projection_lineage.json", "readback_proof.json",
            "source_gates.json", "utc_union_diagnostics.json", "verdict.json"}
SHA = re.compile(r"^[a-f0-9]{64}$")


class Blocked(ValueError):
    pass


def require(value, reason):
    if not value:
        raise Blocked(reason)


def load(root, name):
    return json.loads((root / name).read_text(encoding="utf-8"))


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def utc(value):
    try:
        t = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        require(t.tzinfo is not None, "NAIVE_TIMESTAMP")
        return t.astimezone(timezone.utc)
    except (ValueError, TypeError) as exc:
        raise Blocked("INVALID_TIMESTAMP") from exc


def inspect(root, *, as_of):
    root = Path(root).resolve()
    require(root.is_dir(), "PROOF_DIR_MISSING")
    require(as_of.tzinfo is not None, "EVALUATION_TIME_NAIVE")
    names = EVIDENCE | {"candidate/" + n for n in FILES}
    observed = set()
    for item in root.rglob("*"):
        require(not item.is_symlink(), "SYMLINK_UNSAFE")
        if item.is_file():
            observed.add(item.relative_to(root).as_posix())
    require(observed == names | {"sha256_manifest.json"}, "PROOF_FILE_SET_CHANGED")
    manifest = load(root, "sha256_manifest.json")
    hashes = manifest.get("files")
    require(manifest.get("schema") == "isolated-neon-shadow-proof-v1"
            and isinstance(hashes, dict) and set(hashes) == names,
            "PROOF_MANIFEST_INVALID")
    for name in sorted(names):
        require(SHA.fullmatch(str(hashes[name])) and
                digest((root / name).read_bytes()) == hashes[name],
                "PROOF_SHA_MISMATCH")
    v = load(root, "verdict.json")
    require(v.get("status") == "PASS" and v.get("frontend_compatible") is True
            and v.get("neon_readback_verified") is True
            and v.get("physical_neon_readback_run") is True
            and v.get("physical_readback_verdict") == "PHYSICAL_NEON_READBACK_RUN"
            and v.get("generation_verdict") == "PHYSICAL_GENERATION_PASS"
            and v.get("readback_mode") == "physical", "PHYSICAL_C6_PROOF_REQUIRED")
    require(v.get("neon_writes") == 0 and v.get("upstream_http_gets") == 0
            and v.get("production_file_writes") == 0, "UNEXPECTED_PROOF_SIDE_EFFECTS")
    require(v.get("city_count") == 23 and type(v.get("episode_count")) is int
            and v["episode_count"] > 0 and SHA.fullmatch(str(v.get("c2_corpus_sha256"))),
            "C2_CORPUS_INCOMPLETE")
    actual = v.get("candidate_files")
    require(isinstance(actual, dict) and set(actual) == FILES and
            all(actual[n] == hashes["candidate/" + n] for n in FILES),
            "CANDIDATE_SHA_NOT_BOUND")

    binding = load(root, "historical_freshness_binding.json")
    freshness = load(root, "historical_freshness_gate.json")
    readback = load(root, "readback_proof.json")
    source_gates = load(root, "source_gates.json")
    require(binding.get("schema") == "c6-historical-freshness-v1"
            and binding.get("publication_allowed") is False
            and binding.get("readback") == readback
            and readback.get("physical_neon_readback_run") is True
            and readback.get("meta", {}).get("read_only") == "on"
            and readback.get("meta", {}).get("isolation") == "repeatable read"
            and binding.get("corpus_sha256") == v["c2_corpus_sha256"]
            and readback.get("c2_corpus_sha256") == v["c2_corpus_sha256"]
            and binding.get("db_branch") == v.get("neon_branch"),
            "READBACK_BINDING_MISMATCH")
    keys = binding.get("city_keys")
    require(isinstance(keys, list) and len(keys) == len(set(keys)) == 23
            and {"kyiv", "sevastopol"} <= set(keys)
            and set(binding.get("sources", {})) == set(keys)
            and set(source_gates) == set(keys),
            "HISTORICAL_RECEIPT_CITY_SET_MISSING")
    require(freshness.get("status") == "FRESHNESS_READY_FOR_INTEGRATION"
            and freshness.get("publication_allowed") is False
            and all(freshness.get(k) == 23 for k in
                    ("fresh_cities", "full_receipt_cities", "historically_bound_cities"))
            and freshness.get("freshness_ceiling_hours") == 36.0
            and set(freshness.get("cities", {})) == set(keys),
            "HISTORICAL_FRESHNESS_NOT_READY")
    moment = utc(as_of)
    require(moment >= utc(readback.get("meta", {}).get("read_at")),
            "EVALUATION_BEFORE_READBACK")
    for city in keys:
        row = freshness["cities"][city]
        receipt = binding["sources"][city]
        check = source_gates[city]
        require(row.get("reasons") == [] and row.get("continuity_verified") is True
                and row.get("full_receipt_verified") is True
                and row.get("historical_binding_verified") is True
                and receipt.get("continuity_verified") is True
                and check.get("full_historical_receipt_verified") is True,
                "SOURCE_CONTINUITY_NOT_VERIFIED")
        age = (moment - utc(receipt.get("last_checked_at"))).total_seconds()
        require(0 <= age <= 36 * 3600, "HISTORICAL_SOURCE_STALE_AT_USE")

    dash = load(root, "candidate/dashboard_data.json")
    index = load(root, "candidate/historical-daily-kpi.json")
    derived = load(root, "candidate/site_derived.json")
    require(set(dash.get("cities", {})) == set(keys)
            and set(dash.get("multicity_meta", {}).get("production_city_keys", []))
                == set(keys) and dash.get("historical_daily_kpi") == index,
            "CITY_OR_KPI_INDEX_MISMATCH")
    require(index.get("meta", {}).get("verified_count") == 23
            and index["meta"].get("expected_cities") == 23
            and index["meta"].get("source_dashboard_generated_at")
                == dash.get("meta", {}).get("generated_at")
            and index["meta"].get("source_ref") == "neon:" + v["neon_branch"],
            "INDEX_GENERATION_MISMATCH")
    require("casualties" in dash and "casualties_by_city" in dash
            and isinstance(load(root, "candidate/alerts_combined.json"), list),
            "KYIV_OR_CASUALTY_FIELDS_MISSING")
    authority = dash.get("meta", {}).get("publication_authority", {})
    require(authority.get("branch_id") == v["neon_branch"]
            and authority.get("historical_freshness", {}).get("binding_sha256")
                == binding.get("binding_sha256")
            and authority.get("dst_simulation") is False
            and authority.get("source_fallback") is False
            and authority.get("active_status") == "UNKNOWN_UNCERTIFIED"
            and derived.get("meta", {}).get("publication_authority") == authority
            and all(dash["cities"][c]["meta"].get("current_source_verified") is False
                    for c in keys), "UNVERIFIED_CURRENT_SOURCE_OR_DST")
    deps = load(root, "git_dependencies.json")
    aux = v.get("git_auxiliaries", {})
    require(isinstance(deps, list) and
            set(aux) == {"kyiv_threat_mix.json", "sevastopol_events.json"},
            "AUXILIARY_SET_MISMATCH")
    for name in aux:
        require(aux[name] == actual[name]
                and any(d.get("path") == name and d.get("sha256") == actual[name]
                        and d.get("site_input_sha") == binding.get("input_sha") for d in deps),
                "AUXILIARY_PROVENANCE_MISMATCH")
    # Absolute no-publish safety boundary; future authority needs a separate design.
    require(v.get("publication_allowed") is False
            and freshness.get("publication_allowed") is False
            and authority.get("publication_allowed") is False
            and authority.get("scope") == "RESEARCH_CANDIDATE_NOT_CURRENT_DATA_CERTIFICATION"
            and v.get("production_publication") == "PRODUCTION_PUBLICATION_NOT_AUTHORIZED",
            "RESEARCH_AUTHORITY_NOT_RECOGNIZED")
    return {"status": "PASS_SCOPED_PROOF_NO_PUBLICATION",
            "production_publication_allowed": False,
            "neon_branch": v["neon_branch"], "city_count": 23,
            "candidate_files": {n: actual[n] for n in sorted(FILES)},
            "c2_corpus_sha256": v["c2_corpus_sha256"],
            "compatible_runtime_git_baseline_proven": False,
            "actual_production_rollback_proven": False}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--proof-dir", required=True, type=Path)
    p.add_argument("--as-of", default=None,
                   help="receipt evaluation time; default is real UTC clock")
    p.add_argument("--report", type=Path)
    a = p.parse_args()
    try:
        report = inspect(a.proof_dir, as_of=utc(a.as_of) if a.as_of else
                         datetime.now(timezone.utc))
        exit_code = 0
    except (Blocked, ValueError, KeyError, TypeError, OSError,
            json.JSONDecodeError) as exc:
        report = {"status": "BLOCKED", "production_publication_allowed": False,
                  "reason": str(exc) if isinstance(exc, Blocked) else "MALFORMED_EVIDENCE"}
        exit_code = 2
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps(report, sort_keys=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
