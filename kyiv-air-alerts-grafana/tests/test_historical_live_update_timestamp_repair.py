from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_ROOT = ROOT.parent
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor
import run_historical_attack_event_backfill_batch as batch_runner


UTC = timezone.utc
CASE7_EPISODE_ID = "ae2718c10fcdc7079dbb220a"
CASE7_OBSERVATION_ID = "7f9455ee73cf2aaa84b9d6e3"
BATCH_PATH = (
    CHECKOUT_ROOT
    / "research"
    / "historical_attack_event_backfill"
    / "historical-attack-events-v2-2026-09-27"
    / "sumy"
    / "batch_000029.json"
)


def load_case7():
    doc = json.loads(BATCH_PATH.read_text(encoding="utf-8"))
    observation = next(
        row for row in doc["observations"]
        if row["observation_id"] == CASE7_OBSERVATION_ID
    )
    target = next(
        row for row in doc["episode_results"]
        if row["episode_id"] == CASE7_EPISODE_ID
    )
    same_day = [
        {
            "episode_id": row["episode_id"],
            "city_key": "sumy",
            "city": "Суми",
            "alert_start": row["alert_start"],
            "alert_end": row["alert_end"],
        }
        for row in doc["episode_results"]
        if str(row.get("alert_start") or "").startswith("2026-04-26")
        or str(row.get("alert_end") or "").startswith("2026-04-26")
    ]
    return observation, target, same_day


def case7_row(observation):
    excerpt = observation["excerpt"]
    return {
        "source": observation["source_family"],
        "publisher": "Суспільне Суми",
        "title": "",
        "snippet": excerpt,
        "url": observation["source_url"],
        "published_at": observation["source_timestamp"],
        "discovery_basis": "historical_source_local_html",
        "city_key": "sumy",
    }


def test_proven_case_syntax():
    published = monitor.parse_dt("2026-04-26T06:45:05Z")
    got = monitor.dated_live_update_event_times(
        "26 квітня 22:48 Війська РФ атакували Суми. У Сумах відбулося кілька влучань російських БпЛА.",
        published,
    )
    assert [monitor.iso(value) for value in got] == ["2026-04-26T19:48:00Z"]


def test_existing_clock_grammar_regression():
    observation, _, episodes = load_case7()
    row = {
        **case7_row(observation),
        "snippet": "У Сумах о 22:48 відбулося кілька влучань російських БпЛА.",
    }
    decision = monitor.classify_candidate(row, "sumy", episodes)
    assert decision["temporal_binding"]["event_time"] == "2026-04-26T19:48:00Z"
    assert decision["temporal_binding"]["episode_id"] == CASE7_EPISODE_ID


def test_exact_case7_episode_association():
    observation, target, episodes = load_case7()

    # Frozen input identity guard: the proof reuses the committed observation.
    assert observation["source_timestamp"] == "2026-04-26T06:45:05Z"
    assert observation["classification_outcome"] == "needs_review"
    assert observation["candidate_matching"]["outcome"] == "no_match"
    assert observation["candidate_matching"]["reason"] == "publication_outside_all_tracked_alert_windows"
    assert observation["temporal_binding"]["code"] == "NO_STRICT_TEMPORAL_BINDING"
    assert observation["event_types"] == ["impact"]
    assert observation["content_hash"] == "f3b8f807fd2f9788c463684efd7b7b1ecbe048915cb6139982dc9248b3c40328"
    assert observation["exact_city_evidence"]["present"] is True
    assert observation["aerial_war_context"]["present"] is True
    assert observation["same_attack_context"]["present"] is True
    assert target["alert_start"] == "2026-04-26T17:53:05Z"
    assert target["alert_end"] == "2026-04-26T20:06:11Z"

    row = case7_row(observation)
    matching = monitor.match_candidate_to_episodes(row, episodes)
    decision = monitor.classify_candidate(row, "sumy", episodes, matching)

    # Publication matching remains unchanged; explicit event time independently
    # provides the episode-specific temporal proof.
    assert matching["outcome"] == "no_match"
    assert matching["reason"] == "publication_outside_all_tracked_alert_windows"
    assert decision["temporal_binding"]["code"] == "TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE"
    assert decision["temporal_binding"]["event_time"] == "2026-04-26T19:48:00Z"
    assert decision["temporal_binding"]["supported_episode_ids"] == [CASE7_EPISODE_ID]
    assert decision["temporal_binding"]["episode_id"] == CASE7_EPISODE_ID
    assert decision["proposed_matched_episode_id"] == CASE7_EPISODE_ID
    assert decision["proposed_outcome"] == "approved_strict"

    # Replay the frozen observation through the committed batch normalization and
    # target-level aggregation logic, without any network retrieval or writes.
    replayed_observation = batch_runner.classify_row(
        "sumy",
        row,
        episodes,
        source_family=observation["source_family"],
        source_type=observation["source_type"],
        source_timestamp=observation["source_timestamp"],
        excerpt=observation["excerpt"],
        source_url=observation["source_url"],
        retrieval_provenance=observation["retrieval_provenance"],
    )
    assert replayed_observation["observation_id"] == CASE7_OBSERVATION_ID
    # The committed observation excerpt is intentionally truncated to 1200 chars;
    # its frozen content_hash was computed from the longer pre-truncation text and
    # therefore is guarded above, not recomputed from this lossy replay fixture.
    assert replayed_observation["source_url"] == observation["source_url"]
    assert replayed_observation["source_timestamp"] == observation["source_timestamp"]
    assert replayed_observation["excerpt"] == observation["excerpt"]
    assert replayed_observation["classification_outcome"] == "approved_strict"
    assert replayed_observation["classification_episode_id"] == CASE7_EPISODE_ID
    assert replayed_observation["event_timestamp_if_stated"] == "2026-04-26T19:48:00Z"

    replayed_episode = next(
        result for result in batch_runner.episode_results(
            "sumy", episodes, [replayed_observation], True
        )
        if result["episode_id"] == CASE7_EPISODE_ID
    )
    assert replayed_episode["classifier_result"] == "STRICT_EVENT_POSITIVE"
    assert replayed_episode["event_positive_strict"] is True
    assert replayed_episode["confirmed_event_types"] == ["impact"]


def test_outside_alert_control():
    observation, _, episodes = load_case7()
    row = {
        **case7_row(observation),
        "snippet": "26 квітня 12:48 Війська РФ атакували Суми. У Сумах відбулося кілька влучань російських БпЛА.",
    }
    decision = monitor.classify_candidate(row, "sumy", episodes)
    assert decision["temporal_binding"]["episode_id"] is None
    assert decision["temporal_binding"]["present"] is False


def test_false_date_control():
    published = monitor.parse_dt("2026-04-26T06:45:05Z")
    got = monitor.dated_live_update_event_times(
        "У довідці згадано 26 квітня 22:48 як час засідання. Пізніше описано влучання російського БпЛА.",
        published,
    )
    assert got == []


def test_publication_time_fallback_unchanged():
    episode = {
        "episode_id": "publication-fallback",
        "city_key": "sumy",
        "city": "Суми",
        "alert_start": "2026-04-26T10:00:00Z",
        "alert_end": "2026-04-26T11:00:00Z",
    }
    row = {
        "source": "example",
        "publisher": "example",
        "title": "У Сумах повідомили про влучання російського БпЛА",
        "snippet": "",
        "published_at": "2026-04-26T10:30:00Z",
    }
    matching = monitor.match_candidate_to_episodes(row, [episode])
    decision = monitor.classify_candidate(row, "sumy", [episode], matching)
    assert matching["outcome"] == "unique_match"
    assert matching["matched_episode_id"] == "publication-fallback"
    assert matching["reason"] == "publication_within_unique_tracked_alert_window"
    assert decision["temporal_binding"]["event_time"] is None


def test_adjacent_alert_guard():
    observation, _, episodes = load_case7()
    row = case7_row(observation)
    decision = monitor.classify_candidate(row, "sumy", episodes)
    assert decision["temporal_binding"]["event_time"] == "2026-04-26T19:48:00Z"
    assert decision["temporal_binding"]["supported_episode_ids"] == [CASE7_EPISODE_ID]
    assert decision["proposed_matched_episode_id"] == CASE7_EPISODE_ID


if __name__ == "__main__":
    tests = [
        test_proven_case_syntax,
        test_existing_clock_grammar_regression,
        test_exact_case7_episode_association,
        test_outside_alert_control,
        test_false_date_control,
        test_publication_time_fallback_unchanged,
        test_adjacent_alert_guard,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")

    observation, _, episodes = load_case7()
    decision = monitor.classify_candidate(case7_row(observation), "sumy", episodes)
    print(
        json.dumps(
            {
                "case7_before": observation["classification_outcome"],
                "case7_after": decision["proposed_outcome"],
                "parsed_event_time": decision["temporal_binding"]["event_time"],
                "matched_episode_id": decision["proposed_matched_episode_id"],
                "temporal_code": decision["temporal_binding"]["code"],
                "publication_matching_outcome": decision["matching"]["outcome"],
                "target_after": "STRICT_EVENT_POSITIVE",
                "observation_id_preserved": CASE7_OBSERVATION_ID,
                "tests_passed": len(tests),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
