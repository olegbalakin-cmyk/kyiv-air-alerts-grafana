#!/usr/bin/env python3
"""Offline regression for within-local-day alert-segment means (no source fetch)."""
import sys
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from update_data import Alert, TZ, UTC, build_outputs, union_daily_seconds, union_daily_segment_counts


def alert(start, end):
    return Alert(datetime.fromisoformat(start), datetime.fromisoformat(end), "synthetic")


class DailyMidnightDurationTests(unittest.TestCase):
    def test_real_october_5_case(self):
        intervals = [
            alert("2026-10-04T23:32:50+03:00", "2026-10-05T00:38:04+03:00"),
            alert("2026-10-05T20:21:23+03:00", "2026-10-05T20:27:37+03:00"),
        ]
        rows = build_outputs(intervals, datetime(2026, 10, 7, tzinfo=TZ), {})["daily28"]
        row = next(row for row in rows if row["date"] == "2026-10-05")
        self.assertEqual(row["alerts_started"], 1)
        self.assertEqual(row["active_alerts"], 2)
        self.assertEqual(row["total_alert_duration_minutes"], 44.3)
        self.assertEqual(row["avg_alert_duration_minutes"], 6.233)  # legacy compatibility
        self.assertEqual(row["avg_active_alert_duration_minutes"], 22.15)

    def test_overlap_and_touching_source_intervals_do_not_double_count(self):
        intervals = [
            alert("2026-10-05T00:00:00+03:00", "2026-10-05T00:10:00+03:00"),
            alert("2026-10-05T00:05:00+03:00", "2026-10-05T00:15:00+03:00"),
            alert("2026-10-05T00:15:00+03:00", "2026-10-05T00:20:00+03:00"),
            alert("2026-10-05T04:00:00+03:00", "2026-10-05T04:10:00+03:00"),
        ]
        day = date(2026, 10, 5)
        self.assertEqual(union_daily_segment_counts(intervals, day, day)[day], 2)
        self.assertEqual(union_daily_seconds(intervals, day, day)[day], 1800)

    def test_zero_starts_but_active_cross_midnight(self):
        intervals = [alert("2026-10-04T23:50:00+03:00", "2026-10-05T00:20:00+03:00")]
        rows = build_outputs(intervals, datetime(2026, 10, 7, tzinfo=TZ), {})["daily28"]
        row = next(row for row in rows if row["date"] == "2026-10-05")
        self.assertEqual(row["alerts_started"], 0)
        self.assertEqual(row["active_alerts"], 1)
        self.assertEqual(row["avg_active_alert_duration_minutes"], 20)
        self.assertIsNone(row["avg_alert_duration_minutes"])

    def test_no_active_intervals_is_null(self):
        intervals = [alert("2026-10-04T01:00:00+03:00", "2026-10-04T01:10:00+03:00")]
        rows = build_outputs(intervals, datetime(2026, 10, 7, tzinfo=TZ), {})["daily28"]
        row = next(row for row in rows if row["date"] == "2026-10-05")
        self.assertEqual(row["active_alerts"], 0)
        self.assertIsNone(row["avg_active_alert_duration_minutes"])

    def test_dst_end_midnight_is_local_not_24h_utc_offset(self):
        intervals = [alert("2026-10-24T23:00:00+03:00", "2026-10-25T04:00:00+02:00")]
        a = date(2026, 10, 24)
        b = date(2026, 10, 25)
        self.assertEqual(union_daily_segment_counts(intervals, a, b), {a: 1, b: 1})
        self.assertEqual(union_daily_seconds(intervals, a, b)[a], 3600)
        self.assertEqual(union_daily_seconds(intervals, a, b)[b], 18000)


if __name__ == "__main__":
    unittest.main()
