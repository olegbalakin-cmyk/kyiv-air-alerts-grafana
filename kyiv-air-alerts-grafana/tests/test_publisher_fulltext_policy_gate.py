from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor


EPISODE_ID = "ep-policy-gate"
EPISODES = [
    {
        "episode_id": EPISODE_ID,
        "city_key": "kyiv",
        "alert_start": "2026-10-01T10:00:00Z",
        "alert_end": "2026-10-01T11:00:00Z",
    }
]
MATCHING = {
    "outcome": "unique_match",
    "matched_episode_id": EPISODE_ID,
    "matched_episode_ids": [EPISODE_ID],
}


def _empty_reviewed() -> dict:
    return {
        "usable": False,
        "exact_city": {"present": False, "segments": []},
        "strict_explosion": {"present": False, "segments": [], "event_types": []},
        "air_military_context": {"present": False, "segments": []},
        "same_attack_context": {"present": False},
        "temporal_binding": {
            "present": False,
            "episode_specific": False,
            "episode_id": None,
        },
        "sensitivity_binding": {"present": False},
        "reason_codes": [],
    }


def _decision(
    monkeypatch,
    *,
    discovery_basis: str = "publisher_fulltext",
    exact: bool = True,
    attack: bool = True,
    air: bool = True,
    same_attack: bool = True,
    temporal: bool = True,
    controlled: bool = False,
) -> dict:
    row = {
        "candidate_id": "candidate-policy-gate",
        "city_key": "kyiv",
        "source": "focused-test",
        "publisher": "focused-test",
        "published_at": "2026-10-01T10:30:00Z",
        "title": "",
        "snippet": "",
        "discovery_basis": discovery_basis,
    }

    monkeypatch.setattr(
        monitor,
        "exact_city_classification_evidence",
        lambda *_: {"present": exact, "segments": ["exact"] if exact else []},
    )
    monkeypatch.setattr(
        monitor,
        "strict_explosion_evidence",
        lambda *_: {
            "present": attack,
            "segments": ["attack"] if attack else [],
            "event_types": ["explosion"] if attack else [],
        },
    )
    monkeypatch.setattr(
        monitor,
        "air_military_context_evidence",
        lambda *_: {"present": air, "segments": ["air"] if air else []},
    )
    monkeypatch.setattr(
        monitor,
        "same_attack_context_evidence",
        lambda *_: {"present": same_attack, "reason": "focused-test"},
    )
    monkeypatch.setattr(
        monitor,
        "temporal_binding_evidence",
        lambda *_: {
            "present": temporal,
            "episode_specific": temporal,
            "episode_id": EPISODE_ID if temporal else None,
            "supported_episode_ids": [EPISODE_ID] if temporal else [],
            "code": (
                "TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE"
                if temporal
                else "NO_STRICT_TEMPORAL_BINDING"
            ),
            "near_boundary": {"present": False},
        },
    )
    monkeypatch.setattr(
        monitor,
        "single_episode_day_inference",
        lambda *_: {"present": False, "episode_id": None},
    )
    monkeypatch.setattr(
        monitor,
        "reviewed_provenance_adapter",
        lambda *_: _empty_reviewed(),
    )
    monkeypatch.setattr(
        monitor,
        "classification_segments",
        lambda *_: ["Київ контрольований вибух"] if controlled else [],
    )
    monkeypatch.setattr(monitor, "city_mentioned", lambda *_: controlled)
    monkeypatch.setattr(
        monitor,
        "controlled_blast_nonmilitary_signal",
        lambda *_: controlled,
    )

    return monitor.classify_candidate(row, "kyiv", EPISODES, MATCHING)


def test_publisher_fulltext_all_strict_gates_passes_promotes(monkeypatch) -> None:
    decision = _decision(monkeypatch)
    assert decision["proposed_outcome"] == "approved_strict"
    assert decision["proposed_matched_episode_id"] == EPISODE_ID
    assert "PUBLISHER_FULLTEXT_REQUIRES_REVIEW" not in decision["reason_codes"]


def test_publisher_fulltext_missing_exact_city_not_strict(monkeypatch) -> None:
    decision = _decision(monkeypatch, exact=False)
    assert decision["proposed_outcome"] != "approved_strict"
    assert "PUBLISHER_FULLTEXT_REQUIRES_REVIEW" in decision["reason_codes"]


def test_publisher_fulltext_missing_attack_event_not_strict(monkeypatch) -> None:
    decision = _decision(monkeypatch, attack=False)
    assert decision["proposed_outcome"] != "approved_strict"
    assert "PUBLISHER_FULLTEXT_REQUIRES_REVIEW" in decision["reason_codes"]


def test_publisher_fulltext_missing_air_context_not_strict(monkeypatch) -> None:
    decision = _decision(monkeypatch, air=False)
    assert decision["proposed_outcome"] != "approved_strict"
    assert "PUBLISHER_FULLTEXT_REQUIRES_REVIEW" in decision["reason_codes"]


def test_publisher_fulltext_missing_same_attack_not_strict(monkeypatch) -> None:
    decision = _decision(monkeypatch, same_attack=False)
    assert decision["proposed_outcome"] != "approved_strict"
    assert "PUBLISHER_FULLTEXT_REQUIRES_REVIEW" in decision["reason_codes"]


def test_publisher_fulltext_missing_strict_temporal_binding_not_strict(monkeypatch) -> None:
    decision = _decision(monkeypatch, temporal=False)
    assert decision["proposed_outcome"] != "approved_strict"
    assert "PUBLISHER_FULLTEXT_REQUIRES_REVIEW" in decision["reason_codes"]


def test_ordinary_non_fulltext_classification_remains_strict(monkeypatch) -> None:
    decision = _decision(monkeypatch, discovery_basis="rss_title_snippet")
    assert decision["proposed_outcome"] == "approved_strict"
    assert "PUBLISHER_FULLTEXT_REQUIRES_REVIEW" not in decision["reason_codes"]


def test_deterministic_rejection_remains_unchanged(monkeypatch) -> None:
    decision = _decision(monkeypatch, controlled=True)
    assert decision["proposed_outcome"] == "rejected"
    assert "DETERMINISTIC_CONTROLLED_BLAST" in decision["reason_codes"]


def test_frozen_kyiv_12_policy_replay_promotes_only_four_targets() -> None:
    artifact = json.loads(
        (ROOT.parent / "research" / "kyiv_12_positive_evidence_enrichment_ab_2026-10-04.json")
        .read_text(encoding="utf-8")
    )
    expected_targets = {
        "735a17c8622f113c4abc15b8",
        "6bb2a52b33667e8ddf111326",
        "4684548673d2b83089b0f15e",
        "af3627c04d206a368662136e",
    }

    after = []
    changed = set()
    for episode in artifact["episodes"]:
        strict_eligible = all(
            [
                episode["B_exact_city_parser"],
                episode["B_attack_event_parser"],
                episode["B_air_context_parser"],
                episode["B_same_attack"],
                episode["B_temporal_parser"],
                episode["B_episode_binding"],
            ]
        )
        blocked = monitor.publisher_fulltext_requires_review(
            {"discovery_basis": episode["B_discovery_basis"]},
            {"usable": False},
            strict_eligible=strict_eligible,
        )
        outcome = episode["B_outcome"]
        if strict_eligible and not blocked:
            outcome = "STRICT"
        after.append(outcome)
        if outcome != episode["B_outcome"]:
            changed.add(episode["episode_id"])

    assert changed == expected_targets
    assert after.count("STRICT") == 4
    assert after.count("SENSITIVITY") == 0
    assert after.count("REVIEW") == 8
