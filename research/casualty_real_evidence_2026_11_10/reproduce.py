#!/usr/bin/env python3
"""Bounded real-news, fail-closed proof for the existing casualty auto-propose.
Only four retained excerpts; no network calls, labels, REVIEW, PROMOTE or writes
to the live queue/revisions. This script is a research fixture, not a pipeline.
"""
import csv
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
from casualty_auto_review import extract_cached_reports, run_offline

NUMBERS = {"один": 1, "одна": 1, "двоє": 2, "дві": 2, "троє": 3, "три": 3}
FATALITIES = (
    re.compile(r"\bзагинули\s+(двоє|троє|\d+)\s+люд", re.I),
    re.compile(r"\b(двоє|троє|\d+)\s+люд\w*\s+загинули\b", re.I),
)
CITY_NAMES = {"dnipro": "Дніпро", "odesa": "Одеса"}
PINNED_LEDGER_BLOB = "8d7a2e2540bf4bf0f8c6227023821390bf82ce13"


def git_blob_sha(content):
    return hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()


def retained_text(source):
    value = "\n".join(source["extracts"])
    actual = hashlib.sha256(value.encode("utf-8")).hexdigest()
    if actual != source["excerpt_sha256"]:
        raise ValueError("Excerpt changed: " + source["source_id"])
    return value


def lexical_signals(text):
    """Diagnostic hints only. NEVER used to set reviewer facts or statuses."""
    low = text.casefold()
    hits = []
    for pattern in FATALITIES:
        hits += [NUMBERS.get(m.group(1), int(m.group(1)) if m.group(1).isdigit() else None)
                 for m in pattern.finditer(low)]
    return {
        "death_total_mentions": sorted(set(hits)),
        "date_mentions_2026_11": sorted(set(re.findall(r"\b([0-3]?\d)\s+листопада\b", low))),
        "missile_mention": bool(re.search(r"ракет", low)),
        "drone_mention": bool(re.search(r"безпілотник|дрон", low)),
        "civilian_status_explicit": True if re.search(r"\bцивільн", low) else None,
        "attributed_origins": [name for pattern, name in
            ((r"\bдснс\b", "DSNS"), (r"прокуратур", "prosecutor"),
             (r"\bмва\b", "municipal-military-administration"))
            if re.search(pattern, low)],
        "separate_later_attack_mentioned": bool(re.search(r"повторно\s+атакував", low)),
    }


def shadow_inputs(sources):
    """Routing fields describe the articles, not facts about casualty eligibility."""
    queue, articles, observations = [], [], []
    for source in sources["articles"]:
        text = retained_text(source)
        url = source["url"]
        city = source["city_key"]
        if city not in CITY_NAMES or urlsplit(url).scheme != "https":
            raise ValueError("Unexpected article route")
        candidate_id = "real-excerpt-" + hashlib.sha256(url.encode()).hexdigest()[:20]
        queue.append({"candidate_id": candidate_id, "city_key": city,
                      "city": CITY_NAMES[city], "title": source["title"],
                      "snippet": "", "url": url, "publisher": source["publisher"],
                      "publisher_url": "https://" + urlsplit(url).hostname,
                      "published_at": source["published_date"], "status": "needs_review"})
        articles.append({"candidate_id": candidate_id, "url": url,
                         "text": text, "observed_at": sources["retrieved_date"]})
        observations.append({"source_id": source["source_id"], "case_id": source["case_id"],
                             "source_url": url, "excerpt_sha256": source["excerpt_sha256"],
                             "lexical_signals_only": lexical_signals(text)})
    return queue, articles, observations


def main():
    sources = json.loads((HERE / "sources.json").read_text(encoding="utf-8"))
    queue, articles, observations = shadow_inputs(sources)
    eligible_reports = extract_cached_reports(queue, articles)
    ledger = (HERE / "pinned_revisions.csv").read_bytes()
    if git_blob_sha(ledger) != PINNED_LEDGER_BLOB:
        raise ValueError("Pinned real revision snapshot is not the expected Git blob")
    base = HERE.parent / "casualty_automated_review_2026_11_10/baseline_coverage.json"
    if not base.is_file():
        raise ValueError("Pinned baseline missing")
    results = HERE / "results"
    results.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="casualty-real-excerpts-") as td:
        temp = Path(td)
        (temp / "queue.json").write_text(json.dumps(queue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (temp / "evidence.json").write_text(json.dumps({"schema_version": 1, "reports": [], "articles": articles},
                                                       ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in (temp/"queue.json", temp/"evidence.json", HERE/"pinned_revisions.csv", base)}
        first = run_offline(temp/"queue.json", HERE/"pinned_revisions.csv",
                            temp/"evidence.json", base, results/"first")
        replay = run_offline(temp/"queue.json", HERE/"pinned_revisions.csv",
                             temp/"evidence.json", base, results/"replay",
                             results/"first/proposals.csv")
        after = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in (temp/"queue.json", temp/"evidence.json", HERE/"pinned_revisions.csv", base)}
    if before != after:
        raise RuntimeError("Evidence/queue/ledger input was changed")
    if eligible_reports or first["auto_ready"] or first["unique_proposals"]:
        raise RuntimeError("Unsafe positive result from incomplete article excerpts")
    if first["messages_processed"] != 4 or first["needs_review"] != 4:
        raise RuntimeError("Unexpected source coverage")
    if replay != first:
        raise RuntimeError("Non-idempotent outcome on no-proposal replay")
    for name in ("events.json", "summary.json", "proposals.csv"):
        if (results/"first"/name).read_bytes() != (results/"replay"/name).read_bytes():
            raise RuntimeError("Replay differs: " + name)
    evidence = {
        "status": "NEGATIVE_PROOF_NEEDS_REVIEW",
        "source_count": len(sources["articles"]), "retained_excerpts_hashed": True,
        "auto_reports_from_real_excerpts": len(eligible_reports),
        "auto_proposals": first["unique_proposals"],
        "reviewer": first, "inputs_unchanged": True, "idempotent": True,
        "observations": observations,
        "limitation": "Excerpt-only proof; full HTTP documents not hashed or used. No explicit civilian status; exact timed/addressed identity absent.",
    }
    (results/"verdict.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": evidence["status"], "messages": first["messages_processed"],
                      "reports": len(eligible_reports), "proposals": first["unique_proposals"],
                      "replay_identical": True}, ensure_ascii=False))
    return evidence


if __name__ == "__main__":
    main()
