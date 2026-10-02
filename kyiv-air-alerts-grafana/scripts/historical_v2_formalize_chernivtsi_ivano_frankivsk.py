#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
sys.dont_write_bytecode = True
from copy import deepcopy
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
APP_ROOT = SCRIPT_DIR.parent
REPO_ROOT = APP_ROOT.parent
sys.path.insert(0, str(SCRIPT_DIR))

import monitor_explosion_candidates as monitor

CITY_SET = ("chernivtsi", "ivano_frankivsk")
EXPECTED_CANONICAL_COUNTS = {"chernivtsi": 113, "ivano_frankivsk": 103}
METHODOLOGY_VERSION = "historical-attack-event-air-defense-action-v2"
NORMALIZATION_VERSION = "historical-attack-event-observation-v2"
COMMON_BASE = "fb563dc410fe6614263bdc8d4eb55025a987e950"
PROOF_BRANCH = "historical-v2-formalization-chernivtsi-ivano-frankivsk-proof-2026-10-02"
ARTIFACT_REL = Path("research/historical_v2_formalization_chernivtsi_ivano_frankivsk_proof_2026-10-02.json")
ARTIFACT_PATH = REPO_ROOT / ARTIFACT_REL
BRIDGE_PATH = APP_ROOT / "data/ukrainealarm_bridge.json"
CLASSIFIER_PATH = APP_ROOT / "scripts/monitor_explosion_candidates.py"
CONTAINER_KEYS = (
    "evidence", "records", "items", "results", "candidates", "observations",
    "events", "findings", "articles", "posts", "sources",
)
CONTENT_KEYS = (
    "title", "headline", "snippet", "summary", "description", "text",
    "content", "excerpt", "quote", "message", "body",
)
URL_KEYS = ("url", "link", "source_url", "article_url", "message_url", "canonical_url")
TIME_KEYS = (
    "published_at", "publication_time", "published", "timestamp", "datetime",
    "date_time", "source_time", "created_at", "event_time",
)
TARGET_KEYS = ("matched_episode_id", "target_episode_id", "episode_id", "alert_episode_id")
EVENT_TIME_KEYS = ("event_time", "occurred_at", "event_timestamp", "attack_time")
ALERT_START_KEYS = ("alert_start", "episode_start", "start")
ALERT_END_KEYS = ("alert_end", "episode_end", "end")
SOURCE_ID_KEYS = (
    "evidence_id", "candidate_id", "source_id", "message_id", "article_id",
    "record_id", "id",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def scalar(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float)):
        text = str(value).strip()
        return text or None
    return None


def first_scalar(row: dict, keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = scalar(row.get(key))
        if value:
            return value
    return None


def nested_source_dict(row: dict) -> dict:
    source = row.get("source")
    return source if isinstance(source, dict) else {}


def source_identity(row: dict) -> str | None:
    direct = first_scalar(row, SOURCE_ID_KEYS)
    if direct:
        return direct
    src = nested_source_dict(row)
    nested = first_scalar(src, SOURCE_ID_KEYS + ("slug", "handle", "name"))
    if nested:
        return nested
    return first_scalar(row, URL_KEYS)


def source_name(row: dict) -> str | None:
    value = row.get("source")
    if isinstance(value, str) and value.strip():
        return value.strip()
    src = nested_source_dict(row)
    return first_scalar(src, ("name", "label", "type", "publisher", "channel", "handle")) or first_scalar(
        row, ("source_name", "outlet", "channel", "provider")
    )


def publisher_name(row: dict) -> str | None:
    value = row.get("publisher")
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        nested = first_scalar(value, ("name", "label", "title", "handle"))
        if nested:
            return nested
    src = nested_source_dict(row)
    return first_scalar(src, ("publisher", "name", "label")) or first_scalar(
        row, ("outlet", "channel", "provider")
    )


def source_url(row: dict) -> str | None:
    direct = first_scalar(row, URL_KEYS)
    if direct:
        return direct
    src = nested_source_dict(row)
    return first_scalar(src, URL_KEYS)


def textual_content(row: dict) -> tuple[str | None, str | None]:
    title = first_scalar(row, ("title", "headline"))
    snippet = first_scalar(row, ("snippet", "summary", "description", "text", "content", "excerpt", "quote", "message", "body"))
    if not title and snippet:
        title = snippet[:500]
    if title and not snippet:
        snippet = title
    return title, snippet


def has_record_payload(row: dict) -> bool:
    if any(scalar(row.get(key)) for key in CONTENT_KEYS + URL_KEYS + TIME_KEYS + SOURCE_ID_KEYS):
        return True
    if isinstance(row.get("review_provenance"), dict):
        return True
    src = nested_source_dict(row)
    return bool(src and any(scalar(src.get(key)) for key in URL_KEYS + SOURCE_ID_KEYS + ("name", "handle", "publisher")))


def inherited_context(row: dict, parent: dict) -> dict:
    ctx = dict(parent)
    for key in TARGET_KEYS + EVENT_TIME_KEYS + ALERT_START_KEYS + ALERT_END_KEYS + ("city_key", "city"):
        if key in row and row.get(key) not in (None, "", [], {}):
            ctx[key] = deepcopy(row.get(key))
    return ctx


def extract_records(payload: Any) -> list[dict]:
    out: list[dict] = []

    def walk(node: Any, path: str, context: dict) -> None:
        if isinstance(node, list):
            for idx, child in enumerate(node):
                walk(child, f"{path}[{idx}]", context)
            return
        if not isinstance(node, dict):
            return

        ctx = inherited_context(node, context)
        child_keys = [key for key in CONTAINER_KEYS if isinstance(node.get(key), list)]

        direct_payload = has_record_payload(node)
        wrapper_only = bool(child_keys) and not any(
            scalar(node.get(key))
            for key in CONTENT_KEYS + URL_KEYS + TIME_KEYS + SOURCE_ID_KEYS
        ) and not isinstance(node.get("review_provenance"), dict)

        if direct_payload and not wrapper_only:
            merged = deepcopy(ctx)
            merged.update(deepcopy(node))
            merged["_json_path"] = path
            out.append(merged)

        for key in child_keys:
            for idx, child in enumerate(node.get(key) or []):
                if isinstance(child, dict):
                    child_context = dict(ctx)
                    for carry in TARGET_KEYS + EVENT_TIME_KEYS + ALERT_START_KEYS + ALERT_END_KEYS + ("city_key", "city"):
                        if carry in node and node.get(carry) not in (None, "", [], {}):
                            child_context[carry] = deepcopy(node.get(carry))
                    walk(child, f"{path}.{key}[{idx}]", child_context)
                else:
                    walk(child, f"{path}.{key}[{idx}]", ctx)

        if not child_keys and not direct_payload:
            # Preserve structurally unknown leaf dictionaries as explicit unresolved records.
            if node:
                merged = deepcopy(ctx)
                merged.update(deepcopy(node))
                merged["_json_path"] = path
                merged["_unrecognized_leaf"] = True
                out.append(merged)

    walk(payload, "$", {})
    return out


def canonical_episodes(city_key: str) -> list[dict]:
    bridge = load_json(BRIDGE_PATH)
    rows: dict[str, dict] = {}
    for raw in bridge.get("events", []):
        if not isinstance(raw, dict) or str(raw.get("city_key") or "") != city_key:
            continue
        start = monitor.parse_dt(raw.get("start"))
        end = monitor.parse_dt(raw.get("end"))
        if not start or not end or end <= start:
            continue
        ep = monitor.make_episode(city_key, start, end)
        ep["alert_source"] = "ukrainealarm_bridge_cached"
        rows[ep["episode_id"]] = ep
    return sorted(rows.values(), key=lambda ep: (ep["alert_start"], ep["alert_end"], ep["episode_id"]))


def normalize_observation(city_key: str, raw: dict, ordinal: int) -> dict:
    title, snippet = textual_content(raw)
    url = source_url(raw)
    src_name = source_name(raw)
    publisher = publisher_name(raw)
    published = first_scalar(raw, TIME_KEYS[:-1])
    review_provenance = raw.get("review_provenance") if isinstance(raw.get("review_provenance"), dict) else None

    stable_source = source_identity(raw)
    evidence_id = stable_source or f"{city_key}:{ordinal}:{stable_hash(raw)[:20]}"
    candidate_seed = {
        "city_key": city_key,
        "evidence_id": evidence_id,
        "url": url,
        "title": title,
        "json_path": raw.get("_json_path"),
    }
    candidate_id = first_scalar(raw, ("candidate_id",)) or stable_hash(candidate_seed)[:24]

    normalized = {
        "candidate_id": candidate_id,
        "evidence_id": evidence_id,
        "city_key": city_key,
        "city": monitor.CITY_CONFIG[city_key]["label"],
        "source": src_name or "",
        "publisher": publisher or "",
        "publisher_url": first_scalar(raw, ("publisher_url",)),
        "url": url or "",
        "title": title or "",
        "published_at": published,
        "snippet": snippet or "",
        "discovery_basis": scalar(raw.get("discovery_basis")),
        "resolved_url": scalar(raw.get("resolved_url")),
        "matched_text_excerpt": scalar(raw.get("matched_text_excerpt")),
        "_json_path": raw.get("_json_path"),
        "_raw_target_episode_id": first_scalar(raw, TARGET_KEYS),
        "_raw_event_time": first_scalar(raw, EVENT_TIME_KEYS),
        "_raw_alert_start": first_scalar(raw, ALERT_START_KEYS),
        "_raw_alert_end": first_scalar(raw, ALERT_END_KEYS),
        "_unrecognized_leaf": bool(raw.get("_unrecognized_leaf")),
    }
    if review_provenance is not None:
        normalized["review_provenance"] = deepcopy(review_provenance)
    if normalized["_raw_target_episode_id"]:
        normalized["matched_episode_id"] = normalized["_raw_target_episode_id"]
    return normalized


def provenance_ok(obs: dict) -> bool:
    return bool(
        obs.get("url")
        or obs.get("source")
        or obs.get("publisher")
        or (obs.get("review_provenance") and isinstance(obs.get("review_provenance"), dict))
    )


def direct_binding(obs: dict, episodes: list[dict]) -> tuple[list[str], str | None]:
    by_id = {str(ep["episode_id"]): ep for ep in episodes}
    raw_target = str(obs.get("_raw_target_episode_id") or "")
    if raw_target:
        if raw_target in by_id:
            return [raw_target], "committed_episode_id"
        return [], "committed_episode_id_not_in_canonical_universe"

    alert_start = monitor.parse_dt(obs.get("_raw_alert_start"))
    alert_end = monitor.parse_dt(obs.get("_raw_alert_end"))
    if alert_start and alert_end and alert_end > alert_start:
        probe = monitor.make_episode(obs["city_key"], alert_start, alert_end)
        matches = [
            str(ep["episode_id"])
            for ep in episodes
            if monitor.same_episode_representation(probe, ep)
        ]
        support = monitor.logical_episode_support([by_id[x] for x in matches if x in by_id])
        if support.get("episode_specific"):
            return list(support.get("supported_episode_ids") or []), "committed_alert_window"

    event_time = monitor.parse_dt(obs.get("_raw_event_time"))
    if event_time:
        active = monitor.exact_active_episodes_at(event_time, episodes)
        support = monitor.logical_episode_support(active)
        if support.get("episode_specific"):
            return list(support.get("supported_episode_ids") or []), "committed_event_time"
        if active:
            return list(support.get("supported_episode_ids") or []), "committed_event_time_ambiguous"
    return [], None


def candidate_ids_from_matching(matching: dict) -> list[str]:
    return sorted({str(x) for x in (matching.get("matched_episode_ids") or []) if str(x)})


def compact_unresolved(obs: dict, reason: str, candidate_episode_ids: list[str]) -> dict:
    return {
        "evidence_id": str(obs.get("evidence_id") or obs.get("candidate_id") or ""),
        "event_time": obs.get("_raw_event_time"),
        "reason": reason,
        "candidate_episode_ids": sorted(set(candidate_episode_ids)),
    }


def git_changed_paths() -> list[str]:
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    paths = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def city_formalization(city_key: str) -> dict:
    evidence_path = APP_ROOT / "data/explosion_research" / city_key / "final_evidence.json"
    if not evidence_path.exists():
        return {
            "city_key": city_key,
            "verdict": "CITY V2 FORMALIZATION BLOCKED",
            "blocker": "FINAL_EVIDENCE_MISSING",
            "canonical_episodes": 0,
            "evidence_records_read": 0,
            "normalized_observations": 0,
            "bound_observations": 0,
            "unbound_observations": 0,
            "malformed_provenance": 0,
            "strict_positives": 0,
            "sensitivity_positives": 0,
            "no_confirmed_event": 0,
            "needs_review": 0,
            "missing_targets": 0,
            "duplicate_targets": 0,
            "extra_targets": 0,
            "unresolved_evidence_bindings": 0,
            "unresolved_items": [],
            "target_state_sha256": None,
        }

    episodes = canonical_episodes(city_key)
    canonical_ids = [str(ep["episode_id"]) for ep in episodes]
    canonical_set = set(canonical_ids)
    expected_count = EXPECTED_CANONICAL_COUNTS[city_key]

    payload = load_json(evidence_path)
    raw_records = extract_records(payload)
    observations = [normalize_observation(city_key, raw, idx + 1) for idx, raw in enumerate(raw_records)]

    target_states = {episode_id: "NO_CONFIRMED_EVENT" for episode_id in canonical_ids}
    target_touch_count = {episode_id: 0 for episode_id in canonical_ids}
    unresolved: list[dict] = []
    malformed_provenance = 0
    bound_observations = 0
    unbound_observations = 0
    classifier_exceptions: list[str] = []
    mechanically_unrepresentable = 0

    state_rank = {
        "NO_CONFIRMED_EVENT": 0,
        "NEEDS_REVIEW": 1,
        "SENSITIVITY_EVENT_POSITIVE": 2,
        "STRICT_EVENT_POSITIVE": 3,
    }

    def promote(episode_id: str, state: str) -> None:
        if episode_id not in target_states:
            return
        if state_rank[state] > state_rank[target_states[episode_id]]:
            target_states[episode_id] = state
        target_touch_count[episode_id] += 1

    for obs in observations:
        if obs.get("_unrecognized_leaf") and not (obs.get("title") or obs.get("snippet") or obs.get("review_provenance")):
            mechanically_unrepresentable += 1
            unbound_observations += 1
            unresolved.append(compact_unresolved(obs, "unrecognized_leaf_without_classifiable_content", []))
            continue

        prov_ok = provenance_ok(obs)
        if not prov_ok:
            malformed_provenance += 1

        direct_ids, direct_reason = direct_binding(obs, episodes)
        try:
            matching = monitor.match_candidate_to_episodes(obs, episodes)
            decision = monitor.classify_candidate(obs, city_key, episodes, matching)
        except Exception as exc:
            classifier_exceptions.append(f"{obs['evidence_id']}:{type(exc).__name__}:{exc}")
            unbound_observations += 1
            unresolved.append(compact_unresolved(obs, f"classifier_exception:{type(exc).__name__}", direct_ids))
            continue

        proposed = str(decision.get("proposed_outcome") or "needs_review")
        positive_id = str(decision.get("proposed_matched_episode_id") or "")
        matching_ids = candidate_ids_from_matching(matching)

        association_ids: list[str] = []
        association_reason = None
        if positive_id and positive_id in canonical_set:
            association_ids = [positive_id]
            association_reason = "classifier_positive_binding"
        elif direct_ids:
            association_ids = [x for x in direct_ids if x in canonical_set]
            association_reason = direct_reason
        elif matching.get("outcome") == "unique_match" and matching.get("matched_episode_id") in canonical_set:
            association_ids = [str(matching.get("matched_episode_id"))]
            association_reason = "publication_unique_match"
        elif proposed == "needs_review" and matching_ids:
            association_ids = [x for x in matching_ids if x in canonical_set]
            association_reason = "review_candidate_episode_set"

        if association_ids:
            bound_observations += 1
        else:
            unbound_observations += 1

        if proposed == "approved_strict" and positive_id in canonical_set:
            if prov_ok:
                promote(positive_id, "STRICT_EVENT_POSITIVE")
            else:
                promote(positive_id, "NEEDS_REVIEW")
                unresolved.append(compact_unresolved(obs, "strict_semantics_but_malformed_provenance", [positive_id]))
        elif proposed == "approved_sensitivity" and positive_id in canonical_set:
            if prov_ok:
                promote(positive_id, "SENSITIVITY_EVENT_POSITIVE")
            else:
                promote(positive_id, "NEEDS_REVIEW")
                unresolved.append(compact_unresolved(obs, "sensitivity_semantics_but_malformed_provenance", [positive_id]))
        elif proposed == "needs_review":
            if association_ids:
                for episode_id in association_ids:
                    promote(episode_id, "NEEDS_REVIEW")
                reason = association_reason or "semantic_review_required"
                unresolved.append(compact_unresolved(obs, reason, association_ids))
            else:
                reason = direct_reason or str(matching.get("reason") or "unresolved_evidence_binding")
                unresolved.append(compact_unresolved(obs, reason, matching_ids))
        elif proposed == "rejected":
            # Rejected evidence is represented and classified, but does not alter target state.
            pass
        else:
            unresolved.append(compact_unresolved(obs, f"unknown_classifier_outcome:{proposed}", association_ids or matching_ids))

    target_rows = [
        {"episode_id": episode_id, "state": target_states[episode_id]}
        for episode_id in sorted(canonical_ids)
    ]
    target_sha = sha256_bytes(stable_json(target_rows).encode("utf-8"))

    missing_targets = len(canonical_set - set(target_states))
    extra_targets = len(set(target_states) - canonical_set)
    duplicate_targets = len(target_states) - len(set(target_states))
    counts = {state: 0 for state in state_rank}
    for state in target_states.values():
        counts[state] += 1

    blockers = []
    if len(episodes) != expected_count:
        blockers.append(f"CANONICAL_COUNT_MISMATCH:{len(episodes)}!={expected_count}")
    if not raw_records:
        blockers.append("NO_EVIDENCE_RECORDS_EXTRACTED")
    if len(observations) != len(raw_records):
        blockers.append("NORMALIZATION_RECORD_LOSS")
    if mechanically_unrepresentable:
        blockers.append(f"MECHANICALLY_UNREPRESENTABLE_EVIDENCE:{mechanically_unrepresentable}")
    if classifier_exceptions:
        blockers.append(f"CLASSIFIER_EXCEPTIONS:{len(classifier_exceptions)}")
    if missing_targets or duplicate_targets or extra_targets:
        blockers.append("TARGET_COVERAGE_INVARIANT_FAILED")

    verdict = "CITY V2 FORMALIZATION BLOCKED" if blockers else "CITY V2 FORMALIZATION PROVEN"
    return {
        "city_key": city_key,
        "verdict": verdict,
        "blocker": ";".join(blockers) if blockers else None,
        "canonical_episodes": len(episodes),
        "evidence_records_read": len(raw_records),
        "normalized_observations": len(observations),
        "bound_observations": bound_observations,
        "unbound_observations": unbound_observations,
        "malformed_provenance": malformed_provenance,
        "strict_positives": counts["STRICT_EVENT_POSITIVE"],
        "sensitivity_positives": counts["SENSITIVITY_EVENT_POSITIVE"],
        "no_confirmed_event": counts["NO_CONFIRMED_EVENT"],
        "needs_review": counts["NEEDS_REVIEW"],
        "missing_targets": missing_targets,
        "duplicate_targets": duplicate_targets,
        "extra_targets": extra_targets,
        "unresolved_evidence_bindings": len(unresolved),
        "unresolved_items": unresolved,
        "target_state_sha256": target_sha,
        "mechanically_unrepresentable": mechanically_unrepresentable,
        "classifier_exceptions": classifier_exceptions[:10],
    }


def main() -> int:
    tested_head = os.environ.get("GITHUB_SHA") or subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()

    evidence_paths = {
        city: APP_ROOT / "data/explosion_research" / city / "final_evidence.json"
        for city in CITY_SET
    }
    guarded_inputs = {
        str(BRIDGE_PATH.relative_to(REPO_ROOT)): sha256_file(BRIDGE_PATH),
        str(CLASSIFIER_PATH.relative_to(REPO_ROOT)): sha256_file(CLASSIFIER_PATH),
    }
    for city, path in evidence_paths.items():
        if path.exists():
            guarded_inputs[str(path.relative_to(REPO_ROOT))] = sha256_file(path)

    dirty_before = git_changed_paths()
    if dirty_before:
        raise SystemExit(f"DIRTY_CHECKOUT_BEFORE_PROCESSING:{dirty_before}")

    monitor.self_test()

    city_results = [city_formalization(city) for city in CITY_SET]

    guarded_after = {
        rel: sha256_file(REPO_ROOT / rel)
        for rel in guarded_inputs
    }
    unchanged = guarded_inputs == guarded_after

    changed_before_artifact = git_changed_paths()
    source_mutations = [path for path in changed_before_artifact if path != str(ARTIFACT_REL)]
    mutation_guard_pass = unchanged and not source_mutations

    overall_blockers = []
    if not mutation_guard_pass:
        overall_blockers.append("AUTHORITATIVE_INPUT_MUTATION_GUARD_FAILED")
    if any(row["verdict"].endswith("BLOCKED") for row in city_results):
        overall_blockers.append("ONE_OR_MORE_CITIES_BLOCKED")

    artifact = {
        "schema_version": 1,
        "proof": "historical-v2-formalization-chernivtsi-ivano-frankivsk-proof-2026-10-02",
        "mode": "FREEZE_EXISTING_EVIDENCE",
        "city_set": list(CITY_SET),
        "common_base": COMMON_BASE,
        "tested_head": tested_head,
        "methodology_version": METHODOLOGY_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "overall_verdict": "BLOCKED" if overall_blockers else "PROVEN",
        "overall_blocker": ";".join(overall_blockers) if overall_blockers else None,
        "cities": {row["city_key"]: row for row in city_results},
        "mutation_guards": {
            "guarded_input_sha256_before": guarded_inputs,
            "guarded_input_sha256_after": guarded_after,
            "authoritative_inputs_unchanged": unchanged,
            "unexpected_changed_paths_before_artifact": source_mutations,
            "scope_allowlist": "PASS" if mutation_guard_pass else "FAIL",
            "db_neon": "UNTOUCHED",
            "deployment": "NO",
            "production_dashboard_data": "UNTOUCHED",
            "historical_evidence_mutations": 0 if mutation_guard_pass else None,
        },
        "public_web_research": "NO",
        "source_discovery": "NO",
        "authoritative_evidence_mutations": 0 if mutation_guard_pass else None,
        "incorporation": "NO",
    }

    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    changed_after_artifact = git_changed_paths()
    unexpected = [path for path in changed_after_artifact if path != str(ARTIFACT_REL)]
    if unexpected:
        raise SystemExit(f"UNEXPECTED_MUTATIONS_AFTER_ARTIFACT:{unexpected}")

    compact = {
        city: {
            "verdict": row["verdict"],
            "canonical": row["canonical_episodes"],
            "evidence": row["evidence_records_read"],
            "normalized": row["normalized_observations"],
            "bound": row["bound_observations"],
            "unbound": row["unbound_observations"],
            "strict": row["strict_positives"],
            "sensitivity": row["sensitivity_positives"],
            "no_confirmed": row["no_confirmed_event"],
            "needs_review": row["needs_review"],
            "unresolved": row["unresolved_evidence_bindings"],
            "sha": row["target_state_sha256"],
            "blocker": row["blocker"],
        }
        for city, row in artifact["cities"].items()
    }
    print(json.dumps({"overall": artifact["overall_verdict"], "cities": compact}, ensure_ascii=False, sort_keys=True))
    return 0 if artifact["overall_verdict"] == "PROVEN" else 2


if __name__ == "__main__":
    raise SystemExit(main())
