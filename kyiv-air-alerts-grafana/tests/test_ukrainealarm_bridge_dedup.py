from copy import deepcopy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import apply_ukrainealarm_bridge as bridge


def api(start="2026-09-25T10:00:00Z", end="2026-09-25T11:00:00Z", city="sumy"):
    return {
        "city_key": city,
        "region_id": "114",
        "api_region_name": "Сумський район",
        "start": start,
        "end": end,
        "alert_type": "AIR",
    }


def manual(start="2026-09-25T10:00:05Z", end="2026-09-25T11:00:05Z", city="sumy"):
    return {
        "city_key": city,
        "region_id": "114",
        "api_region_name": "Сумський район",
        "start": start,
        "end": end,
        "alert_type": "AIR",
        "source": "alerts.in.ua_manual_csv_recovery",
        "source_kind": "manual_csv_export",
        "source_files": ["alerts.csv"],
        "recovery_artifact": "research/recovery.json",
    }


def test_manual_recovery_plus_api_within_tolerance_one_api_event():
    rows = bridge.reconcile_completed_air_events([manual(), api()])
    assert len(rows) == 1
    assert rows[0]["start"] == api()["start"]
    assert rows[0]["end"] == api()["end"]
    assert "source" not in rows[0]


def test_exactly_15_seconds_dedupes():
    rows = bridge.reconcile_completed_air_events(
        [manual("2026-09-25T10:00:15Z", "2026-09-25T11:00:15Z"), api()]
    )
    assert len(rows) == 1


def test_more_than_15_seconds_on_start_is_distinct():
    rows = bridge.reconcile_completed_air_events(
        [manual("2026-09-25T10:00:15.001Z", "2026-09-25T11:00:00Z"), api()]
    )
    assert len(rows) == 2


def test_more_than_15_seconds_on_end_is_distinct():
    rows = bridge.reconcile_completed_air_events(
        [manual("2026-09-25T10:00:00Z", "2026-09-25T11:00:15.001Z"), api()]
    )
    assert len(rows) == 2


def test_same_timestamps_different_city_is_distinct():
    rows = bridge.reconcile_completed_air_events([api(city="sumy"), api(city="kharkiv")])
    assert len(rows) == 2


def test_api_timestamps_survive():
    canonical = api(
        "2026-09-25T10:00:00.123456Z",
        "2026-09-25T11:00:00.654321Z",
    )
    rows = bridge.reconcile_completed_air_events([manual(), canonical])
    assert rows[0]["start"] == canonical["start"]
    assert rows[0]["end"] == canonical["end"]


def test_recovery_provenance_survives():
    recovery = manual()
    rows = bridge.reconcile_completed_air_events([recovery, api()])
    assert rows[0]["recovery_provenance"] == {
        "original_recovery_source": recovery["source"],
        "source_kind": recovery["source_kind"],
        "source_files": recovery["source_files"],
        "recovery_artifact": recovery["recovery_artifact"],
        "original_recovery_start": recovery["start"],
        "original_recovery_end": recovery["end"],
    }


def test_repeated_api_fetch_no_duplicate():
    rows = [api()]
    bridge.upsert_completed_air_event(rows, deepcopy(api()))
    assert len(rows) == 1


def test_second_normalization_zero_changes():
    once = bridge.reconcile_completed_air_events([manual(), api()])
    twice = bridge.reconcile_completed_air_events(deepcopy(once))
    assert twice == once
