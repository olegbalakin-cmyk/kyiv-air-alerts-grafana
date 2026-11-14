"""Four accepted Oct 25 DST witnesses; pure offline UTC union regression."""
from datetime import datetime, timezone
from pathlib import Path
import socket
import sys
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import apply_ukrainealarm_bridge as bridge

UTC = timezone.utc
KYIV = ZoneInfo("Europe/Kyiv")
# Exact source intervals from C6-DST-UTC-01; Cherkasy first row must be preserved.
WITNESSES = {
    "cherkasy": [
        ("2026-10-25T00:06:18.166695Z", "2026-10-25T00:26:58.650073Z"),
        ("2026-10-25T01:14:53.333785Z", "2026-10-25T01:19:09.997656Z"),
    ],
    "kharkiv": [
        ("2026-10-24T23:24:46.944947Z", "2026-10-25T00:30:17.068083Z"),
        ("2026-10-25T01:25:28.327265Z", "2026-10-25T02:22:46.862159Z"),
    ],
    "poltava": [
        ("2026-10-25T00:06:15.155767Z", "2026-10-25T00:26:57.986096Z"),
        ("2026-10-25T01:17:40.643305Z", "2026-10-25T01:29:42.507155Z"),
    ],
    "zhytomyr": [
        ("2026-10-25T00:06:17.978268Z", "2026-10-25T00:26:58.980319Z"),
        ("2026-10-25T01:16:21.087757Z", "2026-10-25T01:30:52.777820Z"),
    ],
}


def utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def alert(a, b):
    return bridge.Alert(start=utc(a).astimezone(KYIV),
                        end=utc(b).astimezone(KYIV), source="original")


def intervals(rows):
    return [(v.start.astimezone(UTC), v.end.astimezone(UTC)) for v in rows]


class UTCUnionRegression(unittest.TestCase):
    def setUp(self):
        self.p = patch.object(socket.socket, "connect",
                              side_effect=AssertionError("NO_SOURCE_HTTP"))
        self.p.start()
        self.addCleanup(self.p.stop)

    def test_four_accepted_city_witnesses_remain_separate(self):
        for city, cases in WITNESSES.items():
            with self.subTest(city=city):
                rows = bridge.union_alerts([alert(*v) for v in reversed(cases)], "union")
                self.assertEqual(intervals(rows), [(utc(a), utc(b)) for a, b in cases])
                self.assertEqual([x.source for x in rows], ["union"] * len(cases))

    def test_fold_sort_is_by_utc_instants(self):
        early = alert("2026-10-25T00:50:00Z", "2026-10-25T00:55:00Z")
        late = alert("2026-10-25T01:10:00Z", "2026-10-25T01:20:00Z")
        self.assertEqual(intervals(bridge.union_alerts([late, early], "union")),
                         intervals([early, late]))

    def test_overlapping_end_extends_past_fold(self):
        a = alert("2026-10-24T23:00:00Z", "2026-10-25T00:50:00Z")
        b = alert("2026-10-25T00:30:00Z", "2026-10-25T01:20:00Z")
        self.assertEqual(intervals(bridge.union_alerts([b, a], "union")),
                         [(utc("2026-10-24T23:00:00Z"), utc("2026-10-25T01:20:00Z"))])

    def test_touching_union_and_empty_preserve_original_contract(self):
        a = alert("2026-10-24T20:00:00Z", "2026-10-24T21:00:00Z")
        b = alert("2026-10-24T21:00:00Z", "2026-10-24T22:00:00Z")
        merged = bridge.union_alerts([b, a], "union")
        self.assertEqual(intervals(merged),
                         [(utc("2026-10-24T20:00:00Z"), utc("2026-10-24T22:00:00Z"))])
        self.assertIs(merged[0].start.tzinfo, KYIV)
        self.assertEqual(bridge.union_alerts([], "union"), [])

    def test_idempotence_and_no_provenance_or_timezone_loss(self):
        original = [alert(*v) for v in WITNESSES["kharkiv"]]
        once = bridge.union_alerts(original, "merged")
        twice = bridge.union_alerts(once, "merged")
        self.assertEqual(intervals(once), intervals(twice))
        self.assertTrue(all(v.start.tzinfo is KYIV and v.end.tzinfo is KYIV for v in twice))


if __name__ == "__main__":
    unittest.main()
