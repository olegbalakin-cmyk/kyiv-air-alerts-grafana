#!/usr/bin/env python3
"""Physical four-URL research proof; no hand-entered facts or production writes.

The known source inventory contributes ONLY URL/title/date/city routing fields.
Stored excerpts from the earlier test are deliberately never read.
All casualty decisions are computed by the unchanged reviewer from new HTTP.
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
SOURCES = ROOT / "research/casualty_real_evidence_2026_11_10/sources.json"
LEDGER = ROOT / "research/casualty_real_evidence_2026_11_10/pinned_revisions.csv"
BASELINE = ROOT / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"
MONITOR = ROOT / "kyiv-air-alerts-grafana/scripts/monitor_casualty_candidates.py"


def digest_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_routing_queue():
    sources = load_json(SOURCES)
    if len(sources["articles"]) != 4:
        raise ValueError("Pinned test expects exactly four source URLs")
    queue = []
    for source in sources["articles"]:
        # No source['extracts'] or previous review outcomes are read.
        url = source["url"]
        cid = "real-http-" + hashlib.sha256(url.encode()).hexdigest()[:20]
        city = source["city_key"]
        queue.append({
            "candidate_id": cid, "city_key": city,
            "city": {"dnipro": "Дніпро", "odesa": "Одеса"}[city],
            "title": source["title"], "snippet": "", "url": url,
            "published_at": source["published_date"], "publisher": source["publisher"],
            "publisher_url": "https://" + url.split("/")[2],
            "status": "needs_review",
        })
    return queue


def monitor_call(queue_path, capture_path, output, previous=None):
    args = [sys.executable, str(MONITOR), "--capture-evidence-only",
            "--evidence-queue", str(queue_path), "--evidence-output", str(capture_path),
            "--max-evidence-urls", "4"]
    if output is not None:
        args += ["--auto-propose-output", str(output),
                 "--revision-snapshot", str(LEDGER), "--baseline-snapshot", str(BASELINE)]
    if previous:
        args += ["--previous-proposals", str(previous)]
    done = subprocess.run(args, text=True, capture_output=True, timeout=190, cwd=ROOT)
    # Avoid publishing fetched pages or raw stack traces to job logs.
    summary = {"exit_code": done.returncode}
    if done.returncode == 0:
        summary["result"] = json.loads(done.stdout)
    else:
        summary["error_type"] = "MONITOR_COMMAND_FAILED"
        summary["stderr_tail"] = done.stderr[-850:]
    return summary


def proposal_rows(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    queue_path = RESULTS / "routing_queue.json"
    capture_path = RESULTS / "evidence.json"
    original_queue = build_routing_queue()
    write_json(queue_path, original_queue)
    protected = {str(p.relative_to(ROOT)): digest_file(p) for p in [SOURCES, LEDGER, BASELINE]}
    result = {"status": "BLOCKED", "scope": "4 real URLs, exact HTTP capture via the opt-in existing monitor",
              "reviewer_commit": "719c93c6239999bc430abc95bc8694205c103bbc",
              "routing_source": "four pinned URLs/titles/dates ONLY; previous extracts NOT used",
              "production_modified": False, "publication_allowed": False}
    try:
        # Acquire first. A single bounded retry ONLY for the initially failed
        # source URLs is permitted before the very first reviewer decision.
        initial = monitor_call(queue_path, capture_path, None)
        result["initial_capture_command"] = initial
        if initial["exit_code"]:
            raise RuntimeError("INITIAL_MONITOR_CAPTURE_FAILED")
        initial_summary = initial["result"]["evidence_capture"]
        first_evidence = load_json(capture_path)
        failures_before_retry = list(first_evidence["failures"])
        result["initial_failures"] = failures_before_retry
        retry_summary = {"urls_checked": 0, "http_requests": 0,
                         "articles_downloaded": 0, "usable_evidence_packages": 0}
        if failures_before_retry:
            failed_ids = {x["candidate_id"] for x in failures_before_retry}
            retry_queue = [q for q in original_queue if q["candidate_id"] in failed_ids]
            retry_queue_path = RESULTS / "bounded_retry_queue.json"
            write_json(retry_queue_path, retry_queue)
            retry = monitor_call(retry_queue_path, capture_path, None)
            result["bounded_retry_command"] = retry
            if retry["exit_code"]:
                raise RuntimeError("BOUNDED_RETRY_COMMAND_FAILED")
            retry_summary = retry["result"]["evidence_capture"]
        capture = load_json(capture_path)
        article_ids = {a["candidate_id"] for a in capture["articles"]}
        first_receipts = {x["candidate_id"]: x for x in capture["receipts"]}
        original_ids = {q["candidate_id"] for q in original_queue}
        if not article_ids <= original_ids:
            raise RuntimeError("Capture produced a foreign candidate ID")
        result["capture_summary"] = {
            "urls_checked": len(original_queue),
            "http_requests": initial_summary["http_requests"] + retry_summary["http_requests"],
            "articles_downloaded": min(len(original_queue),
                                       initial_summary["articles_downloaded"] +
                                       retry_summary["articles_downloaded"]),
            "usable_evidence_packages": len(article_ids),
            "failed_candidates": len(capture["failures"]),
            "bounded_retry_urls": len(failures_before_retry),
        }
        result["failed_sources"] = capture["failures"]
        # Pin the completed evidence snapshot, THEN run the unchanged reviewer.
        # No further source HTTP can affect this first decision or its replay.
        sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
        from casualty_auto_review import run_offline
        first_summary = run_offline(queue_path, LEDGER, capture_path, BASELINE,
                                    RESULTS / "first")
        first_rows = proposal_rows(RESULTS / "first/proposals.csv")
        result["review_summary"] = first_summary
        result["proposals"] = [
            {"city_key": x["city_key"], "attack_date": x["attack_date"],
             "deaths_delta": x["deaths_delta"], "candidate_ids": x["candidate_ids"],
             "record_id": x["record_id"]} for x in first_rows]
        first_events = load_json(RESULTS / "first/events.json")
        result["proposal_receipts_linked"] = all(
            set(row["candidate_ids"].split("|")) <= (article_ids & set(first_receipts))
            and any(e.get("proposal_record_id") == row["record_id"] for e in first_events)
            for row in first_rows)
        replay_summary = run_offline(queue_path, LEDGER, capture_path, BASELINE,
                                     RESULTS / "replay", RESULTS / "first/proposals.csv")
        replay_rows = proposal_rows(RESULTS / "replay/proposals.csv")
        result["replay_summary"] = replay_summary
        result["replay_added_proposals"] = len(replay_rows)
        result["replay_added_deaths"] = sum(int(row["deaths_delta"]) for row in replay_rows)
        expected = {"dnipro": ("2026-11-03", 2), "odesa": ("2026-11-09", 3)}
        correct = bool(first_rows) and all(
            (row["attack_date"], int(row["deaths_delta"])) == expected.get(row["city_key"])
            for row in first_rows)
        if (correct and result["proposal_receipts_linked"] and
                result["replay_added_proposals"] == 0 and
                result["replay_added_deaths"] == 0 and
                result["capture_summary"]["usable_evidence_packages"] >= 1):
            result["status"] = "PASS_REAL_AUTOMATED_OFFLINE"
        else:
            result["blocker"] = "NO_CORRECT_AUTO_PROPOSAL_OR_REPLAY_NONZERO"
        if result["status"] != "PASS_REAL_AUTOMATED_OFFLINE":
            result.setdefault("blocker", "NO_COMPLETE_AUTO_READY_PATH")
    except Exception as exc:
        result["blocker"] = type(exc).__name__
        result["error"] = str(exc)[:240]
    after = {str(p.relative_to(ROOT)): digest_file(p) for p in [SOURCES, LEDGER, BASELINE]}
    result["protected_inputs_unchanged"] = after == protected
    if not result["protected_inputs_unchanged"]:
        result["status"] = "BLOCKED"
        result["blocker"] = "PROTECTED_INPUT_MUTATED"
    write_json(RESULTS / "verdict.json", result)
    manifest = {"sha256": {str(p.relative_to(RESULTS)): digest_file(p)
                           for p in sorted(RESULTS.rglob("*")) if p.is_file()
                           and p.name != "manifest.json"},
                "protected_inputs_sha256": protected}
    write_json(RESULTS / "manifest.json", manifest)
    print(json.dumps({"verdict": result["status"], "capture": result.get("capture_summary"),
                      "review": result.get("review_summary"),
                      "replay_added_deaths": result.get("replay_added_deaths"),
                      "blocker": result.get("blocker"),
                      "artifact": str(RESULTS.relative_to(ROOT))}, ensure_ascii=False))
    return 0 if result["status"] == "PASS_REAL_AUTOMATED_OFFLINE" else 1


if __name__ == "__main__":
    sys.exit(main())
