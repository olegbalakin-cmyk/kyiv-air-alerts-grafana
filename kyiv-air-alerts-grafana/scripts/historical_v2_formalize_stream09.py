#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
CITY_SET = ("vinnytsia", "zhytomyr")
EXPECTED = {"vinnytsia": 362, "zhytomyr": 685}
COMMON_BASE = "fb563dc410fe6614263bdc8d4eb55025a987e950"
METHODOLOGY = "historical-attack-event-air-defense-action-v2"
ARTIFACT = REPO_ROOT / "research" / "historical_v2_formalization_vinnytsia_zhytomyr_proof_2026-10-02.json"
MONITOR = ROOT / "scripts" / "monitor_explosion_candidates.py"
HEX24 = re.compile(r"^[0-9a-f]{24}$")

GENERIC_CONTAINER_KEYS = {
    "cities","episodes","alert_episodes","alerts","records","items","data","canonical",
    "episode_states","source_slices","targets","rows","events","results","payload"
}
ID_KEYS = ("episode_id","alert_episode_id","target_episode_id","id")
CITY_KEYS = ("city_key","city","key")
START_KEYS = ("start","started_at","start_at","start_time","episode_start","alert_start","start_utc","from")
END_KEYS = ("end","ended_at","end_at","end_time","episode_end","alert_end","end_utc","to")

def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True).strip()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def norm_city(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_")

def stable_id(row: dict[str, Any]) -> str | None:
    for k in ID_KEYS:
        v = row.get(k)
        if isinstance(v, str) and HEX24.fullmatch(v.lower()):
            return v.lower()
    return None

def first_str(row: dict[str, Any], keys: tuple[str,...]) -> str | None:
    for k in keys:
        v = row.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return None

def row_city(row: dict[str, Any]) -> str | None:
    for k in CITY_KEYS:
        if k in row and row.get(k) is not None:
            return norm_city(row.get(k))
    return None

def candidate_json_paths() -> list[Path]:
    out: list[Path] = []
    for base in (ROOT / "data", REPO_ROOT / "research"):
        if not base.exists():
            continue
        for p in base.rglob("*.json"):
            rel = p.relative_to(REPO_ROOT).as_posix()
            if "/explosion_research/" in rel:
                if not any(f"/explosion_research/{c}/" in rel for c in CITY_SET):
                    continue
            low = p.name.lower()
            pathlow = rel.lower()
            if any(t in low or t in pathlow for t in ("alert","episode","canonical","bridge","source","baseline","seed")):
                out.append(p)
    return sorted(set(out))

def collect_episode_rows(obj: Any, city: str, default_city: str | None = None) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    def walk(node: Any, inherited_city: str | None = default_city, depth: int = 0) -> None:
        if depth > 14:
            return
        if isinstance(node, dict):
            explicit_city = row_city(node)
            if explicit_city and explicit_city not in CITY_SET:
                return
            here_city = explicit_city or inherited_city
            eid = stable_id(node)
            if eid and here_city == city:
                found.setdefault(eid, node)
            for k, v in node.items():
                nk = norm_city(k)
                if nk in CITY_SET:
                    if nk == city:
                        walk(v, city, depth + 1)
                    continue
                if nk in GENERIC_CONTAINER_KEYS or inherited_city == city or explicit_city == city:
                    walk(v, here_city, depth + 1)
                elif isinstance(v, (dict, list)) and depth < 3:
                    walk(v, here_city, depth + 1)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, dict):
                    ec = row_city(item)
                    if ec and ec not in CITY_SET:
                        continue
                walk(item, inherited_city, depth + 1)
    walk(obj)
    return found

def discover_canonical(city: str) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    expected = EXPECTED[city]
    exact: list[tuple[str, dict[str, dict[str, Any]]]] = []
    union: dict[str, dict[str, Any]] = {}
    diagnostics: list[dict[str, Any]] = []
    for p in candidate_json_paths():
        rel = p.relative_to(REPO_ROOT).as_posix()
        default_city = city if f"/{city}/" in rel.lower() or city in p.name.lower() else None
        try:
            obj = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        rows = collect_episode_rows(obj, city, default_city=default_city)
        if not rows:
            continue
        diagnostics.append({"path": rel, "episode_ids": len(rows)})
        for eid, row in rows.items():
            union.setdefault(eid, row)
        if len(rows) == expected:
            exact.append((rel, rows))
    if exact:
        base_ids = set(exact[0][1])
        conflicts = [path for path, rows in exact[1:] if set(rows) != base_ids]
        if conflicts:
            raise RuntimeError(f"{city}: conflicting exact canonical episode sets: {conflicts}")
        return exact[0][1], diagnostics
    if len(union) == expected:
        return union, diagnostics
    raise RuntimeError(f"{city}: canonical discovery expected {expected}, found union={len(union)}, candidates={diagnostics}")

def event_id(ev: dict[str, Any], index: int, bucket: str) -> str:
    for k in ("event_id","candidate_id","evidence_id","id"):
        v = ev.get(k)
        if v is not None and str(v).strip():
            return str(v)
    raw = json.dumps(ev, ensure_ascii=False, sort_keys=True, separators=(",",":"))
    return hashlib.sha256((bucket + ":" + str(index) + ":" + raw).encode()).hexdigest()[:24]

def source_identifier(ev: dict[str, Any]) -> str | None:
    for k in ("source_url","url","source_url_2"):
        v = ev.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    evidence = ev.get("evidence")
    if isinstance(evidence, dict):
        for k in ("source_url","url"):
            v = evidence.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None

def episode_ref(ev: dict[str, Any]) -> str | None:
    for k in ("matched_episode_id","episode_id","target_episode_id"):
        v = ev.get(k)
        if isinstance(v, str) and HEX24.fullmatch(v.lower()):
            return v.lower()
    return None

def event_time(ev: dict[str, Any]) -> str | None:
    for k in ("event_time","published_at","timestamp","time","local_date","date","matched_episode_start"):
        v = ev.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    raw = ev.get("raw_record")
    if isinstance(raw, dict):
        for k in ("event_time","published_at","timestamp","time","date"):
            v = raw.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None

def canonical_time_match(ev: dict[str, Any], canonical: dict[str, dict[str, Any]]) -> tuple[str | None, list[str]]:
    et = event_time(ev)
    if not et:
        return None, []
    candidates: list[str] = []
    date_prefix = et[:10]
    for eid, row in canonical.items():
        vals = [first_str(row, START_KEYS), first_str(row, END_KEYS)]
        if any(v and (et in v or v in et) for v in vals):
            candidates.append(eid)
            continue
        if len(et) == 10 and any(v and v.startswith(date_prefix) for v in vals):
            candidates.append(eid)
    if len(candidates) == 1:
        return candidates[0], candidates
    return None, candidates[:20]

def load_monitor():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("monitor_explosion_candidates_stream09", MONITOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import monitor implementation")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    required = [
        "strict_explosion_evidence","air_military_context_evidence",
        "same_attack_context_evidence","match_candidate_to_episodes",
        "classify_candidate","temporal_binding_evidence"
    ]
    missing = [name for name in required if not hasattr(mod, name)]
    if missing:
        raise RuntimeError(f"classifier API missing: {missing}")
    return mod

def semantic_guard(mod: Any, city: str, ev: dict[str, Any]) -> dict[str, Any]:
    text_parts: list[str] = []
    def pull(x: Any) -> None:
        if isinstance(x, str):
            text_parts.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                pull(v)
        elif isinstance(x, list):
            for v in x:
                pull(v)
    pull(ev.get("evidence"))
    pull(ev.get("decision_basis"))
    pull(ev.get("basis"))
    pull(ev.get("raw_record"))
    row = {
        "city_key": city,
        "title": "",
        "summary": " ".join(text_parts),
        "content": " ".join(text_parts),
        "source_url": source_identifier(ev) or "",
        "published_at": event_time(ev) or "",
    }
    strict = mod.strict_explosion_evidence(city, row)
    air = mod.air_military_context_evidence(row)
    same = mod.same_attack_context_evidence(city, row, strict, air)
    return {
        "strict_signal_type": type(strict).__name__,
        "air_signal_type": type(air).__name__,
        "same_attack_signal_type": type(same).__name__,
    }

def formalize_city(city: str, mod: Any) -> dict[str, Any]:
    canonical, diagnostics = discover_canonical(city)
    expected = EXPECTED[city]
    if len(canonical) != expected:
        raise RuntimeError(f"{city}: canonical count mismatch {len(canonical)} != {expected}")

    evidence_path = ROOT / "data" / "explosion_research" / city / "final_evidence.json"
    evdoc = json.loads(evidence_path.read_text(encoding="utf-8"))
    buckets = {
        "strict": list(evdoc.get("strict_events") or []),
        "sensitivity": list(evdoc.get("sensitivity_only_events") or []),
        "review": list(evdoc.get("review_events") or []),
    }
    excluded = list(evdoc.get("excluded_events") or [])
    states = {eid: "NO_CONFIRMED_EVENT" for eid in sorted(canonical)}

    normalized = 0
    bound = 0
    unbound = 0
    malformed = 0
    unresolved: list[dict[str, Any]] = []
    positive_unbound = 0
    semantic_guard_checked = 0

    precedence = {
        "NO_CONFIRMED_EVENT": 0,
        "NEEDS_REVIEW": 1,
        "SENSITIVITY_EVENT_POSITIVE": 2,
        "STRICT_EVENT_POSITIVE": 3,
    }
    bucket_state = {
        "strict": "STRICT_EVENT_POSITIVE",
        "sensitivity": "SENSITIVITY_EVENT_POSITIVE",
        "review": "NEEDS_REVIEW",
    }

    for bucket, events in buckets.items():
        for idx, ev0 in enumerate(events):
            if not isinstance(ev0, dict):
                ev = {"raw_value": ev0}
            else:
                ev = ev0
            normalized += 1
            sid = source_identifier(ev)
            if not sid:
                malformed += 1
            eid = episode_ref(ev)
            candidates: list[str] = []
            if eid and eid in canonical:
                bind = eid
                candidates = [eid]
            else:
                bind, candidates = canonical_time_match(ev, canonical)
            if bind:
                bound += 1
                target_state = bucket_state[bucket]
                if precedence[target_state] > precedence[states[bind]]:
                    states[bind] = target_state
            else:
                unbound += 1
                if bucket in ("strict","sensitivity"):
                    positive_unbound += 1
                unresolved.append({
                    "evidence_id": event_id(ev, idx, bucket),
                    "stable_source_identifier": sid,
                    "event_time": event_time(ev),
                    "reason": "EPISODE_REFERENCE_NOT_IN_CANONICAL_AND_NO_UNIQUE_TIME_BINDING" if eid else "NO_UNIQUE_EPISODE_BINDING",
                    "candidate_episode_ids": candidates,
                    "bucket": bucket,
                })
            try:
                semantic_guard(mod, city, ev)
                semantic_guard_checked += 1
            except Exception as exc:
                unresolved.append({
                    "evidence_id": event_id(ev, idx, bucket),
                    "stable_source_identifier": sid,
                    "event_time": event_time(ev),
                    "reason": "CURRENT_CLASSIFIER_SEMANTIC_GUARD_EXCEPTION:" + type(exc).__name__,
                    "candidate_episode_ids": [bind] if bind else candidates,
                    "bucket": bucket,
                })

    target_rows = [{"episode_id": eid, "state": states[eid]} for eid in sorted(states)]
    target_sha = hashlib.sha256(
        json.dumps(target_rows, ensure_ascii=False, sort_keys=True, separators=(",",":")).encode()
    ).hexdigest()

    counts = {
        "canonical_episodes": len(canonical),
        "evidence_records_read": sum(len(v) for v in buckets.values()),
        "normalized_observations": normalized,
        "bound_observations": bound,
        "unbound_observations": unbound,
        "malformed_provenance": malformed,
        "strict_positives": sum(v == "STRICT_EVENT_POSITIVE" for v in states.values()),
        "sensitivity_positives": sum(v == "SENSITIVITY_EVENT_POSITIVE" for v in states.values()),
        "no_confirmed_event": sum(v == "NO_CONFIRMED_EVENT" for v in states.values()),
        "needs_review": sum(v == "NEEDS_REVIEW" for v in states.values()),
        "missing_targets": expected - len(states),
        "duplicate_targets": 0,
        "extra_targets": max(0, len(states) - expected),
        "unresolved_evidence_bindings": len(unresolved),
        "excluded_research_records_preserved": len(excluded),
        "semantic_guard_checked": semantic_guard_checked,
    }
    blocker = None
    if counts["missing_targets"] or counts["duplicate_targets"] or counts["extra_targets"]:
        blocker = "TARGET_UNIVERSE_INVARIANT"
    elif positive_unbound:
        blocker = "COUNTED_POSITIVE_EVIDENCE_UNBOUND"
    elif malformed:
        blocker = "MALFORMED_PROVENANCE"
    elif any(str(x.get("reason","")).startswith("CURRENT_CLASSIFIER_SEMANTIC_GUARD_EXCEPTION") for x in unresolved):
        blocker = "CURRENT_CLASSIFIER_SEMANTIC_GUARD_EXCEPTION"

    return {
        "verdict": "CITY V2 FORMALIZATION BLOCKED" if blocker else "CITY V2 FORMALIZATION PROVEN",
        "counts": counts,
        "unresolved_items": unresolved,
        "blocker": blocker,
        "target_state_sha256": target_sha,
        "canonical_discovery": {
            "exact_expected_count": len(canonical) == expected,
            "candidate_sources": diagnostics,
        },
        "input_sha256": sha256_file(evidence_path),
    }

def main() -> int:
    git("merge-base", "--is-ancestor", COMMON_BASE, "HEAD")
    head = git("rev-parse", "HEAD")
    mod = load_monitor()

    before = {
        str((ROOT / "data" / "explosion_research" / c / "final_evidence.json").relative_to(REPO_ROOT)):
        sha256_file(ROOT / "data" / "explosion_research" / c / "final_evidence.json")
        for c in CITY_SET
    }

    cities: dict[str, Any] = {}
    fatal: str | None = None
    for city in CITY_SET:
        try:
            cities[city] = formalize_city(city, mod)
        except Exception as exc:
            cities[city] = {
                "verdict": "CITY V2 FORMALIZATION BLOCKED",
                "counts": {
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
                    "missing_targets": EXPECTED[city],
                    "duplicate_targets": 0,
                    "extra_targets": 0,
                    "unresolved_evidence_bindings": 0,
                },
                "unresolved_items": [],
                "blocker": "PIPELINE_EXCEPTION:" + type(exc).__name__ + ":" + str(exc)[:1000],
                "target_state_sha256": None,
            }
            fatal = "PIPELINE_EXCEPTION"

    after = {
        str((ROOT / "data" / "explosion_research" / c / "final_evidence.json").relative_to(REPO_ROOT)):
        sha256_file(ROOT / "data" / "explosion_research" / c / "final_evidence.json")
        for c in CITY_SET
    }
    artifact = {
        "schema_version": 2,
        "proof": "historical-v2-formalization-vinnytsia-zhytomyr-proof-2026-10-02",
        "common_base": COMMON_BASE,
        "tested_head": head,
        "city_set": list(CITY_SET),
        "mode": "FREEZE_EXISTING_EVIDENCE",
        "methodology_version": METHODOLOGY,
        "classifier_implementation_sha256": sha256_file(MONITOR),
        "cities": cities,
        "mutation_guards": {
            "assigned_evidence_sha256_before": before,
            "assigned_evidence_sha256_after": after,
            "assigned_evidence_unchanged": before == after,
            "historical_source_evidence_inputs_unchanged": before == after,
            "public_web_research": "NO",
            "source_discovery": "NO",
            "db_neon": "UNTOUCHED",
            "deploy": "NO",
            "production_dashboard_data": "UNTOUCHED",
            "authoritative_evidence_mutations": 0,
            "incorporation": "NO",
        },
        "overall_verdict": "PROVEN" if all(v.get("verdict") == "CITY V2 FORMALIZATION PROVEN" for v in cities.values()) else "BLOCKED",
    }
    ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "overall_verdict": artifact["overall_verdict"],
        "cities": {k: {"verdict": v["verdict"], "blocker": v.get("blocker")} for k,v in cities.items()}
    }, ensure_ascii=False))
    return 0 if fatal is None else 1

if __name__ == "__main__":
    raise SystemExit(main())
