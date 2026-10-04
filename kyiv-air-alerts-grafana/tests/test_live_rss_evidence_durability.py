from __future__ import annotations

import copy
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor

UTC = timezone.utc


def episode(episode_id: str, start: str, end: str) -> dict:
    return {
        "episode_id": episode_id,
        "city_key": "poltava",
        "city": "Полтава",
        "alert_start": start,
        "alert_end": end,
    }


EPISODES = [
    episode("early", "2026-10-04T00:10:00Z", "2026-10-04T00:40:00Z"),
    episode("target", "2026-10-04T18:00:00Z", "2026-10-04T18:40:00Z"),
]


def rss_row(**overrides) -> dict:
    row = {
        "title": "У Полтаві під час атаки БпЛА пролунав вибух",
        "snippet": "У Полтаві під час атаки БпЛА пролунав вибух.",
        "url": "https://news.google.test/articles/eligible",
        "publisher": "Fixture News",
        "publisher_url": "https://fixture.test",
        "published_at": "2026-10-04T18:50:00Z",
        "source": "Google News RSS",
        "discovery_basis": "rss_title_snippet",
        "resolved_url": None,
        "matched_text_excerpt": "У Полтаві під час атаки БпЛА пролунав вибух.",
    }
    row.update(overrides)
    return row


def classify(row: dict) -> dict:
    return monitor.classify_candidate(row, "poltava", EPISODES)


def test_positive_durability_capture_and_classification_invariance() -> None:
    row = rss_row()
    before = classify(row)
    assert before["candidate_evidence"]["exact_city"]["present"] is True
    assert before["candidate_evidence"]["strict_explosion"]["present"] is True
    assert before["candidate_evidence"]["air_military_context"]["present"] is True
    assert before["candidate_evidence"]["same_attack_context"]["present"] is True
    assert not (
        before["candidate_evidence"]["temporal_binding"].get("episode_specific")
        and before["candidate_evidence"]["temporal_binding"].get("episode_id")
    )
    assert monitor.rss_durability_enrichment_eligible(row, before)

    calls = []

    def fetcher(url: str):
        calls.append(url)
        return (
            "О 21:17 у Полтаві під час атаки БпЛА пролунав вибух. "
            "За повідомленням влади, це сталося під час повітряної тривоги.",
            "https://fixture.test/news/poltava-attack",
        )

    enriched, fetched, succeeded = monitor.enrich_rss_candidate_for_durability(
        row, before, fulltext_fetcher=fetcher, fetch_cache={}
    )
    assert fetched is True
    assert succeeded is True
    assert calls == [row["url"]]
    assert enriched["resolved_url"] == "https://fixture.test/news/poltava-attack"
    assert "21:17" in enriched["matched_text_excerpt"]
    assert enriched["matched_text_excerpt"] != row["matched_text_excerpt"]
    assert enriched["title"] == row["title"]
    assert enriched["snippet"] == row["snippet"]
    assert enriched["published_at"] == row["published_at"]
    assert enriched["publisher"] == row["publisher"]
    assert enriched["publisher_url"] == row["publisher_url"]
    assert enriched["discovery_basis"] == "rss_title_snippet"

    after = classify(enriched)
    assert after["proposed_outcome"] == before["proposed_outcome"]
    assert after["proposed_matched_episode_id"] == before["proposed_matched_episode_id"]
    assert after["reason_codes"] == before["reason_codes"]
    assert after["candidate_evidence"] == before["candidate_evidence"]


def test_add_candidates_persists_body_evidence_but_uses_pre_enrichment_decision() -> None:
    row = rss_row()
    before = classify(row)
    due_episode = {
        **EPISODES[-1],
        "checks": [{"label": "immediate", "due_at": "2026-10-04T18:40:00Z", "checked_at": None}],
    }
    due = [(due_episode, due_episode["checks"][0])]
    queue = []
    calls = []

    def fetcher(url: str):
        calls.append(url)
        return (
            "О 21:17 у Полтаві під час атаки БпЛА пролунав вибух.",
            "https://fixture.test/news/poltava-attack",
        )

    added, strict = monitor.add_candidates(
        queue,
        "poltava",
        [row],
        due,
        EPISODES,
        datetime(2026, 10, 4, 19, 0, tzinfo=UTC),
        durability_fulltext_fetcher=fetcher,
        durability_fetch_cache={},
    )
    assert added == 1
    assert strict == (1 if before["proposed_outcome"] == "approved_strict" else 0)
    assert calls == [row["url"]]
    persisted = queue[0]
    assert persisted["status"] == before["proposed_outcome"]
    assert persisted["classification_reason_codes"] == before["reason_codes"]
    assert persisted["classification_evidence"] == monitor.classification_evidence_payload(before)
    assert persisted["resolved_url"] == "https://fixture.test/news/poltava-attack"
    assert "21:17" in persisted["matched_text_excerpt"]
    assert persisted["title"] == row["title"]
    assert persisted["snippet"] == row["snippet"]
    assert persisted["discovery_basis"] == "rss_title_snippet"


def test_negative_controls_do_not_fetch() -> None:
    controls = {
        "semantically_weak": rss_row(
            title="У Полтаві сьогодні хмарно",
            snippet="У Полтаві сьогодні хмарно.",
            matched_text_excerpt="У Полтаві сьогодні хмарно.",
        ),
        "wrong_city": rss_row(
            title="У Львові під час атаки БпЛА пролунав вибух",
            snippet="У Львові під час атаки БпЛА пролунав вибух.",
            matched_text_excerpt="У Львові під час атаки БпЛА пролунав вибух.",
        ),
        "no_attack_event": rss_row(
            title="У Полтаві оголошено загрозу БпЛА",
            snippet="У Полтаві оголошено загрозу БпЛА.",
            matched_text_excerpt="У Полтаві оголошено загрозу БпЛА.",
        ),
        "no_air_context": rss_row(
            title="У Полтаві пролунав вибух",
            snippet="У Полтаві пролунав вибух.",
            matched_text_excerpt="У Полтаві пролунав вибух.",
        ),
        "telegram": rss_row(source="Telegram / fixture"),
    }

    strict_row = rss_row(
        title="У Полтаві о 21:17 під час атаки БпЛА пролунав вибух",
        snippet="У Полтаві о 21:17 під час атаки БпЛА пролунав вибух.",
        matched_text_excerpt="У Полтаві о 21:17 під час атаки БпЛА пролунав вибух.",
    )
    controls["strict_temporal"] = strict_row

    calls = []

    def fetcher(url: str):
        calls.append(url)
        return ("body", "https://fixture.test/article")

    for name, row in controls.items():
        decision = classify(row)
        enriched, fetched, succeeded = monitor.enrich_rss_candidate_for_durability(
            row, decision, fulltext_fetcher=fetcher, fetch_cache={}
        )
        assert fetched is False, name
        assert succeeded is False, name
        assert enriched is row, name

    assert calls == []


def test_fetch_failure_is_fail_open_and_classification_invariant() -> None:
    row = rss_row()
    before = classify(row)

    def failing_fetcher(url: str):
        raise RuntimeError("fixture failure")

    enriched, fetched, succeeded = monitor.enrich_rss_candidate_for_durability(
        row, before, fulltext_fetcher=failing_fetcher, fetch_cache={}
    )
    assert fetched is True
    assert succeeded is False
    assert enriched is row
    after = classify(enriched)
    assert after["proposed_outcome"] == before["proposed_outcome"]
    assert after["candidate_evidence"] == before["candidate_evidence"]


def test_in_run_dedup_reuses_same_rss_target() -> None:
    row = rss_row()
    decision = classify(row)
    calls = []
    cache = {}

    def fetcher(url: str):
        calls.append(url)
        return (
            "О 21:17 у Полтаві під час атаки БпЛА пролунав вибух.",
            "https://fixture.test/news/shared",
        )

    first, first_fetched, first_ok = monitor.enrich_rss_candidate_for_durability(
        copy.deepcopy(row), decision, fulltext_fetcher=fetcher, fetch_cache=cache
    )
    second, second_fetched, second_ok = monitor.enrich_rss_candidate_for_durability(
        copy.deepcopy(row), decision, fulltext_fetcher=fetcher, fetch_cache=cache
    )
    assert first_ok and second_ok
    assert first_fetched is True
    assert second_fetched is False
    assert calls == [row["url"]]
    assert first["resolved_url"] == second["resolved_url"] == "https://fixture.test/news/shared"
