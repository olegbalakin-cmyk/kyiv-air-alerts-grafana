#!/usr/bin/env python3
"""Single-use owner-authorized source capture using Work E/I, research only.

Never writes source article bodies, casualty ledgers, WIP, or production data.
Capture is disabled unless a separate launch.json exists and GitHub's first
push is from the one specified reviewed predecessor commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
EXPECTED_BASE = "da49571a9e22e2e1e62a2842f902f984cbd0ab10"
EXPECTED_BRANCH = "research-casualty-one-time-10-source-2026-11-13"
PLAN_PATH = ROOT / "research/casualty_controlled_capture_preflight_2026_11_13/capture_plan.json"
TEMPLATE_PATH = ROOT / "research/casualty_controlled_capture_preflight_2026_11_13/authorization_template.json"
BLOBS = {
    "research/casualty_evidence_ingestion_2026_11_13/ingest.py": "227dced92dfb1252af8ff25ade9aaaf67e93a798",
    "research/casualty_controlled_capture_preflight_2026_11_13/capture_plan.json": "2f45d15b0e79cb11bf8ab605e314436dc0d3ed7c",
    "research/casualty_controlled_capture_preflight_2026_11_13/authorization_template.json": "7d1dc7a8c4e0457197bf3b66f2ce465becaa7d89",
}
import research.casualty_evidence_ingestion_2026_11_13.ingest as e
from review_casualty_candidates import load_queue


def write_json(path: Path, value: object):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha_data(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def check_scope(queue: list[dict]) -> tuple[dict, dict]:
    for path, expected in BLOBS.items():
        if git("rev-parse", "HEAD:" + path) != expected:
            raise RuntimeError("RESEARCH_SOURCE_BLOB_DRIFT:" + Path(path).name)
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    if template.get("status") != "NOT_AUTHORIZED" or template.get("enable_controlled_capture") is not False:
        raise RuntimeError("TEMPLATE_NOT_DEFAULT_OFF")
    if (len(plan["targets"]) != 10 or len(plan["allowed_hosts"]) != 7 or
            plan["limits"]["max_requests_total"] != 20 or
            template.get("authorization_id") is not None or
            template.get("publication_allowed") is not False or
            template.get("schedule_enabled") is not False):
        raise RuntimeError("NON_EXACT_PR111_SCOPE")
    exact_targets = [{"url": t["url"], "role": t["role"],
                      "candidate_ids": t["candidate_ids"], "approved_redirect_urls": []}
                     for t in plan["targets"]]
    if template["targets"] != exact_targets or template["allowed_hosts"] != plan["allowed_hosts"]:
        raise RuntimeError("TARGETS_OR_REDIRECT_SCOPE_CHANGED")
    if (template["max_requests_total"] != 20 or template["max_response_bytes"] != 1000000
            or template["min_delay_seconds"] != 1 or template["timeout_seconds"] != 15
            or template["max_redirects_per_url"] != 3 or template["retries"] != 0):
        raise RuntimeError("RESOURCE_SCOPE_CHANGED")
    ids = {c["candidate_id"] for c in queue}
    if not all(set(t["candidate_ids"]).issubset(ids) for t in plan["targets"]):
        raise RuntimeError("FROZEN_WIP_CANDIDATE_DRIFT")
    return plan, template


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--launch", type=Path)
    ap.add_argument("--preflight-only", action="store_true")
    args = ap.parse_args()
    if not args.output.is_absolute() or str(args.output).startswith(str(ROOT)):
        raise RuntimeError("OUTPUT_MUST_BE_EPHEMERAL_OUTSIDE_REPO")
    args.output.mkdir(parents=True, exist_ok=True)
    queue = load_queue(args.queue)
    plan, template = check_scope(queue)
    if args.preflight_only:
        write_json(args.output / "preflight.json", {
            "decision": "CAPTURE_NOT_STARTED_OFFLINE_PREFLIGHT_PASS",
            "targets": len(plan["targets"]), "allowed_hosts": len(plan["allowed_hosts"]),
            "max_requests_total": 20, "external_get_requests": 0,
            "authorization_status": "NOT_AUTHORIZED",
            "publisher_text_persisted": False, "publication_allowed": False,
        })
        print("ONE_TIME_CAPTURE_PREFLIGHT_PASS; 0 source GET; authorization remains OFF")
        return
    if not args.launch:
        raise RuntimeError("MISSING_SEPARATE_OWNER_GRANT")
    launch = json.loads(args.launch.read_text(encoding="utf-8"))
    if (launch.get("scope") != "EXACT_PR111_T01_TO_T10_SINGLE_EXECUTION"
            or launch.get("expected_source_base_sha") != EXPECTED_BASE
            or launch.get("owner_approval_record") != "2026-11-13: explicit owner message approving the proposed ten-source one-time HTTP pilot"
            or launch.get("publication_allowed") is not False
            or launch.get("automatic_promote_allowed") is not False
            or launch.get("repeat_allowed") is not False):
        raise RuntimeError("OWNER_GRANT_SCOPE_INVALID")
    if (os.getenv("GITHUB_REF") != "refs/heads/" + EXPECTED_BRANCH
            or os.getenv("GITHUB_RUN_ATTEMPT") != "1"
            or os.getenv("GITHUB_EVENT_NAME") != "push"
            or os.getenv("GITHUB_EVENT_BEFORE") != launch.get("expected_previous_commit_sha")):
        raise RuntimeError("SINGLE_PUSH_PROOF_REQUIRED")
    if not launch.get("authorization_id") or not launch.get("expected_previous_commit_sha"):
        raise RuntimeError("MISSING_GRANT_IDENTIFIER")
    try:
        approval_time = datetime.fromisoformat(launch["approved_at_utc"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(launch["expires_at_utc"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise RuntimeError("INVALID_APPROVAL_WINDOW") from exc
    now = datetime.now(timezone.utc)
    if not (approval_time.tzinfo and expires.tzinfo and approval_time <= now < expires
            and timedelta(0) < expires - approval_time <= timedelta(hours=24)):
        raise RuntimeError("SINGLE_USE_AUTHORIZATION_EXPIRED_OR_INVALID")
    policy = dict(template)
    policy.update({
        "authorization_id": launch["authorization_id"],
        "approved_at_utc": launch["approved_at_utc"],
        "expires_at_utc": launch["expires_at_utc"],
        "owner_approval_record": launch["owner_approval_record"],
        "status": "OWNER_APPROVED_SOURCE_CAPTURE_ONCE",
        "enable_controlled_capture": True,
    })
    e.validate_capture_approval(policy, True, queue)
    # No article body is ever saved; the Work I HTTP code is the ONLY source fetcher.
    try:
        volatile, audit = e.controlled_capture(policy, queue, enabled=True)
    except Exception as exc:
        write_json(args.output / "capture_failure.json", {
            "decision": "CAPTURE_ABORTED_NO_PUBLICATION",
            "reason_type": type(exc).__name__,
            "authorization_id": launch["authorization_id"],
            "request_count_after_exception": "UNKNOWN_STOP_NO_RETRY",
            "publication_allowed": False,
            "no_source_body_stored": True,
        })
        raise
    receipts = []
    for target, result in zip(plan["targets"], audit["targets"]):
        receipts.append({
            "target_id": target["target_id"], "case_id": target["case_id"],
            "role": target["role"], "candidate_ids": target["candidate_ids"],
            "receipt": result, "publication_allowed": False,
        })
    if len(receipts) > 10 or audit["requests_used"] > 20:
        raise RuntimeError("CAPTURE_BUDGET_OR_TARGET_OVERFLOW")
    # Only existing Work A/E extraction; no new parser or death-count adjudicator.
    extracted = []
    parser_errors = {}
    try:
        retained, rejected = e.work_a.anchored_articles(queue, volatile)
        reports = e.extract_cached_reports(queue, retained)
        for report in reports:
            item = {
                "candidate_ids": report.get("candidate_ids", []),
                "incident": report.get("incident"),
                "count": report.get("count"),
                "report_sha256": e.stable_digest(report),
                "status": "UNVERIFIED_PARSER_OUTPUT_NEEDS_REVIEW",
                "independent_official_event_link_proven": False,
                "prior_credit_reconciled": False,
                "publication_allowed": False,
            }
            extracted.append(item)
        parser_errors["candidate_binding_issues"] = {
            key: value for key, value in rejected.items()
        }
    except Exception as exc:
        parser_errors["work_a_error_type"] = type(exc).__name__
    source_hashes = []
    for article in volatile["articles"]:
        source_hashes.append({
            "candidate_id": article["candidate_id"],
            "source_url": article["url"],
            "original_text_sha256": sha_data(article["text"].encode("utf-8")),
            "text_characters": len(article["text"]),
            "status": "SOURCE_RETRIEVED_NOT_INDEPENDENTLY_VERIFIED",
            "publication_allowed": False,
        })
    official_hashes = []
    for article in volatile["official_articles"]:
        official_hashes.append({
            "source_url": article["url"],
            "text_sha256": sha_data(article["text"].encode("utf-8")),
            "text_characters": len(article["text"]),
            "status": "OFFICIAL_BODY_PRESENT_BUT_NOT_EVENT_LINKED",
            "publication_allowed": False,
        })
    summary = {
        "decision": "CONTROLLED_SOURCE_CAPTURE_RESEARCH_ONLY",
        "authorization_id": launch["authorization_id"],
        "source_base_commit": EXPECTED_BASE,
        "run_once": True, "requested_urls": 10, "allowed_hosts": 7,
        "max_requests_total": 20, "requests_used": audit["requests_used"],
        "targets_attempted": len(audit["targets"]),
        "targets_not_attempted": 10 - len(audit["targets"]),
        "stopped_early": audit.get("stopped_early", False),
        "stop_reason": audit.get("stop_reason"),
        "captured_publisher_candidate_texts": len(volatile["articles"]),
        "captured_official_source_texts": len(volatile["official_articles"]),
        "unverified_existing_parser_reports": len(extracted),
        "automatic_death_credits": 0, "publication_allowed": False,
        "production_changed": False, "wip_changed": False, "neon_changed": False,
        "full_article_bodies_saved": False, "official_links_verified": False,
    }
    write_json(args.output / "capture_receipts.json", {"summary": summary, "targets": receipts})
    write_json(args.output / "fact_preview_unverified.json", {
        "reports": extracted, "source_text_hashes": source_hashes,
        "official_text_hashes": official_hashes, "parser_errors": parser_errors,
        "no_full_publisher_text": True, "human_review_required": True,
        "publication_allowed": False,
    })
    write_json(args.output / "summary.json", summary)
    proofs = {p.name: sha_data(p.read_bytes()) for p in args.output.glob("*.json")}
    write_json(args.output / "manifest.json", {
        "files_sha256": proofs, "owner_grant_scope": launch["scope"],
        "no_publisher_bodies_committed": True, "publication_allowed": False,
    })
    print("CONTROLLED_CAPTURE_COMPLETE: attempts", summary["targets_attempted"],
          "HTTP requests", summary["requests_used"],
          "source bodies in memory", summary["captured_publisher_candidate_texts"] +
          summary["captured_official_source_texts"],
          "stopped", summary["stopped_early"], "publication forbidden")


if __name__ == "__main__":
    main()
