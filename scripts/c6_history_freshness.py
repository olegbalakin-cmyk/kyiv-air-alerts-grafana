"""Historical source checkpoints bound to the existing C2 export and readback.
No network, SQL, writer, scheduler or publication authority.
"""
from __future__ import annotations
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import zipfile
import importlib.util
from scripts import c2_shadow_bundle as c2

FRESH_AFTER_HOURS = 36.0  # reconcile_bridge_freshness.py production ceiling
TABLES = ("episodes", "observations", "checkpoints", "runs",
          "classifications", "source_links", "events")
INDEPENDENT = {"kyiv": "kyiv_digital", "sevastopol": "sevastopol_history"}

def capture_contract():
    path = Path(__file__).resolve().parents[1] / "kyiv-air-alerts-grafana/scripts/c2_history_capture.py"
    spec = importlib.util.spec_from_file_location("c2_history_capture_contract", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def verified_capture_sources(payload, manifest, *, read_at):
    contract = capture_contract()
    receipts = payload["historical_source_receipts"]
    require(isinstance(receipts, dict) and set(receipts) <= set(payload["cities"]),
            "HISTORY_CAPTURE_CITY_MISMATCH")
    run = {key: manifest[key] for key in
           ("github_run_id", "github_run_attempt", "workflow_sha", "input_sha")}
    sources = {}
    for key, row in receipts.items():
        source = INDEPENDENT.get(key, "ukrainealarm_region_history")
        continuous = contract.verify(row, city=key, source_key=source, run_identity=run, read_at=read_at)
        sources[key] = {k: copy.deepcopy(v) for k, v in row.items() if k != "pages"}
        sources[key].update(continuity_verified=continuous, full_receipt_verified=continuous,
            capture_metadata_verified=True, clock="independent_source_response_capture")
    return sources

class Blocked(ValueError):
    pass

def require(ok, reason):
    if not ok:
        raise Blocked(reason)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def fingerprint(value):
    return digest(json.dumps(value, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"), default=str, allow_nan=False).encode())

def utc(value):
    dt = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    require(dt.tzinfo is not None, "HISTORY_NAIVE_TIMESTAMP")
    return dt.astimezone(timezone.utc)

def from_bundle(bundle, expected_sha256, *, readback_proof, receipt,
                receipt_sha256, workflow_sha, input_sha, db_branch):
    """Caller already verified the production C2 receipt/run and snapshot rows.

    The trusted bundle digest comes from the export, not from the bundle being
    checked. Its hashed dashboard contains the original per-city checkpoints.
    """
    manifest = c2.verify_archive(Path(bundle), expected_sha256,
        workflow_sha=workflow_sha, input_sha=input_sha, db_branch=db_branch)
    with zipfile.ZipFile(bundle) as archive:
        saved_receipt = c2.safe_json(archive.read("receipt.json"))
        status = c2.safe_json(archive.read("status.json"))
        payload = c2.safe_json(archive.read("payload.json"))
        dashboard = c2.safe_json(archive.read("site_data/dashboard_data.json"))
    require(saved_receipt == receipt and manifest["files"]["receipt.json"] == receipt_sha256,
            "HISTORY_C2_RECEIPT_MISMATCH")
    require(receipt.get("status") == "succeeded" and
        status.get("canonical_persistence_status") == "NEON_SUCCEEDED" and
        status.get("canonical_receipt_validated") is True and
        status.get("canonical_db_commit") == "CONFIRMED" and
        all(status.get(k) == receipt.get(k) for k in ("workflow_sha", "input_sha")),
        "HISTORY_C2_NOT_CONFIRMED")
    keys = dashboard.get("multicity_meta", {}).get("production_city_keys", [])
    require(len(keys) == len(set(keys)) == 23 and set(INDEPENDENT) <= set(keys),
            "HISTORY_CITY_COVERAGE_MISMATCH")
    require(payload.get("format") == "multicity-canonical-same-run-v1" and
        payload.get("canonicalization_version") == "alert-canonicalization-v1" and
        set(payload.get("cities", {})) == set(keys), "HISTORY_PAYLOAD_MISMATCH")
    episodes = []
    for key in keys:
        block = payload["cities"][key]
        rows = block.get("episodes", [])
        require(rows and block.get("episode_count") == len(rows) and
                all(r.get("city_key") == key for r in rows), "HISTORY_PAYLOAD_COVERAGE_MISMATCH")
        episodes.extend(rows)
    corpus = fingerprint({"canonicalization_version": payload["canonicalization_version"],
                          "production_city_keys": keys, "episodes": episodes})
    require(corpus == manifest["corpus_sha256"] == receipt.get("corpus_sha256") and
            len(episodes) == receipt.get("canonical_episode_count"), "HISTORY_CORPUS_MISMATCH")
    proof = readback_proof
    meta = proof.get("meta", {})
    require(proof.get("c2_corpus_sha256") == corpus and
            proof.get("receipt_sha256") == receipt_sha256, "HISTORY_READBACK_CORPUS_MISMATCH")
    require(meta.get("read_only") == "on" and meta.get("isolation") == "repeatable read" and
        bool(meta.get("snapshot")) and meta.get("read_at") and
        set(proof.get("table_sha256", {})) == set(TABLES) and
        set(proof.get("counts", {})) == set(TABLES) and
        all(c2.SHA256.fullmatch(str(v)) for v in proof["table_sha256"].values()) and
        all(type(v) is int and v >= 0 for v in proof["counts"].values()),
        "HISTORY_READBACK_IDENTITY_MISSING")
    read_at = utc(meta["read_at"])
    mm = dashboard["multicity_meta"]
    bridge = mm.get("official_ukrainealarm_bridge", {})
    required = set(keys) - set(INDEPENDENT)
    require(set(bridge.get("required_rows", [])) == required and
        set(bridge.get("continuity_verified_rows", [])) == required and
        bridge.get("continuity_unverified_rows") == [] and bridge.get("fully_continuous") is True and
        bridge.get("last_fetch_error") is None and set(bridge.get("rows", {})) == required,
        "HISTORY_BRIDGE_COVERAGE_MISSING")
    sources = {}
    for key in sorted(required):
        row = bridge["rows"][key]
        require(row.get("primary_continuous") is True and row.get("last_error") is None and
                row.get("continuity_reason") == "history_reaches_previous_poll",
                "HISTORY_CONTINUITY_NOT_PROVEN:" + key)
        require(utc(row.get("last_checked_at")) <= utc(bridge.get("last_successful_fetch_at")) <= read_at,
                "HISTORY_CAPTURE_AFTER_READBACK:" + key)
        sources[key] = {"source_key": "ukrainealarm_region_history",
            "last_checked_at": row["last_checked_at"], "continuity_verified": True,
            "continuity_reason": row["continuity_reason"], "clock": "source_history_last_checked_at"}
    # Equivalent independent receipts must be in the same manifest-hashed
    # dashboard. Existing retained Kyiv/Sevastopol data has no such receipts.
    independent = mm.get("historical_source_receipts", {})
    require(set(independent) <= set(INDEPENDENT), "HISTORY_INDEPENDENT_CITY_MISMATCH")
    for key, row in independent.items():
        require(row.get("source_key") == INDEPENDENT[key] and row.get("last_error") is None and
            row.get("continuity_verified") is True and
            row.get("continuity_reason") == "history_reaches_previous_poll" and
            c2.SHA256.fullmatch(str(row.get("source_sha256"))) and
            utc(row.get("oldest_fetched_completed_air_start")) <= utc(row.get("previous_checked_at")) <=
            utc(row.get("last_checked_at")) <= read_at,
            "HISTORY_INDEPENDENT_PROVENANCE_MISSING:" + key)
        sources[key] = {**copy.deepcopy(row), "clock": "source_history_last_checked_at"}
    if "historical_source_receipts" in payload:
        # Modern capture contract is authoritative. Never fill missing same-run
        # captures from an older dashboard checkpoint or another run.
        sources = verified_capture_sources(payload, manifest, read_at=read_at)
    binding = {"schema": "c6-historical-freshness-v1", "publication_allowed": False,
        "corpus_sha256": corpus, "workflow_sha": workflow_sha, "input_sha": input_sha,
        "github_run_id": manifest["github_run_id"], "github_run_attempt": manifest["github_run_attempt"],
        "canonical_run_id": manifest["canonical_run_id"], "db_branch": db_branch,
        "bundle_sha256": expected_sha256, "receipt_sha256": receipt_sha256,
        "source_dashboard_sha256": manifest["files"]["site_data/dashboard_data.json"],
        "readback": copy.deepcopy(proof), "city_keys": list(keys), "sources": sources}
    return {**binding, "binding_sha256": fingerprint(binding)}

def evaluate(binding, *, now, readback_proof):
    """Recompute source age at consumption; ignore cached fresh/age flags."""
    require(binding.get("schema") == "c6-historical-freshness-v1" and
            binding.get("publication_allowed") is False, "HISTORY_BINDING_SCHEMA")
    require(binding.get("binding_sha256") == fingerprint({k: v for k, v in binding.items()
            if k != "binding_sha256"}), "HISTORY_BINDING_DIGEST_MISMATCH")
    require(binding.get("readback") == readback_proof, "HISTORY_READBACK_IDENTITY_MISMATCH")
    now = utc(now)
    require(now >= utc(readback_proof["meta"]["read_at"]), "HISTORY_EVALUATION_BEFORE_READBACK")
    keys = binding["city_keys"]
    require(len(keys) == len(set(keys)) == 23 and set(binding["sources"]) <= set(keys),
            "HISTORY_CITY_COVERAGE_MISMATCH")
    cities = {}
    for key in keys:
        source = binding["sources"].get(key)
        reasons = []
        age = None
        if source is None:
            reasons.append("MISSING_INDEPENDENT_SOURCE_CAPTURE_CHECKPOINT")
        else:
            if source.get("continuity_verified") is not True:
                reasons.append("CAPTURE_HISTORY_CONTINUITY_NOT_PROVEN")
            age = (now - utc(source["last_checked_at"])).total_seconds()
            require(age >= 0, "HISTORY_FUTURE_CAPTURE:" + key)
            if age > FRESH_AFTER_HOURS * 3600:
                reasons.append("STALE_HISTORICAL_SOURCE_CAPTURE")
        cities[key] = {"historical_binding_verified": source is not None,
            "source_checked_at_utc": source["last_checked_at"] if source else None,
            "source_age_seconds": age, "within_36_hour_bound": age is not None and 0 <= age <= 129600,
            "continuity_verified": bool(source and source.get("continuity_verified")),
            "full_receipt_verified": bool(source and source.get("full_receipt_verified")),
            "source_key": source.get("source_key") if source else None,
            "source_identity": source.get("source_identity") if source else None,
            "source_sha256": source.get("source_sha256") if source else None,
            "previous_checkpoint_sha256": source.get("previous_checkpoint_sha256") if source else None,
            "historical_freshness_verdict": "BLOCKED" if reasons else "PASS", "reasons": reasons}
    return {"status": "BLOCKED" if any(c["reasons"] for c in cities.values()) else "FRESHNESS_READY_FOR_INTEGRATION",
        "publication_allowed": False, "freshness_ceiling_hours": FRESH_AFTER_HOURS,
        "historically_bound_cities": len(binding["sources"]),
        "full_receipt_cities": sum(c["full_receipt_verified"] for c in cities.values()),
        "fresh_cities": sum(not c["reasons"] for c in cities.values()),
        "evaluated_at_utc": now.isoformat(), "cities": cities}

def require_ready(report):
    require(report["status"] == "FRESHNESS_READY_FOR_INTEGRATION" and
            report["fresh_cities"] == 23, "HISTORY_FRESHNESS_BLOCKED")
