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
            "--max-evidence-urls", "4", "--auto-propose-output", str(output),
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
        first = monitor_call(queue_path, capture_path, RESULTS / "first")
        result["first_command"] = first
        if first["exit_code"]:
            result["blocker"] = "MONITOR_COMMAND_FAILED"
        else:
            capture = load_json(capture_path)
            summary = load_json(RESULTS / "first/summary.json")
            first_rows = proposal_rows(RESULTS / "first/proposals.csv")
            result["capture_summary"] = capture["last_capture_summary"]
            result["failed_sources"] = capture["failures"]
            result["review_summary"] = summary
            result["proposals"] = [{"city_key": p["city_key"], "attack_date": p["attack_date"],
                                   "deaths_delta": p["deaths_delta"], "candidate_ids": p["candidate_ids"],
                                   "record_id": p["record_id"]} for p in first_rows]
            first_receipts = {c["candidate_id"]: c for c in capture["receipts"]}
            # No candidate may be minted by the capture adapter.
            if any(a["candidate_id"] not in {q["candidate_id"] for q in original_queue}
                   for a in capture["articles"]):
                raise RuntimeError("Capture produced a foreign candidate ID")
            first_links_ok = all(set(p["candidate_ids"].split("|")) <= set(first_receipts)
                                 for p in first_rows)
            result["proposal_receipts_linked"] = first_links_ok

            replay = monitor_call(queue_path, capture_path, RESULTS / "replay",
                                  RESULTS / "first/proposals.csv")
            result["replay_command"] = replay
            if replay["exit_code"]:
                result["blocker"] = "REPLAY_COMMAND_FAILED"
            else:
                replay_rows = proposal_rows(RESULTS / "replay/proposals.csv")
                result["replay_added_proposals"] = len(replay_rows)
                result["replay_added_deaths"] = sum(int(p["deaths_delta"]) for p in replay_rows)
                result["replay_summary"] = load_json(RESULTS / "replay/summary.json")
                result["repeat_capture_summary"] = load_json(capture_path)["last_capture_summary"]
                expected = {"dnipro": 2, "odesa": 3}
                correct = bool(first_rows) and all(
                    int(p["deaths_delta"]) == expected.get(p["city_key"], -1)
                    for p in first_rows)
                if (correct and first_links_ok and
                        result["replay_added_proposals"] == 0 and
                        result["replay_added_deaths"] == 0 and
                        result["capture_summary"]["usable_evidence_packages"] >= 1):
                    result["status"] = "PASS_REAL_AUTOMATED_OFFLINE"
                else:
                    result["blocker"] = "NO_CORRECT_FULL_CHAIN_AUTO_PROPOSAL_OR_REPLAY_NONZERO"
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
