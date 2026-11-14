"""Work AA: offline re-index of the *saved* Work Z short extracts, not fresh HTML."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from research.casualty_evidence_ingestion_2026_11_13 import workx_evidence as x

TARGETS = ("T03", "T04", "T05")
EXPECTED_ZIP_SHA = "ea32abf6eaab69656608b891b272eef6f54ee286844d1f9f2fba217e64e117b8"


def compact_existing(facts: dict, receipts: dict) -> dict:
    """No regenerated text. Only verify/retain what Work Z physically saved."""
    if facts.get("publication_allowed") is not False or facts.get("automatic_credits") != 0:
        raise ValueError("UNSAFE_SAVED_ARCHIVE")
    cards = facts.get("facts")
    targets = receipts.get("targets")
    if len(cards) != 3 or len(targets) != 3:
        raise ValueError("EXPECTED_THREE_SAVED_SOURCES")
    by_url = {}
    for t in targets:
        target = t["target_id"]
        if target not in TARGETS or target in by_url:
            raise ValueError("UNEXPECTED_OR_DUPLICATE_TARGET")
        receipt = t["receipt"]
        by_url[target] = {
            "url": receipt["resolved_url"], "response_sha256": receipt["response_sha256"],
            "capture_time_utc": receipt.get("capture_time_utc"),
            "http_status": receipt["http_status"],
        }
    saved = []
    for target in TARGETS:
        info = by_url[target]
        matches = [c for c in cards if c.get("source_url") == info["url"]]
        if len(matches) != 1:
            raise ValueError("SOURCE_CARD_RECEIPT_MISMATCH")
        original = matches[0]
        if original.get("document_sha256") != info["response_sha256"]:
            raise ValueError("SOURCE_RESPONSE_SHA_MISMATCH")
        card = dict(original)
        card["source_capture_time_utc"] = info["capture_time_utc"]
        # Work Z did not retain the raw page, so excerpts are not reconstructed.
        review = dict(card.get("incident_review") or {})
        mentions = []
        for m in review.get("evidence_mentions") or []:
            m = dict(m)
            q = m.get("excerpt")
            if not isinstance(q, str) or hashlib.sha256(q.encode()).hexdigest() != m.get("excerpt_sha256"):
                raise ValueError("WORKZ_CONTEXT_HASH_MISMATCH")
            # Legal abbreviation fragment is not a complete sentence.
            if q.rstrip().endswith(("(ч.", "(ст.", "(р.")):
                m["context_status"] = "CONTEXT_INCOMPLETE"
                m["sentence_sha256"] = m["excerpt_sha256"]
                m.pop("excerpt", None)
                m.pop("excerpt_sha256", None)
            mentions.append(m)
        review["evidence_mentions"] = mentions
        card["incident_review"] = review
        for item in card.get("excerpts") or []:
            if x._sha(item["text"]) != item["excerpt_sha256"]:
                raise ValueError("WORKZ_EXCERPT_HASH_MISMATCH")
        saved.append(card)
    compact = x.build_review_index({
        "facts": saved, "publication_allowed": False, "automatic_credits": 0,
    }, include_unretained=False)
    if len(compact["cards"]) != 3:
        raise ValueError("UNEXPECTED_INDEX_CARD_COUNT")
    names = [t["target_id"] for t in targets]
    pairs = {}
    for a,b in (("T03","T04"),("T03","T05"),("T04","T05")):
        pairs[a+"-"+b] = "INSUFFICIENT_EVIDENCE"
    return {
        "schema": "casualty-workaa-offline-archive-review-v1",
        "original_source_artifact_sha256": EXPECTED_ZIP_SHA,
        "archive_scope": "SAVED_FACT_CARDS_ONLY_NO_FULL_HTML",
        "target_ids": names,
        "evidence_index": compact,
        "pair_decisions": pairs,
        "attack_date": "UNKNOWN",
        "cross_source_event_link": "NOT_INDEPENDENTLY_PROVEN",
        "two_to_three_change": "PLAUSIBLE_NOT_ESTABLISHED",
        "publication_allowed": False, "automatic_credits": 0,
        "production_mutations": 0, "source_get": 0,
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--zip-sha", required=True)
    p.add_argument("--facts", type=Path, required=True)
    p.add_argument("--receipts", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    if args.zip_sha != EXPECTED_ZIP_SHA:
        raise ValueError("WORKZ_ZIP_HASH_UNVERIFIED")
    manifest = json.loads(args.manifest.read_text())
    for filename, digest in manifest["files_sha256"].items():
        fn = args.manifest.parent / filename
        if hashlib.sha256(fn.read_bytes()).hexdigest() != digest:
            raise ValueError("WORKZ_INNER_HASH_MISMATCH:" + filename)
    report = compact_existing(json.loads(args.facts.read_text()),
                              json.loads(args.receipts.read_text()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print("WORKAA_ARCHIVE_OFFLINE_PASS", report["evidence_index"]["summary"])


if __name__ == "__main__":
    main()
