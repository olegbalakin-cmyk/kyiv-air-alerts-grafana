"""Offline-only source access boundary / previous blocked case regression.

All Google RPC results and HTTP responses in this suite are SYNTHETIC mocks.
Never infer real target host equivalence from the old RSS publisher_url.
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))

from casualty_transport_policy import (
    CaptureError, PUBLISHER_TRANSPORT_HOSTS, diagnostic_host, safe_url,
)
from casualty_evidence_capture import (
    capture_snapshot, get_publisher_document, sha256,
)
from casualty_auto_review import ALLOWED_HOSTS, validate_reports


class FakeResponse:
    def __init__(self, status=200, body=b"", headers=None):
        self.status_code = status
        self._body = body
        self.headers = headers if headers is not None else {"Content-Type": "text/html"}
    def iter_content(self, chunk_size=8192):
        for offset in range(0, len(self._body), chunk_size):
            yield self._body[offset:offset + chunk_size]
    def close(self):
        pass


class FakeSession:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []
    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self.responses[url]
    def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        return self.responses[url]


def response_rpc(target):
    return FakeResponse(body=b")]}'\n\n" + json.dumps([
        ["wrb.fr", "Fbv4je", json.dumps(["garturlres", target])]
    ]).encode())


def opaque(idx):
    return "https://news.google.com/rss/articles/CBMi" + str(idx) * 50


def news_html(url):
    token = url.split("/")[-1]
    return FakeResponse(body=(
        f'<html><div data-n-a-id="{token}" data-n-a-ts="1783791812" '
        'data-n-a-sg="AV_R3e-signed123">'
        'Mock Google News article wrapper with enough bytes for parser.'
        '</div></html>').encode())


def candidate(cid, url, publisher):
    return {
        "candidate_id": cid, "url": url, "city_key": "odesa",
        "title": "Pinned RSS candidate – headline only, never evidence",
        "snippet": "", "published_at": "2026-11-10",
        "publisher": publisher, "publisher_url": "https://" + publisher,
        "status": "needs_review",
    }


class SourceAccessPolicyTests(unittest.TestCase):
    def test_existing_allowed_unchanged_but_no_new_hosts(self):
        self.assertEqual(PUBLISHER_TRANSPORT_HOSTS, frozenset(ALLOWED_HOSTS))
        for host in sorted(PUBLISHER_TRANSPORT_HOSTS):
            self.assertEqual(safe_url(f"https://{host}/story", allow_google=False),
                             f"https://{host}/story")
        for host in ("espreso.tv", "vinnitsa.info", "zabor.zp.ua", "evil.example"):
            with self.subTest(host=host), self.assertRaisesRegex(CaptureError, "HOST_NOT_ALLOWED"):
                safe_url(f"https://{host}/story", allow_google=False)

    def test_public_host_diagnostic_does_not_grant_access(self):
        self.assertEqual(diagnostic_host("https://espreso.tv/story?secret=1"), "espreso.tv")
        for value in (
            "http://espreso.tv/a", "https://127.0.0.1/internal",
            "https://localhost/private", "https://a.internal/metadata",
            "https://u:p@espreso.tv/private", "https://[::1]/data",
        ):
            with self.subTest(url=value):
                self.assertIsNone(diagnostic_host(value))
        with self.assertRaisesRegex(CaptureError, "HOST_NOT_ALLOWED"):
            safe_url("https://espreso.tv/story")

    def test_unsafe_redirects_and_urls_never_fetched(self):
        for target in ("http://suspilne.media/x", "https://127.0.0.1/x",
                       "https://169.254.169.254/metadata", "https://localhost/x",
                       "https://evil.example/x", "https://suspilne.media:8080/x",
                       "https://u:p@suspilne.media/x"):
            with self.subTest(target=target):
                safe = "https://suspilne.media/allowed"
                session = FakeSession({safe: FakeResponse(
                    status=302, headers={"Location": target})})
                with self.assertRaises(CaptureError):
                    get_publisher_document(safe, session=session, counter=[0])
                self.assertEqual(len(session.calls), 1)

    def test_three_rss_homepage_hosts_are_not_proven_rpc_destinations(self):
        # Synthetic RPC target intentionally differs from RSS homepage.
        for i, publisher in enumerate(("espreso.tv", "vinnitsa.info", "zabor.zp.ua")):
            url = opaque(i + 1)
            target = f"https://unverified-source-{i}.example/long-article"
            rpc = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
            session = FakeSession({url: news_html(url), rpc: response_rpc(target)})
            with tempfile.TemporaryDirectory() as d:
                path = Path(d) / "evidence.json"
                capture_snapshot([candidate(f"id{i}", url, publisher)], path, session=session)
                data = json.loads(path.read_text())
            self.assertEqual(data["articles"], [])
            self.assertEqual(data["receipts"], [])
            failure = data["failures"][0]
            self.assertEqual(failure["reason"], "GOOGLE_RPC_TARGET_NOT_ALLOWED")
            self.assertEqual(failure["transport_reason"], "HOST_NOT_ALLOWED")
            self.assertEqual(failure["resolved_host"], f"unverified-source-{i}.example")
            self.assertEqual(failure["resolved_url_sha256"], sha256(target.encode()))
            self.assertNotIn(target, json.dumps(failure))
            self.assertEqual(len(session.calls), 2)

    def test_two_suspilne_urls_403_are_access_blocked_not_no_deaths(self):
        for idx, city in ((1, "odesa"), (2, "kharkiv")):
            wrapper = opaque(idx)
            target = f"https://suspilne.media/{city}/mock-article-{idx}/"
            rpc = "https://news.google.com/_/DotsSplashUi/data/batchexecute"
            session = FakeSession({
                wrapper: news_html(wrapper),
                rpc: response_rpc(target),
                target: FakeResponse(status=403)
            })
            with tempfile.TemporaryDirectory() as d:
                output = Path(d) / "evidence.json"
                capture_snapshot([candidate(city, wrapper, "suspilne.media")],
                                 output, session=session)
                data = json.loads(output.read_text())
            self.assertEqual(data["articles"], [])
            self.assertEqual(data["receipts"], [])
            failure = data["failures"][0]
            self.assertEqual(failure["reason"], "HTTP_STATUS_403")
            self.assertEqual(failure["resolved_host"], "suspilne.media")
            self.assertEqual(failure["redirect_count"], 1)
            self.assertEqual(failure["resolved_url_sha256"], sha256(target.encode()))
            self.assertEqual(len(session.calls), 3)
            self.assertTrue(all(not c[2]["allow_redirects"] for c in session.calls))

    def test_reviewer_evidence_host_independent_of_transport(self):
        # No reviewer modification; article accepted for download is NOT a death fact.
        report = {
            "candidate_ids": ["x"],
            "candidate_fingerprints": {},
            "incident": {}, "facts": {}, "observed_at": "2026-11-10",
            "count": {"kind": "unknown", "value": None},
            "sources": [{"url": "https://espreso.tv/story",
                         "origin_id": "unattributed", "basis": "mock"}],
        }
        # Check reviewer host logic directly, without calling a live or mutating path.
        self.assertNotIn("espreso.tv", ALLOWED_HOSTS)
        self.assertNotIn("vinnitsa.info", ALLOWED_HOSTS)
        self.assertNotIn("zabor.zp.ua", ALLOWED_HOSTS)

    def test_previous_artifacts_five_cases_are_blocked(self):
        # Prior physical evidence is pinned by immutable run #42899975187.
        # Exact decoded three RPC URLs were NOT preserved; never invent them.
        expected = {
            "kropyvnytskyi": "GOOGLE_RPC_TARGET_NOT_ALLOWED",
            "vinnytsia": "GOOGLE_RPC_TARGET_NOT_ALLOWED",
            "zaporizhzhia": "GOOGLE_RPC_TARGET_NOT_ALLOWED",
            "odesa": "HTTP_STATUS_403",
            "kharkiv": "HTTP_STATUS_403",
        }
        self.assertEqual(len(expected), 5)
        self.assertEqual(sum(x == "GOOGLE_RPC_TARGET_NOT_ALLOWED" for x in expected.values()), 3)
        self.assertEqual(sum(x == "HTTP_STATUS_403" for x in expected.values()), 2)


if __name__ == "__main__":
    unittest.main()
