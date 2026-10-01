from datetime import date, datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_data as u


def alert(start, end, source="test"):
    return u.Alert(start.replace(tzinfo=u.TZ), end.replace(tzinfo=u.TZ), source)


def rows_by_date(alerts, now=datetime(2026, 9, 13, 12, 0, tzinfo=u.TZ)):
    output = u.build_outputs(alerts, now, {})
    return {row["date"]: row for row in output["daily28"]}


def segment_minutes(segments):
    return [(end - start).total_seconds() / 60.0 for start, end in segments]


def test_cross_midnight_whole_next_day_and_start_based_compatibility():
    rows = rows_by_date([
        alert(datetime(2026, 9, 10, 23, 59), datetime(2026, 9, 12, 0, 1))
    ])
    assert rows["2026-09-10"]["active_alerts"] == 1
    assert rows["2026-09-10"]["avg_active_alert_duration_minutes"] == 1
    assert rows["2026-09-11"]["active_alerts"] == 1
    assert rows["2026-09-11"]["avg_active_alert_duration_minutes"] == 1440
    assert rows["2026-09-12"]["active_alerts"] == 1
    assert rows["2026-09-12"]["avg_active_alert_duration_minutes"] == 1
    assert rows["2026-09-10"]["alerts_started"] == 1
    assert rows["2026-09-10"]["avg_alert_duration_minutes"] == 1442
    assert rows["2026-09-11"]["alerts_started"] == 0
    assert rows["2026-09-11"]["avg_alert_duration_minutes"] is None
    assert rows["2026-09-12"]["alerts_started"] == 0


def test_ends_exactly_at_midnight_is_half_open():
    segments = u.daily_active_segments(
        [alert(datetime(2026, 9, 10, 23, 0), datetime(2026, 9, 11, 0, 0))],
        date(2026, 9, 10),
        date(2026, 9, 11),
    )
    assert segment_minutes(segments[date(2026, 9, 10)]) == [60]
    assert segments[date(2026, 9, 11)] == []


def test_starts_exactly_at_midnight():
    segments = u.daily_active_segments(
        [alert(datetime(2026, 9, 11, 0, 0), datetime(2026, 9, 11, 2, 0))],
        date(2026, 9, 11),
        date(2026, 9, 11),
    )
    assert segment_minutes(segments[date(2026, 9, 11)]) == [120]


def test_multiple_active_episodes_average_individual_clips():
    rows = rows_by_date([
        alert(datetime(2026, 9, 11, 1, 0), datetime(2026, 9, 11, 7, 0), "a"),
        alert(datetime(2026, 9, 11, 10, 0), datetime(2026, 9, 11, 12, 0), "b"),
    ])
    row = rows["2026-09-11"]
    assert row["active_alerts"] == 2
    assert row["avg_active_alert_duration_minutes"] == 240


def test_carry_in_at_start_of_28_day_window():
    rows = rows_by_date([
        alert(datetime(2026, 8, 15, 23, 0), datetime(2026, 8, 16, 2, 0))
    ])
    row = rows["2026-08-16"]
    assert row["alerts_started"] == 0
    assert row["active_alerts"] == 1
    assert row["avg_active_alert_duration_minutes"] == 120


def test_union_time_remains_distinct_from_active_episode_count():
    rows = rows_by_date([
        alert(datetime(2026, 9, 11, 10, 0), datetime(2026, 9, 11, 12, 0), "a"),
        alert(datetime(2026, 9, 11, 11, 0), datetime(2026, 9, 11, 13, 0), "b"),
    ])
    row = rows["2026-09-11"]
    assert row["total_alert_duration_minutes"] == 180
    assert row["active_alerts"] == 2
    assert row["avg_active_alert_duration_minutes"] == 120
    assert row["alerts_started"] == 2
    assert row["avg_alert_duration_minutes"] == 120


def test_dst_day_uses_actual_elapsed_time_not_1440_constant():
    segments = u.daily_active_segments(
        [alert(datetime(2024, 10, 27, 0, 0), datetime(2024, 10, 28, 0, 0))],
        date(2024, 10, 27),
        date(2024, 10, 27),
    )
    assert segment_minutes(segments[date(2024, 10, 27)]) == [1500]
