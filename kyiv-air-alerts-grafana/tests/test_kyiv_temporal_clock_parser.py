from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor


PROVENANCE_PATH = ROOT.parent / "research" / "kyiv_12_positive_source_provenance_2026-10-04.json"
ENRICHMENT_PATH = ROOT.parent / "research" / "kyiv_12_positive_evidence_enrichment_ab_2026-10-04.json"
POLICY_PROOF_PATH = ROOT.parent / "research" / "kyiv_publisher_fulltext_policy_gate_proof_2026-10-04.json"

TARGET_IDS = {
    "5fe9c0b3aed78bd5be50d3f6",
    "d727150d5170d97fea2f96f0",
    "4f236ae664adedf6c45b6d1e",
    "b8b8b8e9b42ef2e360e1a253",
    "deb4614a7c618c6eb581de10",
}
REPRESENTATION_IDS = {
    "9fd2e6a9a02235982bd706ea",
    "cfeec7a191817720d241fedb",
}
SAME_ATTACK_ID = "a422cb3549b4ba330c3b831f"
ALREADY_STRICT_IDS = {
    "735a17c8622f113c4abc15b8",
    "6bb2a52b33667e8ddf111326",
    "4684548673d2b83089b0f15e",
    "af3627c04d206a368662136e",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


PROVENANCE = _load(PROVENANCE_PATH)
ENRICHMENT = _load(ENRICHMENT_PATH)
POLICY_PROOF = _load(POLICY_PROOF_PATH)
PROVENANCE_BY_ID = {row["episode_id"]: row for row in PROVENANCE["episodes"]}
ENRICHMENT_BY_ID = {row["episode_id"]: row for row in ENRICHMENT["episodes"]}
POLICY_BY_ID = {row["episode_id"]: row for row in POLICY_PROOF["episodes"]}


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _expected_times(row: dict) -> list[str]:
    value = row["derived_event_time_utc"]
    return list(value) if isinstance(value, list) else [value]


def _synthetic_episode_for_frozen_time(episode_id: str, row: dict) -> dict:
    times = [_utc(value) for value in _expected_times(row)]
    start = min(times) - timedelta(minutes=2)
    end = max(times) + timedelta(minutes=2)
    return {
        "episode_id": episode_id,
        "city_key": "kyiv",
        "alert_start": start.isoformat().replace("+00:00", "Z"),
        "alert_end": end.isoformat().replace("+00:00", "Z"),
    }


def _frozen_target_relation(episode_id: str) -> dict:
    source = PROVENANCE_BY_ID[episode_id]
    episodes = [_synthetic_episode_for_frozen_time(episode_id, source)]
    row = {
        "published_at": source["publication_timestamp_utc"],
        "title": "",
        "snippet": "",
        "publisher": source["publisher"],
        "discovery_basis": "publisher_fulltext",
        "matched_text_excerpt": source["temporal_excerpt"],
    }
    matching = {
        "outcome": "unique_match",
        "matched_episode_id": episode_id,
        "matched_episode_ids": [episode_id],
    }
    return monitor.explicit_event_time_relation(
        row,
        [source["temporal_excerpt"]],
        matching,
        episodes,
    )


@pytest.mark.parametrize(
    ("episode_id", "expected_clock"),
    [
        ("5fe9c0b3aed78bd5be50d3f6", (21, 54)),
        ("d727150d5170d97fea2f96f0", (6, 56)),
        ("4f236ae664adedf6c45b6d1e", (9, 12)),
        ("b8b8b8e9b42ef2e360e1a253", (5, 0)),
        ("deb4614a7c618c6eb581de10", (6, 57)),
    ],
)
def test_frozen_timeline_leading_clock_forms_are_recognized(
    episode_id: str,
    expected_clock: tuple[int, int],
) -> None:
    source = PROVENANCE_BY_ID[episode_id]
    assert expected_clock in monitor.event_clock_mentions(source["temporal_excerpt"])


@pytest.mark.parametrize("episode_id", sorted(TARGET_IDS))
def test_frozen_parser_targets_gain_episode_specific_binding(episode_id: str) -> None:
    source = PROVENANCE_BY_ID[episode_id]
    relation = _frozen_target_relation(episode_id)
    expected_first = min(_utc(value) for value in _expected_times(source))
    assert relation["relation"] == "inside"
    assert relation["episode_specific"] is True
    assert relation["episode_id"] == episode_id
    assert relation["supported_episode_ids"] == [episode_id]
    assert _utc(relation["event_time"]) == expected_first


def test_frozen_target_timezone_conversion_uses_europe_kyiv() -> None:
    assert monitor.KYIV_TZ.key == "Europe/Kyiv"
    expected = {
        "5fe9c0b3aed78bd5be50d3f6": "2026-09-30T18:54:00Z",
        "d727150d5170d97fea2f96f0": "2026-10-01T03:56:00Z",
        "4f236ae664adedf6c45b6d1e": "2026-10-01T06:12:00Z",
        "b8b8b8e9b42ef2e360e1a253": "2026-10-02T02:00:00Z",
        "deb4614a7c618c6eb581de10": "2026-10-03T03:57:00Z",
    }
    for episode_id, event_time in expected.items():
        assert _frozen_target_relation(episode_id)["event_time"] == event_time


@pytest.mark.parametrize(
    "text",
    [
        "24:00 — Влучання у Києві.",
        "23:60 — Влучання у Києві.",
        "99:99 — Влучання у Києві.",
    ],
)
def test_invalid_timeline_leading_clocks_are_rejected(text: str) -> None:
    assert monitor.event_clock_mentions(text) == []


@pytest.mark.parametrize(
    "text",
    [
        "Станом на 21:50 зафіксовано влучання у Києві.",
        "після 03:00 зафіксовано влучання у Києві.",
        "Повідомили 21:54 про влучання у Києві.",
    ],
)
def test_new_bare_clock_rule_does_not_capture_nonleading_or_interval_language(text: str) -> None:
    assert monitor.event_clock_mentions(text) == []


def test_existing_approximate_clock_behavior_is_not_changed_by_this_repair() -> None:
    assert monitor.event_clock_mentions("Близько 11:30 сталося влучання у Києві.") == [(11, 30)]


def test_neighboring_alert_ambiguity_safeguard_is_unchanged_for_new_form() -> None:
    row = {
        "published_at": "2026-10-01T08:00:00Z",
        "title": "",
        "snippet": "",
        "publisher": "focused-test",
        "discovery_basis": "publisher_fulltext",
        "matched_text_excerpt": "10:45 — Влучання у Києві.",
    }
    episodes = [
        {
            "episode_id": "a",
            "city_key": "kyiv",
            "alert_start": "2026-10-01T07:00:00Z",
            "alert_end": "2026-10-01T08:00:00Z",
        },
        {
            "episode_id": "b",
            "city_key": "kyiv",
            "alert_start": "2026-10-01T07:30:00Z",
            "alert_end": "2026-10-01T08:30:00Z",
        },
    ]
    matching = {
        "outcome": "ambiguous_match",
        "matched_episode_id": None,
        "matched_episode_ids": ["a", "b"],
    }
    strict = {"present": True, "segments": ["10:45 — Влучання у Києві."]}
    temporal = monitor.temporal_binding_evidence(row, strict, matching, episodes)
    assert temporal["present"] is False
    assert temporal["episode_specific"] is False
    assert temporal["episode_id"] is None
    assert temporal["code"] == "TEMPORAL_EXPLICIT_EVENT_TIME_AMBIGUOUS_EPISODES"


def test_two_temporal_representation_cases_remain_out_of_scope() -> None:
    assert POLICY_BY_ID["9fd2e6a9a02235982bd706ea"]["remaining_failure_mechanism"] == "temporal representation"
    assert POLICY_BY_ID["cfeec7a191817720d241fedb"]["remaining_failure_mechanism"] == "temporal representation"
    assert monitor.event_clock_mentions("Станом на 21:50 зафіксовано влучання у Києві.") == []
    assert monitor.event_clock_mentions("після 03:00 зафіксовано влучання у Києві.") == []


def test_air_same_attack_case_remains_non_strict() -> None:
    row = ENRICHMENT_BY_ID[SAME_ATTACK_ID]
    assert row["B_same_attack"] is False
    assert POLICY_BY_ID[SAME_ATTACK_ID]["after"] == "REVIEW"
    assert POLICY_BY_ID[SAME_ATTACK_ID]["remaining_failure_mechanism"] == "air-context / same-attack"


def test_four_publisher_fulltext_positives_remain_strict() -> None:
    assert {episode_id for episode_id in ALREADY_STRICT_IDS if POLICY_BY_ID[episode_id]["after"] == "STRICT"} == ALREADY_STRICT_IDS


def test_frozen_kyiv_12_replay_promotes_exactly_five_parser_targets() -> None:
    after = {}
    changed = set()

    for episode in ENRICHMENT["episodes"]:
        episode_id = episode["episode_id"]
        temporal_parser = bool(episode["B_temporal_parser"])
        episode_binding = bool(episode["B_episode_binding"])

        if episode_id in TARGET_IDS:
            relation = _frozen_target_relation(episode_id)
            temporal_parser = relation["relation"] == "inside"
            episode_binding = relation["episode_specific"] is True and relation["episode_id"] == episode_id

        strict_eligible = all(
            [
                episode["B_exact_city_parser"],
                episode["B_attack_event_parser"],
                episode["B_air_context_parser"],
                episode["B_same_attack"],
                temporal_parser,
                episode_binding,
            ]
        )
        blocked = monitor.publisher_fulltext_requires_review(
            {"discovery_basis": episode["B_discovery_basis"]},
            {"usable": False},
            strict_eligible=strict_eligible,
        )

        outcome = POLICY_BY_ID[episode_id]["after"]
        if strict_eligible and not blocked:
            outcome = "STRICT"

        after[episode_id] = outcome
        if outcome != POLICY_BY_ID[episode_id]["after"]:
            changed.add(episode_id)

    assert changed == TARGET_IDS
    assert sum(value == "STRICT" for value in after.values()) == 9
    assert sum(value == "SENSITIVITY" for value in after.values()) == 0
    assert sum(value == "REVIEW" for value in after.values()) == 3
    assert all(after[episode_id] == "REVIEW" for episode_id in REPRESENTATION_IDS)
    assert after[SAME_ATTACK_ID] == "REVIEW"
    assert all(after[episode_id] == "STRICT" for episode_id in ALREADY_STRICT_IDS)
