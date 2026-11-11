#!/usr/bin/env python3
"""Validate THREE real retained articles against pre-committed independent gold.

Never makes publisher HTTP requests or edits the operational queue/revisions.
Only shadow proposals for research. A wrong or missed gold outcome is a real
test failure, with complete evidence uploaded by the calling workflow.
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "research/casualty_three_new_http_2026_11_11"
GOLD = R / "INDEPENDENT_GOLD.json"
SRC = R / "selected_queue.json"
ARTIFACT = R / "input/evidence.json"
ARTIFACT_MANIFEST = R / "input/manifest.json"
CAPTURE_VERDICT = R / "input/capture_verdict.json"
LEDGER = ROOT / "research/casualty_real_evidence_2026_11_10/pinned_revisions.csv"
BASELINE = ROOT / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"
REVIEWER = ROOT / "kyiv-air-alerts-grafana/scripts/casualty_auto_review.py"
OUT = R / "offline_results"
PROTECTED = [GOLD, SRC, ARTIFACT, ARTIFACT_MANIFEST, CAPTURE_VERDICT, LEDGER,
             BASELINE, REVIEWER]
EXPECTED_REVIEWER_BLOB = "0ce2cd1658ad8fa8e3d922c4ea5539e97b161301"
EXPECTED_ARTIFACT_SHA256 = "84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df"
IDS = {"e0fba98b19473874e9a1d8f1",
       "42f2a273f56c87e0bcd22af8",
       "5e46ae290e43745fc4b827fa"}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def rows(p):
    with p.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    gold = load(GOLD)
    observed = load(ARTIFACT)
    sample = load(SRC)
    man = load(ARTIFACT_MANIFEST)
    capture = load(CAPTURE_VERDICT)
    if sha(ARTIFACT) != EXPECTED_ARTIFACT_SHA256:
        raise RuntimeError("ORIGINAL_EVIDENCE_HASH_MISMATCH")
    for name, digest in man.get("sha256", {}).items():
        if sha(R / "input" / name) != digest:
            raise RuntimeError("ORIGINAL_ARTIFACT_MANIFEST_MISMATCH")
    if gold["source_artifact"]["artifact_id"] != 13870872313:
        raise RuntimeError("GOLD_NOT_FROM_EXACT_CAPTURE")
    if gold["source_artifact"]["evidence_sha256"] != EXPECTED_ARTIFACT_SHA256:
        raise RuntimeError("GOLD_EVIDENCE_SHA_MISMATCH")
    if capture["status"] != "CAPTURED" or capture["reviewer_has_not_run"] is not True:
        raise RuntimeError("INDEPENDENT_GOLD_NOT_PRE_REVIEWER")
    if capture["protected_inputs_unchanged"] is not True:
        raise RuntimeError("LIVE_PROTECTED_INPUTS_CHANGED")
    if (capture["capture_summary"]["urls_checked"] != 3 or
            capture["capture_summary"]["http_requests"] > 40):
        raise RuntimeError("ORIGINAL_CAPTURE_HTTP_SCOPE_WRONG")
    if gold["gold_frozen_before_reviewer"] is not True:
        raise RuntimeError("GOLD_PRECOMMIT_NOT_CONFIRMED")
    if len(sample) != 3 or len(observed.get("articles", [])) != 3 or len(gold["expected"]) != 3:
        raise RuntimeError("THREE_SOURCE_RECORDS_REQUIRED")
    assert {x["candidate_id"] for x in sample} == IDS
    assert {x["candidate_id"] for x in gold["expected"]} == IDS
    assert {x["candidate_id"] for x in observed["articles"]} == IDS
    code_blob = subprocess.check_output(["git", "hash-object", str(REVIEWER)],
                                        cwd=ROOT, text=True).strip()
    if code_blob != EXPECTED_REVIEWER_BLOB:
        raise RuntimeError("REVIEWER_CHANGED_SINCE_GOLD")

    before = {str(p.relative_to(ROOT)): sha(p) for p in PROTECTED}
    article_by_id = {a["candidate_id"]: a for a in observed["articles"]}
    for item in gold["expected"]:
        a = article_by_id[item["candidate_id"]]
        if sha_string(a["text"]) != item["excerpt_sha256"]:
            raise RuntimeError("EXCERPT_HASH_MISMATCH")
        if a["url"] != item["source_url"]:
            raise RuntimeError("PUBLISHER_URL_MISMATCH")
    sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
    from casualty_auto_review import run_offline

    first = OUT / "first"
    repeat = OUT / "repeat"
    s1 = run_offline(SRC, LEDGER, ARTIFACT, BASELINE, first)
    s2 = run_offline(SRC, LEDGER, ARTIFACT, BASELINE, repeat, first / "proposals.csv")
    first_events = load(first / "events.json")
    second_events = load(repeat / "events.json")
    proposals = rows(first / "proposals.csv")
    added_on_repeat = rows(repeat / "proposals.csv")
    if len(first_events) != 3 or len(second_events) != 3:
        raise RuntimeError("INCORRECT_EVENT_COUNT")
    if added_on_repeat or int(s2.get("unique_proposals", -1)) != 0:
        raise RuntimeError("DUPLICATE_REPLAY_PROPOSAL")
    after = {str(p.relative_to(ROOT)): sha(p) for p in PROTECTED}
    if before != after:
        raise RuntimeError("PROTECTED_INPUT_MUTATED")

    outcomes = []
    for expected in gold["expected"]:
        cid = expected["candidate_id"]
        relevant = [e for e in first_events if any(m.get("candidate_id") == cid
                    for m in e.get("messages", []))]
        if len(relevant) != 1:
            raise RuntimeError("NON_UNIQUE_EVENT_MEMBERSHIP")
        e = relevant[0]
        outcomes.append({
            "candidate_id": cid,
            "city_key": expected["city_key"],
            "kind": expected["kind"],
            "gold_status": expected["expected_status"],
            "reviewer_status": e["category"],
            "matches_gold": e["category"] == expected["expected_status"],
            "reviewer_reasons": e.get("reasons", []),
            "reviewer_incident": e.get("incident"),
            "report_count": len(e.get("reports", [])),
            "expected_civilian_city_delta": expected.get("expected_civilian_city_delta"),
        })
    potential_unjustified = []
    for p in proposals:
        ids = {s for s in str(p.get("candidate_ids") or "").split("|") if s}
        if (ids != {"e0fba98b19473874e9a1d8f1"}
                or p["city_key"] != "zaporizhzhia"
                or p["attack_date"] != "2026-10-10"
                or int(p["deaths_delta"]) != 23):
            potential_unjustified.append({
                "record_id": p["record_id"],
                "candidate_ids": p["candidate_ids"],
                "city_key": p["city_key"],
                "attack_date": p["attack_date"],
                "deaths_delta": p["deaths_delta"],
            })
    false_positive = sum(x["gold_status"] == "NEEDS_REVIEW" and
                         x["reviewer_status"] == "AUTO_READY" for x in outcomes)
    missed_positive = sum(x["gold_status"] == "AUTO_READY" and
                          x["reviewer_status"] != "AUTO_READY" for x in outcomes)
    status = ("PASS_THREE_REAL_ARTICLES" if not false_positive
              and not missed_positive and not potential_unjustified
              and len(proposals) == 1 else "FINDINGS_REQUIRING_REVIEW")
    report = {
        "status": status,
        "independent_gold_commit": "4174d3bbb8e3d34e640c9d2c0677f3fa02d98a6a",
        "gold_frozen_before_reviewer": True,
        "source_http_run": 43053796144,
        "source_http_requests_original": 12,
        "source_http_repeated": False,
        "reviewer_blob": code_blob,
        "articles_evaluated": 3,
        "matching_gold": sum(x["matches_gold"] for x in outcomes),
        "false_auto_ready": false_positive,
        "missed_auto_ready": missed_positive,
        "unexpected_proposals": potential_unjustified,
        "first_new_proposals": len(proposals),
        "replay_new_proposals": len(added_on_repeat),
        "added_deaths_on_replay": 0,
        "first_summary": s1,
        "replay_summary": s2,
        "per_article": outcomes,
        "proposals_research_only": [
            {"candidate_ids": p.get("candidate_ids"), "city_key": p.get("city_key"),
             "attack_date": p.get("attack_date"), "deaths_delta": p.get("deaths_delta")}
            for p in proposals],
        "protected_sha256_unchanged": before == after,
        "protected_sha256": before,
        "publication_allowed": False,
    }
    write(OUT / "verdict.json", report)
    write(OUT / "manifest.json", {
        "sha256": {str(p.relative_to(OUT)): sha(p)
                   for p in sorted(OUT.rglob("*")) if p.is_file()
                   and p.name != "manifest.json"},
        "publication_allowed": False,
    })
    print("FROZEN REAL ARTICLE REVIEW", json.dumps(report, ensure_ascii=False))
    return 0 if status == "PASS_THREE_REAL_ARTICLES" else 1


def sha_string(v: str) -> str:
    return hashlib.sha256(v.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    sys.exit(main())
