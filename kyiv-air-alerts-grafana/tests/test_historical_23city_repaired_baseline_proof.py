from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor


CASE7_EPISODE_ID = "ae2718c10fcdc7079dbb220a"
CASE7_START = "2026-04-26T17:53:05Z"
CASE7_END = "2026-04-26T20:06:11Z"
CASE7_PUBLISHED = "2026-04-26T06:45:05Z"
CASE7_TEXT = (
    "26 квітня 22:48 Війська РФ атакували Суми. "
    "У Сумах відбулося кілька влучань російських БпЛА."
)


def ep(episode_id: str, start: str, end: str, city_key: str = "sumy") -> dict:
    return {
        "episode_id": episode_id,
        "city_key": city_key,
        "city": monitor.CITY_CONFIG[city_key]["label"],
        "alert_start": start,
        "alert_end": end,
    }


def case7_row(text: str = CASE7_TEXT) -> dict:
    return {
        "source": "proof-only frozen fixture",
        "publisher": "proof-only frozen fixture",
        "title": "",
        "snippet": text,
        "url": "https://example.invalid/proof-only-case7",
        "published_at": CASE7_PUBLISHED,
        "city_key": "sumy",
    }


def no_publication_match() -> dict:
    return {
        "outcome": "no_match",
        "matched_episode_ids": [],
        "logical_episode_groups": [],
        "matched_episode_id": None,
        "reason": "publication_outside_all_tracked_alert_windows",
    }


# Accepted live-update timestamp tests: same seven semantic cases, self-contained
# because the 2026-09-27 campaign corpus is intentionally absent from base 0950.

def test_proven_case_syntax() -> None:
    published = monitor.parse_dt(CASE7_PUBLISHED)
    got = monitor.dated_live_update_event_times(CASE7_TEXT, published)
    assert [monitor.iso(value) for value in got] == ["2026-04-26T19:48:00Z"]


def test_existing_clock_grammar_regression() -> None:
    episodes = [ep(CASE7_EPISODE_ID, CASE7_START, CASE7_END)]
    relation = monitor.explicit_event_time_relation(
        case7_row("У Сумах о 22:48 відбулося кілька влучань російських БпЛА."),
        ["У Сумах о 22:48 відбулося кілька влучань російських БпЛА."],
        no_publication_match(),
        episodes,
    )
    assert relation["event_time"] == "2026-04-26T19:48:00Z"
    assert relation["episode_id"] == CASE7_EPISODE_ID
    assert relation["episode_specific"] is True


def test_exact_case7_episode_association() -> None:
    episodes = [ep(CASE7_EPISODE_ID, CASE7_START, CASE7_END)]
    temporal = monitor.temporal_binding_evidence(
        case7_row(),
        {"segments": [CASE7_TEXT]},
        no_publication_match(),
        episodes,
    )
    assert temporal["code"] == "TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE"
    assert temporal["event_time"] == "2026-04-26T19:48:00Z"
    assert temporal["supported_episode_ids"] == [CASE7_EPISODE_ID]
    assert temporal["episode_id"] == CASE7_EPISODE_ID
    assert temporal["present"] is True


def test_outside_alert_control() -> None:
    episodes = [ep(CASE7_EPISODE_ID, CASE7_START, CASE7_END)]
    text = (
        "26 квітня 12:48 Війська РФ атакували Суми. "
        "У Сумах відбулося кілька влучань російських БпЛА."
    )
    relation = monitor.explicit_event_time_relation(
        case7_row(text), [text], no_publication_match(), episodes
    )
    assert relation["episode_id"] is None
    assert relation["episode_specific"] is False


def test_false_date_control() -> None:
    published = monitor.parse_dt(CASE7_PUBLISHED)
    got = monitor.dated_live_update_event_times(
        "У довідці згадано 26 квітня 22:48 як час засідання. "
        "Пізніше описано влучання російського БпЛА.",
        published,
    )
    assert got == []


def test_publication_time_fallback_unchanged() -> None:
    episode = ep(
        "publication-fallback",
        "2026-04-26T10:00:00Z",
        "2026-04-26T11:00:00Z",
    )
    row = {
        "source": "example",
        "publisher": "example",
        "title": "У Сумах повідомили про влучання російського БпЛА",
        "snippet": "",
        "published_at": "2026-04-26T10:30:00Z",
    }
    matching = monitor.match_candidate_to_episodes(row, [episode])
    assert matching["outcome"] == "unique_match"
    assert matching["matched_episode_id"] == "publication-fallback"
    relation = monitor.explicit_event_time_relation(
        row, [row["title"]], matching, [episode]
    )
    assert relation["event_time"] is None


def test_adjacent_alert_guard() -> None:
    episodes = [
        ep("adjacent-before", "2026-04-26T15:00:00Z", "2026-04-26T16:00:00Z"),
        ep(CASE7_EPISODE_ID, CASE7_START, CASE7_END),
        ep("adjacent-after", "2026-04-26T20:30:00Z", "2026-04-26T21:30:00Z"),
    ]
    temporal = monitor.temporal_binding_evidence(
        case7_row(),
        {"segments": [CASE7_TEXT]},
        no_publication_match(),
        episodes,
    )
    assert temporal["event_time"] == "2026-04-26T19:48:00Z"
    assert temporal["supported_episode_ids"] == [CASE7_EPISODE_ID]
    assert temporal["episode_id"] == CASE7_EPISODE_ID


# Accepted exact-city Sevastopol semantic tests, independent of Step-2 source registry.

def test_sevastopol_base_form() -> None:
    assert monitor.city_mentioned("sevastopol", "Севастополь")


def test_sevastopol_ukrainian_locative() -> None:
    assert monitor.city_mentioned("sevastopol", "у Севастополі")


def test_sevastopol_russian_locative() -> None:
    assert monitor.city_mentioned("sevastopol", "в Севастополе")


def test_sevastopol_false_fragment_guard() -> None:
    assert not monitor.city_mentioned(
        "sevastopol",
        "У тексті трапився не-топонімічний токен севастопольськиймаркер.",
    )


def test_sevastopol_wrong_city_guard() -> None:
    row = {
        "source": "proof-only control",
        "publisher": "proof-only control",
        "title": "В Ялте военные отражают атаку, работает ПВО.",
        "snippet": "Сбит БПЛА над акваторией.",
        "url": "https://example.invalid/wrong-city",
        "published_at": "2026-09-04T12:00:47Z",
        "city_key": "sevastopol",
    }
    evidence = monitor.exact_city_classification_evidence("sevastopol", row)
    assert evidence["present"] is False
    assert evidence["segments"] == []
