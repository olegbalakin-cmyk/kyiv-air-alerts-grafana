#!/usr/bin/env python3
"""One owner-authorized, read-only three-WIP-url source capture, no reviewer.

Frozen candidate IDs; no change to operational WIP, ledger, monitor, parsing
or publication. Reviewer must run only after independently frozen article gold.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "research/casualty_three_new_http_2026_11_11/selected_queue.json"
WIP = ROOT / "wip-pin/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json"
BASE = ROOT / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"
LEDGER = ROOT / "research/casualty_real_evidence_2026_11_10/pinned_revisions.csv"
MONITOR = ROOT / "kyiv-air-alerts-grafana/scripts/monitor_casualty_candidates.py"
CAPTURE = ROOT / "kyiv-air-alerts-grafana/scripts/casualty_evidence_capture.py"
POLICY = ROOT / "kyiv-air-alerts-grafana/scripts/casualty_transport_policy.py"
REVIEWER = ROOT / "kyiv-air-alerts-grafana/scripts/casualty_auto_review.py"
OUT = ROOT / "research/casualty_three_new_http_2026_11_11/results"
EXPECTED_QUEUE_BLOB = "f3f7141aa6d7584c63ff42510b40239a18834d15"
EXPECTED_SAMPLE_BLOB = "98f17abc05a4fdcb490d9e27faec189076314ac4"
EXPECTED_CODE_BLOBS = {
    MONITOR: "a6c09d7a8c8c594fccb3b7b8a49172bf6a575e91",
    CAPTURE: "40273785be0cefd70a0c1ac6f37ae7816b116700",
    POLICY: "74450ca96f0a67a8c37bb3eeeb3c6274a9d570d2",
    REVIEWER: "0ce2cd1658ad8fa8e3d922c4ea5539e97b161301",
}
IDS = (
    "e0fba98b19473874e9a1d8f1",  # Zaporizhzhia explicit 10 October
    "42f2a273f56c87e0bcd22af8",  # Ivano-Frankivsk updated deaths
    "5e46ae290e43745fc4b827fa",  # Kharkiv week retrospective
)
ALLOWED_HOSTS = {"suspilne.media", "lb.ua"}
PROTECTED = (SRC, WIP, BASE, LEDGER, MONITOR, CAPTURE, POLICY, REVIEWER)


def git_blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)], cwd=ROOT, text=True).strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def json_write(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def frozen_inputs():
    if git_blob(WIP) != EXPECTED_QUEUE_BLOB:
        raise RuntimeError("WIP_QUEUE_BLOB_CHANGED")
    if git_blob(SRC) != EXPECTED_SAMPLE_BLOB:
        raise RuntimeError("THREE_SELECTION_BLOB_CHANGED")
    for p, h in EXPECTED_CODE_BLOBS.items():
        if git_blob(p) != h:
            raise RuntimeError("FROZEN_IMPLEMENTATION_CHANGED:" + p.name)
    sample = json_read(SRC)
    queue = json_read(WIP)
    if len(queue) != 1657 or len(sample) != 3:
        raise RuntimeError("UNEXPECTED_QUEUE_OR_SAMPLE_SIZE")
    if tuple(x.get("candidate_id") for x in sample) != IDS:
        raise RuntimeError("UNEXPECTED_THREE_IDS")
    if len({x["url"] for x in sample}) != 3:
        raise RuntimeError("DUPLICATE_NEWS_URL")
    for row in sample:
        match = [x for x in queue if x.get("candidate_id") == row["candidate_id"]]
        if len(match) != 1 or match[0] != row:
            raise RuntimeError("CANDIDATE_NOT_EXACT_WIP_SNAPSHOT")
        if row.get("status") != "needs_review" or row.get("source") != "Google News RSS":
            raise RuntimeError("NOT_UNREVIEWED_NEWS")
        if not str(row["url"]).startswith("https://news.google.com/rss/articles/"):
            raise RuntimeError("NOT_FROZEN_GOOGLE_NEWS_ARTICLE")
        pub = urlsplit(row["publisher_url"]).hostname
        if not pub or pub.removeprefix("www.") not in ALLOWED_HOSTS:
            raise RuntimeError("NON_ALLOWLIST_PUBLISHER")
    return sample


def inputs_hashes():
    return {str(p.relative_to(ROOT)): sha256(p) for p in PROTECTED}


def capture():
    OUT.mkdir(parents=True, exist_ok=True)
    before = inputs_hashes()
    verdict = {
        "status": "CAPTURE_INFRA_ERROR",
        "candidate_ids": list(IDS),
        "requested_publisher_root_urls": 3,
        "max_publisher_http_requests": 40,
        "publication_allowed": False,
        "reviewer_has_not_run": True,
        "operational_data_write_allowed": False,
    }
    exitcode = 1
    try:
        sample = frozen_inputs()
        verdict["frozen_queue_blob"] = EXPECTED_QUEUE_BLOB
        verdict["frozen_selection_blob"] = EXPECTED_SAMPLE_BLOB
        verdict["selected"] = [
            {"candidate_id": x["candidate_id"], "city_key": x["city_key"],
             "publisher": x["publisher"], "title": x["title"],
             "published_at": x["published_at"]} for x in sample
        ]
        cmd = [
            sys.executable, str(MONITOR), "--capture-evidence-only",
            "--evidence-queue", str(SRC),
            "--evidence-output", str(OUT / "evidence.json"),
            "--max-evidence-urls", "3",
        ]
        process = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                                 timeout=950, check=False)
        if process.returncode != 0:
            verdict["subprocess_rc"] = process.returncode
            verdict["blocker"] = "CAPTURE_SUBPROCESS_FAILED"
            raise RuntimeError("CAPTURE_SUBPROCESS_FAILED")
        result = json.loads(process.stdout)
        if result.get("mode") != "isolated_capture_only":
            raise RuntimeError("UNEXPECTED_CAPTURE_MODE")
        summary = result["evidence_capture"]
        evidence = json_read(OUT / "evidence.json")
        arrivals = {x["candidate_id"] for x in evidence.get("articles", [])}
        failures = {x["candidate_id"] for x in evidence.get("failures", [])}
        receipts = {x["candidate_id"] for x in evidence.get("receipts", [])}
        if (arrivals & failures or arrivals != receipts or
                arrivals | failures != set(IDS)):
            raise RuntimeError("INCOMPLETE_OR_INCONSISTENT_EVIDENCE")
        if int(summary["urls_checked"]) != 3 or int(summary["http_requests"]) > 40:
            raise RuntimeError("HTTP_SCOPE_VIOLATION")
        if (int(summary["usable_evidence_packages"]) != len(arrivals)
                or int(summary["failed_candidates"]) != len(failures)
                or summary.get("publication_allowed") is not False
                or summary.get("production_enabled") is not False):
            raise RuntimeError("INVALID_CAPTURE_SUMMARY")
        verdict["status"] = "CAPTURED" if len(arrivals) == 3 else "CAPTURE_PARTIAL"
        verdict["capture_summary"] = summary
        verdict["per_candidate"] = [{
            "candidate_id": row["candidate_id"],
            "city": row["city_key"],
            "status": "ARTICLE_CAPTURED" if row["candidate_id"] in arrivals else
                      next(x["reason"] for x in evidence["failures"]
                           if x["candidate_id"] == row["candidate_id"]),
            "resolved_host": next((
                urlsplit(x.get("resolved_url") or "").hostname for x in evidence["receipts"]
                if x["candidate_id"] == row["candidate_id"]),
                None),
        } for row in sample]
        exitcode = 0
    except Exception as e:
        verdict["blocker"] = type(e).__name__ + ":" + str(e)[:160]
    finally:
        try:
            after = inputs_hashes()
            verdict["protected_inputs_unchanged"] = (before == after)
            verdict["protected_sha256"] = before
            if before != after:
                verdict["status"] = "CAPTURE_INFRA_ERROR"
                verdict["blocker"] = "PROTECTED_INPUT_MUTATION"
                exitcode = 1
        except Exception:
            verdict["status"] = "CAPTURE_INFRA_ERROR"
            verdict["blocker"] = "PROTECTED_INPUT_HASH_CHECK_FAILED"
            exitcode = 1
        json_write(OUT / "capture_verdict.json", verdict)
        json_write(OUT / "manifest.json", {
            "sha256": {str(x.relative_to(OUT)): sha256(x)
                       for x in sorted(OUT.rglob("*")) if x.is_file()
                       and x.name != "manifest.json"},
            "source_http_attempts_authorized": 1,
            "publication_allowed": False,
        })
        print(json.dumps({
            "status": verdict["status"],
            "capture_summary": verdict.get("capture_summary"),
            "per_candidate": verdict.get("per_candidate"),
            "protected_inputs_unchanged": verdict.get("protected_inputs_unchanged"),
            "blocker": verdict.get("blocker"),
        }, ensure_ascii=False))
    return exitcode


if __name__ == "__main__":
    arg = argparse.ArgumentParser()
    group = arg.add_mutually_exclusive_group(required=True)
    group.add_argument("--preflight", action="store_true")
    group.add_argument("--live", action="store_true")
    a = arg.parse_args()
    if a.preflight:
        x = frozen_inputs()
        print(json.dumps({"preflight": "PASS", "wip_count": 1657,
                          "candidate_ids": [y["candidate_id"] for y in x]}, ensure_ascii=False))
        sys.exit(0)
    sys.exit(capture())
