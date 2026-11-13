#!/usr/bin/env python3
"""Offline Work I package assertions only, no HTTP to media."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
G = ROOT / "research/casualty_controlled_capture_preflight_2026_11_13"
E = ROOT / "research/casualty_evidence_ingestion_2026_11_13/ingest.py"
PLAN = json.loads((G / "capture_plan.json").read_text(encoding="utf-8"))
AUTH = json.loads((G / "authorization_template.json").read_text(encoding="utf-8"))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main(output):
    targets = PLAN["targets"]
    assert len(targets) == len({t["url"] for t in targets}) == 10
    assert len(PLAN["allowed_hosts"]) == 7
    assert AUTH["targets"] == [
        {"url":t["url"], "role":t["role"], "candidate_ids":t["candidate_ids"],
         "approved_redirect_urls": []} for t in targets]
    assert AUTH["allowed_hosts"] == PLAN["allowed_hosts"]
    assert AUTH["redirect_policy"] == "EXACT_PER_INITIAL_TARGET_DEFAULT_DENY"
    assert PLAN["limits"]["max_requests_total"] == AUTH["max_requests_total"] == 20
    assert PLAN["limits"]["min_delay_seconds"] == AUTH["min_delay_seconds"] == 1
    assert PLAN["limits"]["max_response_bytes"] == AUTH["max_response_bytes"] == 1000000
    assert PLAN["limits"]["timeout_seconds"] == AUTH["timeout_seconds"] == 15
    assert PLAN["limits"]["max_redirects_per_url"] == AUTH["max_redirects_per_url"] == 3
    assert PLAN["limits"]["retries"] == AUTH["retries"] == 0
    assert AUTH["expires_after_hours_max"] == 24
    assert AUTH["authorization_id"] is None
    assert AUTH["approved_at_utc"] is None and AUTH["expires_at_utc"] is None
    assert AUTH["status"] == "NOT_AUTHORIZED"
    assert not AUTH["enable_controlled_capture"] and not AUTH["publication_allowed"]
    assert not AUTH["schedule_enabled"] and not PLAN["automatic_credit_allowed"]
    hashes = {str(x.relative_to(ROOT)): sha(x) for x in [
        E, G/"test_preflight.py", G/"capture_plan.json",
        G/"authorization_template.json", HERE/"test_redirect.py"]}
    proof = {
        "checkpoint": "CASUALTY-STRICT-REDIRECT-WORKI-OFFLINE-01",
        "decision": "STRICT_REDIRECT_PREFLIGHT_PASS",
        "execution": "OFFLINE_ONLY",
        "authorization_status": "NOT_AUTHORIZED",
        "publisher_http_requests": 0,
        "initial_url_count": 10,
        "allowed_host_count": 7,
        "exact_approved_redirect_target_count": 0,
        "max_requests_total": 20,
        "max_redirects_per_url": 3,
        "min_delay_seconds": 1,
        "max_response_bytes": 1000000,
        "timeout_seconds": 15,
        "retries": 0,
        "max_authorization_hours": 24,
        "publication_allowed": False,
        "automatic_promote_allowed": False,
        "source_sha256": hashes,
        "limitations": [
            "Mock-only safety proof; no live source-body or factual casualty verification",
            "No owner approval for any publisher HTTP",
            "No merge, deployment, casualty publication, C2, Neon or WIP changes",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(proof, ensure_ascii=False, sort_keys=True, indent=2)+"\n",
                      encoding="utf-8")
    print("STRICT_REDIRECT_PREFLIGHT_PASS: offline policy and 10 URL package, 0 external GETs")

if __name__ == "__main__":
    main(Path(sys.argv[1]))
