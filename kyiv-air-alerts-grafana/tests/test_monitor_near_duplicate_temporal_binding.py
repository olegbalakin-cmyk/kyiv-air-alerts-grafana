from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor


UTC = timezone.utc
KYIV_TARGET = "e97e6e816f96832d02c8b2cd"
KYIV_DUPLICATE = "782041e0741ad4cee3d3180e"
KYIV_ANCHOR = "73d817926f66c8dce397b91b"
KYIV_CONTEXT = "4bdc4c0a5f95dc1e01632d22"
KYIV_MESSAGE_TIME = datetime(2026, 9, 23, 7, 55, 51, tzinfo=UTC)


def ep(episode_id: str, start: str, end: str) -> dict:
    return {
        "episode_id": episode_id,
        "city_key": "kyiv",
        "alert_start": start,
        "alert_end": end,
    }


def live_row(at: str = "2026-09-23T07:55:51Z") -> dict:
    return {
        "city_key": "kyiv",
        "source": "Telegram / focused-test",
        "publisher": "focused-test",
        "published_at": at,
        "title": "У Києві лунають вибухи",
        "snippet": "У Києві лунають вибухи",
    }


def live_temporal(episodes: list[dict], at: str = "2026-09-23T07:55:51Z") -> dict:
    row = live_row(at)
    strict = {"present": True, "segments": ["У Києві лунають вибухи"]}
    matching = monitor.match_candidate_to_episodes(row, episodes)
    return monitor.temporal_binding_evidence(row, strict, matching, episodes)


def test_known_kyiv_regression_and_real_composition() -> None:
    state = json.loads((ROOT / "data" / "explosion_candidate_monitor_state.json").read_text(encoding="utf-8"))
    queue = json.loads((ROOT / "data" / "explosion_review_queue.json").read_text(encoding="utf-8"))
    episodes = list((state.get("cities", {}).get("kyiv", {}) or {}).get("episodes") or [])
    by_episode = {str(row.get("episode_id")): row for row in episodes}
    assert KYIV_TARGET in by_episode
    assert KYIV_DUPLICATE in by_episode

    active = monitor.exact_active_episodes_at(KYIV_MESSAGE_TIME, episodes)
    active_ids = {str(row.get("episode_id")) for row in active}
    assert {KYIV_TARGET, KYIV_DUPLICATE}.issubset(active_ids)

    target_active = [row for row in active if str(row.get("episode_id")) in {KYIV_TARGET, KYIV_DUPLICATE}]
    support = monitor.logical_episode_support(target_active)
    assert support["episode_specific"] is True
    assert support["supported_episode_ids"] == sorted([KYIV_TARGET, KYIV_DUPLICATE])
    assert support["logical_episode_groups"] == [sorted([KYIV_TARGET, KYIV_DUPLICATE])]
    assert support["episode_id"] is None

    by_candidate = {str(row.get("candidate_id")): row for row in queue}
    anchor = by_candidate[KYIV_ANCHOR]
    context = by_candidate[KYIV_CONTEXT]

    anchor_matching = monitor.match_candidate_to_episodes(anchor, episodes)
    anchor_decision = monitor.classify_candidate(anchor, "kyiv", episodes, anchor_matching)
    temporal = anchor_decision["temporal_binding"]
    assert temporal["present"] is True
    assert temporal["episode_specific"] is True
    assert {KYIV_TARGET, KYIV_DUPLICATE}.issubset(set(temporal["supported_episode_ids"]))
    assert temporal["episode_id"] is None

    composed = monitor.compose_episode_candidates(
        "kyiv",
        by_episode[KYIV_TARGET],
        [anchor, context],
        episodes,
    )
    assert composed["final_composed_verdict"] == "approved_strict"
    assert composed["anchor_candidate_id"] == KYIV_ANCHOR
    assert set(composed["contributing_candidate_ids"]) == {KYIV_ANCHOR, KYIV_CONTEXT}


def test_genuine_multi_window_ambiguity_remains_ambiguous() -> None:
    episodes = [
        ep("a", "2026-09-23T07:24:00Z", "2026-09-23T09:29:00Z"),
        ep("b", "2026-09-23T07:27:00Z", "2026-09-23T09:45:00Z"),
    ]
    temporal = live_temporal(episodes)
    assert len(monitor.episode_representation_clusters(episodes)) == 2
    assert temporal["present"] is False
    assert temporal["episode_specific"] is False
    assert temporal["episode_id"] is None
    assert temporal["code"] == "TEMPORAL_CONTEMPORANEOUS_LIVE_AMBIGUOUS_EPISODES"


def test_three_transitive_raw_representations_are_one_logical_window() -> None:
    episodes = [
        ep("a", "2026-09-23T07:24:00Z", "2026-09-23T09:29:00Z"),
        ep("b", "2026-09-23T07:25:00Z", "2026-09-23T09:30:00Z"),
        ep("c", "2026-09-23T07:26:00Z", "2026-09-23T09:31:00Z"),
    ]
    assert monitor.MATCH_REPRESENTATION_TOLERANCE_SECONDS == 90.0
    support = monitor.logical_episode_support(episodes)
    assert support["episode_specific"] is True
    assert support["supported_episode_ids"] == ["a", "b", "c"]
    assert support["logical_episode_groups"] == [["a", "b", "c"]]
    assert support["episode_id"] is None


def test_boundary_outside_representation_tolerance_stays_distinct() -> None:
    episodes = [
        ep("a", "2026-09-23T07:24:00Z", "2026-09-23T09:29:00Z"),
        ep("b", "2026-09-23T07:25:31Z", "2026-09-23T09:30:31Z"),
    ]
    assert len(monitor.episode_representation_clusters(episodes)) == 2
    temporal = live_temporal(episodes)
    assert temporal["episode_specific"] is False
    assert temporal["present"] is False


def test_single_raw_episode_behavior_is_unchanged() -> None:
    episodes = [ep("only", "2026-09-23T07:24:00Z", "2026-09-23T09:29:00Z")]
    temporal = live_temporal(episodes)
    assert temporal["present"] is True
    assert temporal["episode_specific"] is True
    assert temporal["supported_episode_ids"] == ["only"]
    assert temporal["logical_episode_groups"] == [["only"]]
    assert temporal["episode_id"] == "only"
