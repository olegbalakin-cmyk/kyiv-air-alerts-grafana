import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "scripts" / "replay_explosion_history.py"
SPEC = importlib.util.spec_from_file_location(
    "historical_replay_dnipro_multi_event_split_test", REPLAY_PATH
)
replay = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(replay)
monitor = replay.import_monitor(ROOT)

TARGET_ID = "2793d79590a849624744439a"
EP_A = "00c24c9cccd9e66de7eba62b"
EP_B = "ed19badd30731bd1aeb7e326"


def episode(eid, start, end):
    return {
        "episode_id": eid,
        "city_key": "dnipro",
        "city": "dnipro",
        "alert_start": start,
        "alert_end": end,
        "alert_start_date_kyiv": replay.local_day(start, monitor),
    }


EPISODES = [
    episode(EP_A, "2026-02-05T11:02:13Z", "2026-02-05T13:08:11Z"),
    episode(EP_B, "2026-02-05T13:20:14Z", "2026-02-05T15:20:38Z"),
]

TARGET_ROW = {
    "alert_episode_start": "2026-02-05 ~14:31",
    "event_time": "14:45; 15:39",
    "source_url": "https://24tv.ua/dnipro-skolihnula-seriya-vibuhiv_n3003501",
    "evidence": (
        "Після попередження про БпЛА та тривоги близько 14:31 у Дніпрі "
        "о 14:45 і 15:39 пролунали вибухи."
    ),
    "decision": "strict",
    "basis": "exact_city; confirmed_air_war; timed_inside_alert",
}


def expand(row, episodes=EPISODES):
    return replay.expand_historical_evidence_observations(
        "dnipro", "strict_events", 74, row, episodes, monitor
    )


def classify(observation, episodes=EPISODES):
    target_id = observation["binding"]["episode_id"]
    candidate = replay.candidate_from_history(
        "dnipro",
        observation["row"],
        "strict_events",
        target_id,
        monitor,
        next(ep for ep in episodes if ep["episode_id"] == target_id),
    )
    decision = monitor.classify_candidate(
        candidate,
        "dnipro",
        episodes,
        replay.manual_matching(target_id),
    )
    return candidate, decision


def test_target_parent_identity_matches_accepted_inventory():
    assert (
        replay.historical_record_id("dnipro", "strict_events", 74, TARGET_ROW)
        == TARGET_ID
    )


def test_one_parent_two_explicit_events_bind_two_different_episodes():
    observations = expand(TARGET_ROW)
    assert len(observations) == 2
    assert all(item["is_split_child"] for item in observations)
    assert {item["binding"]["episode_id"] for item in observations} == {EP_A, EP_B}
    assert {item["parent_record_id"] for item in observations} == {TARGET_ID}
    assert all(item["event_fact_present"] is True for item in observations)


def test_each_target_event_independently_passes_current_v2_classifier():
    observations = expand(TARGET_ROW)
    decisions = []
    for observation in observations:
        child_text = replay.evidence_text(observation["row"])
        assert monitor.strict_attack_event_signal(child_text)
        exact = monitor.exact_city_classification_evidence(
            "dnipro",
            {
                "title": child_text,
                "snippet": "",
                "publisher": "historical_audit",
            },
        )
        assert exact["present"] is True
        assert monitor.air_military_context(child_text)
        assert observation["binding"]["episode_id"] in {EP_A, EP_B}
        _, decision = classify(observation)
        decisions.append(decision["proposed_outcome"])
    assert decisions == ["approved_strict", "approved_strict"]


def test_parent_provenance_is_preserved_in_each_child_candidate():
    for observation in expand(TARGET_ROW):
        candidate, _ = classify(observation)
        assert candidate["historical_parent_record_id"] == TARGET_ID
        assert candidate["historical_record"] == TARGET_ROW
        assert candidate["historical_event_observation"]["observation_id"] == observation["observation_id"]
        assert candidate["historical_event_observation"]["event_time_utc"] == observation["event_time_utc"]


def test_two_explicit_events_same_episode_yield_one_episode_positive():
    episodes = [
        episode("same", "2026-02-05T11:00:00Z", "2026-02-05T14:00:00Z")
    ]
    row = {**TARGET_ROW, "alert_episode_start": "2026-02-05 ~14:31"}
    observations = expand(row, episodes)
    assert len(observations) == 1
    assert observations[0]["binding"]["episode_id"] == "same"
    assert {observations[0]["binding"]["episode_id"]} == {"same"}


def test_duplicate_timestamp_representation_does_not_duplicate_child():
    row = {
        **TARGET_ROW,
        "event_time": "14:45; 14:45",
        "evidence": "У Дніпрі о 14:45 пролунали вибухи під час атаки БпЛА; о 14:45 вибухи повторно згадані.",
    }
    observations = expand(row)
    assert len(observations) == 1


def test_one_bound_child_and_one_ambiguous_child_stay_independent():
    episodes = [
        episode("first", "2026-02-05T11:02:13Z", "2026-02-05T13:08:11Z"),
        episode("overlap-a", "2026-02-05T13:20:14Z", "2026-02-05T15:20:38Z"),
        episode("overlap-b", "2026-02-05T13:30:00Z", "2026-02-05T14:30:00Z"),
    ]
    observations = expand(TARGET_ROW, episodes)
    assert len(observations) == 2
    by_time = {item["event_time_utc"]: item for item in observations}
    first = by_time["2026-02-05T12:45:00+00:00"]
    second = by_time["2026-02-05T13:39:00+00:00"]
    assert first["binding"]["episode_id"] == "first"
    assert second["binding"]["episode_id"] is None
    assert second["binding"]["method"] == "event_time_ambiguous_containment"


def test_one_qualifying_and_one_nonqualifying_child_only_keeps_event_child():
    row = {
        **TARGET_ROW,
        "evidence": (
            "У Дніпрі о 14:45 пролунав вибух під час атаки БпЛА; "
            "о 15:39 опубліковано оновлення матеріалу."
        ),
    }
    observations = expand(row)
    assert len(observations) == 2
    valid = [item for item in observations if item["event_fact_present"] is True]
    invalid = [item for item in observations if item["event_fact_present"] is False]
    assert len(valid) == 1
    assert valid[0]["binding"]["episode_id"] == EP_A
    assert len(invalid) == 1
    assert invalid[0]["binding"]["episode_id"] == EP_B


def test_publication_time_must_not_create_second_child():
    row = {
        **TARGET_ROW,
        "event_time": "14:45",
        "publication_time": "2026-02-05T15:39:00+02:00",
        "evidence": "У Дніпрі о 14:45 пролунав вибух під час атаки БпЛА.",
    }
    observations = expand(row)
    assert len(observations) == 1
    assert observations[0]["binding"]["episode_id"] == EP_A


def test_vague_interval_is_not_split_into_multiple_events():
    row = {
        **TARGET_ROW,
        "event_time": "14:45–15:39",
        "evidence": "У Дніпрі між 14:45–15:39 було чутно вибухи під час атаки БпЛА.",
    }
    observations = expand(row)
    assert len(observations) == 1
    assert observations[0]["is_split_child"] is False
    assert observations[0]["binding"]["episode_id"] is None


def test_repeated_textual_mention_same_explosion_does_not_duplicate():
    row = {
        **TARGET_ROW,
        "event_time": "14:45; 14:45",
        "evidence": (
            "У Дніпрі о 14:45 пролунав вибух під час атаки БпЛА; "
            "той самий вибух о 14:45 згадано повторно."
        ),
    }
    observations = expand(row)
    assert len(observations) == 1


def test_split_child_candidate_ids_are_distinct_but_share_parent():
    observations = expand(TARGET_ROW)
    candidates = [classify(item)[0] for item in observations]
    assert len({candidate["candidate_id"] for candidate in candidates}) == 2
    assert {candidate["historical_parent_record_id"] for candidate in candidates} == {TARGET_ID}
