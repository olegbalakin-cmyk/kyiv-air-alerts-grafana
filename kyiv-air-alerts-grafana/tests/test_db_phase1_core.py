from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from db_phase1_core import (  # noqa: E402
    Interval,
    alerts_in_ua_source_record_key,
    legacy_episode_id,
    merge_intervals,
    parse_timestamp,
    reconcile_api_manual,
    ukrainealarm_source_record_key,
    vadimkin_source_record_key,
)


class SourceRecordKeyVectors(unittest.TestCase):
    def test_ukrainealarm_literal_vector_and_timezone_equivalence(self):
        original = {
            "city_key": " lviv ",
            "region_id": "90",
            "alert_type": "AIR",
            "start_at": "2026-09-12T22:00:05.398348Z",
            "end_at": "2026-09-12T22:14:23.315771+00:00",
        }
        expected_json = '{"alert_type":"AIR","city_key":"lviv","end_at":"2026-09-12T22:14:23.315771Z","region_id":"90","start_at":"2026-09-12T22:00:05.398348Z","version":"ukrainealarm-region-history-v1"}'
        expected_digest = "6438e15f3ba3fc00edafa8bbfe1e00059376367cde5940f8c982129173aae0b4"
        actual_json, actual_digest = ukrainealarm_source_record_key(original)
        self.assertEqual(expected_json, actual_json)
        self.assertEqual(expected_digest, actual_digest)

        equivalent = dict(
            original,
            start_at="2026-09-13T01:00:05.398348+03:00",
            end_at="2026-09-13T01:14:23.315771+03:00",
        )
        self.assertEqual(expected_digest, ukrainealarm_source_record_key(equivalent)[1])
        changed = dict(original, end_at="2026-09-12T22:14:23.315772Z")
        self.assertNotEqual(expected_digest, ukrainealarm_source_record_key(changed)[1])

    def test_alertsinua_literal_vector_non_utc(self):
        original = {
            "city_key": " lviv ",
            "alert_type": "AIR",
            "start_at": "2026-09-13T01:00:06+03:00",
            "end_at": "2026-09-13T01:14:27+03:00",
        }
        expected_json = '{"alert_type":"AIR","city_key":"lviv","end_at":"2026-09-12T22:14:27.000000Z","start_at":"2026-09-12T22:00:06.000000Z","version":"alerts-in-ua-v1"}'
        expected_digest = "980d8771eb46bca4bc542aa98c987795f254e01ce4fc59d25b1e4cd0fb55c7e0"
        self.assertEqual(
            (expected_json, expected_digest),
            alerts_in_ua_source_record_key(original),
        )
        equivalent = dict(
            original,
            start_at="2026-09-12T22:00:06Z",
            end_at="2026-09-12T22:14:27+00:00",
        )
        self.assertEqual(expected_digest, alerts_in_ua_source_record_key(equivalent)[1])

    def test_vadimkin_literal_vector_unicode_nfc(self):
        original = {
            "level": " raion ",
            "oblast": "Львівська область",
            "raion": "Львівський район",
            "hromada": " Cafe\u0301 ",
            "source": " official_data_uk ",
            "start_at": "2026-01-01T02:00:00+02:00",
            "end_at": "2026-01-01T03:30:00+02:00",
        }
        expected_json = '{"end_at":"2026-01-01T01:30:00.000000Z","hromada":"Café","level":"raion","oblast":"Львівська область","raion":"Львівський район","source":"official_data_uk","start_at":"2026-01-01T00:00:00.000000Z","version":"vadimkin-official-data-uk-v1"}'
        expected_digest = "cd1687233c7d2413e692845c965a81590222d4b511008ad3d8d06379f5dc6378"
        self.assertEqual(
            (expected_json, expected_digest),
            vadimkin_source_record_key(original),
        )
        equivalent = dict(original, hromada="Café")
        self.assertEqual(expected_digest, vadimkin_source_record_key(equivalent)[1])


class LegacyAndUnionTests(unittest.TestCase):
    def test_legacy_ids_remain_byte_compatible(self):
        self.assertEqual(
            "b3df9090f7264ddbd726e113",
            legacy_episode_id(
                "lviv",
                "2026-09-12T22:00:05.398348Z",
                "2026-09-12T22:14:23.315771Z",
            ),
        )
        self.assertEqual(
            "b6bdcdab5875c553d87509f1",
            legacy_episode_id(
                "lviv",
                "2025-09-01T07:19:00Z",
                "2025-09-01T07:40:44Z",
            ),
        )
        self.assertEqual(
            "7dd411c2a2587efc740a1a66",
            legacy_episode_id(
                "lviv",
                "2026-09-12T22:00:05.398348Z",
                "2026-09-12T22:14:27Z",
            ),
        )

    def test_overlap_touch_and_gap(self):
        a = Interval(
            parse_timestamp("2026-01-01T00:00:00Z"),
            parse_timestamp("2026-01-01T01:00:00Z"),
        )
        overlap = Interval(
            parse_timestamp("2026-01-01T00:30:00Z"),
            parse_timestamp("2026-01-01T02:00:00Z"),
        )
        touch = Interval(
            parse_timestamp("2026-01-01T02:00:00Z"),
            parse_timestamp("2026-01-01T03:00:00Z"),
        )
        gap = Interval(
            parse_timestamp("2026-01-01T03:00:00.000001Z"),
            parse_timestamp("2026-01-01T04:00:00Z"),
        )
        merged = merge_intervals([gap, touch, overlap, a])
        self.assertEqual(2, len(merged))
        self.assertEqual(parse_timestamp("2026-01-01T00:00:00Z"), merged[0].start)
        self.assertEqual(parse_timestamp("2026-01-01T03:00:00Z"), merged[0].end)

    def test_stage_b_negative_guards(self):
        api = {
            "city_key": "kharkiv",
            "alert_type": "AIR",
            "start_at": "2026-01-01T00:00:00Z",
            "end_at": "2026-01-01T01:00:00Z",
        }
        self.assertFalse(
            reconcile_api_manual(
                api, dict(api, start_at="2026-01-01T00:00:15.001Z")
            )["matched"]
        )
        self.assertFalse(
            reconcile_api_manual(
                api, dict(api, end_at="2026-01-01T01:00:15.001Z")
            )["matched"]
        )
        self.assertFalse(
            reconcile_api_manual(api, dict(api, city_key="sumy"))["matched"]
        )
        self.assertFalse(
            reconcile_api_manual(api, dict(api, alert_type="ARTILLERY"))["matched"]
        )


if __name__ == "__main__":
    unittest.main()
