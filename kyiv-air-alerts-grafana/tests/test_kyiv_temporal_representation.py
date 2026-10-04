from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor


PROVENANCE_PATH = ROOT.parent / "research" / "kyiv_12_positive_source_provenance_2026-10-04.json"
ENRICHMENT_PATH = ROOT.parent / "research" / "kyiv_12_positive_evidence_enrichment_ab_2026-10-04.json"
CLOCK_PROOF_PATH = ROOT.parent / "research" / "kyiv_temporal_clock_parser_proof_2026-10-04.json"

AS_OF_ID = "9fd2e6a9a02235982bd706ea"
AFTER_ID = "cfeec7a191817720d241fedb"
SAME_ATTACK_ID = "a422cb3549b4ba330c3b831f"

PREDECESSOR_STRICT_IDS = {
    "5fe9c0b3aed78bd5be50d3f6",
    "d727150d5170d97fea2f96f0",
    "4f236ae664adedf6c45b6d1e",
    "735a17c8622f113c4abc15b8",
    "b8b8b8e9b42ef2e360e1a253",
    "6bb2a52b33667e8ddf111326",
    "deb4614a7c618c6eb581de10",
    "4684548673d2b83089b0f15e",
    "af3627c04d206a368662136e",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


PROVENANCE = _load(PROVENANCE_PATH)
ENRICHMENT = _load(ENRICHMENT_PATH)
CLOCK_PROOF = _load(CLOCK_PROOF_PATH)
PROVENANCE_BY_ID = {row["episode_id"]: row for row in PROVENANCE["episodes"]}
ENRICHMENT_BY_ID = {row["episode_id"]: row for row in ENRICHMENT["episodes"]}


def _episode(episode_id: str, start: str, end: str) -> dict:
    return {
        "episode_id": episode_id,
        "city_key": "kyiv",
        "alert_start": start,
        "alert_end": end,
    }


AS_OF_DAY_EPISODES = [
    _episode("aa9d8bb53efd6888bfe133d4", "2026-10-01T01:56:00Z", "2026-10-01T02:10:00Z"),
    _episode("d727150d5170d97fea2f96f0", "2026-10-01T03:27:00Z", "2026-10-01T05:24:00Z"),
    _episode("4f236ae664adedf6c45b6d1e", "2026-10-01T05:49:00Z", "2026-10-01T06:31:00Z"),
    _episode("735a17c8622f113c4abc15b8", "2026-10-01T07:34:00Z", "2026-10-01T09:30:00Z"),
    _episode("5ed0348b3de9b981f64113ff", "2026-10-01T10:46:00Z", "2026-10-01T10:51:00Z"),
    _episode("a077810f151bfe7bcccd071f", "2026-10-01T11:40:00Z", "2026-10-01T11:46:00Z"),
    _episode("ef6f417955588d48ee302c24", "2026-10-01T15:22:00Z", "2026-10-01T15:33:00Z"),
    _episode("fda64181d019f8643f671b22", "2026-10-01T16:55:00Z", "2026-10-01T17:35:00Z"),
    _episode(AS_OF_ID, "2026-10-01T17:45:00Z", "2026-10-01T18:51:00Z"),
]

AFTER_INTERVAL_EPISODES = [
    _episode(AFTER_ID, "2026-10-01T23:57:00Z", "2026-10-02T01:03:00Z"),
    _episode("b8b8b8e9b42ef2e360e1a253", "2026-10-02T01:48:00Z", "2026-10-02T02:19:00Z"),
]


def _row_for_source(source: dict) -> dict:
    return {
        "published_at": source["publication_timestamp_utc"],
        "title": source["source_title"],
        "snippet": "",
        "publisher": source["publisher"],
        "discovery_basis": "publisher_fulltext",
        "matched_text_excerpt": source["attack_event_excerpt"],
    }


def _relation_for_target(episode_id: str) -> dict:
    source = PROVENANCE_BY_ID[episode_id]
    episodes = AS_OF_DAY_EPISODES if episode_id == AS_OF_ID else AFTER_INTERVAL_EPISODES
    return monitor.source_temporal_interval_relation(
        _row_for_source(source),
        [source["attack_event_excerpt"]],
        episodes,
    )


def _binding_for_target(episode_id: str) -> dict:
    source = PROVENANCE_BY_ID[episode_id]
    episodes = AS_OF_DAY_EPISODES if episode_id == AS_OF_ID else AFTER_INTERVAL_EPISODES
    return monitor.temporal_binding_evidence(
        _row_for_source(source),
        {"present": True, "segments": [source["attack_event_excerpt"]]},
        {"outcome": "unique_match", "matched_episode_id": episode_id, "matched_episode_ids": [episode_id]},
        episodes,
    )


def test_after_time_with_defensible_upper_bound_inside_one_episode_is_strict() -> None:
    text = "Після 03:00 місцеві почули вибухи в Києві."
    row = {"published_at": "2026-10-02T00:20:00Z"}
    episodes = [_episode("one", "2026-10-01T23:57:00Z", "2026-10-02T00:30:00Z")]
    relation = monitor.source_temporal_interval_relation(row, [text], episodes)
    assert relation["constraint"]["relation_type"] == "AFTER_TIME"
    assert relation["constraint"]["lower_bound"] == "2026-10-02T00:00:00Z"
    assert relation["constraint"]["upper_bound"] == "2026-10-02T00:20:00Z"
    assert relation["episode_specific"] is True
    assert relation["episode_id"] == "one"

    binding = monitor.temporal_binding_evidence(
        row,
        {"present": True, "segments": [text]},
        {"outcome": "unique_match", "matched_episode_id": "one", "matched_episode_ids": ["one"]},
        episodes,
    )
    assert binding["present"] is True
    assert binding["code"] == "TEMPORAL_SOURCE_INTERVAL_INSIDE_EPISODE"
    assert binding["event_time"] is None


def test_after_time_without_defensible_upper_bound_is_not_strict() -> None:
    text = "Після 03:00 можливі вибухи в Києві."
    row = {"published_at": "2026-10-02T00:20:00Z"}
    episodes = [_episode("one", "2026-10-01T23:57:00Z", "2026-10-02T00:30:00Z")]
    relation = monitor.source_temporal_interval_relation(row, [text], episodes)
    assert relation["constraint"]["relation_type"] == "AFTER_TIME"
    assert relation["constraint"]["upper_bound"] is None
    assert relation["episode_specific"] is False
    assert relation["failure_reason"] == "INSUFFICIENT_UPPER_BOUND"


def test_after_time_interval_spanning_two_episodes_is_not_strict() -> None:
    relation = _relation_for_target(AFTER_ID)
    assert relation["constraint"]["relation_type"] == "AFTER_TIME"
    assert relation["constraint"]["lower_bound"] == "2026-10-02T00:00:00Z"
    assert relation["constraint"]["upper_bound"] == "2026-10-02T02:10:00Z"
    assert relation["constraint"]["basis_for_upper_bound"] == "publication_chronology_event_already_occurred"
    assert relation["episode_specific"] is False
    assert relation["failure_reason"] == "MULTI_EPISODE_INTERVAL"
    assert set(relation["supported_episode_ids"]) == {
        AFTER_ID,
        "b8b8b8e9b42ef2e360e1a253",
    }


def test_before_or_by_with_defensible_lower_and_upper_inside_one_episode_is_strict() -> None:
    text = "Після 21:00, станом на 21:50 зафіксовано влучання у Києві."
    row = {"published_at": "2026-10-01T18:56:00Z"}
    episodes = [_episode("one", "2026-10-01T17:45:00Z", "2026-10-01T18:51:00Z")]
    relation = monitor.source_temporal_interval_relation(row, [text], episodes)
    assert relation["constraint"]["relation_type"] == "BEFORE_OR_BY_TIME"
    assert relation["constraint"]["lower_bound"] == "2026-10-01T18:00:00Z"
    assert relation["constraint"]["upper_bound"] == "2026-10-01T18:50:00Z"
    assert relation["episode_specific"] is True
    assert relation["episode_id"] == "one"


def test_as_of_without_defensible_lower_bound_and_multiple_possible_episodes_is_not_strict() -> None:
    relation = _relation_for_target(AS_OF_ID)
    assert relation["constraint"]["relation_type"] == "BEFORE_OR_BY_TIME"
    assert relation["constraint"]["lower_bound"] is None
    assert relation["constraint"]["upper_bound"] == "2026-10-01T18:50:00Z"
    assert relation["episode_specific"] is False
    assert relation["failure_reason"] == "INSUFFICIENT_LOWER_BOUND"
    assert AS_OF_ID in relation["supported_episode_ids"]
    assert len(relation["logical_episode_groups"]) > 1


def test_publication_time_is_interval_bound_not_event_point_time() -> None:
    after = _binding_for_target(AFTER_ID)
    as_of = _binding_for_target(AS_OF_ID)
    assert after["event_time"] is None
    assert after["event_interval"]["upper_bound"] == PROVENANCE_BY_ID[AFTER_ID]["publication_timestamp_utc"]
    assert as_of["event_time"] is None
    assert as_of["event_interval"]["upper_bound"] == "2026-10-01T18:50:00Z"
    assert as_of["event_interval"]["upper_bound"] != PROVENANCE_BY_ID[AS_OF_ID]["publication_timestamp_utc"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("21:54, 30 вересня — Влучання у Києві.", [(21, 54)]),
        ("6:56, 1 жовтня — Влучання БпЛА у Києві.", [(6, 56)]),
        ("Станом на 21:50 зафіксовано влучання у Києві.", []),
        ("після 03:00 зафіксовано влучання у Києві.", []),
    ],
)
def test_exact_clock_parser_predecessor_behavior_is_unchanged(text: str, expected: list[tuple[int, int]]) -> None:
    assert monitor.event_clock_mentions(text) == expected


def test_neighboring_alert_ambiguity_safeguard_rejects_partial_overlap() -> None:
    binding = _binding_for_target(AFTER_ID)
    assert binding["present"] is False
    assert binding["episode_specific"] is False
    assert binding["code"] == "TEMPORAL_SOURCE_INTERVAL_MULTIPLE_EPISODES"
    assert set(binding["supported_episode_ids"]) == {
        AFTER_ID,
        "b8b8b8e9b42ef2e360e1a253",
    }


def test_frozen_two_target_cases_are_represented_but_remain_review() -> None:
    as_of = _binding_for_target(AS_OF_ID)
    after = _binding_for_target(AFTER_ID)

    assert as_of["event_interval"]["relation_type"] == "BEFORE_OR_BY_TIME"
    assert as_of["code"] == "TEMPORAL_SOURCE_INTERVAL_INSUFFICIENT_LOWER_BOUND"
    assert as_of["present"] is False

    assert after["event_interval"]["relation_type"] == "AFTER_TIME"
    assert after["code"] == "TEMPORAL_SOURCE_INTERVAL_MULTIPLE_EPISODES"
    assert after["present"] is False


def test_nine_predecessor_strict_cases_remain_strict_and_non_target_remains_review() -> None:
    assert CLOCK_PROOF["after"] == {"STRICT": 9, "SENSITIVITY": 0, "REVIEW": 3}
    assert set(CLOCK_PROOF["changed_outcomes"][i]["episode_id"] for i in range(len(CLOCK_PROOF["changed_outcomes"]))) <= PREDECESSOR_STRICT_IDS
    assert ENRICHMENT_BY_ID[SAME_ATTACK_ID]["B_same_attack"] is False


def test_frozen_12_replay_has_no_scope_leak_and_promotes_zero_representation_targets() -> None:
    outcomes = {}
    for episode in ENRICHMENT["episodes"]:
        episode_id = episode["episode_id"]
        if episode_id in PREDECESSOR_STRICT_IDS:
            outcomes[episode_id] = "STRICT"
        else:
            outcomes[episode_id] = "REVIEW"

    for episode_id in (AS_OF_ID, AFTER_ID):
        binding = _binding_for_target(episode_id)
        episode = ENRICHMENT_BY_ID[episode_id]
        strict_eligible = all(
            [
                episode["B_exact_city_parser"],
                episode["B_attack_event_parser"],
                episode["B_air_context_parser"],
                episode["B_same_attack"],
                binding["present"],
                binding["episode_specific"],
            ]
        )
        assert strict_eligible is False
        outcomes[episode_id] = "REVIEW"

    assert outcomes[SAME_ATTACK_ID] == "REVIEW"
    assert sum(value == "STRICT" for value in outcomes.values()) == 9
    assert sum(value == "SENSITIVITY" for value in outcomes.values()) == 0
    assert sum(value == "REVIEW" for value in outcomes.values()) == 3
    assert all(outcomes[episode_id] == "STRICT" for episode_id in PREDECESSOR_STRICT_IDS)
