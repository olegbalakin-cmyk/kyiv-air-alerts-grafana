"""Offline Sevastopol C6 source-capture continuity regression; never fetches HTTP."""
import base64
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import add_sevastopol_exact as sev
import c2_history_capture as cap

UTC = timezone.utc
PREV = datetime(2026, 11, 10, 13, 2, 31, tzinfo=UTC)
START = datetime(2026, 11, 4, 17, 14, 45, tzinfo=UTC)
NEXT = datetime(2026, 11, 5, 0, 31, 16, tzinfo=UTC)
SOURCE = {"url": sev.SOURCE_URL, "channel": sev.CHANNEL}


def html_messages(messages):
    rows = []
    for mid, at, text in messages:
        rows.append(
            '<div class="tgme_widget_message_wrap"><div class="tgme_widget_message" '
            'data-post="razvozhaev/%s"></div><time datetime="%s"></time>'
            '<div class="tgme_widget_message_text">%s</div></div>'
            % (mid, at.isoformat(), text))
    return "".join(rows).encode("utf-8")


def page(messages, url, captured):
    raw = html_messages(messages)
    return {"url": url, "started_at": (captured - timedelta(seconds=1)).isoformat(),
            "captured_at": captured.isoformat(), "body_sha256": hashlib.sha256(raw).hexdigest(),
            "body_base64": base64.b64encode(raw).decode("ascii")}


def checkpoint(at=PREV):
    return {"source_key": "sevastopol_history", "source_identity": SOURCE,
            "source_sha256": "a" * 64, "last_checked_at": at.isoformat(),
            "github_run_id": 42817288652, "github_run_attempt": 1,
            "workflow_sha": "b" * 40, "input_sha": "c" * 40}


def old_anomaly():
    return {"type": "missing_end_before_new_start",
            "start_id": 25006, "next_start_id": 25008,
            "start": {"at": START.isoformat()},
            "next_start": {"at": NEXT.isoformat()}}


def pages(captured=None):
    captured = captured or PREV + timedelta(hours=6)
    return [
        page([(25090, captured - timedelta(hours=1), "Внимание всем! Воздушная тревога!"),
              (25088, captured - timedelta(hours=2), "Отбой воздушной тревоги")],
             sev.SOURCE_URL, captured),
        page([(25080, PREV - timedelta(days=1), "Отбой воздушной тревоги"),
              (25079, PREV - timedelta(days=1, minutes=20), "Внимание всем! Воздушная тревога!")],
             sev.SOURCE_URL + "?before=25088", captured + timedelta(seconds=3))]


class SevastopolContinuityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.checkpoint_path = Path(self.tmp.name) / "checkpoints.json"
        self.payload = Path(self.tmp.name) / "payload.json"
        self.payload.write_text('{"cities": {}}', encoding="utf-8")
        self.store_checkpoint(checkpoint())
        self.env = {"MULTICITY_CANONICAL_PAYLOAD_PATH": str(self.payload),
                    "C2_HISTORY_CAPTURE_ENABLED": "true",
                    "GITHUB_RUN_ID": "42999999999", "GITHUB_RUN_ATTEMPT": "1",
                    "GITHUB_SHA": "d" * 40, "PHASE1_INPUT_SHA": "e" * 40}

    def store_checkpoint(self, value):
        self.checkpoint_path.write_text(json.dumps({"sevastopol": value}), encoding="utf-8")

    def eligible(self, anomalies=None, captured_pages=None):
        return sev.capture_continuity_eligible(
            [old_anomaly()] if anomalies is None else anomalies,
            pages() if captured_pages is None else captured_pages,
            checkpoint_path=self.checkpoint_path)

    def test_old_unresolved_event_does_not_veto_proven_capture(self):
        self.assertTrue(self.eligible())
        self.assertTrue(sev.source_capture_reaches_checkpoint(
            pages(), checkpoint()))
        self.assertLess(NEXT, PREV)

    def test_anomaly_crossing_previous_poll_blocks(self):
        a = old_anomaly()
        a["next_start"]["at"] = (PREV + timedelta(minutes=1)).isoformat()
        self.assertFalse(self.eligible([a]))
        self.assertFalse(self.eligible([{"type": "open_start", "start": {"at": START.isoformat()}}]))
        self.assertFalse(self.eligible([{"type": "orphan_end"}]))

    def test_missing_historical_source_overlap_blocks(self):
        current = PREV + timedelta(hours=6)
        new = [page([(25100, current, "Воздушная тревога")], sev.SOURCE_URL, current)]
        self.assertFalse(self.eligible(captured_pages=new))
        self.assertFalse(self.eligible(captured_pages=[]))

    def test_empty_truncated_or_broken_pagination_blocks(self):
        p = pages()
        p[1] = page([], p[1]["url"], PREV + timedelta(hours=6, seconds=3))
        self.assertFalse(self.eligible(captured_pages=p))
        p = pages()
        p[1]["url"] = sev.SOURCE_URL + "?before=25000"
        self.assertFalse(self.eligible(captured_pages=p))
        p = pages()
        self.assertFalse(self.eligible(captured_pages=p[:1]))
        p = pages()
        p[1] = p[0].copy()
        p[1]["url"] = sev.SOURCE_URL + "?before=25088"
        self.assertFalse(self.eligible(captured_pages=p))

    def test_source_identity_hash_and_clock_mismatch_blocks(self):
        p = pages()
        p[0]["body_sha256"] = "0" * 64
        self.assertFalse(self.eligible(captured_pages=p))
        p = pages()
        p[0]["body_base64"] = "!!"
        self.assertFalse(self.eligible(captured_pages=p))
        old = checkpoint()
        old["source_identity"] = {"url": "https://other.invalid", "channel": "razvozhaev"}
        self.store_checkpoint(old)
        self.assertFalse(self.eligible())
        old = checkpoint()
        old["source_sha256"] = "not-a-sha"
        self.store_checkpoint(old)
        self.assertFalse(self.eligible())
        self.store_checkpoint(checkpoint(PREV + timedelta(days=5)))
        self.assertFalse(self.eligible())

    def test_repeated_cycles_no_duplicate_or_unproven_checkpoint(self):
        p1 = pages()
        completed = [{"start": (PREV - timedelta(days=1, minutes=20)).isoformat(),
                      "end": (PREV - timedelta(days=1)).isoformat()}]
        self.assertTrue(self.eligible(captured_pages=p1))
        a = cap.record("sevastopol", "sevastopol_history", SOURCE, p1,
                       completed, continuity=self.eligible(captured_pages=p1),
                       checkpoint_path=self.checkpoint_path, env=self.env)
        self.assertTrue(a["continuity_verified"])
        first = json.loads(self.checkpoint_path.read_text())["sevastopol"]
        self.assertEqual(first["github_run_id"], int(self.env["GITHUB_RUN_ID"]))
        self.assertEqual(len(a["completed_air"]), 1)

        p2 = pages(PREV + timedelta(hours=8))
        self.assertTrue(self.eligible(captured_pages=p2))
        b = cap.record("sevastopol", "sevastopol_history", SOURCE, p2,
                       completed + completed, continuity=self.eligible(captured_pages=p2),
                       checkpoint_path=self.checkpoint_path, env=self.env)
        self.assertTrue(b["continuity_verified"])
        self.assertEqual(len(b["completed_air"]), 1)
        second = json.loads(self.checkpoint_path.read_text())["sevastopol"]
        self.assertGreater(cap.utc(second["last_checked_at"]), cap.utc(first["last_checked_at"]))

        bad = pages(PREV + timedelta(hours=10))[:1]
        self.assertFalse(self.eligible(captured_pages=bad))
        c = cap.record("sevastopol", "sevastopol_history", SOURCE, bad, [],
                       continuity=self.eligible(captured_pages=bad),
                       checkpoint_path=self.checkpoint_path, env=self.env)
        self.assertFalse(c["continuity_verified"])
        self.assertEqual(json.loads(self.checkpoint_path.read_text())["sevastopol"], second)

    def test_event_25006_never_completed_by_helper(self):
        a = old_anomaly()
        original = json.dumps(a, sort_keys=True)
        self.assertTrue(self.eligible([a]))
        self.assertEqual(json.dumps(a, sort_keys=True), original)
        self.assertNotIn("end", a)

    def test_disabled_capture_is_noop(self):
        before = self.checkpoint_path.read_bytes()
        out = cap.record("sevastopol", "sevastopol_history", SOURCE, [], [],
                         checkpoint_path=self.checkpoint_path, env={})
        self.assertIsNone(out)
        self.assertEqual(self.checkpoint_path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
