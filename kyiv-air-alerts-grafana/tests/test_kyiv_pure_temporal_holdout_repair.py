from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor


def _episode(episode_id: str = "target", start: str = "2026-09-29T16:29:00Z", end: str = "2026-09-29T18:36:00Z") -> dict:
    return {
        "episode_id": episode_id,
        "city_key": "kyiv",
        "city": "Київ",
        "alert_start": start,
        "alert_end": end,
    }


def _row(text: str, *, published_at: str = "2026-09-29T17:53:52Z", source: str = "Telegram / СУСПІЛЬНЕ НОВИНИ", matched_episode_id: str | None = "target") -> dict:
    return {
        "candidate_id": "focused-live",
        "city_key": "kyiv",
        "title": text,
        "snippet": text,
        "publisher": "СУСПІЛЬНЕ НОВИНИ",
        "source": source,
        "published_at": published_at,
        "matched_episode_id": matched_episode_id,
    }


@pytest.mark.parametrize(
    "text",
    [
        "працює ППО",
        "У Києві працює ППО, повідомив міський голова Кличко.",
        "Вибухи в Києві, повідомляють кореспонденти Суспільного.",
        "Вибухи в Києві, повідомляють кореспонденти Суспільного. У столиці працюють сили ППО.",
    ],
)
def test_demonstrated_trusted_live_forms_are_contemporaneous(text: str) -> None:
    assert monitor.contemporaneous_live_wording(text)


@pytest.mark.parametrize(
    "text",
    [
        "У Києві було чутно вибухи.",
        "Вдень у Києві було чутно вибухи.",
        "Вдень у Києві працювала ППО.",
        "Протягом дня у Києві було чути вибухи.",
        "Київ під ударом цілий день: вибухи лунали у різних районах.",
        "Добове зведення: у Києві були вибухи.",
    ],
)
def test_retrospective_broad_and_cumulative_forms_are_not_contemporaneous(text: str) -> None:
    assert not monitor.contemporaneous_live_wording(text)


@pytest.mark.parametrize(
    "text",
    [
        "У Києві працює ППО, повідомив міський голова Кличко.",
        "Вибухи в Києві, повідомляють кореспонденти Суспільного. У столиці працюють сили ППО, повідомив міський голова Кличко.",
    ],
)
def test_trusted_live_publication_time_can_bind_only_inside_one_active_episode(text: str) -> None:
    row = _row(text)
    episodes = [_episode()]
    decision = monitor.classify_candidate(row, "kyiv", episodes)
    assert decision["proposed_outcome"] == "approved_strict"
    temporal = decision["temporal_binding"]
    assert temporal["present"] is True
    assert temporal["episode_specific"] is True
    assert temporal["episode_id"] == "target"
    assert temporal["event_time"] is None
    assert temporal["event_interval"] is None
    assert temporal["message_time"] == row["published_at"]
    assert temporal["code"] == "TEMPORAL_CONTEMPORANEOUS_LIVE_WORDING"


def test_near_duplicate_raw_rows_require_existing_persisted_identity() -> None:
    text = "У Києві працює ППО, повідомив міський голова Кличко."
    precise = _episode(
        "054d4f23b2e548d59fd03fd5",
        "2026-09-28T16:19:22Z",
        "2026-09-28T16:43:04Z",
    )
    near_duplicate = _episode(
        "0706f59ff3fb1a5343152699",
        "2026-09-28T16:19:00Z",
        "2026-09-28T16:43:00Z",
    )
    episodes = [precise, near_duplicate]

    persisted = _row(
        text,
        published_at="2026-09-28T16:37:33Z",
        matched_episode_id="0706f59ff3fb1a5343152699",
    )
    decision = monitor.classify_candidate(persisted, "kyiv", episodes)
    assert decision["proposed_outcome"] == "approved_strict"
    assert decision["temporal_binding"]["episode_id"] == "0706f59ff3fb1a5343152699"
    assert set(decision["temporal_binding"]["supported_episode_ids"]) == {
        "054d4f23b2e548d59fd03fd5",
        "0706f59ff3fb1a5343152699",
    }

    no_existing_identity = dict(persisted)
    no_existing_identity["matched_episode_id"] = None
    blocked = monitor.classify_candidate(no_existing_identity, "kyiv", episodes)
    assert blocked["proposed_outcome"] != "approved_strict"
    assert blocked["temporal_binding"]["present"] is True
    assert blocked["temporal_binding"]["episode_specific"] is True
    assert blocked["temporal_binding"]["episode_id"] is None


def test_untrusted_source_cannot_use_live_publication_time() -> None:
    text = "У Києві працює ППО, повідомив міський голова Кличко."
    decision = monitor.classify_candidate(
        _row(text, source="Google News RSS"),
        "kyiv",
        [_episode()],
    )
    assert decision["proposed_outcome"] != "approved_strict"
    assert decision["temporal_binding"]["present"] is False


def test_publication_outside_episode_cannot_bind() -> None:
    text = "У Києві працює ППО, повідомив міський голова Кличко."
    decision = monitor.classify_candidate(
        _row(text, published_at="2026-09-29T19:00:00Z"),
        "kyiv",
        [_episode()],
    )
    assert decision["proposed_outcome"] != "approved_strict"
    assert decision["temporal_binding"]["present"] is False


def test_semantically_incomplete_live_message_does_not_become_strict() -> None:
    text = "Вибухи в Києві, повідомляють кореспонденти Суспільного."
    decision = monitor.classify_candidate(_row(text), "kyiv", [_episode()])
    assert decision["temporal_binding"]["present"] is True
    assert decision["air_military_context"]["present"] is False
    assert decision["proposed_outcome"] != "approved_strict"


@pytest.mark.parametrize(
    "text",
    [
        "У Києві було чутно вибухи, працювала ППО.",
        "Вдень у Києві працювала ППО.",
        "Протягом дня у Києві було чути вибухи та працювала ППО.",
    ],
)
def test_retrospective_live_source_still_has_no_strict_publication_binding(text: str) -> None:
    decision = monitor.classify_candidate(_row(text), "kyiv", [_episode()])
    assert decision["temporal_binding"]["present"] is False
    assert decision["proposed_outcome"] != "approved_strict"
