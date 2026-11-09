"""Narrow no-network regression checks for C6 receipt wiring (no old proof replay)."""
import base64
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from scripts import c6_history_freshness as freshness


class IntegrationWiring(unittest.TestCase):
    def test_capture_off_does_not_modify_existing_payload_or_checkpoint(self):
        contract = freshness.capture_contract()
        with tempfile.TemporaryDirectory() as d:
            payload = Path(d) / "payload.json"
            checkpoint = Path(d) / "checkpoints.json"
            payload.write_text('{"cities": {}}', encoding="utf-8")
            env = {"MULTICITY_CANONICAL_PAYLOAD_PATH": str(payload)}
            out = contract.record("kyiv", "kyiv_digital", {"url": "test"},
                                  [], [], env=env, checkpoint_path=checkpoint)
            self.assertIsNone(out)
            self.assertEqual(payload.read_text(), '{"cities": {}}')
            self.assertFalse(checkpoint.exists())

    def test_response_page_hashes_actual_content_bytes(self):
        contract = freshness.capture_contract()
        response = Mock(content=b'{"capture":true}', text='different decoded text')
        page = contract.response_page(response, url="https://example.org/source",
                                      started_at=datetime.now(timezone.utc) - timedelta(seconds=1))
        self.assertEqual(base64.b64decode(page["body_base64"]), response.content)
        self.assertEqual(page["body_sha256"], hashlib.sha256(response.content).hexdigest())

    def test_bootstrap_requires_true_capture_and_followup_overlap(self):
        contract = freshness.capture_contract()
        with tempfile.TemporaryDirectory() as d:
            payload = Path(d) / "payload.json"
            checkpoint = Path(d) / "checkpoints.json"
            payload.write_text('{"cities": {}}', encoding="utf-8")
            env = {"MULTICITY_CANONICAL_PAYLOAD_PATH": str(payload),
                   "C2_HISTORY_CAPTURE_ENABLED": "true", "GITHUB_RUN_ID": "123",
                   "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40,
                   "PHASE1_INPUT_SHA": "b" * 40}
            now = datetime.now(timezone.utc)
            completed = [{"start": now - timedelta(days=2),
                          "end": now - timedelta(days=1)}]
            def page(data):
                return contract.response_page(Mock(content=data), url="https://example.org/source",
                                              started_at=datetime.now(timezone.utc) - timedelta(seconds=1))
            identity = {"url": "https://example.org/source"}
            a = contract.record("kyiv", "kyiv_digital", identity, [page(b'one')],
                                completed, checkpoint_path=checkpoint, env=env)
            self.assertFalse(a["continuity_verified"])
            first = json.loads(checkpoint.read_text())["kyiv"]
            b = contract.record("kyiv", "kyiv_digital", identity, [page(b'two')],
                                completed, checkpoint_path=checkpoint, env=env)
            self.assertTrue(b["continuity_verified"])
            second = json.loads(checkpoint.read_text())["kyiv"]
            self.assertNotEqual(first["source_sha256"], second["source_sha256"])
            c = contract.record("kyiv", "kyiv_digital", identity, [page(b'three')],
                                [], checkpoint_path=checkpoint, env=env)
            self.assertFalse(c["continuity_verified"])
            self.assertEqual(json.loads(checkpoint.read_text())["kyiv"], second)


    def test_export_clock_uses_last_page_without_changing_freshness_clock(self):
        from scripts.c2_shadow_bundle import capture_validation_clock, BundleBlocked

        now = datetime.now(timezone.utc)
        first = (now - timedelta(minutes=4)).isoformat()
        last = (now - timedelta(minutes=1)).isoformat()
        receipts = [{"last_checked_at": first, "pages": [
            {"captured_at": first}, {"captured_at": last}]}]
        self.assertEqual(capture_validation_clock(receipts, now=now), now)
        # The conservative per-source freshness timestamp must remain the first page.
        self.assertEqual(receipts[0]["last_checked_at"], first)
        with self.assertRaisesRegex(BundleBlocked, "CAPTURE_PAGE_AFTER_EXPORT"):
            capture_validation_clock(receipts, now=now - timedelta(minutes=2))



if __name__ == "__main__":
    unittest.main()
