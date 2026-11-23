#!/usr/bin/env python3
"""No-network tests for the one-shot monthly collector."""
from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import monthly_one_shot_collector as m

HEAD = "a" * 40
NOW = datetime(2026, 11, 22, 16, 0, tzinfo=timezone.utc)


def env():
    return {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": m.RESEARCH_REF,
        "GITHUB_REPOSITORY": m.REPO,
        "GITHUB_ACTOR": m.ACTOR,
        "GITHUB_TRIGGERING_ACTOR": m.ACTOR,
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_SHA": HEAD,
        "CASUALTY_MONTHLY_GO": "OWNER_APPROVED_ONE_SHOT",
        "CASUALTY_MONTHLY_APPROVED_HEAD": HEAD,
        "CASUALTY_MONTHLY_GO_ID": "casualty-23city-monthly-20261122-001",
    }


def grant(manifest_bytes):
    return {
        "owner_go_id": "casualty-23city-monthly-20261122-001",
        "approved_head": HEAD,
        "source_manifest_sha256": m.sha256(manifest_bytes),
        "get_budget": 27,
        "allowed_methods": ["GET"],
        "expires_at": (NOW + timedelta(hours=2)).isoformat(),
    }


class OfflineCollectorTests(unittest.TestCase):
    def setUp(self):
        self.manifest, self.manifest_bytes = m.load_manifest()
        self.grant = grant(self.manifest_bytes)
        self.env = env()
        self.env["CASUALTY_MONTHLY_ARCHIVE_KEY_B64"] = base64.b64encode(os.urandom(32)).decode("ascii")
        self.env["CASUALTY_MONTHLY_GO_DIGEST"] = m.canonical_sha256(self.grant)
        self.env["CASUALTY_MONTHLY_GRANT_JSON"] = json.dumps(self.grant)
        self.assertEqual(len(self.manifest["targets"]), 27)
        self.assertEqual(len(self.manifest["cities"]), 23)

    def validates(self, gr=None, e=None, now=NOW):
        grant_data = self.grant if gr is None else gr
        environment = self.env if e is None else e
        m.validate_grant(
            grant_data,
            digest=environment["CASUALTY_MONTHLY_GO_DIGEST"],
            head=HEAD,
            manifest=self.manifest,
            manifest_bytes=self.manifest_bytes,
            env=environment,
            now=now,
        )

    def test_manifest_and_exact_grant(self):
        self.validates()
        self.assertEqual(self.manifest["get_budget"], m.MAX_GETS)
        self.assertEqual(self.grant["get_budget"], 27)
        self.assertTrue(all(row["url"].startswith("https://") for row in self.manifest["targets"]))

    def test_no_go_by_default(self):
        e = dict(self.env, CASUALTY_MONTHLY_GO="OFF")
        with self.assertRaises(m.Blocked):
            m.validate_environment(e)

    def test_push_and_rerun_and_wrong_branch_and_actor_fail_closed(self):
        for key, value in [
            ("GITHUB_EVENT_NAME", "push"),
            ("GITHUB_RUN_ATTEMPT", "2"),
            ("GITHUB_REF", "refs/heads/main"),
            ("GITHUB_REPOSITORY", "untrusted/repo"),
            ("GITHUB_ACTOR", "someone-else"),
            ("GITHUB_TRIGGERING_ACTOR", "someone-else"),
            ("GITHUB_SHA", "b" * 40),
            ("CASUALTY_MONTHLY_APPROVED_HEAD", "b" * 40),
        ]:
            with self.subTest(key=key):
                with self.assertRaises(m.Blocked):
                    m.validate_environment(dict(self.env, **{key: value}))

    def test_expired_or_long_grant_blocked(self):
        with self.assertRaises(m.Blocked):
            self.validates(now=NOW + timedelta(hours=3))
        bad = dict(self.grant, expires_at=(NOW + timedelta(hours=48)).isoformat())
        e = dict(self.env, CASUALTY_MONTHLY_GO_DIGEST=m.canonical_sha256(bad))
        with self.assertRaises(m.Blocked):
            self.validates(gr=bad, e=e)

    def test_tampering_blocked(self):
        for key, value in [
            ("get_budget", 50),
            ("allowed_methods", ["GET", "POST"]),
            ("source_manifest_sha256", "b" * 64),
            ("owner_go_id", "new-id"),
            ("approved_head", "b" * 40),
        ]:
            with self.subTest(key=key):
                modified = copy.deepcopy(self.grant)
                modified[key] = value
                e = dict(self.env, CASUALTY_MONTHLY_GO_DIGEST=m.canonical_sha256(modified))
                with self.assertRaises(m.Blocked):
                    self.validates(gr=modified, e=e)
        e = dict(self.env, CASUALTY_MONTHLY_GO_DIGEST="b" * 64)
        with self.assertRaises(m.Blocked):
            self.validates(e=e)

    def test_rejects_unsafe_urls(self):
        hosts = set(self.manifest["allowed_hosts"])
        for url in [
            "http://suspilne.media/",
            "https://127.0.0.1/",
            "https://suspilne.media.evil.test/",
            "https://user:pass@suspilne.media/",
            "https://suspilne.media:444/",
            "https://suspilne.media/#fragment",
            "https://suspilne.media/\nsecret",
            "https://suspilne.media\\@evil.test/",
            "https://suspilne.media./",
        ]:
            with self.subTest(url=url):
                with self.assertRaises(m.Blocked):
                    m.safe_https_url(url, hosts)

    def test_rejects_private_dns_answers(self):
        with mock.patch.object(m.socket, "getaddrinfo", return_value=[
            (m.socket.AF_INET, m.socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443))
        ]):
            with self.assertRaises(m.Blocked):
                m._public_addresses("suspilne.media", m.time.monotonic() + 2)

    def test_atomic_spent_ref_fail_closed_and_replay_blocked(self):
        attempts = set()
        def once(ref, head):
            if ref in attempts:
                return False
            attempts.add(ref)
            return True
        target = m.claim_once(self.grant, HEAD, self.env, create_ref=once)
        self.assertTrue(target.startswith(m.TAG_PREFIX))
        with self.assertRaises(m.Blocked):
            m.claim_once(self.grant, HEAD, self.env, create_ref=once)
        with self.assertRaises(m.Blocked):
            m.claim_once(self.grant, HEAD, self.env, create_ref=lambda ref, sha: None)

    def test_claim_occurs_before_source_get_and_receipts_are_redacted(self):
        with tempfile.TemporaryDirectory(prefix="casualty-monthly-test-") as tmp:
            # Only /tmp/casualty-monthly-* proof paths are permitted.
            self.env["CASUALTY_MONTHLY_OUTPUT"] = tmp
            called = []
            body_sample = b"<html><title>Example</title><article>Two people were killed.</article></html>"
            def claim(ref, sha):
                called.append("claim")
                return True
            def fake_transport(url, hosts):
                self.assertEqual(called[0], "claim")
                self.assertIn(url, [x["url"] for x in self.manifest["targets"]])
                called.append(url)
                body = body_sample
                return {
                    "http_status": 200, "content_type": "text/html",
                    "raw_bytes": len(body), "decoded_bytes": len(body),
                    "raw_sha256": m.sha256(body),
                    "decoded_sha256": m.sha256(body),
                    "_raw": body, "_decoded": body,
                }
            result = mock.Mock(stdout=HEAD + "\n")
            with mock.patch.object(m.subprocess, "run", return_value=result):
                proof = m.capture(self.env, transport=fake_transport,
                                  tag_claim=claim, now=NOW)
            self.assertEqual(proof["attempted_gets"], 27)
            self.assertEqual(proof["successful_gets"], 27)
            self.assertEqual(proof["automatic_credits"], 0)
            self.assertEqual(proof["production_writes"], 0)
            self.assertEqual(proof["wip_writes"], 0)
            self.assertTrue(proof["source_full_text_saved"])
            self.assertEqual(proof["encrypted_archive"]["record_count"], 27)
            from private_body_archive import PrivateBodyArchive
            archive = PrivateBodyArchive(
                Path(tmp) / "private-archive",
                self.env["CASUALTY_MONTHLY_ARCHIVE_KEY_B64"],
                checkout_root=m.HERE.parents[1],
            )
            receipt = proof["results"][0]["archive_receipt"]
            restored = archive.verify(receipt)
            self.assertEqual(restored["raw"], body_sample)
            self.assertEqual(restored["decoded"], body_sample)
            self.assertEqual(receipt["decoded_sha256"], hashlib.sha256(body_sample).hexdigest())
            for path in (Path(tmp) / "private-archive").rglob("*"):
                if path.is_file():
                    raw_file = path.read_bytes()
                    self.assertNotIn(body_sample, raw_file)
                    self.assertNotIn(b"Two people were killed", raw_file)
            self.assertFalse(any("_decoded" in p for p in proof["results"]))
            report = (Path(tmp) / "capture_report.json").read_bytes()
            manifest = json.loads((Path(tmp) / "sha256_manifest.json").read_text())
            self.assertEqual(m.sha256(report), manifest["capture_report.json"])
            self.assertNotIn("<html>", report.decode())
            self.assertNotIn("<article>", report.decode())
            self.assertEqual(len(proof["results"][0]["context"]), 23)
            self.assertLessEqual(len(proof["results"][0]["context"]), 150)

    def test_preclaim_refusal_has_no_network(self):
        e = dict(self.env, GITHUB_EVENT_NAME="push")
        transport = mock.Mock(side_effect=AssertionError("GET MUST NOT RUN"))
        with self.assertRaises(m.Blocked):
            m.capture(e, transport=transport, now=NOW)
        transport.assert_not_called()

    def test_per_url_network_failures_never_retry(self):
        with tempfile.TemporaryDirectory(prefix="casualty-monthly-test-") as tmp:
            self.env["CASUALTY_MONTHLY_OUTPUT"] = tmp
            calls = []
            def failing_transport(url, hosts):
                calls.append(url)
                raise m.Blocked("REDIRECT_BLOCKED_STATUS_301")
            with mock.patch.object(m.subprocess, "run",
                                   return_value=mock.Mock(stdout=HEAD + "\n")):
                proof = m.capture(self.env, transport=failing_transport,
                                  tag_claim=lambda ref, sha: True, now=NOW)
            self.assertEqual(len(calls), 27)
            self.assertEqual(len(set(calls)), 27)
            self.assertEqual(proof["successful_gets"], 0)
            self.assertFalse(proof["source_full_text_saved"])
            self.assertEqual(proof["encrypted_archive"]["record_count"], 0)
            self.assertEqual(proof["attempted_gets"], 27)
            self.assertEqual(proof["rss_gets"], 0)
            self.assertTrue(all(p["status"] == "BLOCKED_OR_FAILED" for p in proof["results"]))

    def test_missing_key_prevents_go_claim_and_get(self):
        self.env.pop("CASUALTY_MONTHLY_ARCHIVE_KEY_B64")
        claim = mock.Mock(side_effect=AssertionError("GO MUST NOT BE SPENT"))
        transport = mock.Mock(side_effect=AssertionError("GET MUST NOT RUN"))
        with tempfile.TemporaryDirectory(prefix="casualty-monthly-test-") as tmp:
            self.env["CASUALTY_MONTHLY_OUTPUT"] = tmp
            with mock.patch.object(m.subprocess, "run",
                                   return_value=mock.Mock(stdout=HEAD + "\n")):
                with self.assertRaisesRegex(m.Blocked, "ENCRYPTED_ARCHIVE_NOT_READY"):
                    m.capture(self.env, transport=transport, tag_claim=claim, now=NOW)
        claim.assert_not_called()
        transport.assert_not_called()

    def test_bad_original_digest_stops_after_first_get(self):
        with tempfile.TemporaryDirectory(prefix="casualty-monthly-test-") as tmp:
            self.env["CASUALTY_MONTHLY_OUTPUT"] = tmp
            calls = []
            def tampered_transport(url, hosts):
                calls.append(url)
                data = b"<html><article>synthetic report</article></html>"
                return {
                    "http_status": 200, "content_type": "text/html",
                    "raw_bytes": len(data), "decoded_bytes": len(data),
                    "raw_sha256": "0" * 64,
                    "decoded_sha256": m.sha256(data),
                    "_raw": data, "_decoded": data,
                }
            with mock.patch.object(m.subprocess, "run",
                                   return_value=mock.Mock(stdout=HEAD + "\n")):
                with self.assertRaisesRegex(m.Blocked, "PRIVATE_ARCHIVE_FAILURE_STOP"):
                    m.capture(self.env, transport=tampered_transport,
                              tag_claim=lambda ref, head: True, now=NOW)
            self.assertEqual(len(calls), 1)
            report = json.loads((Path(tmp) / "capture_report.json").read_text())
            self.assertEqual(report["successful_gets"], 0)
            self.assertEqual(report["encrypted_archive"]["record_count"], 0)
            self.assertEqual(report["results"][0]["status"], "ARCHIVE_FAILED_STOP")

    def test_pdf_is_hash_only(self):
        evidence = m.brief_evidence(b"%PDF-1.4 fake", "application/pdf")
        self.assertEqual(evidence["review_note"], "PDF_CAPTURED_HASH_ONLY")
        self.assertIsNone(evidence["context"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
