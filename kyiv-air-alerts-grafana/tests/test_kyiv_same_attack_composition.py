from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor


PROVENANCE_PATH = ROOT.parent / "research" / "kyiv_12_positive_source_provenance_2026-10-04.json"
ENRICHMENT_PATH = ROOT.parent / "research" / "kyiv_12_positive_evidence_enrichment_ab_2026-10-04.json"
REPRESENTATION_PROOF_PATH = ROOT.parent / "research" / "kyiv_temporal_representation_proof_2026-10-04.json"
QUEUE_PATH = ROOT / "data" / "explosion_review_queue.json"
STATE_PATH = ROOT / "data" / "explosion_candidate_monitor_state.json"

TARGET_ID = "a422cb3549b4ba330c3b831f"
TARGET_START = "2026-10-02T02:47:00Z"
TARGET_END = "2026-10-02T03:42:00Z"
TARGET_SOURCE_URL = "https://dnipr.kyivcity.gov.ua/news/vorozha-ataka-na-stolytsiu-2-zhovtnia-informatsiia-onovliuietsia"
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
TEMPORAL_REVIEW_IDS = {
    "9fd2e6a9a02235982bd706ea": "INSUFFICIENT_LOWER_BOUND",
    "cfeec7a191817720d241fedb": "MULTI_EPISODE_INTERVAL",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


PROVENANCE = _load(PROVENANCE_PATH)
ENRICHMENT = _load(ENRICHMENT_PATH)
REPRESENTATION_PROOF = _load(REPRESENTATION_PROOF_PATH)
PROVENANCE_BY_ID = {row["episode_id"]: row for row in PROVENANCE["episodes"]}
ENRICHMENT_BY_ID = {row["episode_id"]: row for row in ENRICHMENT["episodes"]}


def _episode(
    episode_id: str = TARGET_ID,
    start: str = TARGET_START,
    end: str = TARGET_END,
    city_key: str = "kyiv",
) -> dict:
    return {
        "episode_id": episode_id,
        "city_key": city_key,
        "city": "Київ" if city_key == "kyiv" else city_key,
        "alert_start": start,
        "alert_end": end,
    }


def _target_row(
    *,
    air_text: str = "Оголошена дронова небезпека.",
    air_clock: str = "5:48",
    event_text: str | None = None,
    source_url: str = TARGET_SOURCE_URL,
    title: str | None = None,
    between: str = "",
) -> dict:
    source = PROVENANCE_BY_ID[TARGET_ID]
    event_text = event_text or source["attack_event_excerpt"]
    title = title or source["source_title"]
    parts = [f"{air_clock}, 2 жовтня — {air_text}"]
    if between:
        parts.append(between)
    parts.append(f"6:30, 2 жовтня — {event_text}")
    return {
        "candidate_id": "target-synthetic-frozen-chronology",
        "city_key": "kyiv",
        "published_at": source["publication_timestamp_utc"],
        "title": title,
        "snippet": "",
        "publisher": source["publisher"],
        "url": source_url,
        "resolved_url": source_url,
        "discovery_basis": "publisher_fulltext",
        "matched_text_excerpt": " ".join(parts),
    }


def _target_evidence(row: dict, episodes: list[dict] | None = None) -> tuple[dict, dict, dict]:
    source = PROVENANCE_BY_ID[TARGET_ID]
    episodes = episodes or [_episode()]
    strict = {
        "present": True,
        "segments": [f"6:30, 2 жовтня — {source['attack_event_excerpt']}"],
        "event_types": ["impact", "fire"],
    }
    air = {
        "present": True,
        "segments": [f"5:48, 2 жовтня — {source['air_context_excerpt'].split('…')[-1].strip()}"],
    }
    matching = {
        "outcome": "unique_match",
        "matched_episode_id": TARGET_ID,
        "matched_episode_ids": [TARGET_ID],
    }
    temporal = monitor.temporal_binding_evidence(row, strict, matching, episodes)
    return strict, air, temporal


def _composition(
    row: dict | None = None,
    *,
    episodes: list[dict] | None = None,
    strict_override: dict | None = None,
    air_override: dict | None = None,
    temporal_override: dict | None = None,
) -> dict:
    row = row or _target_row()
    episodes = episodes or [_episode()]
    strict, air, temporal = _target_evidence(row, episodes)
    return monitor.same_source_timeline_air_context_evidence(
        "kyiv",
        row,
        strict_override if strict_override is not None else strict,
        air_override if air_override is not None else air,
        temporal_override if temporal_override is not None else temporal,
        episodes,
    )


def test_target_identity_and_interval_are_exact() -> None:
    assert monitor.event_id("kyiv", TARGET_START, TARGET_END) == TARGET_ID
    source = PROVENANCE_BY_ID[TARGET_ID]
    assert source["source_url"] == TARGET_SOURCE_URL
    assert source["source_stated_event_time_raw"] == "6:30"
    assert source["air_context_excerpt"] == "5:48, 2 жовтня … Оголошена дронова небезпека."
    assert source["attack_event_excerpt"] == (
        "У Дарницькому районі влучання у верхні поверхи житлової багатоповерхівки. "
        "Є загоряння."
    )


def test_target_precondition_is_only_same_attack_gap() -> None:
    frozen = ENRICHMENT_BY_ID[TARGET_ID]
    assert frozen["B_exact_city_parser"] is True
    assert frozen["B_attack_event_parser"] is True
    assert frozen["B_air_context_parser"] is True
    assert frozen["B_same_attack"] is False
    assert frozen["earliest_B_failure"] == "SAME_ATTACK_CONTEXT_GAP"


def test_target_event_temporal_binding_is_preexisting_and_unique() -> None:
    row = _target_row()
    strict, _, temporal = _target_evidence(row)
    assert strict["present"] is True
    assert temporal["present"] is True
    assert temporal["episode_specific"] is True
    assert temporal["episode_id"] == TARGET_ID
    assert temporal["event_time"] == "2026-10-02T03:30:00Z"
    assert temporal["code"] == "TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE"


def test_target_same_source_timeline_composes_only_missing_air_same_attack_role() -> None:
    result = _composition()
    assert result["present"] is True
    assert result["reason"] == "same_source_timeline_air_context"
    assert result["gap_seconds"] == 42 * 60
    assert result["air_entry_time"] == "2026-10-02T02:48:00Z"
    assert result["event_entry_time"] == "2026-10-02T03:30:00Z"
    assert "event_time_from_existing_temporal_binding" in result["basis"]
    assert result["air_neighbor_check"]["passed"] is True
    assert result["event_neighbor_check"]["passed"] is True


def test_different_source_documents_do_not_compose() -> None:
    event_only = _target_row(air_text="")
    event_only["matched_text_excerpt"] = (
        "6:30, 2 жовтня — "
        + PROVENANCE_BY_ID[TARGET_ID]["attack_event_excerpt"]
    )
    strict, _, temporal = _target_evidence(event_only)
    assert monitor.same_source_timeline_air_context_evidence(
        "kyiv",
        event_only,
        strict,
        {"present": False, "segments": []},
        temporal,
        [_episode()],
    )["present"] is False

    air_only = _target_row()
    air_only["matched_text_excerpt"] = "5:48, 2 жовтня — Оголошена дронова небезпека."
    assert monitor.same_source_timeline_air_context_evidence(
        "kyiv",
        air_only,
        {"present": False, "segments": []},
        {"present": True, "segments": ["Оголошена дронова небезпека."]},
        {"present": False, "episode_specific": False},
        [_episode()],
    )["present"] is False


def test_different_city_air_entry_does_not_compose() -> None:
    row = _target_row(air_text="В Одесі оголошена дронова небезпека.")
    strict, _, temporal = _target_evidence(row)
    air = {"present": True, "segments": ["В Одесі оголошена дронова небезпека."]}
    result = monitor.same_source_timeline_air_context_evidence(
        "kyiv", row, strict, air, temporal, [_episode()]
    )
    assert result["present"] is False


def test_different_canonical_episode_does_not_compose() -> None:
    row = _target_row(air_clock="5:30")
    episodes = [
        _episode("previous", "2026-10-02T02:20:00Z", "2026-10-02T02:40:00Z"),
        _episode(),
    ]
    strict, _, temporal = _target_evidence(row, episodes)
    air = {"present": True, "segments": ["5:30, 2 жовтня — Оголошена дронова небезпека."]}
    result = monitor.same_source_timeline_air_context_evidence(
        "kyiv", row, strict, air, temporal, episodes
    )
    assert result["present"] is False


def test_gap_over_existing_45_minute_bound_does_not_compose() -> None:
    long_episode = _episode(start="2026-10-02T02:20:00Z")
    row = _target_row(air_clock="5:40")
    strict, _, temporal = _target_evidence(row, [long_episode])
    air = {"present": True, "segments": ["5:40, 2 жовтня — Оголошена дронова небезпека."]}
    result = monitor.same_source_timeline_air_context_evidence(
        "kyiv", row, strict, air, temporal, [long_episode]
    )
    assert result["present"] is False


def test_intervening_conflicting_entry_blocks_composition() -> None:
    row = _target_row(
        between="6:00, 2 жовтня — В Одесі зафіксовано влучання ракети."
    )
    strict, air, temporal = _target_evidence(row)
    result = monitor.same_source_timeline_air_context_evidence(
        "kyiv", row, strict, air, temporal, [_episode()]
    )
    assert result["present"] is False
    assert result["reason"] == "intervening_timeline_conflict"


def test_generic_alert_language_does_not_supply_qualifying_air_context() -> None:
    row = _target_row(air_text="Оголошена повітряна тривога.")
    strict, _, temporal = _target_evidence(row)
    air = {"present": True, "segments": ["Оголошена повітряна тривога."]}
    result = monitor.same_source_timeline_air_context_evidence(
        "kyiv", row, strict, air, temporal, [_episode()]
    )
    assert result["present"] is False
    assert result["reason"] == "qualifying_air_timeline_entry_not_recovered"


def test_event_evidence_absent_does_not_compose() -> None:
    result = _composition(strict_override={"present": False, "segments": []})
    assert result["present"] is False
    assert result["reason"] == "missing_event_or_air_context"


def test_ambiguous_temporal_binding_does_not_compose() -> None:
    result = _composition(
        temporal_override={
            "present": False,
            "episode_specific": False,
            "episode_id": None,
            "event_time": None,
        }
    )
    assert result["present"] is False
    assert result["reason"] == "event_temporal_binding_not_unique"


def test_untrusted_non_kyiv_official_timeline_does_not_use_new_path() -> None:
    row = _target_row(
        source_url="https://example.org/live-update",
        title="Ворожа атака на столицю 2 жовтня (інформація оновлюється)",
    )
    strict, air, temporal = _target_evidence(row)
    result = monitor.same_source_timeline_air_context_evidence(
        "kyiv", row, strict, air, temporal, [_episode()]
    )
    assert result["present"] is False
    assert result["reason"] == "unsupported_source_chronology"


def test_kherson_and_other_city_composition_scope_is_unchanged() -> None:
    row = _target_row()
    strict, air, temporal = _target_evidence(row)
    result = monitor.same_source_timeline_air_context_evidence(
        "kherson", row, strict, air, temporal, [_episode(city_key="kherson")]
    )
    assert result["present"] is False
    assert result["reason"] == "unsupported_source_chronology"


def test_same_attack_wrapper_promotes_target_basis_only_after_temporal_binding() -> None:
    row = _target_row()
    strict, air, temporal = _target_evidence(row)
    result = monitor.same_attack_context_evidence(
        "kyiv", row, strict, air, temporal, [_episode()]
    )
    assert result["present"] is True
    assert result["reason"] == "same_source_timeline_air_context"


def test_frozen_12_replay_becomes_10_strict_0_sensitivity_2_review() -> None:
    result = _composition()
    assert result["present"] is True

    outcomes = {}
    for episode in ENRICHMENT["episodes"]:
        episode_id = episode["episode_id"]
        if episode_id in PREDECESSOR_STRICT_IDS:
            outcomes[episode_id] = "STRICT"
        elif episode_id == TARGET_ID:
            strict_eligible = all(
                [
                    episode["B_exact_city_parser"],
                    episode["B_attack_event_parser"],
                    episode["B_air_context_parser"],
                    result["present"],
                    True,
                    True,
                ]
            )
            blocked = monitor.publisher_fulltext_requires_review(
                {"discovery_basis": episode["B_discovery_basis"]},
                {"usable": False},
                strict_eligible=strict_eligible,
            )
            outcomes[episode_id] = "STRICT" if strict_eligible and not blocked else "REVIEW"
        else:
            outcomes[episode_id] = "REVIEW"

    assert sum(value == "STRICT" for value in outcomes.values()) == 10
    assert sum(value == "SENSITIVITY" for value in outcomes.values()) == 0
    assert sum(value == "REVIEW" for value in outcomes.values()) == 2
    assert outcomes[TARGET_ID] == "STRICT"
    assert all(outcomes[episode_id] == "STRICT" for episode_id in PREDECESSOR_STRICT_IDS)
    assert all(outcomes[episode_id] == "REVIEW" for episode_id in TEMPORAL_REVIEW_IDS)


def test_temporal_safety_cases_retain_exact_review_reasons() -> None:
    details = {
        row["episode_id"]: row["result"]
        for row in REPRESENTATION_PROOF["replay"]["target_results"]
    }
    assert details == TEMPORAL_REVIEW_IDS


def test_bounded_repository_candidate_differential(monkeypatch) -> None:
    queue = _load(QUEUE_PATH)
    state = _load(STATE_PATH)
    candidates = queue if isinstance(queue, list) else (queue.get("candidates") or queue.get("queue") or [])

    with monkeypatch.context() as before_patch:
        before_patch.setattr(
            monitor,
            "same_source_timeline_air_context_evidence",
            lambda *_args, **_kwargs: {
                "present": False,
                "reason": "predecessor_no_same_source_timeline_composition",
            },
        )
        before = {
            str(item.get("candidate_id") or f"row-{index}"): monitor.dry_classify_existing_candidate(item, state)
            for index, item in enumerate(candidates)
            if isinstance(item, dict)
        }

    after = {
        str(item.get("candidate_id") or f"row-{index}"): monitor.dry_classify_existing_candidate(item, state)
        for index, item in enumerate(candidates)
        if isinstance(item, dict)
    }

    changed = []
    for candidate_id in sorted(set(before) & set(after)):
        pre = before[candidate_id]
        post = after[candidate_id]
        if (
            pre.get("proposed_outcome") != post.get("proposed_outcome")
            or pre.get("proposed_matched_episode_id") != post.get("proposed_matched_episode_id")
        ):
            changed.append(
                {
                    "candidate_id": candidate_id,
                    "before": pre.get("proposed_outcome"),
                    "after": post.get("proposed_outcome"),
                    "predicate": (post.get("same_attack_context") or {}).get("reason"),
                }
            )

    assert all(row["predicate"] == "same_source_timeline_air_context" for row in changed)
    summary = {
        "total": len(after),
        "changed": len(changed),
        "changed_to_strict": sum(row["after"] == "approved_strict" for row in changed),
        "all_changes_satisfy_target_predicate": all(
            row["predicate"] == "same_source_timeline_air_context" for row in changed
        ),
        "changed_rows": changed,
    }
    print("BOUNDED_DIFFERENTIAL_JSON=" + json.dumps(summary, ensure_ascii=False, sort_keys=True))
