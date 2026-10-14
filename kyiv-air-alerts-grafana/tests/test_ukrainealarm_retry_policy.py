"""Offline regression for UkraineAlarm scheduling; NO network calls."""
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import requests
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ukrainealarm_request_policy as policy


class Clock:
    def __init__(self):
        self.t = 1000.0
        self.waits = []

    def now(self):
        return self.t

    def sleep(self, seconds):
        assert seconds >= 0
        self.waits.append(seconds)
        self.t += seconds

    def utcnow(self):
        return datetime.fromtimestamp(self.t, tz=timezone.utc)


def response(status, body="", headers=None):
    r = requests.Response()
    r.status_code = status
    r._content = body.encode()
    r.reason = str(status)
    r.headers.update(headers or {})
    return r


class Session:
    def __init__(self, replies, clock):
        self.replies = list(replies)
        self.calls = []
        self.clock = clock

    def get(self, url, *, headers, params, timeout):
        self.calls.append((url, self.clock.t, params))
        if not self.replies:
            raise AssertionError("unexpected extra API call")
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


class PolicyTest(unittest.TestCase):
    def client(self, replies, *, handoff=None, budget=2700):
        clock = Clock()
        session = Session(replies, clock)
        client = policy.UkraineAlarmClient(
            "test-only", capture_diagnostic_path=handoff, session=session,
            monotonic=clock.now, sleep=clock.sleep, utcnow=clock.utcnow,
            total_api_seconds=budget,
        )
        return client, session, clock

    def handoff(self, clock, age, enabled=True):
        path = Path(self.tmp.name) / "handoff.json"
        path.write_text(json.dumps({
            "capture_enabled": enabled,
            "sources": {"ukrainealarm": {
                "logical_acquisition_count": 1,
                "request_finished_at": datetime.fromtimestamp(
                    clock.t - age, timezone.utc
                ).isoformat(),
            }}
        }))
        return str(path)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_01_cross_component_handoff_23_seconds(self):
        c0 = Clock()
        path = self.handoff(c0, 23)
        client, session, clock = self.client([response(200)], handoff=path)
        self.assertEqual(client.get("history", context="first").status_code, 200)
        self.assertAlmostEqual(session.calls[0][1], 1047.0)
        self.assertAlmostEqual(clock.waits[0], 47.0)

    def test_02_429_then_success(self):
        client, session, clock = self.client([
            response(429, "Please wait 36 seconds and try again"),
            response(200),
        ])
        self.assertEqual(client.get("history", context="x").status_code, 200)
        self.assertEqual(len(session.calls), 2)
        self.assertGreaterEqual(session.calls[1][1] - session.calls[0][1], 70)

    def test_03_retry_after_header(self):
        client, session, clock = self.client([
            response(429, "Please wait 5 seconds", {"Retry-After": "125"}),
            response(200),
        ])
        self.assertTrue(client.get("history", context="x").ok)
        self.assertEqual(session.calls[1][1] - session.calls[0][1], 125)

    def test_04_429_body_wait(self):
        client, session, clock = self.client([
            response(429, "Please wait 90 seconds and try again"),
            response(200),
        ])
        self.assertTrue(client.get("history", context="x").ok)
        self.assertEqual(session.calls[1][1] - session.calls[0][1], 90)

    def test_05_401_then_success(self):
        client, session, clock = self.client([response(401), response(200)])
        self.assertTrue(client.get("history", context="x").ok)
        self.assertEqual(len(session.calls), 2)

    def test_06_429_exhaustion(self):
        client, session, clock = self.client([response(429)] * 3)
        with self.assertRaises(policy.UkraineAlarmRateLimitExhausted):
            client.get("history", context="x")
        self.assertEqual(len(session.calls), 3)

    def test_07_network_disconnect_then_success(self):
        client, session, clock = self.client([
            requests.ConnectionError("synthetic disconnect"), response(200)
        ])
        self.assertTrue(client.get("history", context="x").ok)
        self.assertGreaterEqual(session.calls[1][1] - session.calls[0][1], 70)

    def test_08_persistent_auth_failure(self):
        client, session, clock = self.client([response(401)] * 3)
        with self.assertRaises(policy.UkraineAlarmAuthenticationError):
            client.get("history", context="x")
        self.assertEqual(len(session.calls), 3)

    def test_09_429_date_header(self):
        c0 = Clock()
        hdr = "Thu, 01 Jan 1970 00:18:25 GMT"  # 1105 UTC
        client, session, clock = self.client([
            response(429, "Please wait 2 seconds", {"Retry-After": hdr}), response(200)
        ])
        self.assertTrue(client.get("history", context="x").ok)
        self.assertEqual(session.calls[1][1] - session.calls[0][1], 105)

    def test_10_missing_handoff_waits_full_guard(self):
        client, session, clock = self.client([response(200)], handoff="/nonexistent.json")
        self.assertTrue(client.get("history", context="x").ok)
        self.assertEqual(session.calls[0][1], 1070)

    def test_11_missing_or_bad_handoff_does_not_lower_interval(self):
        clock = Clock()
        path = self.handoff(clock, 23, enabled=False)
        client, session, clock = self.client([response(200)], handoff=path)
        self.assertTrue(client.get("history", context="x").ok)
        self.assertEqual(session.calls[0][1], 1070)

    def test_12_fallback_429_wait(self):
        client, session, clock = self.client([response(429, "bad"), response(200)])
        self.assertTrue(client.get("history", context="x").ok)
        self.assertEqual(session.calls[1][1] - session.calls[0][1], 70)

    def test_13_budget_exhaustion(self):
        client, session, clock = self.client([response(200)], budget=65)
        with self.assertRaises(policy.UkraineAlarmRetryBudgetExceeded):
            client.get("history", context="x")
        self.assertEqual(len(session.calls), 0)

    def test_14_failed_capture_still_handoff(self):
        clock = Clock()
        path = self.handoff(clock, 10)
        doc = json.loads(Path(path).read_text())
        doc["sources"]["ukrainealarm"]["status"] = "FAILED"
        Path(path).write_text(json.dumps(doc))
        client, session, clock = self.client([response(200)], handoff=path)
        self.assertTrue(client.get("history", context="x").ok)
        self.assertEqual(session.calls[0][1], 1060)

    def test_15_no_token_or_raw_body_in_error(self):
        client, session, clock = self.client([response(403, "private-secret")])
        with self.assertRaisesRegex(RuntimeError, "HTTP 403") as cm:
            client.get("history", context="x")
        self.assertNotIn("private-secret", str(cm.exception))

    def test_16_transport_exhaustion(self):
        client, session, clock = self.client([requests.Timeout("secret"), requests.Timeout("secret")])
        with self.assertRaisesRegex(RuntimeError, "Timeout"):
            client.get("history", context="x")
        self.assertEqual(len(session.calls), 2)

    def test_17_no_shortening_interval(self):
        client, session, clock = self.client([response(200), response(200)], budget=500)
        client.get("history", context="first")
        client.get("history", context="second")
        self.assertGreaterEqual(session.calls[1][1] - session.calls[0][1], 70)


if __name__ == "__main__":
    unittest.main()
