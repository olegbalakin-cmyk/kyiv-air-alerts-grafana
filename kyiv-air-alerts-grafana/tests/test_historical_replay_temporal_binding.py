import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "scripts" / "replay_explosion_history.py"
SPEC = importlib.util.spec_from_file_location("historical_replay_temporal_binding_test", REPLAY_PATH)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(replay)
monitor = replay.import_monitor(ROOT)


def episode(eid, start, end):
    return {
        "episode_id": eid,
        "alert_start": start,
        "alert_end": end,
        "alert_start_date_kyiv": replay.local_day(start, monitor),
    }


def test_alert_episode_start_kyiv_alias_binds_unique_episode():
    episodes = [episode("ep1", "2026-01-07T10:33:36Z", "2026-01-07T11:21:51Z")]
    got = replay.bind_evidence_record(
        {"alert_episode_start_kyiv": "2026-01-07T12:33:36+02:00"},
        episodes,
        monitor,
    )
    assert got["episode_id"] == "ep1"
    assert got["method"] == "legacy_start_alias"
    assert got["binding_field"] == "alert_episode_start_kyiv"


def test_alert_start_utc_alias_treats_naive_value_as_utc():
    episodes = [episode("ep1", "2026-01-07T10:33:36Z", "2026-01-07T11:21:51Z")]
    got = replay.bind_evidence_record(
        {"alert_start_utc": "2026-01-07T10:33:36"},
        episodes,
        monitor,
    )
    assert got["episode_id"] == "ep1"
    assert got["method"] == "legacy_start_alias"


def test_alert_episode_start_kyiv_normalizes_offset():
    episodes = [episode("ep1", "2026-07-07T07:00:00Z", "2026-07-07T08:00:00Z")]
    got = replay.bind_evidence_record(
        {"alert_episode_start_kyiv": "2026-07-07T10:00:00+03:00"},
        episodes,
        monitor,
    )
    assert got["episode_id"] == "ep1"


def test_nonexistent_legacy_start_does_not_bind():
    episodes = [episode("ep1", "2026-07-07T07:00:00Z", "2026-07-07T08:00:00Z")]
    got = replay.bind_evidence_record(
        {"alert_episode_start_kyiv": "2026-07-07T12:00:00+03:00"},
        episodes,
        monitor,
    )
    assert got["episode_id"] is None


def test_event_time_inside_exactly_one_episode_binds():
    episodes = [
        episode("ep1", "2026-01-26T07:06:13Z", "2026-01-26T08:08:44Z"),
        episode("ep2", "2026-01-26T09:00:00Z", "2026-01-26T10:00:00Z"),
    ]
    row = {
        "matched_episode_start": "2026-01-26T08:58:00+02:00",
        "event_time": "2026-01-26T09:42:00+02:00",
    }
    got = replay.bind_evidence_record(row, episodes, monitor)
    assert got["episode_id"] == "ep1"
    assert got["method"] == "event_time_unique_containment"


def test_clock_only_event_time_uses_retained_start_date():
    episodes = [episode("ep1", "2026-08-02T11:33:54Z", "2026-08-02T12:46:21Z")]
    row = {
        "episode_start": "2026-08-02T14:38:00+03:00",
        "event_time": "~15:21",
    }
    got = replay.bind_evidence_record(row, episodes, monitor)
    assert got["episode_id"] == "ep1"
    assert got["method"] == "event_time_unique_containment"


def test_multiple_retained_event_times_must_all_resolve_to_same_episode():
    episodes = [episode("ep1", "2025-12-06T12:51:54Z", "2025-12-06T21:59:35Z")]
    row = {
        "matched_episode_start": "2025-12-06T14:51:54+02:00",
        "event_time": "2025-12-06T15:11:00+02:00; 15:23:00+02:00",
    }
    got = replay.bind_evidence_record(row, episodes, monitor)
    assert got["episode_id"] == "ep1"
    assert got["method"] == "alert_start_within_90s"


def test_event_time_inside_zero_episodes_remains_unbound():
    episodes = [episode("ep1", "2026-08-01T17:37:20Z", "2026-08-01T18:04:52Z")]
    row = {
        "episode_start": "2026-08-01T20:04:00+03:00",
        "event_time": "~20:30",
    }
    got = replay.bind_evidence_record(row, episodes, monitor)
    assert got["episode_id"] is None
    assert got["method"] == "event_time_no_containing_episode"


def test_event_time_ambiguous_across_overlapping_episodes_does_not_guess():
    episodes = [
        episode("ep1", "2026-05-01T10:00:00Z", "2026-05-01T11:00:00Z"),
        episode("ep2", "2026-05-01T10:30:00Z", "2026-05-01T11:30:00Z"),
    ]
    row = {
        "alert_start_date": "2026-05-01",
        "event_time_kyiv": "13:45",
    }
    got = replay.bind_evidence_record(row, episodes, monitor)
    assert got["episode_id"] is None
    assert got["method"] == "event_time_ambiguous_containment"
    assert got["candidates"] == ["ep1", "ep2"]


def test_publication_timestamp_alone_must_not_bind():
    episodes = [episode("ep1", "2026-05-01T10:00:00Z", "2026-05-01T11:00:00Z")]
    got = replay.bind_evidence_record(
        {
            "published_at": "2026-05-01T10:30:00Z",
            "publication_time": "2026-05-01T10:30:00Z",
        },
        episodes,
        monitor,
    )
    assert got["episode_id"] is None
    assert got["method"] == "missing_episode_binding"


def test_persisted_canonical_binding_wins_and_conflict_is_surfaced():
    episodes = [
        episode("ep1", "2026-05-01T10:00:00Z", "2026-05-01T11:00:00Z"),
        episode("ep2", "2026-05-01T12:00:00Z", "2026-05-01T13:00:00Z"),
    ]
    got = replay.bind_evidence_record(
        {
            "matched_episode_id": "ep1",
            "event_time": "2026-05-01T12:30:00Z",
        },
        episodes,
        monitor,
    )
    assert got["episode_id"] == "ep1"
    assert got["method"] == "persisted_episode_id"
    assert got["temporal_conflicts"] == [
        {"method": "event_time_unique_containment", "episode_id": "ep2"}
    ]


def test_event_time_fallback_does_not_create_event_semantics():
    episodes = [episode("ep1", "2026-05-01T10:00:00Z", "2026-05-01T11:00:00Z")]
    row = {
        "alert_start_date": "2026-05-01",
        "event_time": "13:30",
        "evidence": "У Сумах повітряна тривога через загрозу БпЛА.",
        "source_url": "https://example.invalid/threat-only",
    }
    binding = replay.bind_evidence_record(row, episodes, monitor)
    assert binding["episode_id"] == "ep1"
    roles = replay.historical_review_roles("sumy", row, monitor)[0]
    assert "same_attack_basis" not in roles
    candidate = replay.candidate_from_history(
        "sumy", row, "strict_events", "ep1", monitor, episodes[0]
    )
    decision = monitor.classify_candidate(
        candidate, "sumy", episodes, replay.manual_matching("ep1")
    )
    assert decision["proposed_outcome"] != "approved_strict"


def test_known_outside_corpus_shape_remains_unresolved():
    episodes = [
        episode("prev", "2026-08-01T16:08:05Z", "2026-08-01T16:24:42Z"),
        episode("next", "2026-08-01T17:37:20Z", "2026-08-01T18:04:52Z"),
    ]
    row = {
        "episode_start": "2026-08-01T20:04:00+03:00",
        "event_time": "~20:30",
    }
    got = replay.bind_evidence_record(row, episodes, monitor)
    assert got["episode_id"] is None


def test_known_old_long_alert_split_without_event_clock_remains_unresolved():
    episodes = [
        episode("night-a", "2025-12-12T22:40:37Z", "2025-12-13T00:10:13Z"),
        episode("night-b", "2025-12-13T00:26:47Z", "2025-12-13T07:10:19Z"),
    ]
    row = {
        "episode_start": "2025-12-13T00:27:00",
        "event_time": None,
    }
    got = replay.bind_evidence_record(row, episodes, monitor)
    assert got["episode_id"] is None


def test_cross_midnight_clock_with_trailing_date_keeps_explicit_next_day():
    episodes = [
        episode("ep1", "2025-11-07T19:24:20Z", "2025-11-08T05:33:11Z")
    ]
    row = {
        "alert_episode_start": "2025-11-07 23:26",
        "event_time": "23:44 і після 00:00 2025-11-08",
    }
    got = replay.bind_evidence_record(row, episodes, monitor)
    assert got["episode_id"] == "ep1"
    assert got["method"] == "event_time_unique_containment"
    assert sorted(got["event_times_utc"]) == [
        "2025-11-07T21:44:00+00:00",
        "2025-11-07T22:00:00+00:00",
    ]


def test_approximate_full_datetime_keeps_its_explicit_day():
    episodes = [
        episode("wrong-day", "2025-03-05T01:00:00Z", "2025-03-05T02:00:00Z"),
    ]
    row = {
        "alert_episode_start": "2025-03-05T23:28:00+02:00",
        "event_time": "2025-03-06 ~03:50 Europe/Kyiv",
    }
    got = replay.bind_evidence_record(row, episodes, monitor)
    assert got["episode_id"] is None
    assert got["method"] == "event_time_no_containing_episode"
    assert got["event_times_utc"] == ["2025-03-06T01:50:00+00:00"]


def test_event_clock_can_use_explicit_date_retained_in_prose_start_field():
    episodes = [
        episode("ep1", "2026-03-04T00:36:19Z", "2026-03-04T02:59:13Z"),
    ]
    row = {
        "alert_episode_start": "2026-03-04 до 04:27 (точна хвилина не вказана)",
        "event_time": "~04:27",
    }
    got = replay.bind_evidence_record(row, episodes, monitor)
    assert got["episode_id"] == "ep1"
    assert got["method"] == "event_time_unique_containment"


def test_multiple_event_times_in_different_episodes_are_not_collapsed_to_one():
    episodes = [
        episode("first", "2026-02-05T11:02:13Z", "2026-02-05T13:08:11Z"),
        episode("second", "2026-02-05T13:20:14Z", "2026-02-05T15:20:38Z"),
    ]
    row = {
        "alert_episode_start": "2026-02-05 ~14:31",
        "event_time": "14:45; 15:39",
    }
    got = replay.bind_evidence_record(row, episodes, monitor)
    assert got["episode_id"] is None
    assert got["method"] == "event_time_ambiguous_containment"
    assert got["per_time_candidates"] == [["first"], ["second"]]


def test_new_temporal_fallback_can_be_disabled_for_review_only_evidence():
    episodes = [
        episode("ep1", "2026-06-21T05:00:00Z", "2026-06-21T06:00:00Z"),
        episode("ep2", "2026-06-21T08:00:00Z", "2026-06-21T09:00:00Z"),
    ]
    row = {
        "alert_start_date": "2026-06-21",
        "event_time": "08:20",
    }
    enabled = replay.bind_evidence_record(row, episodes, monitor)
    disabled = replay.bind_evidence_record(
        row,
        episodes,
        monitor,
        allow_new_temporal_fallback=False,
    )
    assert enabled["episode_id"] == "ep1"
    assert enabled["method"] == "event_time_unique_containment"
    assert disabled["episode_id"] is None
    assert disabled["method"] == "ambiguous_local_day"
