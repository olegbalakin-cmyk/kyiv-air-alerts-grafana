#!/usr/bin/env python3
"""Hard assertions against REAL archived sources and unchanged Work A generator."""
import json
import sys
from pathlib import Path

def load(root,name):
    return json.loads((Path(root)/name).read_text(encoding="utf-8"))

ingest, worka = sys.argv[1:3]
summary=load(ingest,"summary.json")
cards=load(ingest,"fact_cards.json")
blocked=load(ingest,"blocked_clusters.json")
handoff=load(ingest,"work_a_reports.json")
real=load(worka,"summary.json")
proposals=load(worka,"proposals.json")
generator=load(worka,"generator_probe.json")
assert summary["external_publisher_http_requests"] == 0
assert summary["candidate_count"] == 1682
assert summary["parsed_fact_reports"] == 1
assert len(cards) == 1 and len(handoff["reports"]) == 1
card=cards[0]
assert card["candidate_id"] == "e0fba98b19473874e9a1d8f1"
assert card["incident"]["attack_date"] == "2026-10-10"
assert card["incident"]["city_key"] == "zaporizhzhia"
assert card["confirmed_total"] == 23
assert sorted(card["reported_totals"]) == [18,20,23]
assert card["attributed_official_origin_id"] == "dsns"
assert card["original_text_sha256"] == "011894b7c4bd906dcfd0c5d2f7cef07a932976ca313220fa9089999264feb259"
assert card["official_update_sentence_sha256"]
assert all(x.get("publication_allowed") is False for x in cards)
assert len(blocked) == 5 and sum(len(x["candidate_ids"]) for x in blocked) == 11
assert all(x["status"] == "NEEDS_REVIEW" and x["confirmed_deaths"] is None for x in blocked)
assert any("SAME_ORIGINAL_URL_NOT_INDEPENDENT_SOURCE" in x["reasons"] for x in blocked)
assert all("BASELINE_EVENT_ALLOCATION_UNKNOWN" in x["reasons"] for x in blocked if x["cluster_id"].startswith("sep_"))
assert any("LATE_DEATH_NEEDS_INDEPENDENT_OFFICIAL_CONFIRMATION" in x["reasons"] for x in blocked)
assert real["candidates_seen"] == 1682
assert real["auto_ready_candidates"] == 1
assert real["shadow_proposals"] == 1
assert len(proposals) == 1
assert proposals[0]["count_kind"] == "cumulative"
assert int(proposals[0]["deaths_delta"]) == 23
assert generator["status"] == "PASS" and generator["shadow_month"] == 23
assert generator["publication_allowed"] is False
print("EVIDENCE_INGESTION_OFFLINE_PASS: real archived source 18->20->23; Work A generator +23; 5 missing-source clusters held; no publisher HTTP or publication")
