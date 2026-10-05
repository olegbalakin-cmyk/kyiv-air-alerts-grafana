from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor


def episode(episode_id: str, start: str, end: str) -> dict:
    return {"episode_id": episode_id, "alert_start": start, "alert_end": end}


def relation(text: str, published_at: str, episodes: list[dict]) -> dict:
    row = {
        "published_at": published_at,
        "title": "",
        "snippet": "",
        "discovery_basis": "publisher_fulltext",
        "matched_text_excerpt": text,
    }
    return monitor.explicit_event_time_relation(
        row,
        [text],
        {"outcome": "no_match", "matched_episode_ids": []},
        episodes,
    )


def test_explicit_source_date_plus_event_clock_uses_source_date_not_publication_date() -> None:
    text = "24 вересня, близько 10:37 у Кропивницькому пролунав вибух."
    got = relation(
        text,
        "2026-09-28T06:22:00Z",
        [episode("kropy", "2026-09-24T07:00:00Z", "2026-09-24T08:00:00Z")],
    )
    assert got["relation"] == "inside"
    assert got["event_time"] == "2026-09-24T07:37:00Z"
    assert got["episode_id"] == "kropy"


def test_direct_attack_verb_with_explicit_source_date_is_recognized() -> None:
    text = "Що відомо про авіаудар по Сумах 27 вересня Близько 15:00 російська армія ударила по Зарічному району Сум трьома КАБами."
    got = relation(
        text,
        "2026-09-28T20:02:06Z",
        [episode("sumy27", "2026-09-27T11:30:00Z", "2026-09-27T12:30:00Z")],
    )
    assert got["relation"] == "inside"
    assert got["event_time"] == "2026-09-27T12:00:00Z"
    assert got["episode_id"] == "sumy27"


def test_frozen_dot_punctuation_direct_attack_form_is_recognized() -> None:
    assert monitor.event_clock_mentions(
        "близько 8.00 неділі Росія ударила КАБами по житловому масиву Сум"
    ) == [(8, 0)]


def test_direct_event_noun_and_attack_verb_forms_are_recognized() -> None:
    assert monitor.event_clock_mentions("Удар стався близько 14:00 години.") == [(14, 0)]
    assert monitor.event_clock_mentions(
        "Близько 14:00 ворог атакував місто шістьма керованими авіабомбами."
    ) == [(14, 0)]
    assert monitor.event_clock_mentions(
        "одне з місць удару авіабомби близько 8:00 у Зарічному районі міста."
    ) == [(8, 0)]


def test_tightly_bounded_adjacent_sentence_series_clock_is_recognized() -> None:
    text = (
        "У Києві 3 жовтня знову пролунали вибухи. "
        "Нову серію було чутно близько 22.30."
    )
    got = relation(
        text,
        "2026-10-03T19:37:54Z",
        [episode("kyiv", "2026-10-03T19:00:00Z", "2026-10-03T20:00:00Z")],
    )
    assert got["relation"] == "inside"
    assert got["event_time"] == "2026-10-03T19:30:00Z"
    assert got["episode_id"] == "kyiv"


def test_near_negatives_do_not_bind_without_attack_referent() -> None:
    assert monitor.event_clock_mentions("Близько 14:00 оприлюднили оновлення.") == []
    assert monitor.event_clock_mentions("Станом на 14:00 повідомили про наслідки.") == []


def test_near_negative_reporting_clock_does_not_bind() -> None:
    assert monitor.event_clock_mentions(
        "Станом на 14:00, за медичною допомогою звернулися 13 людей після удару."
    ) == []


def test_adjacent_sentence_rule_rejects_unrelated_sentence() -> None:
    text = "У Києві пролунали вибухи. Нову інформацію оприлюднили близько 22.30."
    assert monitor.event_clock_mentions(text) == []


def test_multiple_plausible_target_events_remain_ambiguous() -> None:
    text = "Удар стався близько 14:00 години."
    got = relation(
        text,
        "2026-10-04T16:03:28Z",
        [
            episode("a", "2026-10-04T10:30:00Z", "2026-10-04T12:00:00Z"),
            episode("b", "2026-10-04T10:45:00Z", "2026-10-04T12:30:00Z"),
        ],
    )
    assert got["relation"] == "inside"
    assert got["episode_specific"] is False
    assert got["episode_id"] is None
    assert got["supported_episode_ids"] == ["a", "b"]


def test_different_source_date_does_not_use_publication_day_episode() -> None:
    text = "27 вересня близько 15:00 російська армія ударила по Сумах."
    got = relation(
        text,
        "2026-09-28T20:02:06Z",
        [episode("wrong-day", "2026-09-28T11:30:00Z", "2026-09-28T12:30:00Z")],
    )
    assert got["relation"] is None
    assert got["episode_id"] is None
