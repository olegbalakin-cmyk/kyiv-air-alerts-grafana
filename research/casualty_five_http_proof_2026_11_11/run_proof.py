#!/usr/bin/env python3
"""One owner-authorized, five-URL WIP casualty shadow proof. No publication.

The selected queue and operational WIP queue are immutable checked inputs.
--preflight makes no source HTTP calls. --live invokes the existing opt-in
capture-only monitor once, then runs a network-free reviewer replay.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SELECTED = ROOT / "research/casualty_five_candidate_selection_2026_11_11/selected_queue.json"
WIP_QUEUE = ROOT / "wip-pin/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json"
OP_DATA = ROOT / "kyiv-air-alerts-grafana/data/casualties"
MONITOR = ROOT / "kyiv-air-alerts-grafana/scripts/monitor_casualty_candidates.py"
LEDGER = ROOT / "research/casualty_real_evidence_2026_11_10/pinned_revisions.csv"
BASELINE = ROOT / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"
OUT = ROOT / "research/casualty_five_http_proof_2026_11_11/results"
EXPECTED_SELECTED_BLOB = "050d85606f6742306d28651a410baa23947557bd"
EXPECTED_WIP_BLOB = "f3f7141aa6d7584c63ff42510b40239a18834d15"
EXPECTED_IDS = (
    "5d60e1c78026fdc494ea3c84",  # Dnipro, Suspilne
    "96dc8052cf48f4ce74df29f6",  # Kharkiv, LB.ua
    "6c946bfd46fffbe953d795bf",  # Lutsk, UNIAN
    "f4719e871b92e7563c7150da",  # Odesa, Suspilne
    "81196e29c4a6ac2141a93617",  # Kharkiv, Korrespondent
)
FIELDS = ("candidate_id", "city", "city_key", "url", "published_at",
          "title", "publisher", "publisher_url", "status", "source",
          "snippet", "first_discovered_at")
PROTECTED = [
    SELECTED, WIP_QUEUE, LEDGER, BASELINE,
    OP_DATA / "multicity_review_queue.json",
    OP_DATA / "candidate_monitor_last_run.json",
    OP_DATA / "candidate_monitor_state.json",
    OP_DATA / "revisions.csv",
    ROOT / "kyiv-air-alerts-grafana/scripts/monitor_casualty_candidates.py",
    ROOT / "kyiv-air-alerts-grafana/scripts/casualty_auto_review.py",
    ROOT / "kyiv-air-alerts-grafana/scripts/casualty_transport_policy.py",
    ROOT / "kyiv-air-alerts-grafana/scripts/casualty_evidence_capture.py",
]


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def blob(path: Path) -> str:
    return subprocess.check_output(
        ["git", "hash-object", str(path)], text=True, cwd=ROOT
    ).strip()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(name: str, value) -> None:
    target = OUT / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")


def csv_rows(path: Path):
    with path.open("r", encoding="utf-8", newline="") as fp:
        return list(csv.DictReader(fp))


def validate_inputs():
    if blob(SELECTED) != EXPECTED_SELECTED_BLOB:
        raise ValueError("SELECTION_BLOB_MISMATCH")
    if blob(WIP_QUEUE) != EXPECTED_WIP_BLOB:
        raise ValueError("WIP_BLOB_MISMATCH")
    sample = load(SELECTED)
    if not isinstance(sample, list) or len(sample) != 5:
        raise ValueError("SELECTION_MUST_BE_FIVE")
    if tuple(row.get("candidate_id") for row in sample) != EXPECTED_IDS:
        raise ValueError("SELECTED_CANDIDATE_IDS_CHANGED")
    if len({row.get("url") for row in sample}) != 5:
        raise ValueError("DUPLICATE_SELECTED_URL")
    queue = load(WIP_QUEUE)
    if not isinstance(queue, list) or len(queue) != 1657:
        raise ValueError("UNEXPECTED_WIP_QUEUE_LENGTH")
    matches = {}
    for row in queue:
        if isinstance(row, dict) and row.get("candidate_id") in EXPECTED_IDS:
            matches.setdefault(row["candidate_id"], []).append(row)
    for row in sample:
        cid = row["candidate_id"]
        if len(matches.get(cid, [])) != 1:
            raise ValueError("WIP_CANDIDATE_NOT_UNIQUE")
        reference = matches[cid][0]
        if row.get("status") != "needs_review" or reference.get("status") != "needs_review":
            raise ValueError("CANDIDATE_NO_LONGER_PENDING")
        if any(row.get(field) != reference.get(field) for field in FIELDS):
            raise ValueError("SAVED_SELECTION_WIP_FIELD_MISMATCH")
        if row.get("source") != "Google News RSS":
            raise ValueError("NOT_A_GOOGLE_NEWS_CANDIDATE")
        if not str(row.get("url") or "").startswith("https://news.google.com/rss/articles/"):
            raise ValueError("NON_GOOGLE_RSS_URL")
    # Frozen revised ledger includes one unrelated Sumy case, not a selected ID.
    if any(any(cid in str(item) for cid in EXPECTED_IDS) for item in csv_rows(LEDGER)):
        raise ValueError("PREVIOUSLY_ACCOUNTED_CANDIDATE")
    return sample


def protected_hashes():
    return {str(p.relative_to(ROOT)): digest(p) for p in PROTECTED}


def proof_summary(sample):
    return {
        "queue_git_blob": EXPECTED_WIP_BLOB,
        "selection_git_blob": EXPECTED_SELECTED_BLOB,
        "queue_size": 1657,
        "candidate_count": len(sample),
        "candidate_ids": [x["candidate_id"] for x in sample],
        "cities": dict(sorted(Counter(x["city_key"] for x in sample).items())),
        "publication_allowed": False,
        "source_http_limit_urls": 5,
        "source_http_max_requests": 40,
    }


def run(live: bool):
    if not live:
        sample = validate_inputs()
        print(json.dumps({"status": "PREFLIGHT_PASS", **proof_summary(sample)}, ensure_ascii=False))
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    verdict = {"status": "BLOCKED", "mode": "one owner-approved live shadow capture",
               "publication_allowed": False, "production_modified": False,
               "wip_state_modified": False, "max_candidate_urls": 5,
               "max_http_requests": 40}
    before = {}
    try:
        before = protected_hashes()
        sample = validate_inputs()
        verdict.update(proof_summary(sample))

        evidence_path = OUT / "evidence.json"
        first = OUT / "first"
        cmd = [
            sys.executable, str(MONITOR), "--capture-evidence-only",
            "--evidence-queue", str(SELECTED),
            "--evidence-output", str(evidence_path),
            "--max-evidence-urls", "5",
            "--auto-propose-output", str(first),
            "--revision-snapshot", str(LEDGER),
            "--baseline-snapshot", str(BASELINE),
        ]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                                text=True, timeout=1000, check=False)
        if result.returncode:
            raise RuntimeError("CAPTURE_SUBPROCESS_NONZERO")
        summary = json.loads(result.stdout)
        capture, review = summary["evidence_capture"], summary["auto_propose"]
        verdict["capture"] = capture
        verdict["reviewer"] = review
        evidence = load(evidence_path)
        ids = set(EXPECTED_IDS)
        articles = {x["candidate_id"] for x in evidence.get("articles", [])}
        receipts = {x["candidate_id"] for x in evidence.get("receipts", [])}
        failures = {x["candidate_id"] for x in evidence.get("failures", [])}
        if not articles <= (ids & receipts) or not failures <= ids:
            raise ValueError("UNKNOWN_OR_UNLINKED_EVIDENCE")
        if len(articles | failures) != 5 or articles & failures:
            raise ValueError("INCOMPLETE_CANDIDATE_ACCOUNTING")
        if int(capture["urls_checked"]) != 5 or int(capture["http_requests"]) > 40:
            raise ValueError("UNEXPECTED_HTTP_SCOPE")
        if int(capture["usable_evidence_packages"]) != len(articles):
            raise ValueError("USABLE_EVIDENCE_COUNT_MISMATCH")
        failures_by_reason = Counter(x.get("reason", "UNKNOWN")
                                     for x in evidence.get("failures", []))
        verdict["per_candidate"] = [
            {
                "candidate_id": c["candidate_id"], "city_key": c["city_key"],
                "publisher": c["publisher"],
                "status": "ARTICLE_CAPTURED" if c["candidate_id"] in articles else
                          next((x.get("reason", "UNKNOWN") for x in evidence["failures"]
                                if x["candidate_id"] == c["candidate_id"]), "UNKNOWN"),
                "resolved_host": next((x.get("resolved_host") for x in evidence.get("failures", [])
                                       if x["candidate_id"] == c["candidate_id"]), None)
            } for c in sample
        ]
        verdict["failures_by_reason"] = dict(sorted(failures_by_reason.items()))
        rows = csv_rows(first / "proposals.csv")
        if int(review["unique_proposals"]) != len(rows):
            raise ValueError("PROPOSAL_COUNT_MISMATCH")
        for row in rows:
            linked = {x for x in str(row.get("candidate_ids", "")).split("|") if x}
            if not linked or not linked <= articles:
                raise ValueError("PROPOSAL_LACKS_CAPTURED_SOURCE")
        verdict["first_proposals"] = [
            {k: row.get(k) for k in ("record_id", "city_key", "attack_date",
                                      "deaths_delta", "candidate_ids")} for row in rows
        ]

        # Network-free replay; the first proposals become previous proposals.
        sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
        from casualty_auto_review import run_offline
        replay = run_offline(SELECTED, LEDGER, evidence_path, BASELINE,
                             OUT / "replay", first / "proposals.csv")
        duplicates = csv_rows(OUT / "replay/proposals.csv")
        verdict["replay"] = replay
        verdict["replay_added_proposals"] = len(duplicates)
        verdict["replay_added_deaths"] = sum(int(x["deaths_delta"])
                                             for x in duplicates)
        if duplicates or int(replay.get("unique_proposals", -1)) != 0:
            raise ValueError("REPLAY_DUPLICATE_PROPOSAL")
        if len(articles) > 0:
            verdict["status"] = ("PASS_AUTO_PROPOSAL" if rows
                                 else "PASS_CAPTURE_ONLY")
        else:
            verdict["status"] = "BLOCKED_NO_USABLE_EVIDENCE"
    except Exception as exc:
        verdict["status"] = "BLOCKED"
        verdict["blocker"] = type(exc).__name__ + ":" + str(exc)[:140]
    finally:
        try:
            after = protected_hashes()
            verdict["protected_inputs_unchanged"] = before == after
            if before != after:
                verdict["status"] = "BLOCKED"
                verdict["blocker"] = "PROTECTED_INPUT_CHANGED"
            verdict["protected_sha256_before"] = before
        except Exception:
            verdict["status"] = "BLOCKED"
            verdict["blocker"] = "PROTECTED_INPUT_CHECK_FAILED"
        write_json("verdict.json", verdict)
        manifest = {
            "sha256": {str(f.relative_to(OUT)): digest(f)
                        for f in sorted(OUT.rglob("*")) if f.is_file()
                        and f.name != "manifest.json"},
            "publication_allowed": False,
        }
        write_json("manifest.json", manifest)
        print(json.dumps({
            "status": verdict["status"],
            "capture": verdict.get("capture"), "reviewer": verdict.get("reviewer"),
            "per_candidate": verdict.get("per_candidate"),
            "failures_by_reason": verdict.get("failures_by_reason"),
            "first_proposals": verdict.get("first_proposals"),
            "replay_added_deaths": verdict.get("replay_added_deaths"),
            "protected_inputs_unchanged": verdict.get("protected_inputs_unchanged"),
            "blocker": verdict.get("blocker"),
        }, ensure_ascii=False))
    return 0 if verdict["status"].startswith("PASS_") else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true", help="Offline input verification")
    group.add_argument("--live", action="store_true", help="One approved HTTP shadow capture")
    options = p.parse_args()
    sys.exit(run(live=options.live))
