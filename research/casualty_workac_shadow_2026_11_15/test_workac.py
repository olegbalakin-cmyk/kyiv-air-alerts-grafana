"""Work AC fully offline verification. No source HTTP; WIP read-only."""
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana" / "scripts"))
import casualty_workac_capture as ac
import monitor_casualty_candidates as monitor
import casualty_workx_evidence as workx

NOW = datetime(2026, 11, 15, 0, 0, tzinfo=timezone.utc)
URL = "https://mig.com.ua/synthetic-offline-never-request/"
TEXT = ("У Запоріжжі внаслідок ракетного удару загинули двоє людей. "
        "Пізніше повідомили про уточнення кількості загиблих після удару. "
        "Рятувальники працювали на місці влучання після атаки ракетами. "
        "Зазначається, що інформація про обставини загибелі уточнюється.")
PAGE = ("<html><main><article>" + TEXT + "</article></main></html>").encode()
OUT = Path(os.getenv("WORKAC_OUT", "/tmp/workac"))
COUNTERS = {"external_http": 0}

def candidate(n, url=None):
    return {"candidate_id": "synthetic-" + str(n), "city_key": "zaporizhzhia",
            "source": "Google News RSS", "url": url or URL,
            "published_at": "2026-11-14T20:00:00Z", "title": "synthetic"}

def fake(url):
    assert url.startswith("https://mig.com.ua/")
    return PAGE, "text/html; charset=utf-8", 200, "identity"

class WorkAC(unittest.TestCase):
    def test_01_off_default_and_allowlist(self):
        q = [candidate(1)]
        state, index, report = ac.capture_cycle(q, {}, {}, NOW, enabled=False,
                                                 fetch=lambda u: self.fail("network"))
        self.assertEqual(report["article_gets"], 0)
        self.assertFalse(index.get("cards"))
        for url in ("http://mig.com.ua/test", "https://127.0.0.1/x",
                    "https://localhost/x", "https://169.254.169.254/x",
                    "https://example.com/x", "https://news.google.com/rss/articles/1",
                    "https://mig.com.ua@127.0.0.1/x",
                    "https://user:pass@mig.com.ua/x"):
            with self.assertRaises(ac.CaptureBlocked):
                ac.allowed_article_url(url)
        self.assertEqual(ac.allowed_article_url(URL), URL)

    def test_02_03_three_cycles_article_to_index_and_idempotence(self):
        first = ac.capture_cycle([candidate(1)], {}, {}, NOW, enabled=True, fetch=fake)
        self.assertEqual(first[2]["article_gets"], 1)
        self.assertEqual(first[2]["evidence_new"], 1)
        card = first[1]["cards"][0]
        self.assertEqual(card["response_sha256"], hashlib.sha256(PAGE).hexdigest())
        self.assertEqual(card["decision"], "NEEDS_REVIEW")
        self.assertTrue(card["source_excerpts"] or card["unverified_context"])
        self.assertEqual(card["automatic_credits"], 0)
        self.assertIsNone(card["incident_id"])
        self.assertEqual(card["publication_date_claimed"], "2026-11-14T20:00:00Z")
        self.assertEqual(card["source_capture_time_utc"], ac.timestamp(NOW))
        second = ac.capture_cycle([candidate(1)], first[0], first[1],
                                  NOW + timedelta(hours=4), enabled=True, fetch=fake)
        self.assertEqual(second[2]["evidence_new"], 0)
        self.assertEqual(second[2]["evidence_replay_duplicates"], 1)
        third = ac.capture_cycle([candidate(1)], second[0], second[1],
                                 NOW + timedelta(hours=8), enabled=True, fetch=fake)
        self.assertEqual(third[2]["evidence_new"], 0)
        self.assertEqual(len(third[1]["cards"]), 1)
        self.assertEqual(third[2]["automatic_credits"], 0)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT/"cycles.json").write_text(json.dumps({
            "head": os.getenv("GITHUB_SHA", "LOCAL"), "cities": 23,
            "cycles": [dict(first[2]),dict(second[2]),dict(third[2])],
            "cards": len(third[1]["cards"]), "external_http": 0,
            "automatic_credits": 0, "PROMOTE": "OFF",
        }, indent=2, sort_keys=True), encoding="utf-8")

    def test_04_capture_failure_retry_without_cursor_loss(self):
        def failing(url):
            raise TimeoutError("mock 20 second cutoff")
        failed = ac.capture_cycle([candidate(1)], {}, {}, NOW, enabled=True, fetch=failing)
        self.assertEqual(failed[0]["candidates"]["synthetic-1"]["status"], "RETRY_PENDING")
        self.assertEqual(failed[2]["article_errors"], 1)
        recovered = ac.capture_cycle([candidate(1)], failed[0], failed[1],
                                     NOW+timedelta(hours=4), enabled=True, fetch=fake)
        self.assertEqual(recovered[2]["evidence_new"], 1)

    def test_05_ten_attempt_budget_even_failures(self):
        calls = []
        def failed(url):
            calls.append(url)
            raise TimeoutError("offline")
        q = [candidate(i, "https://mig.com.ua/fixture/" + str(i)) for i in range(23)]
        s,i,r = ac.capture_cycle(q, {}, {}, NOW, enabled=True, fetch=failed)
        self.assertEqual((len(calls),r["article_gets"],r["article_errors"]),(10,10,10))

    def test_06_reject_oversize_decompression_and_html_type(self):
        with self.assertRaises(ac.CaptureBlocked):
            ac._decode_limited(b"x" * (ac.MAX_BYTES+1), "identity")
        import gzip
        with self.assertRaises(ac.CaptureBlocked):
            ac._decode_limited(gzip.compress(b"z"*(ac.MAX_BYTES+1)), "gzip")
        def redirect(url):
            return b"", "text/html", 302, "identity"
        self.assertEqual(ac.capture_cycle([candidate(1)],{},{},NOW,enabled=True,fetch=redirect)[2]["article_errors"],1)
        def bad_type(url):
            return PAGE, "application/json", 200, "identity"
        self.assertEqual(ac.capture_cycle([candidate(1)],{},{},NOW,enabled=True,fetch=bad_type)[2]["article_errors"],1)

    def test_07_private_dns_and_transport_boundary(self):
        with patch.object(ac.socket, "getaddrinfo", return_value=[
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1",443))]):
            with self.assertRaises(ac.CaptureBlocked):
                ac._public_dns("mig.com.ua", ac.time.monotonic()+5)
        with patch.object(ac.PinnedHTTPS, "connect", side_effect=ac.CaptureBlocked("TOTAL_DEADLINE")):
            with self.assertRaises(ac.CaptureBlocked):
                ac.get_html(URL)

    def test_08_same_day_other_attack_and_revision_not_promoted(self):
        rows = []
        for n in (18,20,23):
            fact = {"candidate_id":str(n),"source_url":URL, "source_role":"publisher",
                    "document_sha256":hashlib.sha256(str(n).encode()).hexdigest(),
                    "extracted_text_sha256":"f"*64, "claim_deaths":n,
                    "decision":"NEEDS_REVIEW","publication_allowed":False}
            index = workx.build_review_index(
                {"facts":[fact],"automatic_credits":0,"publication_allowed":False},
                previous=rows[-1:] if rows else [], include_unretained=False)
            rows.append(index["cards"][0])
        self.assertEqual([r["fatal_total_claimed_not_credited"] for r in rows],[18,20,23])
        self.assertEqual(sum(r["automatic_credits"] for r in rows),0)
        self.assertTrue(all(r["incident_id"] is None for r in rows))
        other = candidate(2, "https://mig.com.ua/separate-attack")
        index = ac.capture_cycle([candidate(1),other],{}, {},NOW,enabled=True,fetch=fake)[1]
        self.assertEqual(len(index["cards"]), 2)
        self.assertTrue(all(c["incident_id"] is None for c in index["cards"]))

    def test_09_rss_budget_timeout_no_redirect_and_cursor(self):
        class Response:
            status_code=200
            content=b"<rss><channel></channel></rss>"
            def raise_for_status(self): pass
        calls=[]
        def get(url, **kwargs):
            calls.append(kwargs)
            if len(calls)==2:
                raise TimeoutError("mock feed down")
            return Response()
        with patch.object(monitor.requests, "get", side_effect=get):
            monitor.HTTP_REQUESTS_THIS_RUN=0
            monitor.search_city_news("kyiv", NOW-timedelta(days=8), NOW)
            with self.assertRaises(TimeoutError):
                monitor.search_city_news("kharkiv", NOW-timedelta(days=8), NOW)
        self.assertEqual(monitor.HTTP_REQUESTS_THIS_RUN,2)
        self.assertTrue(all(c["timeout"]==15 and c["allow_redirects"] is False for c in calls))
        with patch.object(monitor.requests, "get", side_effect=AssertionError("RSS OVER BUDGET")):
            monitor.HTTP_REQUESTS_THIS_RUN=23
            with self.assertRaises(RuntimeError):
                monitor.search_city_news("kyiv",NOW-timedelta(days=8),NOW)

    def test_10_no_raw_html_in_stored_artifacts(self):
        state,index,_=ac.capture_cycle([candidate(1)],{},{},NOW,enabled=True,fetch=fake)
        saved=json.dumps({"state":state,"index":index},ensure_ascii=False)
        self.assertNotIn("<html",saved.lower())
        self.assertNotIn("<article",saved.lower())
        self.assertNotIn(TEXT,saved)
        self.assertTrue(all(c["automatic_credits"]==0 for c in index["cards"]))

if __name__=="__main__":
    unittest.main()
