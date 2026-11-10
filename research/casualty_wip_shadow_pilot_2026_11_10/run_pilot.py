#!/usr/bin/env python3
"""One-shot WIP casualty shadow pilot on a frozen, real candidate queue.

No source search, WIP queue/state writes, REVIEW/PROMOTE, or publication.
All network requests go through existing opt-in capture-evidence-only monitor.
"""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "kyiv-air-alerts-grafana/data/casualties"
QUEUE = DATA / "multicity_review_queue.json"
LAST_RUN = DATA / "candidate_monitor_last_run.json"
STATE = DATA / "candidate_monitor_state.json"
WIP_LEDGER = DATA / "revisions.csv"
MONITOR = ROOT / "kyiv-air-alerts-grafana/scripts/monitor_casualty_candidates.py"
PINNED_LEDGER = ROOT / "research/casualty_real_evidence_2026_11_10/pinned_revisions.csv"
BASELINE = ROOT / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"
OUT = ROOT / "research/casualty_wip_shadow_pilot_2026_11_10/results"
EXPECTED_QUEUE_BLOB = "73928294881fba2c70eabc28fe85e4146d465a95"
EXPECTED_LAST_RUN_BLOB = "6d2d170c14b58093c0887e11347701f179d88fab"
SINCE = "2026-11-03"
LIMIT = 20


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_blob(path: Path) -> str:
    return subprocess.check_output(["git", "hash-object", str(path)],
                                   cwd=ROOT, text=True).strip()


def put(name: str, value) -> None:
    dest = OUT / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def select_candidates(rows):
    """Recent needs_review candidates, deterministic, geographically diverse.

    Select one per city first, then fill from newest remaining candidates.
    No synthetic article, no facts, no selection by anticipated death count.
    """
    recent = [
        c for c in rows
        if isinstance(c, dict)
        and c.get("status") == "needs_review"
        and c.get("source") == "Google News RSS"
        and str(c.get("first_discovered_at") or "")[:10] >= SINCE
        and str(c.get("url") or "").startswith("https://")
        and c.get("candidate_id") and c.get("city_key")
    ]
    recent.sort(key=lambda c: (
        str(c.get("first_discovered_at") or ""),
        str(c.get("candidate_id") or "")), reverse=True)
    chosen = []
    seen_ids = set()
    seen_cities = set()
    for c in recent:
        if c["city_key"] not in seen_cities and c["candidate_id"] not in seen_ids:
            chosen.append(c)
            seen_ids.add(c["candidate_id"])
            seen_cities.add(c["city_key"])
        if len(chosen) == LIMIT:
            break
    if len(chosen) < LIMIT:
        for c in recent:
            if c["candidate_id"] not in seen_ids:
                chosen.append(c)
                seen_ids.add(c["candidate_id"])
            if len(chosen) == LIMIT:
                break
    return chosen, len(recent)


def csv_rows(path: Path):
    if not path.is_file():
        raise RuntimeError("REVIEWER_PROPOSALS_CSV_MISSING")
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def run():
    OUT.mkdir(parents=True, exist_ok=True)
    verdict = {"status": "BLOCKED", "scope": "one bounded WIP candidate-queue shadow snapshot",
               "research_only": True, "publication_allowed": False,
               "production_modified": False, "source_search_performed": False,
               "max_candidate_urls": LIMIT, "max_http_requests": 40,
               "sample_since": SINCE}
    protected = [QUEUE, LAST_RUN, STATE, WIP_LEDGER, PINNED_LEDGER, BASELINE]
    before = {}
    try:
        before = {str(p.relative_to(ROOT)): digest(p) for p in protected}
        if git_blob(QUEUE) != EXPECTED_QUEUE_BLOB:
            raise RuntimeError("WIP_QUEUE_GIT_BLOB_MISMATCH")
        if git_blob(LAST_RUN) != EXPECTED_LAST_RUN_BLOB:
            raise RuntimeError("WIP_LAST_RUN_BLOB_MISMATCH")
        last_run = load(LAST_RUN)
        if last_run.get("review_queue_size") != 1656 or last_run.get("started_at", "")[:10] != "2026-11-10":
            raise RuntimeError("UNEXPECTED_WIP_LAST_RUN")
        rows = load(QUEUE)
        if len(rows) != last_run["review_queue_size"]:
            raise RuntimeError("WIP_QUEUE_COUNT_MISMATCH")
        selected, recent_count = select_candidates(rows)
        if not selected:
            raise RuntimeError("NO_RECENT_UNREVIEWED_WIP_CANDIDATES")
        put("selected_queue.json", selected)
        verdict["queue"] = {
            "source": "unchanged WIP branch snapshot",
            "git_blob": EXPECTED_QUEUE_BLOB, "last_run_at": last_run["started_at"],
            "full_queue_candidates": len(rows),
            "recent_unreviewed_candidates": recent_count,
            "sampled_candidate_count": len(selected),
            "distinct_urls": len({c["url"] for c in selected}),
            "cities": dict(sorted(Counter(c["city_key"] for c in selected).items())),
        }
        evidence = OUT / "evidence.json"
        first_dir = OUT / "first"
        cmd = [
            sys.executable, str(MONITOR), "--capture-evidence-only",
            "--evidence-queue", str(OUT / "selected_queue.json"),
            "--evidence-output", str(evidence),
            "--max-evidence-urls", str(len(selected)),
            "--auto-propose-output", str(first_dir),
            "--revision-snapshot", str(PINNED_LEDGER),
            "--baseline-snapshot", str(BASELINE),
        ]
        proc = subprocess.run(cmd, cwd=ROOT, capture_output=True,
                              text=True, timeout=1050)
        if proc.returncode != 0:
            raise RuntimeError("ISOLATED_MONITOR_FAILED_" + str(proc.returncode))
        monitor_out = json.loads(proc.stdout)
        capture = monitor_out["evidence_capture"]
        initial_review = monitor_out["auto_propose"]
        verdict["capture"] = capture
        verdict["review"] = initial_review
        proof = load(evidence)
        candidate_ids = {x["candidate_id"] for x in selected}
        article_ids = {x["candidate_id"] for x in proof["articles"]}
        receipt_ids = {x["candidate_id"] for x in proof.get("receipts", [])}
        if not article_ids <= (candidate_ids & receipt_ids):
            raise RuntimeError("EVIDENCE_HAS_FOREIGN_OR_UNLINKED_CANDIDATES")
        fail_counts = Counter(x.get("reason", "UNKNOWN") for x in proof.get("failures", []))
        verdict["capture_failures_by_reason"] = dict(sorted(fail_counts.items()))
        first_proposals = csv_rows(first_dir / "proposals.csv")
        if int(initial_review["unique_proposals"]) != len(first_proposals):
            raise RuntimeError("PROPOSAL_COUNT_DISAGREEMENT")
        for p in first_proposals:
            linked = set(x for x in str(p.get("candidate_ids", "")).split("|") if x)
            if not linked or not linked <= article_ids:
                raise RuntimeError("PROPOSAL_WITHOUT_FETCHED_EVIDENCE")
        verdict["proposals"] = [{
            "record_id": x.get("record_id"),
            "city_key": x.get("city_key"),
            "attack_date": x.get("attack_date"),
            "deaths_delta": x.get("deaths_delta"),
            "candidate_ids": x.get("candidate_ids"),
        } for x in first_proposals]
        sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
        from casualty_auto_review import run_offline
        replay = run_offline(
            OUT / "selected_queue.json", PINNED_LEDGER, evidence, BASELINE,
            OUT / "replay", first_dir / "proposals.csv"
        )
        replay_rows = csv_rows(OUT / "replay/proposals.csv")
        verdict["replay"] = replay
        verdict["replay_added_proposals"] = len(replay_rows)
        verdict["replay_added_deaths"] = sum(int(x["deaths_delta"]) for x in replay_rows)
        if replay_rows or replay.get("unique_proposals", 0) != 0:
            raise RuntimeError("DUPLICATE_PROPOSAL_ON_REPLAY")
        verdict["status"] = "PASS_SHADOW_PILOT" if capture.get("usable_evidence_packages", 0) > 0 else "BLOCKED_NO_USABLE_EVIDENCE"
    except Exception as exc:
        verdict["status"] = "BLOCKED"
        verdict["blocker"] = type(exc).__name__ + ":" + str(exc)[:150]
    finally:
        try:
            after = {str(p.relative_to(ROOT)): digest(p) for p in protected}
            verdict["protected_inputs_unchanged"] = after == before
            if after != before:
                verdict["status"] = "BLOCKED"
                verdict["blocker"] = "PROTECTED_WIP_INPUT_CHANGED"
            verdict["protected_sha256"] = before
        except Exception:
            verdict["status"] = "BLOCKED"
            verdict["blocker"] = "PROTECTED_INPUT_RECHECK_FAILED"
        put("verdict.json", verdict)
        manifest = {
            "file_sha256": {str(p.relative_to(OUT)): digest(p)
                            for p in sorted(OUT.rglob("*")) if p.is_file()
                            and p.name != "manifest.json"},
            "publication_allowed": False,
            "production_modified": False,
        }
        put("manifest.json", manifest)
        print(json.dumps({
            "status": verdict["status"], "queue": verdict.get("queue"),
            "capture": verdict.get("capture"), "review": verdict.get("review"),
            "replay_added_proposals": verdict.get("replay_added_proposals"),
            "replay_added_deaths": verdict.get("replay_added_deaths"),
            "failures_by_reason": verdict.get("capture_failures_by_reason"),
            "protected_inputs_unchanged": verdict.get("protected_inputs_unchanged"),
            "blocker": verdict.get("blocker"),
        }, ensure_ascii=False))
    return 0 if verdict["status"] == "PASS_SHADOW_PILOT" else 1


if __name__ == "__main__":
    sys.exit(run())
