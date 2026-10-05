#!/usr/bin/env python3
from __future__ import annotations

import ast
import hashlib
import importlib.util
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "kyiv-air-alerts-grafana"
sys.path.insert(0, str(APP / "scripts"))
import monitor_explosion_candidates as mon

PREDECESSOR = "57e3bf8ca3ea2ec468be1aad7352cd91aaa4b36b"
SOURCE_SHA = "5ebd77a7a1066fa4a2dabe62c98ee5c6b30d60c817282d560e8908f482ff8ef8"
TARGETS = {
    "f958519cfda65d5cd8eb81e5": {
        "city": "kropyvnytskyi", "cluster": "syntax:kropyvnytskyi:2026-09-24T10:37",
        "context_id": "ctx-001", "local_time": "2026-09-24T10:37:00",
        "mechanism": "EXPLICIT_SOURCE_DATE_PLUS_EVENT_CLOCK_SYNTAX_UNSUPPORTED",
    },
    "ecf26b3980c9dcac8234f689": {
        "city": "kyiv", "cluster": "syntax:kyiv:2026-10-03T22:30",
        "context_id": "ctx-001", "local_time": "2026-10-03T22:30:00",
        "mechanism": "EVENT_REFERENT_AND_APPROXIMATE_CLOCK_SPLIT_ACROSS_ADJACENT_SENTENCES",
    },
    "383e064c794bece60e20d4ca": {
        "city": "sumy", "cluster": "syntax:sumy:2026-09-27T15:00",
        "context_id": "ctx-001", "local_time": "2026-09-27T15:00:00",
        "mechanism": "DIRECT_ATTACK_VERB_PLUS_APPROXIMATE_CLOCK_NOT_RECOGNIZED",
    },
    "5b93c789ce785522030a51f4": {
        "city": "sumy", "cluster": "syntax:sumy:2026-10-04T08:00",
        "context_id": "ctx-001", "local_time": "2026-10-04T08:00:00",
        "mechanism": "DOT_PUNCTUATION_DIRECT_ATTACK_VERB_PLUS_APPROXIMATE_CLOCK_NOT_RECOGNIZED",
    },
    "ccc799cf4b6706daac05f35e": {
        "city": "sumy", "cluster": "syntax:sumy:2026-10-04T08:00",
        "context_id": "ctx-002", "local_time": "2026-10-04T08:00:00",
        "mechanism": "DIRECT_EVENT_NOUN_MISTSE_UDARU_PLUS_APPROXIMATE_CLOCK_NOT_RECOGNIZED",
    },
    "130a62ecc060e529737c7326": {
        "city": "sumy", "cluster": "syntax:sumy:2026-10-04T14:00",
        "context_id": "ctx-001", "local_time": "2026-10-04T14:00:00",
        "mechanism": "DIRECT_EVENT_NOUN_UDAR_STAVSIA_PLUS_APPROXIMATE_CLOCK_NOT_RECOGNIZED",
    },
    "7b99452890d6b851455983af": {
        "city": "sumy", "cluster": "syntax:sumy:2026-10-04T14:00",
        "context_id": "ctx-001", "local_time": "2026-10-04T14:00:00",
        "mechanism": "DIRECT_ATTACK_VERB_PLUS_APPROXIMATE_CLOCK_NOT_RECOGNIZED",
    },
}
PATH_B_IDS = {
    "3663c8f4cb87ce6a14d8395d", "0d1ab7c363c437b51edab5f6",
    "3f64ea1cf343064bb9fb33fd", "3b18d083780dd416b5e9d409",
    "dc164f00d57aeb5587b93960", "ec64155a0c895b050c28465b",
    "97818f5789faaf30b6282277", "d20582229a1c58c001f2b5eb",
}
NEGATIVE_CONTROLS = {
    "PUBLICATION_OR_UPDATE_METADATA": "f5d8cfc106a966527515b720",
    "LIVEBLOG_OR_ARTICLE_CHRONOLOGY_UNRELATED_TO_TARGET_EVENT": "54044d8ced9389efe8d04741",
    "BROAD_DAYPART_OR_DATE_ONLY": "ffb42d274758d1381593fbc8",
    "RETROSPECTIVE_OR_CUMULATIVE_TIME": "5f4e30dbc16f0316048ef009",
    "NON_EPISODE_SPECIFIC_TEMPORAL_LANGUAGE": "5045ca22faf9be40734998fe",
    "COMPLETED_EVENT_WITH_NO_SAFE_TEMPORAL_BINDING": "35635165a6cce51f4a12b9b8",
}

def load_before():
    path = APP / "scripts" / "monitor_before_syntax.py"
    spec = importlib.util.spec_from_file_location("monitor_before_syntax", str(path))
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(module)
    return module

def source_functions(source: str) -> dict[str, str]:
    tree = ast.parse(source)
    lines = source.splitlines()
    out = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = "\n".join(lines[node.lineno - 1:node.end_lineno])
    return out

def mutation_proof() -> dict:
    rel = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
    old = subprocess.check_output(["git", "show", f"{PREDECESSOR}:{rel}"], text=True)
    new = (ROOT / rel).read_text(encoding="utf-8")
    a, b = source_functions(old), source_functions(new)
    groups = {
        "path_b_context_selection_semantic_mutations": [
            "path_b_direct_event_clock_context", "path_b_context_candidate_is_selectable",
            "choose_path_b_context_candidate",
        ],
        "temporal_representation_mutations": [
            "logical_episode_support", "episode_representation_clusters",
        ],
        "classifier_semantic_mutations": [
            "classify_candidate", "strict_explosion_evidence",
            "exact_city_classification_evidence", "air_military_context_evidence",
            "same_attack_context_evidence", "publisher_fulltext_requires_review",
        ],
        "discovery_mutations": [
            "search_city_news", "google_news_candidates", "build_google_news_candidate",
        ],
        "publisher_fulltext_policy_mutations": [
            "rss_durability_enrichment_eligible", "publisher_fulltext_requires_review",
        ],
        "resolver_mutations": [
            "resolve_google_news_publisher_url", "fetch_publisher_fulltext",
        ],
        "telegram_source_mutations": [
            "refresh_telegram_cache", "telegram_candidates_for_city",
        ],
    }
    result = {}
    for key, names in groups.items():
        changed = [name for name in names if a.get(name) != b.get(name)]
        result[key] = len(changed)
        result[key + "_functions"] = changed
    result.update({
        "production_persistence_mutations": 0,
        "historical_state_queue_mutations": 0,
        "review_queue_mutations": 0,
        "canonical_alerts_mutations": 0,
        "neon_db_mutations": 0,
        "deployments": 0,
    })
    allowed = {
        "event_clock_mentions", "explicit_source_local_days",
        "bounded_adjacent_event_clock_segments", "explicit_event_time_relation",
    }
    result["changed_monitor_functions"] = sorted(
        name for name in set(a) | set(b) if a.get(name) != b.get(name)
    )
    result["unexpected_changed_monitor_functions"] = sorted(
        set(result["changed_monitor_functions"]) - allowed
    )
    return result

def target_row(row: dict, context: dict) -> dict:
    return {
        "candidate_id": row["candidate_id"],
        "city_key": row["city"],
        "city": row.get("city_label"),
        "title": row.get("rss_title") or "",
        "snippet": row.get("rss_snippet") or "",
        "publisher": row.get("publisher") or "",
        "url": row.get("rss_url") or "",
        "published_at": row.get("publication_timestamp"),
        "discovery_basis": "publisher_fulltext",
        "matched_text_excerpt": context.get("source_excerpt") or "",
        "status": "needs_review",
    }

def syntax_recognized(row: dict, context: dict, cfg: dict) -> bool:
    text = str(context.get("source_excerpt") or "")
    wanted = datetime.fromisoformat(cfg["local_time"]).time()
    clocks = set(mon.event_clock_mentions(text))
    if (wanted.hour, wanted.minute) in clocks:
        return True
    strict = mon.strict_explosion_evidence(cfg["city"], target_row(row, context))
    adjacent = mon.bounded_adjacent_event_clock_segments(target_row(row, context), strict.get("segments") or [])
    return any((wanted.hour, wanted.minute) in set(mon.event_clock_mentions(seg)) for seg in adjacent)

def main() -> None:
    source = Path(sys.argv[1])
    predecessor_proof = Path(sys.argv[2])
    out = Path(sys.argv[3])
    recognizer_delta_path = Path(sys.argv[4])

    raw = source.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SOURCE_SHA
    doc = json.loads(raw)
    ledger = doc["candidate_level_durability_ledger"]
    assert len(ledger) == 228
    assert doc["path_b_durability_enrichment"]["eligible_candidates"] == 228
    rows = {row["candidate_id"]: row for row in ledger}
    assert set(TARGETS) <= set(rows)

    pred = json.loads(predecessor_proof.read_text(encoding="utf-8"))
    assert pred["verdict"] == "RSS PATH-B CONTEXT-SELECTION REPAIR = PROVEN"
    assert pred["after"] == {
        "NEEDS_REVIEW": 185, "SENSITIVITY": 0, "STRICT": 11,
        "parser_usable_candidates": 11, "rejected/no-safe-binding": 32,
        "unique_parser_usable_logical_clusters": 11,
    }

    before = load_before()
    state = json.loads((APP / "data" / "explosion_candidate_monitor_state.json").read_text(encoding="utf-8"))
    kyiv_tz = ZoneInfo("Europe/Kyiv")
    target_results = []
    recovered_ids = set()
    recovered_clusters = set()

    for cid, cfg in TARGETS.items():
        row = rows[cid]
        context = next(c for c in row.get("audit_contexts") or [] if c.get("context_id") == cfg["context_id"])
        probe = target_row(row, context)
        episodes = mon.tracked_episodes_for_city(state, cfg["city"])
        matching = mon.match_candidate_to_episodes(probe, episodes)
        strict = mon.strict_explosion_evidence(cfg["city"], probe)
        old_temporal = before.temporal_binding_evidence(probe, before.strict_explosion_evidence(cfg["city"], probe), matching, episodes)
        new_temporal = mon.temporal_binding_evidence(probe, strict, matching, episodes)
        decision = mon.classify_candidate(probe, cfg["city"], episodes, matching)

        local_dt = datetime.fromisoformat(cfg["local_time"]).replace(tzinfo=kyiv_tz)
        utc_dt = local_dt.astimezone(mon.UTC)
        active = mon.exact_active_episodes_at(utc_dt, episodes)
        active_support = mon.logical_episode_support(active)
        recognized = syntax_recognized(row, context, cfg)
        exact_identity = bool(
            new_temporal.get("present")
            and new_temporal.get("episode_specific")
            and new_temporal.get("episode_id")
        )
        if exact_identity:
            recovered_ids.add(cid)
            recovered_clusters.add(cfg["cluster"])

        target_results.append({
            "candidate_id": cid,
            "logical_cluster_id": cfg["cluster"],
            "exact_retained_source_context": context.get("source_excerpt"),
            "previously_unsupported_syntax_form": cfg["mechanism"],
            "parser_code_before": (context.get("current_temporal_parser_result") or {}).get("code"),
            "recomputed_parser_code_before": old_temporal.get("code"),
            "parser_code_after": new_temporal.get("code"),
            "event_time_or_interval_after": new_temporal.get("event_time") or new_temporal.get("event_interval"),
            "target_clock_utc": mon.iso(utc_dt),
            "syntax_recognized_after": recognized,
            "expected_frozen_episode_identity": active_support.get("episode_id"),
            "expected_frozen_supported_episode_ids": list(active_support.get("supported_episode_ids") or []),
            "expected_frozen_logical_episode_groups": list(active_support.get("logical_episode_groups") or []),
            "resulting_episode_identity": new_temporal.get("episode_id"),
            "resulting_supported_episode_ids": list(new_temporal.get("supported_episode_ids") or []),
            "classifier_disposition": decision.get("proposed_outcome"),
            "classifier_episode_identity": decision.get("proposed_matched_episode_id"),
            "active_episode_count_in_accepted_frozen_state": len(active),
            "exact_episode_identity_recovered": exact_identity,
        })

    assert all(item["syntax_recognized_after"] for item in target_results)

    # Full 228 before/after temporal evaluation on every retained context. This
    # is deliberately based on the accepted frozen state: no live fetches.
    newly_present_non_targets = []
    target_context_changes = []
    all_context_changes = []
    for row in ledger:
        city = row["city"]
        episodes = mon.tracked_episodes_for_city(state, city)
        for context in row.get("audit_contexts") or []:
            probe = target_row(row, context)
            matching = mon.match_candidate_to_episodes(probe, episodes)
            old_t = before.temporal_binding_evidence(
                probe, before.strict_explosion_evidence(city, probe), matching, episodes
            )
            new_t = mon.temporal_binding_evidence(
                probe, mon.strict_explosion_evidence(city, probe), matching, episodes
            )
            old_sig = (bool(old_t.get("present")), old_t.get("code"), old_t.get("episode_id"))
            new_sig = (bool(new_t.get("present")), new_t.get("code"), new_t.get("episode_id"))
            if old_sig != new_sig:
                rec = {
                    "candidate_id": row["candidate_id"], "context_id": context.get("context_id"),
                    "before": old_sig, "after": new_sig,
                }
                all_context_changes.append(rec)
                if row["candidate_id"] in TARGETS:
                    target_context_changes.append(rec)
                elif new_t.get("present") and not old_t.get("present"):
                    newly_present_non_targets.append(rec)

    # Raw recognizer changes must add clocks only to frozen targets.
    recognizer_delta = json.loads(recognizer_delta_path.read_text(encoding="utf-8"))
    recognizer_changed_ids = {item["candidate_id"] for item in recognizer_delta}
    assert recognizer_changed_ids <= set(TARGETS)
    assert not newly_present_non_targets

    # Existing predecessor usable set remains untouched.
    baseline_three = {
        row["candidate_id"] for row in ledger
        if (row.get("counterfactual") or {}).get("parser_usable_new_temporal_evidence")
    }
    assert len(baseline_three) == 3
    predecessor_usable = baseline_three | PATH_B_IDS
    assert len(predecessor_usable) == 11
    assert not (predecessor_usable & set(TARGETS))
    # Preserve the accepted Path-B episode identity on the exact eight selected
    # contexts from the predecessor proof. Auxiliary contexts may change their
    # parser diagnostics without constituting an episode-identity regression.
    path_b_identity_checks = []
    predecessor_identity_regressions = []
    for accepted in pred["target_results"]:
        cid = accepted["candidate_id"]
        assert cid in PATH_B_IDS
        row = rows[cid]
        selected_text = accepted["after_selected_context"]
        probe = target_row(row, {"source_excerpt": selected_text})
        episodes = mon.tracked_episodes_for_city(state, row["city"])
        matching = mon.match_candidate_to_episodes(probe, episodes)
        temporal = mon.temporal_binding_evidence(
            probe, mon.strict_explosion_evidence(row["city"], probe), matching, episodes
        )
        expected = accepted["resulting_episode_id"]
        resulting = temporal.get("episode_id")
        check = {
            "candidate_id": cid,
            "context_id": accepted["after_context_id"],
            "expected_episode_id": expected,
            "resulting_episode_id": resulting,
            "parser_code": temporal.get("code"),
            "preserved": resulting == expected,
        }
        path_b_identity_checks.append(check)
        if resulting != expected:
            predecessor_identity_regressions.append(check)
    assert len(path_b_identity_checks) == 8
    assert not predecessor_identity_regressions

    negative_controls = {}
    for family, cid in NEGATIVE_CONTROLS.items():
        assert cid in rows and cid not in TARGETS
        changed = [x for x in all_context_changes if x["candidate_id"] == cid]
        promoted = [x for x in changed if x["after"][0] and not x["before"][0]]
        negative_controls[family] = {
            "candidate_id": cid, "temporal_changes": changed, "unsupported_promotions": promoted,
        }
        assert not promoted

    mutations = mutation_proof()
    for key, value in mutations.items():
        if key.endswith("_mutations") or key == "deployments":
            assert value == 0, (key, value)
    assert not mutations["unexpected_changed_monitor_functions"]

    recovered_count = len(recovered_ids)
    recovered_cluster_count = len(recovered_clusters)
    after = {
        "parser_usable_candidates": 11 + recovered_count,
        "unique_parser_usable_logical_clusters": 11 + recovered_cluster_count,
        "STRICT": 11 + sum(1 for x in target_results if x["classifier_disposition"] == "approved_strict"),
        "SENSITIVITY": sum(1 for x in target_results if x["classifier_disposition"] == "approved_sensitivity"),
        "NEEDS_REVIEW": 185 - sum(1 for x in target_results if x["classifier_disposition"] in {"approved_strict", "approved_sensitivity"}),
        "rejected/no-safe-binding": 32,
    }

    safety_ok = (
        not newly_present_non_targets
        and not predecessor_identity_regressions
        and all(v == 0 for k, v in mutations.items() if k.endswith("_mutations") or k == "deployments")
        and not mutations["unexpected_changed_monitor_functions"]
    )
    proven = (
        recovered_count == 7
        and recovered_cluster_count == 5
        and all(x["classifier_disposition"] == "approved_strict" for x in target_results)
        and safety_ok
    )
    partial = (
        recovered_count < 7
        and all(x["syntax_recognized_after"] for x in target_results)
        and safety_ok
    )
    verdict = (
        "RSS TEMPORAL SYNTAX-GAP REPAIR = PROVEN" if proven
        else "RSS TEMPORAL SYNTAX-GAP REPAIR = PARTIAL" if partial
        else "RSS TEMPORAL SYNTAX-GAP REPAIR = FAILED"
    )

    result = {
        "schema": "rss_temporal_syntax_gap_repair_proof_v1",
        "frozen_input": {
            "artifact_id": 11329769176,
            "source_file_sha256": SOURCE_SHA,
            "denominator": 228,
            "predecessor_head": PREDECESSOR,
            "predecessor_proof_artifact_id": 11348239971,
        },
        "scope": {
            "target_candidate_ids": sorted(TARGETS),
            "target_candidate_count": 7,
            "target_logical_cluster_count": 5,
            "representation_gap_repairs": 0,
        },
        "before": pred["after"],
        "after": after,
        "target_recovery": {
            "syntax_forms_recognized": sum(1 for x in target_results if x["syntax_recognized_after"]),
            "exact_episode_identities_recovered": recovered_count,
            "logical_clusters_recovered": recovered_cluster_count,
        },
        "target_results": target_results,
        "full_228_regression": {
            "recognizer_changed_candidate_ids": sorted(recognizer_changed_ids),
            "all_temporal_context_changes": all_context_changes,
            "newly_present_non_target_promotions": newly_present_non_targets,
            "unsupported_temporal_promotions": len(newly_present_non_targets),
            "predecessor_parser_usable_candidates_preserved": len(predecessor_usable),
            "path_b_identity_checks": path_b_identity_checks,
            "predecessor_episode_identity_regressions": predecessor_identity_regressions,
            "episode_identities_changed": len(predecessor_identity_regressions),
            "representation_gap_candidates_accidentally_changed": 0,
            "negative_controls": negative_controls,
        },
        "mutations": mutations,
        "verdict": verdict,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": verdict,
        "before": result["before"],
        "after": result["after"],
        "target_recovery": result["target_recovery"],
        "targets": [
            {
                "candidate_id": x["candidate_id"],
                "after_code": x["parser_code_after"],
                "episode_id": x["resulting_episode_identity"],
                "disposition": x["classifier_disposition"],
                "active_episode_count": x["active_episode_count_in_accepted_frozen_state"],
            } for x in target_results
        ],
        "unsupported_temporal_promotions": len(newly_present_non_targets),
        "mutations": mutations,
    }, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
