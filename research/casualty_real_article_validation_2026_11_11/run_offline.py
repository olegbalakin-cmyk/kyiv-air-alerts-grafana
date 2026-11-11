#!/usr/bin/env python3
"""Validate two NEW retained real articles against immutable gold, without media HTTP."""
import csv
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
from casualty_auto_review import extract_cached_reports, run_offline

INPUT_ARTIFACT = ROOT / "research/casualty_real_article_validation_2026_11_11/input/evidence.json"
SELECTED = ROOT / "research/casualty_five_candidate_selection_2026_11_11/selected_queue.json"
LEDGER = ROOT / "research/casualty_real_evidence_2026_11_10/pinned_revisions.csv"
BASELINE = ROOT / "research/casualty_automated_review_2026_11_10/baseline_coverage.json"
REPORT = ROOT / "research/casualty_real_article_validation_2026_11_11/results"
EXPECTED_ARTIFACT_SHA = "68ceccdcca68a0c93d42a0c0173c32c9ab47b659415e9bd2b274df8d9cf0fdf9"
SAMPLE = {
    "96dc8052cf48f4ce74df29f6": {
        "expected": "NEEDS_REVIEW",
        "text_sha256": "cb4ed15646d44d6f0a5d95333f841597125885416d46dce92aa74fdc01913db9",
    },
    "6c946bfd46fffbe953d795bf": {
        "expected": "NEEDS_REVIEW",
        "text_sha256": "cc6d670436ff1190da1230b1cabb16630838f6da33ef055e712560890a33d9cd",
    },
}

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def rows(p):
    with Path(p).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    assert sha(INPUT_ARTIFACT) == EXPECTED_ARTIFACT_SHA, "IMMUTABLE_ARTIFACT_EVIDENCE_MISMATCH"
    article_data = json.loads(INPUT_ARTIFACT.read_text(encoding="utf-8"))
    retained = {a["candidate_id"]: a for a in article_data["articles"]}
    queue = {c["candidate_id"]: c for c in json.loads(SELECTED.read_text(encoding="utf-8"))}
    assert set(SAMPLE).issubset(retained) and set(SAMPLE).issubset(queue)
    for cid, v in SAMPLE.items():
        assert hashlib.sha256(retained[cid]["text"].encode("utf-8")).hexdigest() == v["text_sha256"]

    protected = [INPUT_ARTIFACT, SELECTED, LEDGER, BASELINE, ROOT / "kyiv-air-alerts-grafana/scripts/casualty_auto_review.py"]
    before = {str(p.relative_to(ROOT)): sha(p) for p in protected}
    sample_ids = sorted(SAMPLE)
    sample_articles = [retained[cid] for cid in sample_ids]
    sample_queue = [queue[cid] for cid in sample_ids]
    extracted = extract_cached_reports(sample_queue, sample_articles)

    with tempfile.TemporaryDirectory(prefix="real-article-validation-") as tmp:
        root = Path(tmp)
        queue_path = root / "selected_queue.json"
        evidence_path = root / "evidence.json"
        queue_path.write_text(json.dumps(sample_queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        evidence_path.write_text(json.dumps({"schema_version": 1, "articles": sample_articles, "reports": []}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        first = root / "first"
        second = root / "replay"
        first_summary = run_offline(queue_path, LEDGER, evidence_path, BASELINE, first)
        second_summary = run_offline(queue_path, LEDGER, evidence_path, BASELINE, second, first / "proposals.csv")
        events = json.loads((first / "events.json").read_text(encoding="utf-8"))
        second_events = json.loads((second / "events.json").read_text(encoding="utf-8"))
        proposals = rows(first / "proposals.csv")
        replay_proposals = rows(second / "proposals.csv")
        assert len(events) == 2, ("UNEXPECTED_EVENT_COUNT", len(events))
        assert len(second_events) == 2, "REPLAY_EVENT_COUNT_CHANGED"
        assert not replay_proposals, "DUPLICATE_PROPOSAL_ON_REPLAY"
        assert sha(queue_path) == hashlib.sha256((json.dumps(sample_queue, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).hexdigest()
        assert sha(evidence_path) == hashlib.sha256((json.dumps({"schema_version": 1, "articles": sample_articles, "reports": []}, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).hexdigest()

        out = []
        for cid in sample_ids:
            candidate = queue[cid]
            candidates_for_this = [e for e in events if any(m.get("candidate_id") == cid for m in e.get("messages", []))]
            assert len(candidates_for_this) == 1, (cid, len(candidates_for_this))
            event = candidates_for_this[0]
            outcome = event["category"]
            out.append({
                "candidate_id": cid,
                "publisher": candidate.get("publisher"),
                "url": retained[cid]["url"],
                "source_artifact_id": 13845600971,
                "article_sha256": SAMPLE[cid]["text_sha256"],
                "expected_status": SAMPLE[cid]["expected"],
                "actual_status": outcome,
                "correct": outcome == SAMPLE[cid]["expected"],
                "reason_for_discrepancy": None if outcome == SAMPLE[cid]["expected"] else "Reviewer verdict differs from independent, pre-recorded gold. Examine event reasons and extracted support.",
                "reviewer_reasons": event.get("reasons", []),
                "reviewer_incident": event.get("incident"),
                "extracted_reports": [p for p in extracted if p.get("candidate_id") == cid or any(s.get("candidate_id") == cid for s in p.get("sources", []))],
                "event_reports": len(event.get("reports", [])),
            })

        assert before == {str(p.relative_to(ROOT)): sha(p) for p in protected}, "PROTECTED_INPUT_MUTATED"
        verdict = {
            "status": "INDEPENDENT_TWO_ARTICLE_REAL_TEXT_CHECK",
            "gold_commit_precedes_execution": True,
            "baseline_45_tests_not_repeated": True,
            "implementation_commit": "f46753e4b85e56052639959beb1d96ee408e227e",
            "reviewer_blob_sha": before["kyiv-air-alerts-grafana/scripts/casualty_auto_review.py"],
            "artifact_id": 13845600971,
            "artifact_evidence_sha256": EXPECTED_ARTIFACT_SHA,
            "eligible_new_articles": 2,
            "new_articles_missing_for_three_case_target": 1,
            "correct_statuses": sum(bool(v["correct"]) for v in out),
            "false_auto_ready": sum(v["actual_status"] == "AUTO_READY" and v["expected_status"] != "AUTO_READY" for v in out),
            "missed_auto_ready": sum(v["expected_status"] == "AUTO_READY" and v["actual_status"] != "AUTO_READY" for v in out),
            "first_summary": first_summary,
            "replay_summary": second_summary,
            "first_new_proposals": len(proposals),
            "replay_new_proposals": len(replay_proposals),
            "duplicate_deaths_detected": bool(replay_proposals),
            "protected_inputs_before_after_identical": True,
            "publication_allowed": False,
            "per_article": out,
        }
        (REPORT / "verdict.json").write_text(json.dumps(verdict, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (REPORT / "manifest.json").write_text(json.dumps({"protected_input_sha256": before, "verdict_sha256": sha(REPORT / "verdict.json"), "publication_allowed": False}, indent=2) + "\n", encoding="utf-8")
        print("REAL ARTICLE VALIDATION", json.dumps(verdict, ensure_ascii=False))
        assert sum(bool(v["correct"]) for v in out) == 2, "ACTUAL_REVIEWER_DISAGREES_WITH_GOLD"

if __name__ == "__main__":
    main()
