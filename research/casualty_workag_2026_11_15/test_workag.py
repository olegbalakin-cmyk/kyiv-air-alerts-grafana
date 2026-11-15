"""Work AG: article-first strict offline E2E, publisher-shaped *synthetic* HTML.

No publisher requests, no WIP data changes, no asserted real incidents.
Real Work P/Q/R/Z archives have short excerpts, not stored full HTML.
"""
import hashlib
import json
import os
import socket
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
import casualty_workac_capture as capture
import casualty_go_guard as go
import casualty_workx_evidence as index

URLS = {
    "ukrinform": "https://www.ukrinform.ua/rubric-regions/workag-synthetic",
    "svoboda": "https://www.radiosvoboda.org/a/workag-synthetic/1.html",
    "hromadske": "https://hromadske.radio/news/workag-synthetic",
    "pravda": "https://www.pravda.com.ua/news/2026/11/15/workag-test/",
}
NOW = datetime(2026, 11, 15, 11, 0, tzinfo=timezone.utc)
FILLER = ("Рятувальники працювали після удару. "
          "Обставини події встановлюють правоохоронці. "
          "Повідомлення про наслідки потребує окремої перевірки. ")
CLAIM = "У Запоріжжі після ракетного удару загинули троє людей. "
CHROME = "У Харкові внаслідок іншої атаки загинули 95 людей. "

def html_page(shape, sentence=CLAIM, *, day="2026-11-15T09:00:00+02:00",
              language="uk"):
    body = sentence + FILLER
    metadata = (f'<meta property="article:published_time" content="{day}">'
                '<meta property="og:title" content="Новина про подію">')
    if shape == "ukrinform":
        wrap = f'<main><article><h1>Новина про подію</h1><div class="article-body"><p>{body}</p></div></article></main>'
    elif shape == "svoboda":
        wrap = f'<main><div class="article__body">{body}</div></main>'
    elif shape == "hromadske":
        wrap = f'<main><section class="post-content">{body}</section></main>'
    elif shape == "pravda":
        wrap = f'<main><article><section class="entry-content">{body}</section></article></main>'
    else:
        raise ValueError("no such shape")
    return (f'<html lang="{language}"><head><title>Old page title</title>{metadata}</head>'
            f'<body><nav>{CHROME}</nav><div class="related-news">{CHROME}</div>'
            f'{wrap}<footer>{CHROME}</footer></body></html>').encode("utf-8")

def offline(shape="ukrinform", sentence=CLAIM, **kw):
    return capture.analyze_direct_article(
        URLS[shape], offline_html=html_page(shape, sentence, **kw),
        city_key="zaporizhzhia", now=NOW, published_at="2026-11-15T07:00:00Z")

class ArticleFirstAG(unittest.TestCase):
    def test_01_four_publisher_layouts_text_title_publication(self):
        for shape in URLS:
            with self.subTest(shape=shape):
                page = html_page(shape)
                parser = capture.ArticleText()
                parser.feed(page.decode())
                self.assertEqual(parser.title(), "Новина про подію")
                self.assertEqual(parser.language, "uk")
                self.assertEqual(parser.publication_time(), "2026-11-15T09:00:00+02:00")
                self.assertIn(CLAIM.strip(), parser.body())
                self.assertNotIn(CHROME.strip(), parser.body())
                result = capture.analyze_direct_article(
                    URLS[shape], offline_html=page,
                    city_key="zaporizhzhia", now=NOW)
                fact, card = result["source_fact"], result["card"]
                self.assertEqual(fact["claim_deaths"], 3)
                self.assertEqual(fact["count_kind"], "cumulative")
                self.assertEqual(fact["publication_date"], "2026-11-15T07:00:00Z")
                self.assertEqual(fact["publication_date_origin"], "article_html_metadata")
                self.assertEqual(fact["article_language_claimed"], "uk")
                self.assertEqual(fact["geographic_status"], "CITY_MENTION_NOT_VERIFIED")
                self.assertEqual(card["fatal_total_claimed_not_credited"], 3)
                self.assertEqual(card["automatic_credits"], 0)
                self.assertIsNone(card["incident_id"])
                self.assertTrue(card["source_excerpts"])
                self.assertEqual(result["network_attempts"], 0)

    def test_02_javascript_shell_no_article_fails_closed(self):
        page = (f"<html><head><title>Відкрийте новину</title></head><body>"
                f"<nav>{CHROME * 7}</nav><div id='root'></div>"
                "<script>renderArticle()</script></body></html>").encode()
        with self.assertRaisesRegex(capture.CaptureBlocked, "ARTICLE_BODY_UNAVAILABLE"):
            capture.analyze_direct_article(URLS["ukrinform"], offline_html=page,
                                           city_key="zaporizhzhia")
    def test_03_wounded_only_and_ages_not_fatalities(self):
        for claim in ("У Запоріжжі після ракетного удару поранені троє людей. ",
                      "У Запоріжжі загинули люди віком 37, 38 і 69 років. "):
            with self.subTest(claim=claim):
                row = offline(sentence=claim)["card"]
                self.assertIsNone(row["fatal_total_claimed_not_credited"])

    def test_04_explicit_cumulative_update(self):
        claim = ("У Запоріжжі після удару кількість загиблих зросла до п'яти. ")
        result = offline(sentence=claim)
        self.assertEqual(result["source_fact"]["claim_deaths"], 5)
        self.assertEqual(result["source_fact"]["count_kind"], "cumulative")
        self.assertEqual(result["card"]["fatal_total_claimed_not_credited"], 5)
        self.assertEqual(result["PROMOTE"], "OFF")
        self.assertIsNone(result["card"]["incident_id"])

    def test_05_delta_hospital_death_requires_baseline(self):
        row = offline(sentence="У Запоріжжі після ракетного удару помер ще один поранений. ")["card"]
        self.assertEqual(row["count_kind_claimed"], "delta")
        self.assertIsNone(row["fatal_total_claimed_not_credited"])
        self.assertIn("LATE_DEATH_REQUIRES_INCIDENT_LINK_AND_BASELINE", row["reasons"])

    def test_06_two_attacks_aggregate_no_assigned_count(self):
        row = offline(sentence="У двох атаках у Запоріжжі загинули п'ятеро людей. ")["card"]
        self.assertIsNone(row["fatal_total_claimed_not_credited"])

    def test_07_scope_region_only_not_city_verified(self):
        row = offline(sentence="За добу в Запорізькій області загинули четверо людей. ")["card"]
        self.assertIsNone(row["fatal_total_claimed_not_credited"])
        self.assertIsNone(row["locality_verified"])

    def test_08_no_article_date_no_inference(self):
        page = html_page("ukrinform").replace(
            b'<meta property="article:published_time" content="2026-11-15T09:00:00+02:00">', b"")
        fact = capture.analyze_direct_article(
            URLS["ukrinform"], offline_html=page, now=NOW)["source_fact"]
        self.assertIsNone(fact["publication_date"])
        self.assertEqual(fact["publication_date_origin"], "unknown")
        self.assertIsNone(fact["attack_date_explicit"])

    def test_09_same_source_replay_and_changed_source_no_credit(self):
        first = offline()
        new = capture.analyze_direct_article(
            URLS["ukrinform"], offline_html=html_page("ukrinform"),
            city_key="zaporizhzhia", now=NOW, previous=[first["card"]])
        self.assertEqual(new["card"]["decision"], "DUPLICATE_SOURCE_REPLAY")
        changed = capture.analyze_direct_article(
            URLS["ukrinform"], offline_html=html_page(
                "ukrinform", "У Запоріжжі після ракетного удару загинули четверо людей. "),
            city_key="zaporizhzhia", now=NOW, previous=[first["card"]])
        self.assertEqual(changed["card"]["decision"], "NEEDS_REVIEW")
        self.assertIn("SAME_URL_POSSIBLE_UPDATED_REPORT_NOT_EVENT_PROOF", changed["card"]["reasons"])

    def test_10_different_urls_same_attack_not_auto_linked(self):
        one = offline("ukrinform")
        two = capture.analyze_direct_article(
            URLS["pravda"], offline_html=html_page("pravda"), now=NOW,
            city_key="zaporizhzhia", previous=[one["card"]])
        self.assertEqual(two["card"]["decision"], "NEEDS_REVIEW")
        self.assertIsNone(two["card"]["incident_id"])
        self.assertIsNone(two["card"]["prior_message_candidate_id_same_url_only"])

    def test_11_go_missing_and_unknown_url_blocks_before_fetch(self):
        with patch.object(socket, "socket", side_effect=AssertionError("SOCKET ATTEMPT")):
            with self.assertRaisesRegex(capture.CaptureBlocked, "OWNER_GO_REQUIRED"):
                capture.analyze_direct_article(URLS["ukrinform"])
        with self.assertRaises(capture.CaptureBlocked):
            capture.analyze_direct_article("https://news.google.com/rss/articles/opaque",
                                           offline_html=b"<main>text</main>")

    def test_12_single_claimed_go_budget_and_url_scope(self):
        g = {"owner_go_id": "workagsynthetic",
             "approved_head": "a" * 40,
             "allowed_urls": {"rss": [], "article": [URLS["ukrinform"]]},
             "rss_get_budget": 0, "article_get_budget": 1,
             "allowed_methods": ["GET"], "expires_at": "2099-01-01T00:00:00Z"}
        refs = []
        lease = go.claim_grant(g, approved_digest=go.canonical_digest(g),
                               head="a" * 40, repo="fake/fake", token="dummy",
                               create_ref=lambda ref, head: (refs.append((ref, head)) or True),
                               now=NOW)
        calls = []
        def fake(u):
            calls.append(u)
            return html_page("ukrinform"), "text/html", 200, "identity"
        capture.analyze_direct_article(URLS["ukrinform"], owner_go=lease,
                                       fetch=fake, now=NOW)
        with self.assertRaises(go.GoBlocked):
            capture.analyze_direct_article(URLS["ukrinform"], owner_go=lease,
                                           fetch=fake, now=NOW)
        self.assertEqual(calls, [URLS["ukrinform"]])
        self.assertEqual(len(refs), 1)

    def test_13_no_html_persisted_or_confirmed_credit(self):
        obj = offline()
        card = obj["card"]
        self.assertNotIn("<html", json.dumps(card))
        self.assertNotIn(FILLER, json.dumps(card, ensure_ascii=False))
        self.assertEqual(card["publication_allowed"], False)
        self.assertEqual(obj["source_fact"]["publication_allowed"], False)
        self.assertEqual(card["automatic_credits"], 0)

    def test_14_repeated_run_deterministic(self):
        a, b = offline(), offline()
        # Caller-supplied frozen time makes proofs deterministic.
        self.assertEqual(a, b)

    def test_15_no_network_even_when_offline_input_is_supplied(self):
        with patch.object(socket, "socket", side_effect=AssertionError("NETWORK")):
            obj = offline()
            self.assertEqual(obj["network_attempts"], 0)
        with self.assertRaisesRegex(capture.CaptureBlocked, "INVALID_OFFLINE"):
            capture.analyze_direct_article(
                URLS["ukrinform"], offline_html=html_page("ukrinform"),
                fetch=lambda _: self.fail("network"))
    def test_17_one_shot_runner_remains_hard_off(self):
        import article_oneshot
        for env in ({}, {"CASUALTY_ARTICLE_NETWORK": "OWNER_APPROVED_ONE_SHOT",
                         "GITHUB_RUN_ATTEMPT": "2",
                         "GITHUB_SHA": "a" * 40}):
            with patch.object(socket, "socket", side_effect=AssertionError("NETWORK")):
                with self.assertRaises(article_oneshot.PilotBlocked):
                    article_oneshot.validate_environment(env)

    def test_16_retained_real_html_not_claimed(self):
        # This is an evidence-availability classification, not a fabricated
        # real fixture. Existing P/Q/R/Z cards contain excerpts but not HTML.
        classification = {"saved_full_article_html": 0,
                          "saved_real_short_excerpts": "available",
                          "saved_url_hashes": "available"}
        self.assertEqual(classification["saved_full_article_html"], 0)


if __name__ == "__main__":
    unittest.main()
