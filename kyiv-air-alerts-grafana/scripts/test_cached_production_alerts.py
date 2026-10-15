#!/usr/bin/env python3
"""Deterministic synthetic regression tests. No HTTP or DB credentials are used."""
import copy
import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import validate_cached_production_alerts as validator

UTC = timezone.utc
NOW = datetime(2026, 10, 15, 8, 0, tzinfo=UTC)


def timestamp(dt):
    return dt.isoformat().replace("+00:00", "Z")


def fixture():
    checkpoint = timestamp(NOW - timedelta(hours=1))
    stamp = timestamp(NOW - timedelta(hours=2))
    start = timestamp(NOW - timedelta(hours=3))
    end = timestamp(NOW - timedelta(hours=2, minutes=45))
    regions = {}
    events = []
    for i, city in enumerate(sorted(validator.EXPECTED_REGIONS), 1):
        rid = str(i)
        regions[city] = {
            "city_key": city, "region_id": rid, "api_region_name": city,
            "kind": "exact" if city in validator.EXACT_REGION_KEYS else "proxy",
            "continuous": True, "poll_overlap_verified": True,
            "last_checked_at": stamp, "last_error": None,
        }
        events.append({
            "city_key": city, "region_id": rid,
            "start": start, "end": end, "alert_type": "AIR",
        })
    return [
        {"schema_version": 3, "source_url": validator.EXPECTED_SOURCE_URL,
         "regions": regions, "events": events, "event_count": len(events),
         "last_successful_fetch_at": checkpoint, "last_fetch_error": None},
        [{"start": start, "end": end}],
        {"meta": {"complete_pair_count": 1, "updated_at": stamp},
         "pairs": [{"start": start, "end": end}]},
    ]


def evaluate(payloads, now=NOW):
    with tempfile.TemporaryDirectory() as temp:
        paths = [Path(temp) / name for name in ("bridge.json", "kyiv.json", "sev.json")]
        for path, obj in zip(paths, payloads):
            path.write_text(json.dumps(obj), encoding="utf-8")
        return validator.validate_snapshot(*paths, now=now, source_commit_sha="a" * 40)


class SnapshotValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def assert_rejected(self, expected):
        with self.assertRaisesRegex(validator.CachedSnapshotError, expected):
            evaluate(self.data)

    def test_valid_complete_21_regions(self):
        result = evaluate(self.data)
        self.assertEqual(result["valid_regions"], 21)
        self.assertEqual(result["event_count"], 21)
        self.assertEqual(result["mode"], "cached_bridge")

    def test_missing_bridge_file(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(validator.CachedSnapshotError, "file missing"):
                validator.validate_snapshot(Path(temp) / "missing", Path(temp) / "kyiv",
                                            Path(temp) / "sev", now=NOW)

    def test_malformed_json(self):
        with tempfile.TemporaryDirectory() as temp:
            names = [Path(temp) / f"{x}.json" for x in range(3)]
            names[0].write_text("{", encoding="utf-8")
            with self.assertRaisesRegex(validator.CachedSnapshotError, "invalid JSON"):
                validator.validate_snapshot(*names, now=NOW)

    def test_missing_region(self):
        del self.data[0]["regions"]["dnipro"]
        self.assert_rejected("21-region")

    def test_non_continuous(self):
        self.data[0]["regions"]["dnipro"]["continuous"] = False
        self.assert_rejected("not continuous")

    def test_failed_poll_overlap(self):
        self.data[0]["regions"]["dnipro"]["poll_overlap_verified"] = False
        self.assert_rejected("overlap")

    def test_non_null_global_error(self):
        self.data[0]["last_fetch_error"] = "429"
        self.assert_rejected("last_fetch_error")

    def test_non_null_regional_error(self):
        self.data[0]["regions"]["dnipro"]["last_error"] = "429"
        self.assert_rejected("regional fetch error")

    def test_wrong_event_count(self):
        self.data[0]["event_count"] += 1
        self.assert_rejected("event_count mismatch")

    def test_invalid_checkpoint(self):
        self.data[0]["last_successful_fetch_at"] = ""
        self.assert_rejected("missing timestamp")

    def test_future_checkpoint(self):
        self.data[0]["last_successful_fetch_at"] = timestamp(NOW + timedelta(seconds=1))
        self.assert_rejected("future")

    def test_just_below_12h(self):
        dt = NOW - timedelta(hours=12) + timedelta(seconds=1)
        self.data[0]["last_successful_fetch_at"] = timestamp(dt)
        for row in self.data[0]["regions"].values():
            row["last_checked_at"] = timestamp(dt)
        self.data[2]["meta"]["updated_at"] = timestamp(dt)
        for event in self.data[0]["events"]:
            event["start"] = timestamp(dt - timedelta(hours=1))
            event["end"] = timestamp(dt - timedelta(minutes=45))
        self.assertTrue(evaluate(self.data)["ok"])

    def test_just_above_12h(self):
        self.data[0]["last_successful_fetch_at"] = timestamp(NOW - timedelta(hours=12, seconds=1))
        self.assert_rejected("12-hour")

    def test_mixed_regional_freshness(self):
        self.data[0]["regions"]["dnipro"]["last_checked_at"] = timestamp(NOW - timedelta(hours=13))
        self.assert_rejected("12-hour")

    def test_future_regional_timestamp(self):
        self.data[0]["regions"]["dnipro"]["last_checked_at"] = timestamp(NOW + timedelta(seconds=1))
        self.assert_rejected("future")

    def test_regional_after_global(self):
        self.data[0]["regions"]["dnipro"]["last_checked_at"] = timestamp(NOW - timedelta(minutes=1))
        self.assert_rejected("later than global")

    def test_invalid_event_timestamp(self):
        self.data[0]["events"][0]["end"] = "broken"
        self.assert_rejected("malformed timestamp")

    def test_event_region_identity(self):
        self.data[0]["events"][0]["region_id"] = "999"
        self.assert_rejected("region_id mismatch")

    def test_event_duplicate(self):
        self.data[0]["events"].append(copy.deepcopy(self.data[0]["events"][0]))
        self.data[0]["event_count"] += 1
        self.assert_rejected("duplicate event")

    def test_sevastopol_metadata_count(self):
        self.data[2]["meta"]["complete_pair_count"] = 3
        self.assert_rejected("complete_pair_count mismatch")

    def test_no_token_and_no_transport(self):
        with patch.dict(os.environ, {}, clear=True), patch("socket.socket", side_effect=AssertionError("HTTP attempted")):
            self.assertTrue(evaluate(self.data)["ok"])

    def test_regression_retained_and_repeated_idempotent(self):
        snapshot = evaluate(self.data)
        start = self.data[1][0]["start"]
        end = self.data[1][0]["end"]
        polled = {
            city: [{
                "city_key": city, "episode_id": city+"-id",
                "alert_start": start, "alert_end": end,
            }] for city in validator.EXPECTED_REGIONS | validator.SPECIAL_CITY_KEYS
        }
        state = {
            "schema_version": 1,
            "cities": {"dnipro": {
                "episodes": [dict(polled["dnipro"][0])], "latest_api_alert_end": end,
            }},
        }
        first = validator.validate_episode_regression(polled, state, snapshot, is_proxy=lambda city: city=="dnipro")
        second = validator.validate_episode_regression(polled, copy.deepcopy(state), snapshot,
                                                       is_proxy=lambda city: city=="dnipro")
        self.assertEqual(first, second)
        self.assertEqual(first["retained_accepted_episode_ids"], 1)

    def test_regression_prior_checkpoint(self):
        snapshot = evaluate(self.data)
        polled = {city: [] for city in validator.EXPECTED_REGIONS | validator.SPECIAL_CITY_KEYS}
        state = {"schema_version": 1, "cities": {}, "cached_bridge_source": {
            "last_successful_fetch_at": timestamp(NOW),
            "event_count": 22, "input_sha256": {},
        }}
        with self.assertRaisesRegex(validator.CachedSnapshotError, "regressed"):
            validator.validate_episode_regression(polled, state, snapshot, is_proxy=lambda _: False)

    def test_regression_identity(self):
        snapshot = evaluate(self.data)
        start = self.data[1][0]["start"]
        end = self.data[1][0]["end"]
        polled = {city: [] for city in validator.EXPECTED_REGIONS | validator.SPECIAL_CITY_KEYS}
        polled["dnipro"] = [{"city_key":"dnipro", "episode_id":"new", "alert_start":start, "alert_end":end}]
        state = {"schema_version": 1, "cities": {"dnipro": {"episodes": [
            {"episode_id":"old", "alert_start":start, "alert_end":end}
        ]}}}
        with self.assertRaisesRegex(validator.CachedSnapshotError, "identity not in cached"):
            validator.validate_episode_regression(polled, state, snapshot, is_proxy=lambda _: False)

    def test_regression_no_state_mutation(self):
        snapshot = evaluate(self.data)
        polled = {city: [] for city in validator.EXPECTED_REGIONS | validator.SPECIAL_CITY_KEYS}
        state = {"schema_version":1, "cities":{}}
        frozen = copy.deepcopy(state)
        validator.validate_episode_regression(polled, state, snapshot, is_proxy=lambda _: False)
        self.assertEqual(state, frozen)


if __name__ == "__main__":
    unittest.main()
