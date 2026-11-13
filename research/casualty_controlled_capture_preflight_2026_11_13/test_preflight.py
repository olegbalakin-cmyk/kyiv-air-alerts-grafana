#!/usr/bin/env python3
"""Work G offline-only deterministic safety preflight. No socket opens."""
import copy
import csv
import hashlib
import importlib.util
import json
import os
import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
E = ROOT / "research/casualty_evidence_ingestion_2026_11_13/ingest.py"
PR102 = ROOT / "_pr102/research/casualty_zaporizhzhia_http_capture_2026_11_12/capture_once.py"
SITE = ROOT / "_site/kyiv-air-alerts-grafana/data/casualties"
with (HERE / "capture_plan.json").open(encoding="utf-8") as f:
    PLAN = json.load(f)
with (HERE / "authorization_template.json").open(encoding="utf-8") as f:
    TEMPLATE = json.load(f)
spec = importlib.util.spec_from_file_location("work_e_ingest_preflight", E)
e = importlib.util.module_from_spec(spec)
spec.loader.exec_module(e)
pr_spec = importlib.util.spec_from_file_location("pr102_frozen_capture", PR102)
pr102 = importlib.util.module_from_spec(pr_spec)
pr_spec.loader.exec_module(pr102)


def live_shaped():
    a = copy.deepcopy(TEMPLATE)
    now = datetime.now(timezone.utc)
    a.update(authorization_id="SYNTHETIC-UNITTEST-NOT-OWNER-APPROVAL",
             approved_at_utc=(now-timedelta(minutes=5)).isoformat(),
             expires_at_utc=(now+timedelta(hours=1)).isoformat())
    return a


class Response:
    def __init__(self, status=200, location=None, content_type="text/html", body=None):
        self.status = self.code = status
        self.headers = {"Content-Type": content_type}
        if location:
            self.headers["Location"] = location
        self.body = body if body is not None else (b"<html><head><title>Research Fixture</title></head><body><article>" +
            b"Test news reporting casualties and contextual source event. " * 6 + b"</article></body></html>")
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, count):
        return self.body[:count]


class FakeOpener:
    def __init__(self, replies):
        self.replies = replies
        self.urls = []
    def open(self, req, timeout):
        assert isinstance(req, Request)
        assert timeout == 15
        self.urls.append(req.full_url)
        return self.replies.pop(0)


class Preflight(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.queue = [{"candidate_id": x} for t in PLAN["targets"] for x in t["candidate_ids"]]
        cls.queue = list({q["candidate_id"]: q for q in cls.queue}.values())

    def test_01_exact_source_inventory(self):
        targets = PLAN["targets"]
        self.assertEqual(len(targets), 10)
        self.assertEqual(len({x["url"] for x in targets}), 10)
        self.assertEqual(len({x["target_id"] for x in targets}), 10)
        self.assertEqual(len({x["case_id"] for x in targets}), 5)
        self.assertEqual(len([x for x in targets if x["role"] == "official"]), 4)
        self.assertEqual(len([x for x in targets if x["role"] == "publisher"]), 6)
        for t in targets:
            self.assertTrue(t["url"].startswith("https://"))
            self.assertEqual(e.host(t["url"]), t["domain"])
            self.assertNotIn(t["domain"], {"news.google.com", "ukr.net"})
            self.assertIn(t["domain"], e.CAPTURE_HOSTS)
            self.assertFalse(t["publication_allowed"])
            if t["role"] == "publisher":
                self.assertTrue(t["candidate_ids"])
                for cid in t["candidate_ids"]:
                    self.assertEqual(pr102.DIRECT[cid], t["url"])
            else:
                self.assertIn(t["url"], pr102.OFFICIAL.values())
                self.assertEqual(t["candidate_ids"], [])
        self.assertEqual(PLAN["allowed_hosts"], sorted({t["domain"] for t in targets}))
        self.assertEqual({x["case_id"] for x in targets if x["role"] == "official"},
                         {"oct18", "oct22", "sep26", "sep27"})
        self.assertEqual(sum(x["case_id"] == "late05" for x in targets), 1)
        self.assertFalse(PLAN["automatic_credit_allowed"])

    def test_02_template_not_authorized(self):
        self.assertEqual(TEMPLATE["status"], "NOT_AUTHORIZED")
        self.assertIsNone(TEMPLATE["authorization_id"])
        self.assertIsNone(TEMPLATE["approved_at_utc"])
        self.assertIsNone(TEMPLATE["expires_at_utc"])
        self.assertFalse(TEMPLATE["enable_controlled_capture"])
        self.assertFalse(TEMPLATE["publication_allowed"])
        self.assertFalse(TEMPLATE["schedule_enabled"])
        with self.assertRaisesRegex(RuntimeError, "DEFAULT_OFF"):
            e.controlled_capture(TEMPLATE, self.queue, enabled=False)
        with self.assertRaisesRegex(RuntimeError, "WRITTEN_OWNER"):
            e.controlled_capture(TEMPLATE, self.queue, enabled=True)

    def test_03_valid_synthetic_shape_only(self):
        self.assertEqual(e.validate_capture_approval(live_shaped(), True, self.queue)["max_requests_total"], 20)

    def test_04_missing_expired_excessive_and_wrong_host_fail(self):
        for patch_value, error in [
            ({"authorization_id": None}, "WRITTEN_OWNER"),
            ({"allowed_hosts": []}, "UNAPPROVED_HOST"),
            ({"max_requests_total": 31}, "INVALID_REQUEST_BUDGET"),
            ({"max_response_bytes": 1000001}, "INVALID_BODY_LIMIT"),
            ({"min_delay_seconds": 0.9}, "CAPTURE_RATE_LIMIT"),
            ({"expires_at_utc": "2025-11-13T00:00:00Z"}, "EXPIRED"),
            ({"expires_at_utc": "2099-11-13T00:00:00Z"}, "EXPIRED"),
        ]:
            a = live_shaped()
            a.update(patch_value)
            with self.subTest(patch_value=patch_value), self.assertRaisesRegex(RuntimeError, error):
                e.validate_capture_approval(a, True, self.queue)
        for url in ("http://zprz.city/news/x", "https://zprz.city.evil.test/news/x",
                    "https://name:pass@zprz.city/news/x", "https://zprz.city:444/news/x",
                    "https://news.google.com/rss/articles/x"):
            a = live_shaped()
            a["targets"][0]["url"] = url
            with self.subTest(url=url), self.assertRaisesRegex(RuntimeError, "TARGET_NOT_EXACT"):
                e.validate_capture_approval(a, True, self.queue)

    def test_05_duplicate_missing_unknown_and_extra_targets_fail(self):
        a = live_shaped()
        a["targets"][1]["url"] = a["targets"][0]["url"]
        with self.assertRaisesRegex(RuntimeError, "DUPLICATE_HTTP_TARGET"):
            e.validate_capture_approval(a, True, self.queue)
        a = live_shaped()
        a["targets"][0]["candidate_ids"] = ["unknown-id"]
        with self.assertRaisesRegex(RuntimeError, "UNPINNED_WIP"):
            e.validate_capture_approval(a, True, self.queue)
        a = live_shaped()
        a["targets"][1]["candidate_ids"] = ["43a268ae2e19123554d6d476"]
        with self.assertRaisesRegex(RuntimeError, "OFFICIAL_NEEDS"):
            e.validate_capture_approval(a, True, self.queue)
        a = live_shaped()
        a["targets"] = a["targets"] + [dict(a["targets"][0], url="https://zprz.city/news/"+str(i)) for i in range(5)]
        with self.assertRaisesRegex(RuntimeError, "INVALID_APPROVED_TARGET_COUNT"):
            e.validate_capture_approval(a, True, self.queue)

    def test_06_redirect_escape_blocked_before_request(self):
        opener = FakeOpener([Response(302, "https://evil.invalid/steal")])
        policy = live_shaped()
        with patch.object(e.time, "sleep") as sleeper:
            receipt, body = e._capture_once(PLAN["targets"][0]["url"], policy, {"used": 0}, opener)
        self.assertEqual(len(opener.urls), 1)
        self.assertEqual(receipt["reason"], "REDIRECT_NOT_ALLOWLISTED")
        self.assertEqual(body, "")
        sleeper.assert_not_called()

    def test_07_redirect_count_and_budget(self):
        url = PLAN["targets"][0]["url"]
        opener = FakeOpener([Response(302, url) for _ in range(4)])
        with patch.object(e.time, "sleep"):
            receipt, body = e._capture_once(url, live_shaped(), {"used": 0}, opener)
        self.assertEqual(receipt["reason"], "REDIRECT_LIMIT")
        self.assertEqual(len(opener.urls), 4)
        self.assertEqual(body, "")
        opener = FakeOpener([])
        policy = live_shaped()
        receipt, body = e._capture_once(url, policy, {"used": policy["max_requests_total"]}, opener)
        self.assertEqual(receipt["reason"], "REQUEST_BUDGET_EXCEEDED")
        self.assertEqual(opener.urls, [])

    def test_08_body_cap_nonhtml_and_content_guard(self):
        url = PLAN["targets"][0]["url"]
        for resp, reason in [(Response(200, body=b"x"*1000001), "BODY_LIMIT_EXCEEDED"),
                             (Response(200, content_type="application/pdf"), "NON_HTML"),
                             (Response(200, body=b"<html>CAPTCHA</html>"), "CONTENT_INACCESSIBLE")]:
            with self.subTest(reason=reason), patch.object(e.time, "sleep"):
                receipt, body = e._capture_once(url, live_shaped(), {"used": 0}, FakeOpener([resp]))
            self.assertEqual(receipt["reason"], reason)
            self.assertEqual(body, "")

    def test_09_isolated_mock_response_not_casualty_confirmation(self):
        url = PLAN["targets"][0]["url"]
        receipt, text = e._capture_once(url, live_shaped(), {"used": 0}, FakeOpener([Response()]))
        self.assertEqual(receipt["status"], "BODY_EXTRACTED_NOT_VERIFIED")
        self.assertEqual(receipt["response_sha256"], hashlib.sha256(Response().body).hexdigest())
        self.assertTrue(text)
        self.assertNotIn("confirmed_deaths", receipt)

    def test_10_no_actual_capture_when_disabled(self):
        with patch.object(e, "_capture_once", side_effect=AssertionError("NETWORK_ATTEMPT")) as network:
            with self.assertRaises(RuntimeError):
                e.controlled_capture(TEMPLATE, self.queue, enabled=True)
            network.assert_not_called()

    def test_11_baseline_and_credit_fail_closed(self):
        manifest = json.loads((SITE / "cities/zaporizhzhia/manifest.json").read_text())
        with (SITE / "cities/zaporizhzhia/zaporizhzhia_air_attack_deaths_monthly.csv").open() as f:
            monthly = list(csv.DictReader(f))
        with (SITE / "revisions.csv").open() as f:
            revisions = list(csv.DictReader(f))
        self.assertEqual(manifest["validated_through"], "2026-09-18")
        self.assertEqual(next(x for x in monthly if x["month"] == "2026-09")["deaths_confirmed"], "4")
        self.assertFalse(any(x["month"] == "2026-10" for x in monthly))
        self.assertFalse(any(x["city_key"] == "zaporizhzhia" for x in revisions))
        for case_id, case in PLAN["cases"].items():
            self.assertNotEqual(case["credit_gate"], "CREDIT_CONFIRMED")
        self.assertEqual(PLAN["cases"]["late05"]["credit_gate"], "LATER_OFFICIAL_CONFIRMATION_MISSING")
        self.assertEqual(PLAN["cases"]["sep26"]["credit_gate"], "SEPTEMBER_BASELINE_EVENT_ALLOCATION_UNKNOWN")
        self.assertEqual(PLAN["cases"]["sep27"]["credit_gate"], "SEPTEMBER_BASELINE_EVENT_ALLOCATION_UNKNOWN")

    def test_12_no_article_archive_or_release_workflow(self):
        self.assertEqual(PLAN["limits"]["max_requests_total"], 20)
        self.assertEqual(PLAN["limits"]["timeout_seconds"], 15)
        self.assertEqual(PLAN["limits"]["max_redirects_per_url"], 3)
        self.assertEqual(PLAN["limits"]["retries"], 0)
        self.assertFalse(PLAN["full_articles_public_github"])
        self.assertFalse(TEMPLATE["full_articles_saved_to_public_github"])
        self.assertTrue(PLAN["no_google_news_or_ukrnet_targets"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
