"""Work X regression suite: OFFLINE, including retained Work P/Work V archives in CI.

Synthetic examples are expressly *not* factual confirmations. Source-backed
claims are checked only using GitHub's previously accepted proof artifacts.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from research.casualty_evidence_ingestion_2026_11_13 import workx_evidence as x
from research.casualty_evidence_ingestion_2026_11_13 import ingest as existing

UTC = timezone.utc
SOURCE = "https://www.ukrinform.ua/simulation-not-real-source"
CITY = "zaporizhzhia"


def fact(cid="offline-simulator", *, url=SOURCE, total=2,
         kind="single_report_total", date="2026-10-22",
         reasons=None, excerpt="Загинули двоє людей."):
    # Explicitly synthetic; SHA checks validate the index, not the claim.
    return {
        "candidate_id": cid, "source_url": url,
        "source_role": "publisher", "publication_date": "2026-10-23T13:00:00Z",
        "attack_date_explicit": date, "city_key_candidate_not_verified": CITY,
        "claim_deaths": total, "count_kind": kind,
        "document_sha256": "a" * 64, "extracted_text_sha256": "b" * 64,
        "excerpts": ([{"text": excerpt, "excerpt_sha256": x._sha(excerpt),
                      "claim_number": total}] if excerpt else []),
        "decision": "NEEDS_REVIEW", "publication_allowed": False,
        "reasons": reasons or [],
        "incident_review": {"status": "INSUFFICIENT_EVIDENCE",
                            "locality_verified": None,
                            "attack_time_verified": None,
                            "struck_object_verified": None,
                            "evidence_mentions": []},
    }


def index(cards, queue=None, previous=None):
    return x.build_review_index(
        {"publication_allowed": False, "automatic_credits": 0, "facts": cards},
        queue=queue, previous=previous)


class WorkXRetainedEvidence(unittest.TestCase):
    def test_01_source_type_and_two_dates_are_separate(self):
        c = fact()
        result = index([c])["cards"][0]
        self.assertEqual(result["source_type"], "EDITORIAL_OR_OTHER_UNVERIFIED")
        self.assertEqual(result["publication_date_claimed"], "2026-10-23T13:00:00Z")
        self.assertEqual(result["attack_date_claimed_not_verified"], "2026-10-22")
        self.assertEqual(result["decision"], "NEEDS_REVIEW")
        self.assertIsNone(result["incident_id"])
        self.assertEqual(x.source_type("https://zp.npu.gov.ua/news/example"), "POLICE")
        self.assertEqual(x.source_type("https://dsns.gov.ua/a"), "EMERGENCY_SERVICE")
        self.assertEqual(x.source_type("https://city.gov.ua/a"), "GOVERNMENT_OR_LOCAL_AUTHORITY")
        self.assertEqual(x.source_type("https://news.google.com/a"), "AGGREGATOR_NOT_PRIMARY")

    def test_02_original_URL_and_replay_never_double_credit(self):
        first = index([fact("T01")])["cards"]
        second = index([fact("T02")], previous=first)
        self.assertEqual(second["summary"]["duplicate_source_replay"], 1)
        self.assertEqual(second["cards"][0]["prior_message_candidate_id_same_url_only"], "T01")
        self.assertEqual(second["cards"][0]["automatic_credits"], 0)
        self.assertIsNone(second["cards"][0]["incident_id"])

    def test_03_changed_article_is_a_review_hint_not_incident_link(self):
        first = index([fact("T01")])["cards"]
        updated = fact("T02", total=3)
        updated["document_sha256"] = "c" * 64
        row = index([updated], previous=first)["cards"][0]
        self.assertEqual(row["decision"], "NEEDS_REVIEW")
        self.assertIn("SAME_URL_POSSIBLE_UPDATED_REPORT_NOT_EVENT_PROOF", row["reasons"])
        self.assertIsNone(row["incident_id"])

    def test_04_two_attacks_same_city_and_day_remain_distinct(self):
        a = fact("attack-A", url="https://www.ukrinform.ua/a")
        b = fact("attack-B", url="https://mig.com.ua/b", total=3)
        result = index([a, b])
        self.assertEqual(result["summary"]["needs_review"], 2)
        self.assertEqual(result["summary"]["automatically_linked_incidents"], 0)
        self.assertTrue(all(v["prior_message_candidate_id_same_url_only"] is None
                            for v in result["cards"]))

    def test_05_multi_attack_article_never_assigns_combined_total(self):
        c = fact("many", total=7, reasons=["MULTIPLE_POSSIBLE_INCIDENTS"])
        row = index([c])["cards"][0]
        self.assertIsNone(row["fatal_total_claimed_not_credited"])
        self.assertIn("CANNOT_ATTRIBUTE_TOTAL_TO_ONE_ATTACK", row["reasons"])

    def test_06_hospital_late_death_not_new_incident(self):
        c = fact("hospital", total=None, kind="ADDITIONAL_DEATH_REPORTED",
                 excerpt="Пізніше стало відомо, що загинула також жінка.")
        row = index([c])["cards"][0]
        self.assertIsNone(row["incident_id"])
        self.assertIsNone(row["fatal_total_claimed_not_credited"])
        self.assertIn("LATE_DEATH_REQUIRES_INCIDENT_LINK_AND_BASELINE", row["reasons"])

    def test_07_missing_text_http200_or_conflict_fail_closed(self):
        c = fact()
        c["excerpts"] = []
        c["document_sha256"] = None
        row = index([c])["cards"][0]
        self.assertIn("RESPONSE_SHA256_NOT_RETAINED", row["reasons"])
        self.assertIn("VERIFIABLE_SOURCE_EXCERPT_MISSING", row["reasons"])
        self.assertEqual(row["automatic_credits"], 0)
        conflict = fact(reasons=["CONFLICTING_FATAL_TOTALS"])
        self.assertIsNone(index([conflict])["cards"][0]["fatal_total_claimed_not_credited"])
        blank = index([], queue=[{"candidate_id": "rss-only", "city_key": CITY,
                                  "url": "https://news.google.com/a",
                                  "title": "This is not death evidence"}])
        self.assertIn("SOURCE_TEXT_NOT_RETAINED", blank["cards"][0]["reasons"])

    def test_08_privacy_hash_and_upstream_fail_closed(self):
        c = fact()
        c["excerpts"][0]["excerpt_sha256"] = "f" * 64
        r = index([c])["cards"][0]
        self.assertEqual(r["source_excerpts"], [])
        self.assertIn("EVIDENCE_EXCERPT_UNSAFE_OR_HASH_MISMATCH", r["reasons"])
        c = fact()
        c["decision"] = "AUTO_READY"
        with self.assertRaisesRegex(ValueError, "UPSTREAM_FACT_NOT_FAIL_CLOSED"):
            index([c])
        with self.assertRaisesRegex(ValueError, "UNSAFE_UPSTREAM"):
            x.build_review_index({"facts": [], "publication_allowed": True,
                                  "automatic_credits": 0})

    def test_09_preserved_work_J_fact_parser_with_real_WQ_wording(self):
        # Saved Work Q excerpt: this is not reconstructed full HTML.
        from research.casualty_workq_real_excerpts_2026_11_14.test_workq import card
        t03 = card("Загинули двоє людей.")
        t04 = card("Пізніше стало відомо, що загинула також 69-річна жінка.")
        self.assertEqual(t03["claim_deaths"], 2)
        self.assertIsNone(t04["claim_deaths"])
        self.assertEqual(t04["claim_type"], "ADDITIONAL_DEATH_REPORTED")
        t03["candidate_id"], t04["candidate_id"] = "T03", "T04"
        t04["source_url"] = "https://mig.com.ua/simulation-other-article"
        result = index([t03, t04])
        self.assertEqual(result["summary"]["automatically_linked_incidents"], 0)
        self.assertEqual(result["summary"]["automatic_credits"], 0)

    def test_10_no_rebuilt_html_or_count_from_RSS_title(self):
        c = fact()
        c["text"] = "SENSITIVE FULL SOURCE BODY THAT MUST NOT BE SAVED"
        r = index([c])["cards"][0]
        self.assertFalse(any(k in r for k in ("text", "body", "html", "page_title")))
        self.assertTrue(all(len(e["text"]) <= 170 for e in r["source_excerpts"]))
        self.assertIsNone(r["incident_identity_proof"])

    def test_11_real_saved_WorkP_source_cards_not_AUTO_READY(self):
        path = os.getenv("WORKX_WORKP_FACTS")
        if not path:
            self.skipTest("Real retained Work P artifact provided by exact-head CI")
        p = Path(path)
        self.assertTrue(p.is_file(), p)
        source = json.loads(p.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(source.get("facts") or []), 3)
        result = x.build_review_index(source)
        self.assertGreaterEqual(result["summary"]["needs_review"], 3)
        self.assertEqual(result["summary"]["automatically_linked_incidents"], 0)
        self.assertEqual(result["summary"]["automatic_credits"], 0)
        self.assertTrue(all(z["incident_id"] is None for z in result["cards"]))
        self.assertTrue(all(z["publication_allowed"] is False for z in result["cards"]))
        self.assertTrue(any(z["source_type"] == "POLICE" for z in result["cards"]))
        self.assertTrue(any(z["source_type"] == "EDITORIAL_OR_OTHER_UNVERIFIED"
                            for z in result["cards"]))

    def test_12_existing_WorkV_real_source_backed_proof_18_to_23(self):
        path = os.getenv("WORKX_WORKV_RESULT")
        if not path:
            self.skipTest("Accepted Work V archive provided by exact-head CI")
        source = json.loads(Path(path).read_text(encoding="utf-8"))
        self.assertEqual(source["status"], "PASS")
        self.assertEqual(source["latest_total"], 23)
        self.assertEqual([z["review_increment"] for z in source["effective_progression"]],
                         [18, 2, 3])
        self.assertEqual(source["replay_increment"], 0)
        self.assertEqual(source["production_mutations"], 0)


    def test_17_workr_text_is_retained_by_workx_with_matching_sha(self):
        quote = "Вранці 22 жовтня в [ГЕО] зафіксовано наслідки удару."
        c = fact()
        c["incident_review"]["evidence_mentions"] = [{
            "article_sentence_order": 7,
            "tags": ["DATE_MENTION_NOT_ATTACK_DATE"],
            "excerpt": quote, "excerpt_sha256": x._sha(quote),
        }]
        row = index([c])["cards"][0]
        self.assertEqual(row["unverified_context"][0]["excerpt"], quote)
        self.assertEqual(row["unverified_context"][0]["excerpt_sha256"], x._sha(quote))
        self.assertEqual(row["decision"], "NEEDS_REVIEW")
        self.assertIsNone(row["incident_id"])

    def test_18_bad_context_hash_and_private_context_fail_closed(self):
        c = fact()
        c["incident_review"]["evidence_mentions"] = [{
            "article_sentence_order": 1, "tags": ["DATE_MENTION_NOT_ATTACK_DATE"],
            "excerpt": "Про місце удару повідомила поліція.",
            "excerpt_sha256": "a" * 64,
        }]
        row = index([c])["cards"][0]
        self.assertEqual(row["unverified_context"], [])
        self.assertIn("CONTEXT_EXCERPT_UNSAFE_OR_HASH_MISMATCH", row["reasons"])
        self.assertEqual(row["automatic_credits"], 0)

    def test_19_new_one_shot_branch_requires_explicit_workx_grant(self):
        from research.casualty_one_time_capture_2026_11_13 import run_capture as r
        self.assertEqual(r.EXPECTED_BRANCH, "research-casualty-workr-identity-2026-11-14")
        with self.assertRaisesRegex(RuntimeError, "WORKZ_WORKX_HEAD_MISMATCH"):
            r._pilot_branch({"workz_evidence_pilot": True})
        with self.assertRaisesRegex(RuntimeError, "WORKZ_NOT_EXPLICITLY_AUTHORIZED"):
            r._pilot_branch({"workx_head_sha": r.WORKX_HEAD})
        self.assertEqual(
            r._pilot_branch({"workz_evidence_pilot": True,
                             "workx_head_sha": r.WORKX_HEAD}), r.WORKZ_BRANCH)

    def test_20_in_memory_context_keeps_later_correction(self):
        from research.casualty_one_time_capture_2026_11_13 import run_capture as r
        text = ("Удень 22 жовтня російська ракета влучила у приватний будинок у Запоріжжі. "
                "Спочатку повідомили про двох загиблих людей. "
                + "Повідомлення про наслідки удару уточнюється. " * 16
                + "Пізніше стало відомо, що загинула також 69-річна жінка. "
                "Поліція повідомила про трьох загиблих людей.")
        proof = r.retain_incident_review_clues(text)
        mentions = proof["evidence_mentions"]
        tags = {t for m in mentions for t in m["tags"]}
        self.assertIn("DATE_MENTION_NOT_ATTACK_DATE", tags)
        self.assertIn("REPORT_SEQUENCE_MENTION_NOT_LINK", tags)
        self.assertIn("FATALITY_MENTION_NOT_A_CONFIRMED_TOTAL", tags)
        self.assertTrue(any("Пізніше стало" in m["excerpt"] for m in mentions))
        self.assertLessEqual(len(mentions), 8)
        self.assertEqual(proof["status"], "INSUFFICIENT_EVIDENCE")
        self.assertFalse(proof["independent_police_link_proven"])


class WorkXIndependentDiscovery(unittest.TestCase):
    def test_13_all_cities_when_no_new_alerts_but_http_not_enabled(self):
        from monitor_casualty_candidates import CITY_CONFIG, plan_source_scans
        start = datetime(2026, 11, 14, 12, 0, tzinfo=UTC)
        state = {"cities": {}}
        plans = plan_source_scans(state, {}, start, independent=True)
        self.assertEqual(len(plans), len(CITY_CONFIG))
        self.assertEqual(len(plans), 23)
        self.assertEqual(plans[CITY]["earliest"], start - timedelta(days=8))
        self.assertEqual(plan_source_scans(state, {}, start, independent=False), {})

    def test_14_independent_48h_overlap_and_retry_failed(self):
        from monitor_casualty_candidates import plan_source_scans
        now = datetime(2026, 11, 14, 12, tzinfo=UTC)
        previous = now - timedelta(hours=4)
        state = {"cities": {CITY: {
            "last_independent_source_scan_at": previous.isoformat()}}}
        plans = plan_source_scans(state, {}, now, independent=True)
        self.assertEqual(plans[CITY]["earliest"], previous - timedelta(hours=48))
        # An unsuccessful attempt does not advance the successful cursor.
        self.assertEqual(state["cities"][CITY]["last_independent_source_scan_at"],
                         previous.isoformat())

    def test_15_identical_publication_different_title_deduplicated(self):
        from monitor_casualty_candidates import add_news_candidates
        now = datetime(2026, 11, 14, 12, tzinfo=UTC)
        q = []
        a = {"url": "https://news.google.com/rss/articles/a", "title": "Атака в Запоріжжі, загинули двоє",
             "publisher": "News", "published_at": now.isoformat()}
        b = dict(a, title="Уточнення: атака в Запоріжжі, загинули троє")
        self.assertEqual(add_news_candidates(q, CITY, [a], [], now,
                                             independent=True), 1)
        self.assertEqual(add_news_candidates(q, CITY, [b], [], now,
                                             independent=True), 0)
        self.assertEqual(len(q), 1)
        self.assertEqual(q[0]["discovery_triggers"], ["independent_source_scan"])
        self.assertEqual(q[0]["status"], "needs_review")

    def test_16_default_off_network_opt_in_and_capture_integration(self):
        root = Path(__file__).resolve().parents[2]
        monitor = (root / "kyiv-air-alerts-grafana/scripts/monitor_casualty_candidates.py").read_text()
        runner = (root / "research/casualty_one_time_capture_2026_11_13/run_capture.py").read_text()
        self.assertIn('parser.add_argument("--source-http"', monitor)
        self.assertIn('parser.add_argument("--independent-source-check"', monitor)
        self.assertIn('if args.source_http and not args.local_only:', monitor)
        self.assertIn("workx_evidence.build_review_index", runner)
        self.assertIn("CONTROLLED_CAPTURE", existing.MODE_DEFAULT + " CONTROLLED_CAPTURE")


if __name__ == "__main__":
    unittest.main()
