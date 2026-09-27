#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

import monitor_explosion_candidates as m


def legacy_strict_explosion_signal(text: str) -> bool:
    low = m.normalize_evidence_text(text)
    if not low:
        return False
    if m.controlled_blast_nonmilitary_signal(low):
        return False
    if re.search(r"\bвибух\w*", low):
        return True
    if re.search(r"\b(?:влуч\w*|поціл\w*|приліт\w*|вдарил\w*)", low):
        return True
    if re.search(r"\b(?:завдал\w*|нанес\w*)\b.{0,50}\bудар\w*", low):
        return True
    if re.search(r"\bудар(?:у|и|ів|ом|ами)?\b", low):
        threat_only = bool(re.search(r"\bзагроз\w*.{0,30}\bудар(?:у|и|ів|ом|ами)?\b", low))
        if not threat_only:
            return True
    return False


def legacy_relative_alert_chronology_relation(row: dict, episodes: list[dict]) -> dict:
    return {
        "relation": None,
        "event_time": None,
        "alert_time": None,
        "offset_minutes": None,
        "episode_specific": False,
        "supported_episode_ids": [],
        "episode_id": None,
    }


def classify_all(queue: list[dict], state: dict, signal, relative_relation) -> dict[str, dict]:
    original_signal = m.strict_attack_event_signal
    original_relative = m.relative_alert_chronology_relation
    m.strict_attack_event_signal = signal
    m.relative_alert_chronology_relation = relative_relation
    try:
        out = {}
        for item in queue:
            if not isinstance(item, dict):
                continue
            cid = str(item.get("candidate_id") or "")
            city = str(item.get("city_key") or "")
            if not cid or city not in m.CITY_CONFIG:
                continue
            episodes = m.tracked_episodes_for_city(state, city)
            matching = m.match_candidate_to_episodes(item, episodes)
            decision = m.classify_candidate(item, city, episodes, matching)
            out[cid] = {
                "city_key": city,
                "proposed_outcome": decision.get("proposed_outcome"),
                "proposed_matched_episode_id": decision.get("proposed_matched_episode_id"),
                "candidate_strict_present": bool((decision.get("candidate_evidence") or {}).get("strict_explosion", {}).get("present")),
                "event_types": list(decision.get("event_types") or []),
                "reason_codes": list(decision.get("reason_codes") or []),
                "temporal_code": (decision.get("temporal_binding") or {}).get("code"),
            }
        return out
    finally:
        m.strict_attack_event_signal = original_signal
        m.relative_alert_chronology_relation = original_relative


def main() -> None:
    queue = m.load_json(m.QUEUE_FILE, [])
    state = m.load_json(m.STATE_FILE, {})
    if not isinstance(queue, list):
        raise RuntimeError("queue is not a list")

    old = classify_all(
        queue,
        state,
        legacy_strict_explosion_signal,
        legacy_relative_alert_chronology_relation,
    )
    new = classify_all(
        queue,
        state,
        m.strict_attack_event_signal,
        m.relative_alert_chronology_relation,
    )

    changes = []
    uncontrolled = []
    regressions = []
    for cid in sorted(set(old) & set(new)):
        before = old[cid]
        after = new[cid]
        if before["proposed_outcome"] == after["proposed_outcome"] and before["proposed_matched_episode_id"] == after["proposed_matched_episode_id"]:
            continue
        gained_strict = (not before["candidate_strict_present"]) and after["candidate_strict_present"]
        consequence_types = sorted(set(after["event_types"]) & {"damage", "fire"})
        targeted_damage_fire = gained_strict and bool(consequence_types)
        targeted_relative_chronology = after.get("temporal_code") == "TEMPORAL_RELATIVE_ALERT_CHRONOLOGY"
        targeted = targeted_damage_fire or targeted_relative_chronology
        row = {
            "candidate_id": cid,
            "city_key": after["city_key"],
            "old_outcome": before["proposed_outcome"],
            "new_outcome": after["proposed_outcome"],
            "old_episode_id": before["proposed_matched_episode_id"],
            "new_episode_id": after["proposed_matched_episode_id"],
            "event_types": after["event_types"],
            "old_temporal_code": before.get("temporal_code"),
            "new_temporal_code": after.get("temporal_code"),
            "targeted_damage_fire_widening": targeted_damage_fire,
            "targeted_relative_chronology": targeted_relative_chronology,
        }
        changes.append(row)
        if not targeted:
            uncontrolled.append(row)
        if before["proposed_outcome"] in {"approved_strict", "approved_sensitivity"} and after["proposed_outcome"] not in {"approved_strict", "approved_sensitivity"}:
            regressions.append(row)

    summary = {
        "schema_version": 1,
        "evaluated_candidates": len(new),
        "changed_candidate_count": len(changes),
        "targeted_damage_fire_widening_count": sum(1 for row in changes if row["targeted_damage_fire_widening"]),
        "targeted_relative_chronology_count": sum(1 for row in changes if row["targeted_relative_chronology"]),
        "uncontrolled_drift_count": len(uncontrolled),
        "approved_regression_count": len(regressions),
        "changes": changes,
        "uncontrolled_drift": uncontrolled,
        "approved_regressions": regressions,
        "verdict": "ATTACK-EVENT CLASSIFIER CONTROL REPLAY CLEAN" if not uncontrolled and not regressions else "ATTACK-EVENT CLASSIFIER CONTROL REPLAY BLOCKED",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if uncontrolled or regressions:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
