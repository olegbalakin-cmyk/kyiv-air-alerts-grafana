"""Offline, synthetic-only C6 UkraineAlarm replay timestamp regressions.

No HTTP, database, production workflow, or real-capture assertion.
"""
import base64
import copy
import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock

from scripts import c2_shadow_bundle as bundle
from scripts import c6_history_freshness as freshness


SOURCE = "ukrainealarm_region_history"
URL = "https://api.ukrainealarm.com/api/v3/alerts/regionHistory"
IDENTITY = {"url": URL, "region_id": "17"}
RUN = {"github_run_id": 31415, "github_run_attempt": 1,
       "workflow_sha": "a" * 40, "input_sha": "b" * 40}


def source_bytes(start, end, *, kind="AIR"):
    return json.dumps([{"alarms": [{"alertType": kind, "startDate": start,
                                   "endDate": end}]}], separators=(",", ":")).encode()


def example(*, start="2026-11-10T01:00:00", end="2026-11-10T02:00:00",
            previous=True, completed=None, kind="AIR"):
    contract = freshness.capture_contract()
    now = datetime.now(timezone.utc)
    raw = source_bytes(start, end, kind=kind)
    page = contract.response_page(Mock(content=raw),
        url=URL + "?regionId=17", started_at=now - timedelta(seconds=5))
    previous_row = ({"source_key": SOURCE, "source_identity": IDENTITY,
                     "last_checked_at": "2026-11-10T01:30:00+00:00",
                     "source_sha256": "f" * 64, **RUN} if previous else None)
    with tempfile.TemporaryDirectory() as temp:
        payload = Path(temp) / "payload.json"
        checkpoint = Path(temp) / "checkpoint.json"
        payload.write_text('{"cities": {"testcity": {"episodes": []}}}')
        env = {"C2_HISTORY_CAPTURE_ENABLED": "true",
               "MULTICITY_CANONICAL_PAYLOAD_PATH": str(payload),
               "GITHUB_RUN_ID": str(RUN["github_run_id"]),
               "GITHUB_RUN_ATTEMPT": str(RUN["github_run_attempt"]),
               "GITHUB_SHA": RUN["workflow_sha"], "PHASE1_INPUT_SHA": RUN["input_sha"]}
        if completed is None:
            completed = [{"start": contract.ukrainealarm_event_utc(start),
                          "end": contract.ukrainealarm_event_utc(end)}]
        row = contract.record("testcity", SOURCE, IDENTITY, [page],
            completed, previous=previous_row, checkpoint_path=checkpoint, env=env)
        assert row is not None
    return row, raw, now


def verify(row, *, at=None, source=SOURCE):
    return freshness.capture_contract().verify(
        row, city="testcity", source_key=source, run_identity=RUN,
        read_at=at or datetime.now(timezone.utc) + timedelta(seconds=2))


def resign(row):
    contract = freshness.capture_contract()
    row["source_sha256"] = contract.fingerprint(row["pages"])
    row["completed_air_sha256"] = contract.fingerprint(row["completed_air"])
    row["previous_checkpoint_sha256"] = contract.fingerprint(row["previous_checkpoint"])
    row["oldest_fetched_completed_air_start"] = (
        row["completed_air"][0]["start"] if row["completed_air"] else None)
    return row


class SourceSpecificTimestampTests(unittest.TestCase):
    def test_naive_ukrainealarm_replay_and_normalized_completed_intervals(self):
        row, raw, _ = example()
        contract = freshness.capture_contract()
        self.assertEqual(contract.replay(row), row["completed_air"])
        self.assertEqual(row["completed_air"][0]["start"], "2026-11-10T01:00:00+00:00")
        self.assertTrue(verify(row))
        self.assertEqual(base64.b64decode(row["pages"][0]["body_base64"]), raw)
        self.assertEqual(row["pages"][0]["body_sha256"], hashlib.sha256(raw).hexdigest())
        self.assertFalse(row["publication_allowed"])

    def test_z_and_explicit_offset_are_converted_to_same_utc_instant(self):
        for start, end in [
            ("2026-11-10T01:00:00Z", "2026-11-10T02:00:00Z"),
            ("2026-11-10T03:00:00+02:00", "2026-11-10T04:00:00+02:00"),
            ("2026-11-09T20:00:00-05:00", "2026-11-09T21:00:00-05:00"),
        ]:
            with self.subTest(start=start):
                row, raw, _ = example(start=start, end=end)
                self.assertTrue(verify(row))
                self.assertEqual(row["completed_air"][0]["start"],
                                 "2026-11-10T01:00:00+00:00")
                self.assertEqual(base64.b64decode(row["pages"][0]["body_base64"]), raw)

    def test_non_air_and_inverted_ranges_cannot_be_included(self):
        contract = freshness.capture_contract()
        row, _, _ = example(kind="ARTILLERY", completed=[])
        self.assertTrue(verify(row) is False)
        row, _, _ = example(start="2026-11-10T02:00:00",
                            end="2026-11-10T01:00:00", completed=[])
        self.assertFalse(verify(row))
        self.assertEqual(contract.replay(row), [])

    def test_strict_clock_and_unknown_source_are_not_relaxed(self):
        contract = freshness.capture_contract()
        for bad in ("2026-11-10T01:00:00", datetime(2026, 11, 10, 1)):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(ValueError, "CAPTURE_NAIVE_TIMESTAMP"):
                    contract.utc(bad)
        row, _, _ = example()
        row["pages"][0]["started_at"] = "2026-11-10T01:00:00"
        resign(row)
        with self.assertRaisesRegex(ValueError, "CAPTURE_NAIVE_TIMESTAMP"):
            verify(row)
        row, _, _ = example()
        row["source_key"] = "unrecognized"
        resign(row)
        with self.assertRaisesRegex(ValueError, "CAPTURE_SCHEMA"):
            verify(row, source=SOURCE)
        with self.assertRaisesRegex(ValueError, "CAPTURE_UNKNOWN_SOURCE"):
            contract.replay(row)

    def test_body_hash_provenance_run_identity_and_false_continuity(self):
        row, _, _ = example()
        self.assertTrue(verify(row))
        tampered = copy.deepcopy(row)
        tampered["pages"][0]["body_base64"] = base64.b64encode(b'{"alarms":[]}').decode()
        with self.assertRaisesRegex(ValueError, "CAPTURE_SOURCE_SHA"):
            verify(tampered)
        tampered = copy.deepcopy(row)
        tampered["pages"][0]["body_base64"] = base64.b64encode(b'{"alarms":[]}').decode()
        resign(tampered)
        with self.assertRaisesRegex(ValueError, "CAPTURE_BODY_SHA"):
            verify(tampered)
        tampered = copy.deepcopy(row)
        tampered["github_run_id"] += 1
        with self.assertRaisesRegex(ValueError, "CAPTURE_RUN_MISMATCH"):
            verify(tampered)
        tampered = copy.deepcopy(row)
        tampered["previous_checkpoint"]["last_checked_at"] = (
            datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        tampered["previous_checked_at"] = tampered["previous_checkpoint"]["last_checked_at"]
        resign(tampered)
        with self.assertRaisesRegex(ValueError, "CAPTURE_FALSE_CONTINUITY"):
            verify(tampered)
        tampered = copy.deepcopy(row)
        tampered["completed_air"][0]["end"] = "2026-11-10T01:30:00+00:00"
        resign(tampered)
        with self.assertRaisesRegex(ValueError, "CAPTURE_REPLAY_MISMATCH"):
            verify(tampered)

    def test_capture_clocks_and_export_clock_fail_closed(self):
        row, _, _ = example()
        self.assertTrue(verify(row))
        early = datetime.fromisoformat(row["pages"][0]["captured_at"]) - timedelta(seconds=1)
        with self.assertRaisesRegex(ValueError, "CAPTURE_CLOCK"):
            verify(row, at=early)
        with self.assertRaisesRegex(bundle.BundleBlocked, "CAPTURE_PAGE_AFTER_EXPORT"):
            bundle.capture_validation_clock([row], now=early)
        self.assertEqual(row["last_checked_at"], row["pages"][0]["captured_at"])

    def test_synthetic_bundle_export_happy_path_and_independent_verification(self):
        # This exercises the real export/archive verifier with only synthetic data.
        # A mock C2 receipt verifier stands in for the production DB-dependent gate.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            site = root / "site"
            (site / "data").mkdir(parents=True)
            keys = ["testcity"] + ["city" + str(i) for i in range(22)]
            rows = [{"city_key": k, "uuid": "synthetic-" + k} for k in keys]
            serial = {"canonicalization_version": "alert-canonicalization-v1",
                      "production_city_keys": keys, "episodes": rows}
            corpus = hashlib.sha256(json.dumps(serial, ensure_ascii=False,
                sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
            receipt = {"corpus_sha256": corpus, "city_count": 23,
                       "canonical_episode_count": 23, "run_id": "synthetic-run",
                       "workflow_sha": RUN["workflow_sha"], "input_sha": RUN["input_sha"],
                       "db_branch": "br-synthetic-test"}
            status = {"canonical_persistence_status": "NEON_SUCCEEDED",
                      "canonical_receipt_validated": True,
                      "canonical_db_commit": "CONFIRMED",
                      "workflow_sha": RUN["workflow_sha"], "input_sha": RUN["input_sha"]}
            payload = {"format": "multicity-canonical-same-run-v1",
                       "canonicalization_version": "alert-canonicalization-v1",
                       "cities": {k: {"episodes": [r], "episode_count": 1}
                                  for k, r in zip(keys, rows)}}
            row, raw, _ = example()
            payload["history_capture_contract"] = "c2-history-capture-v1"
            payload["historical_source_receipts"] = {"testcity": row}
            paths = {}
            for name, obj in (("receipt", receipt), ("status", status), ("payload", payload)):
                path = root / (name + ".json")
                path.write_text(json.dumps(obj, sort_keys=True))
                paths[name] = path
            for name in bundle.SITE_DATA:
                content = ({"multicity_meta": {"production_city_keys": keys}}
                           if name == "dashboard_data.json" else {})
                (site / "data" / name).write_text(json.dumps(content))
            output = root / "export"
            result = bundle.export_bundle(enabled="true", site=site,
                receipt_path=paths["receipt"], status_path=paths["status"],
                payload_path=paths["payload"], output=output,
                run_id=RUN["github_run_id"], run_attempt=1,
                workflow_sha=RUN["workflow_sha"], input_sha=RUN["input_sha"],
                db_branch="br-synthetic-test",
                writer_url="postgresql://placeholder@ep-synthetic.us-east-2.aws.neon.tech/test",
                verifier=lambda _: receipt)
            self.assertEqual(result["status"], "EXPORTED")
            path = output / "c2-shadow-inputs.zip"
            manifest = bundle.verify_archive(path, result["bundle_sha256"])
            self.assertIn("testcity", manifest["historical_capture_receipts"]["receipt_cities"])
            self.assertEqual(manifest["historical_capture_receipts"]["publication_allowed"], False)
            self.assertEqual(manifest["files"]["payload.json"],
                             hashlib.sha256(paths["payload"].read_bytes()).hexdigest())
            import zipfile
            with zipfile.ZipFile(path) as archive:
                retained = json.loads(archive.read("payload.json"))
            kept = retained["historical_source_receipts"]["testcity"]["pages"][0]
            self.assertEqual(base64.b64decode(kept["body_base64"]), raw)
            self.assertEqual(kept["body_sha256"], hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    unittest.main()
