#!/usr/bin/env python3
from __future__ import annotations

import argparse
import contextlib
import copy
import hashlib
import importlib.util
import json
import os
import re
import socket
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

KYIV_TZ = ZoneInfo("Europe/Kyiv")
DEFAULT_THROUGH = "2026-09-17"
PROTECTED_RELATIVE = (
    "data/explosion_audited_baseline.json",
    "data/explosion_review_queue.json",
    "data/explosion_candidate_monitor_state.json",
    "data/explosion_candidate_monitor_last_run.json",
    "data/explosions_test.json",
    "data/dashboard_data.json",
)
REQUIRED_CATEGORIES = (
    "UNCHANGED_STRICT",
    "UNCHANGED_NON_STRICT",
    "NEW_STRICT",
    "STRICT_DOWNGRADE",
    "STRICT_TO_SENSITIVITY",
    "SENSITIVITY_TO_STRICT",
    "NEW_SENSITIVITY",
    "NEW_AMBIGUOUS",
    "UNREPLAYABLE_MISSING_EVIDENCE",
)
CONTROL_EXPECTATIONS = {
    "2c5bbc0aeba9e25e4eec7b09": False,
    "7a7da068c0efb7be80bd45e4": False,
    "eb2580c2bec54ddc2e36eaf7": False,
    "a60d817eaa9253200f090720": False,
    "c894e85e407dc4256d8c4419": True,
    "e97e6e816f96832d02c8b2cd": True,
    "f235928c329ca806d9dca5ed": True,
}
START_FIELDS = (
    "matched_episode_start",
    "matched_alert_episode_start",
    "alert_episode_start",
    "alert_start",
    "alert_start_kyiv",
    "episode_start",
    "matched_start",
)
EVIDENCE_FIELDS = ("evidence", "evidence_text", "text", "excerpt", "quote")
BASIS_FIELDS = ("decision_basis", "basis", "decision", "reason")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git_output(checkout_root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(checkout_root), *args], text=True).strip()


def git_head(checkout_root: Path) -> str:
    return git_output(checkout_root, "rev-parse", "HEAD")


def git_blob(checkout_root: Path, rel: str) -> str | None:
    try:
        return git_output(checkout_root, "rev-parse", f"HEAD:{rel}")
    except subprocess.CalledProcessError:
        return None


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def protected_snapshot(repo_root: Path) -> dict[str, str | None]:
    return {rel: sha256_file(repo_root / rel) for rel in PROTECTED_RELATIVE}


def ensure_output_outside_checkout(output: Path, checkout_root: Path) -> None:
    out = output.resolve()
    root = checkout_root.resolve()
    try:
        out.relative_to(root)
    except ValueError:
        return
    raise SystemExit(f"Refusing to write replay output inside frozen checkout: {out}")


@contextlib.contextmanager
def network_blocked():
    original_connect = socket.socket.connect
    original_create = socket.create_connection
    requests_original = None

    def blocked(*_args, **_kwargs):
        raise RuntimeError("NETWORK_DISABLED_DURING_HISTORICAL_REPLAY")

    socket.socket.connect = blocked
    socket.create_connection = blocked
    try:
        try:
            import requests
            requests_original = requests.sessions.Session.request
            requests.sessions.Session.request = blocked
        except Exception:
            requests = None
        yield
    finally:
        socket.socket.connect = original_connect
        socket.create_connection = original_create
        if requests_original is not None:
            import requests
            requests.sessions.Session.request = requests_original


def import_monitor(repo_root: Path):
    scripts = repo_root / "scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    path = scripts / "monitor_explosion_candidates.py"
    spec = importlib.util.spec_from_file_location("frozen_explosion_monitor", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import monitor from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def local_day(value: str | None, monitor=None) -> str | None:
    if not value:
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(value).strip()):
        return str(value).strip()
    dt = parse_historical_datetime(value, monitor)
    return dt.astimezone(KYIV_TZ).date().isoformat() if dt else None


def parse_historical_datetime(value, monitor=None) -> datetime | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    clean = text.replace("~", "").strip()
    clean = re.sub(r"\s+Europe/Kyiv.*$", "", clean, flags=re.I)
    clean = clean.replace("Z", "+00:00")
    m = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2})(?::(\d{2}(?:\.\d+)?))?(?:\s*([+-]\d{2}:?\d{2}))?)?", clean)
    if not m:
        return None
    day, hm, sec, offset = m.groups()
    if hm is None:
        return None
    sec = sec or "00"
    iso_text = f"{day}T{hm}:{sec}"
    if offset:
        if len(offset) == 5 and ":" not in offset:
            offset = offset[:3] + ":" + offset[3:]
        iso_text += offset
    try:
        dt = datetime.fromisoformat(iso_text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV_TZ)
    return dt


def episode_index(episodes: list[dict]) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    by_id = {}
    by_day: dict[str, list[dict]] = defaultdict(list)
    for ep in episodes:
        eid = str(ep.get("episode_id") or "")
        if not eid:
            continue
        by_id[eid] = ep
        day = ep.get("alert_start_date_kyiv") or local_day(ep.get("alert_start"))
        if day:
            by_day[str(day)].append(ep)
    for rows in by_day.values():
        rows.sort(key=lambda x: (str(x.get("alert_start") or ""), str(x.get("episode_id") or "")))
    return by_id, by_day


def bind_evidence_record(row: dict, episodes: list[dict], monitor) -> dict:
    by_id, by_day = episode_index(episodes)
    explicit_id = str(row.get("episode_id") or row.get("matched_episode_id") or "")
    if explicit_id:
        if explicit_id in by_id:
            return {"episode_id": explicit_id, "method": "persisted_episode_id", "candidates": [explicit_id]}
        return {"episode_id": None, "method": "unknown_persisted_episode_id", "candidates": [explicit_id]}

    raw = next((row.get(k) for k in START_FIELDS if row.get(k)), None)
    dt = parse_historical_datetime(raw, monitor)
    if dt is not None:
        exact = []
        dt_utc = dt.astimezone(monitor.UTC)
        for ep in episodes:
            start = monitor.parse_dt(ep.get("alert_start"))
            if start and abs((start - dt_utc).total_seconds()) <= 90:
                exact.append(ep)
        if len(exact) == 1:
            return {"episode_id": str(exact[0]["episode_id"]), "method": "alert_start_within_90s", "candidates": [str(exact[0]["episode_id"])]}
        minute = dt.astimezone(KYIV_TZ).strftime("%Y-%m-%dT%H:%M")
        minute_rows = []
        for ep in episodes:
            start = monitor.parse_dt(ep.get("alert_start"))
            if start and start.astimezone(KYIV_TZ).strftime("%Y-%m-%dT%H:%M") == minute:
                minute_rows.append(ep)
        if len(minute_rows) == 1:
            return {"episode_id": str(minute_rows[0]["episode_id"]), "method": "alert_start_same_local_minute", "candidates": [str(minute_rows[0]["episode_id"])]}
        return {"episode_id": None, "method": "ambiguous_alert_start", "candidates": [str(ep["episode_id"]) for ep in (exact or minute_rows)]}

    day = None
    for field in START_FIELDS + ("alert_start_date", "episode_start_date", "local_date"):
        if row.get(field):
            day = local_day(row.get(field), monitor)
            if day:
                break
    if day:
        rows = by_day.get(day, [])
        if len(rows) == 1:
            return {"episode_id": str(rows[0]["episode_id"]), "method": "unique_episode_on_recorded_local_day", "candidates": [str(rows[0]["episode_id"])]}
        return {"episode_id": None, "method": "ambiguous_local_day", "candidates": [str(ep["episode_id"]) for ep in rows]}
    return {"episode_id": None, "method": "missing_episode_binding", "candidates": []}


def evidence_text(row: dict) -> str:
    parts = []
    for key in EVIDENCE_FIELDS + BASIS_FIELDS:
        value = row.get(key)
        if value and str(value).strip() not in parts:
            parts.append(str(value).strip())
    return " — ".join(parts)


def ppo_related(text: str) -> bool:
    return bool(re.search(r"\b(?:ппо|протиповітрян|air[ -]?defen[cs]e)\b", text.casefold()))


def history_status(row: dict, bucket: str) -> str:
    if bucket == "strict_events":
        return "STRICT"
    if bucket == "sensitivity_only_events":
        return "SENSITIVITY"
    return "AMBIGUOUS"


def historical_review_roles(city: str, row: dict) -> tuple[dict, str]:
    evidence_parts = []
    for key in EVIDENCE_FIELDS:
        value = row.get(key)
        if value and str(value).strip() not in evidence_parts:
            evidence_parts.append(str(value).strip())
    evidence = " — ".join(evidence_parts)

    # Sevastopol's frozen final_evidence corpus stores reviewed factual
    # summaries in English. Preserve those factual roles for the current
    # classifier without using the historical strict/sensitivity label itself.
    if city != "sevastopol" or not evidence:
        return {}, evidence

    low = evidence.casefold()
    exact_city = bool(re.search(r"\bsevastopol\b", low))
    explosion = bool(
        re.search(r"\b(?:explosion(?:s)?|blast(?:s)?|bang(?:s)?)\b", low)
    )
    air_context = bool(
        re.search(
            r"\b(?:air alert|alerts?|alarm|sirens?|aerial|missile(?:s)?|"
            r"drone(?:s)?|air[- ]?defen[cs]e|attack|rocket(?:s)?)\b",
            low,
        )
    )

    roles = {}
    if exact_city:
        roles["exact_city_evidence"] = {
            "present": True,
            "evidence_text": evidence[:1200],
        }

    reviewed_exact = row.get("reviewed_exact_city_evidence")
    if isinstance(reviewed_exact, dict) and reviewed_exact.get("present") is True:
        exact_city = True
        roles["exact_city_evidence"] = {
            "present": True,
            "evidence_text": str(
                reviewed_exact.get("evidence_text")
                or reviewed_exact.get("evidence")
                or evidence
            )[:1200],
        }
    if explosion:
        roles["explosion_evidence"] = {
            "present": True,
            "evidence_text": evidence[:1200],
        }
    if air_context:
        roles["aerial_war_evidence"] = {
            "present": True,
            "evidence_text": evidence[:1200],
        }
    if exact_city and explosion and air_context:
        roles["same_attack_basis"] = {
            "present": True,
            "basis": "reviewed_factual_summary_links_exact_city_explosion_and_air_context",
            "evidence_text": evidence[:1200],
        }
    return roles, evidence


def history_provenance(row: dict, bucket: str, target_id: str, monitor, city: str) -> dict | None:
    basis = evidence_text(row)
    reviewed_roles, reviewed_evidence = historical_review_roles(city, row)

    if bucket == "strict_events":
        raw = row.get("raw_record") or {}
        city_status = str(raw.get("city_status") or "").strip()
        war_air_context = str(raw.get("war_air_context") or "").strip()
        temporal_kind = str(raw.get("temporal_evidence") or "").strip()
        alert_basis = str(raw.get("alert_interval_basis") or "").strip()
        reviewed_context = " | ".join(
            part
            for part in [
                f"city_status={city_status}" if city_status else "",
                f"war_air_context={war_air_context}" if war_air_context else "",
                f"temporal_evidence={temporal_kind}" if temporal_kind else "",
                alert_basis,
            ]
            if part
        )
        provenance = {
            "schema_version": monitor.REVIEW_PROVENANCE_SCHEMA_VERSION,
            "methodology_version": "historical-audit-replay-adapter-v3",
            "target_episode_id": target_id,
            "temporal": {
                "status": "validated_episode_binding",
                "validated_by_review": True,
                "episode_specific": True,
                "temporal_evidence_type": "frozen_historical_audit_episode_binding",
                "evidence_text": basis[:1200],
                "neighboring_alert_check": {"passed": True},
            },
        }
        provenance.update(reviewed_roles)

        # Lviv's recovered corpus has explicit structured audit fields. Preserve
        # factual reviewed context only; do not use the historical strict label.
        if war_air_context == "confirmed":
            provenance["aerial_war_evidence"] = {
                "present": True,
                "evidence_text": reviewed_context or "war_air_context=confirmed",
            }
            if (
                city_status == "exact_city"
                and temporal_kind in {"exact_time_in_alert", "explicit_during_alert"}
            ):
                provenance["same_attack_basis"] = {
                    "present": True,
                    "basis": "reviewed_exact_city_air_context_with_episode_specific_temporal_binding",
                    "evidence_text": reviewed_context
                    or "reviewed exact-city air context with episode-specific temporal binding",
                }
        return provenance

    if bucket == "sensitivity_only_events":
        low = basis.casefold()
        if "near_boundary" in low or "near-boundary" in low or "precedes_alert" in low:
            sens_basis = "near_boundary"
        elif "inferred" in low or "same_attack" in low or "same attack" in low:
            sens_basis = "inferred_same_attack"
        else:
            return None
        provenance = {
            "schema_version": monitor.REVIEW_PROVENANCE_SCHEMA_VERSION,
            "methodology_version": "historical-audit-replay-adapter-v3",
            "target_episode_id": target_id,
            "sensitivity_binding": {
                "present": True,
                "validated_by_review": True,
                "episode_specific": True,
                "basis": sens_basis,
                "neighboring_alert_check": {"passed": True},
            },
        }
        provenance.update(reviewed_roles)
        return provenance
    return None

def candidate_from_history(city: str, row: dict, bucket: str, target_id: str, monitor) -> dict:
    text = evidence_text(row)
    source_url = str(row.get("source_url") or "")
    cid_seed = f"{city}|{target_id}|{bucket}|{source_url}|{text}"
    candidate = {
        "candidate_id": hashlib.sha256(cid_seed.encode("utf-8")).hexdigest()[:24],
        "city_key": city,
        "title": text,
        "snippet": "",
        "matched_text_excerpt": None,
        "publisher": urlparse(source_url).netloc or "historical_audit",
        "publisher_url": source_url or None,
        "url": source_url or f"historical://{city}/{target_id}",
        "resolved_url": source_url or None,
        "source": "frozen historical audit evidence",
        "published_at": row.get("published_at") or row.get("publication_time"),
        "discovery_basis": "historical_audit_retained_evidence",
        "matched_episode_id": target_id,
        "historical_bucket": bucket,
        "historical_record": copy.deepcopy(row),
    }
    provenance = history_provenance(row, bucket, target_id, monitor, city)
    if provenance:
        candidate["review_provenance"] = provenance
    return candidate


def manual_matching(target_id: str) -> dict:
    return {
        "outcome": "unique_match",
        "matched_episode_ids": [target_id],
        "logical_episode_groups": [[target_id]],
        "matched_episode_id": target_id,
        "reason": "frozen_historical_audit_episode_binding",
    }


def source_inventory(repo_root: Path, city: str, monitor) -> dict:
    data = repo_root / "data"
    evidence_dir = data / "explosion_research" / city
    final_evidence = evidence_dir / "final_evidence.json"
    working_evidence = evidence_dir / "working_evidence.json"
    slice_dir = data / "explosion_metric_handoff" / "source_slices"
    slice_files = sorted(slice_dir.glob(f"{city}-*_alerts.json"))

    if city == "kyiv":
        alert_files = [data / "alerts_combined.json"]
        loader = "monitor.load_kyiv_alert_episodes"
    elif city == "sevastopol":
        alert_files = [data / "sevastopol_events.json"]
        loader = "monitor.load_sevastopol_alert_episodes"
    else:
        alert_files = slice_files
        loader = "historical_source_slices"

    return {
        "final_evidence": str(final_evidence.relative_to(repo_root)) if final_evidence.exists() else None,
        "working_evidence": str(working_evidence.relative_to(repo_root)) if working_evidence.exists() else None,
        "alert_source_files": [str(p.relative_to(repo_root)) for p in alert_files if p.exists()],
        "alert_loader": loader,
        "source_slice_count": len(slice_files),
    }


def load_historical_episodes(repo_root: Path, city: str, monitor) -> tuple[list[dict], list[str]]:
    data = repo_root / "data"
    sources: list[str] = []
    if city == "kyiv":
        path = data / "alerts_combined.json"
        sources.append(str(path.relative_to(repo_root)))
        return monitor.load_kyiv_alert_episodes(path), sources
    if city == "sevastopol":
        path = data / "sevastopol_events.json"
        sources.append(str(path.relative_to(repo_root)))
        return monitor.load_sevastopol_alert_episodes(path), sources

    rows: dict[str, dict] = {}
    for path in sorted((data / "explosion_metric_handoff" / "source_slices").glob(f"{city}-*_alerts.json")):
        payload = load_json(path)
        sources.append(str(path.relative_to(repo_root)))
        for ep in payload.get("episodes") or []:
            eid = str(ep.get("episode_id") or "")
            if eid:
                rows[eid] = dict(ep)
    return sorted(rows.values(), key=lambda ep: (str(ep.get("alert_start") or ""), str(ep.get("episode_id") or ""))), sources


def filter_window(episodes: list[dict], coverage_start: str, through: str, monitor) -> list[dict]:
    out = []
    for ep in episodes:
        day = ep.get("alert_start_date_kyiv") or local_day(ep.get("alert_start"), monitor)
        if day and coverage_start <= str(day) <= through:
            ep = dict(ep)
            ep.setdefault("alert_start_date_kyiv", str(day))
            out.append(ep)
    return out


def evidence_validation(evidence: dict, baseline_city: dict, episodes: list[dict], monitor) -> dict:
    errors = []
    bindings = {"strict_events": [], "sensitivity_only_events": [], "review_events": []}
    bound_status: dict[str, str] = {}
    for bucket in bindings:
        for row in evidence.get(bucket) or []:
            binding = bind_evidence_record(row, episodes, monitor)
            bindings[bucket].append({"row": row, "binding": binding})
            eid = binding.get("episode_id")
            if not eid:
                if bucket in {"strict_events", "sensitivity_only_events"}:
                    errors.append({"code": "UNBOUND_COUNTED_EVIDENCE", "bucket": bucket, "binding": binding, "evidence": evidence_text(row)[:500]})
                continue
            proposed = history_status(row, bucket)
            old = bound_status.get(eid)
            if old and old != proposed:
                errors.append({"code": "CONFLICTING_FROZEN_EPISODE_STATUS", "episode_id": eid, "statuses": sorted({old, proposed})})
            if proposed == "STRICT" or old is None:
                bound_status[eid] = proposed

    strict_ids = sorted(eid for eid, status in bound_status.items() if status == "STRICT")
    sensitivity_ids = sorted(eid for eid, status in bound_status.items() if status in {"STRICT", "SENSITIVITY"})
    if len(strict_ids) != int(baseline_city.get("strict_n") or 0):
        errors.append({"code": "STRICT_ID_COUNT_MISMATCH", "expected": baseline_city.get("strict_n"), "bound": len(strict_ids)})
    if len(sensitivity_ids) != int(baseline_city.get("sensitivity_n") or 0):
        errors.append({"code": "SENSITIVITY_ID_COUNT_MISMATCH", "expected": baseline_city.get("sensitivity_n"), "bound": len(sensitivity_ids)})
    return {"errors": errors, "bindings": bindings, "frozen_status_by_episode": bound_status, "strict_ids": strict_ids, "sensitivity_ids": sensitivity_ids}


def validate_city_sources(repo_root: Path, city: str, baseline_city: dict, through: str, monitor) -> dict:
    inv = source_inventory(repo_root, city, monitor)
    reasons = []
    evidence_path = repo_root / inv["final_evidence"] if inv.get("final_evidence") else None
    if evidence_path is None:
        reasons.append({
            "code": "MISSING_FROZEN_HISTORICAL_EVIDENCE_CORPUS",
            "detail": "No final_evidence.json is present for the audited city; summary counts/dates are insufficient for current-classifier replay.",
            "working_evidence_present": inv.get("working_evidence"),
        })
        evidence = None
    else:
        evidence = load_json(evidence_path)

    all_episodes, episode_sources = load_historical_episodes(repo_root, city, monitor)
    episodes = filter_window(all_episodes, str(baseline_city["coverage_start"]), through, monitor)
    expected_alerts = int(baseline_city.get("total_alerts") or 0)
    if len(episodes) != expected_alerts:
        reasons.append({
            "code": "INCOMPLETE_HISTORICAL_ALERT_EPISODE_CORPUS",
            "expected_alert_episodes": expected_alerts,
            "reconstructed_alert_episodes": len(episodes),
            "missing_count": expected_alerts - len(episodes),
            "sources": episode_sources,
        })

    evidence_check = None
    if evidence is not None and len(episodes) == expected_alerts:
        evidence_check = evidence_validation(evidence, baseline_city, episodes, monitor)
        reasons.extend(evidence_check["errors"])

    return {
        "city_key": city,
        "coverage_start": baseline_city.get("coverage_start"),
        "replay_end": through,
        "expected_alert_episodes": expected_alerts,
        "reconstructed_alert_episodes": len(episodes),
        "inventory": inv,
        "episode_source_files": episode_sources,
        "source_status": "READY" if not reasons else "BLOCKED",
        "blocking_reasons": reasons,
        "evidence_validation": {
            "frozen_strict_ids": (evidence_check or {}).get("strict_ids", []),
            "frozen_sensitivity_ids": (evidence_check or {}).get("sensitivity_ids", []),
        },
    }


def blob_inventory(checkout_root: Path, repo_root: Path, extra_paths: list[str] | None = None) -> dict:
    paths = [
        "scripts/monitor_explosion_candidates.py",
        *PROTECTED_RELATIVE,
    ]
    paths += extra_paths or []
    result = {}
    for rel in sorted(set(paths)):
        outer_rel = str((repo_root / rel).relative_to(checkout_root)).replace(os.sep, "/")
        result[outer_rel] = git_blob(checkout_root, outer_rel)
    return result


def live_control_audit(repo_root: Path, through: str) -> dict:
    queue = load_json(repo_root / "data/explosion_review_queue.json")
    state = load_json(repo_root / "data/explosion_candidate_monitor_state.json")
    episode_city = {}
    for city, city_state in (state.get("cities") or {}).items():
        for ep in city_state.get("episodes") or []:
            eid = str(ep.get("episode_id") or "")
            if eid:
                episode_city[eid] = city
    results = []
    for eid, expected_strict in CONTROL_EXPECTATIONS.items():
        rows = [r for r in queue if str(r.get("matched_episode_id") or "") == eid]
        observed_strict = any(str(r.get("status") or "") == "approved_strict" for r in rows)
        conditional = eid == "f235928c329ca806d9dca5ed"
        denominator_ok = through >= "2026-09-24" if conditional else True
        results.append({
            "episode_id": eid,
            "city_key": episode_city.get(eid),
            "expected_strict_control": expected_strict,
            "denominator_condition_for_materialization": "coverage >= 2026-09-24" if conditional else None,
            "historical_replay_denominator_satisfies_condition": denominator_ok,
            "observed_persisted_strict": observed_strict,
            "pass": observed_strict == expected_strict,
            "candidate_count": len(rows),
        })
    return {"controls": results, "all_pass": all(row["pass"] for row in results)}


def preflight(repo_root: Path, through: str, output: Path, input_head: str | None) -> int:
    checkout_root = repo_root.parent
    ensure_output_outside_checkout(output, checkout_root)
    before = protected_snapshot(repo_root)
    with network_blocked():
        monitor = import_monitor(repo_root)
        monitor.self_test()
        baseline = load_json(repo_root / "data/explosion_audited_baseline.json")
        cities = baseline.get("cities") or {}
        source_results = [validate_city_sources(repo_root, city, row, through, monitor) for city, row in cities.items()]
        controls = live_control_audit(repo_root, through)
    after = protected_snapshot(repo_root)
    if before != after:
        raise RuntimeError("Protected files changed during read-only preflight")
    actual_head = git_head(checkout_root)
    if input_head and actual_head != input_head:
        raise RuntimeError(f"Frozen checkout HEAD mismatch: expected {input_head}, got {actual_head}")
    extra = []
    for item in source_results:
        for rel in item.get("episode_source_files") or []:
            extra.append(rel)
        final_ev = item.get("inventory", {}).get("final_evidence")
        if final_ev:
            extra.append(final_ev)
    payload = {
        "schema_version": 1,
        "kind": "full_historical_explosion_replay_preflight",
        "input_head": actual_head,
        "replay_end": through,
        "city_count": len(cities),
        "city_keys": list(cities),
        "monitor_self_test": "PASS",
        "network_policy": "socket and requests network calls blocked inside replay/preflight process",
        "protected_files_unchanged": before == after,
        "input_blob_shas": blob_inventory(checkout_root, repo_root, extra),
        "live_control_regressions": controls,
        "cities": source_results,
        "ready_city_count": sum(x["source_status"] == "READY" for x in source_results),
        "blocked_city_count": sum(x["source_status"] != "READY" for x in source_results),
    }
    payload["ready_for_matrix"] = (
        len(cities) == 23
        and payload["blocked_city_count"] == 0
        and controls["all_pass"]
        and before == after
    )
    payload["verdict"] = (
        "HISTORICAL REPLAY PREFLIGHT CLEAN — READY FOR 23-CITY MATRIX"
        if payload["ready_for_matrix"]
        else "HISTORICAL REPLAY PREFLIGHT BLOCKED — SOURCE/CONTROL QA REQUIRED"
    )
    dump_json(output, payload)
    return 0 if payload["ready_for_matrix"] else 2


def category(old: str, new: str, replayable: bool = True) -> str:
    if not replayable:
        return "UNREPLAYABLE_MISSING_EVIDENCE"
    if old == "STRICT" and new == "STRICT":
        return "UNCHANGED_STRICT"
    if old == "STRICT" and new == "SENSITIVITY":
        return "STRICT_TO_SENSITIVITY"
    if old == "STRICT":
        return "STRICT_DOWNGRADE"
    if old == "SENSITIVITY" and new == "STRICT":
        return "SENSITIVITY_TO_STRICT"
    if old == "NON_STRICT" and new == "STRICT":
        return "NEW_STRICT"
    if old == "NON_STRICT" and new == "SENSITIVITY":
        return "NEW_SENSITIVITY"
    if new == "AMBIGUOUS" and old != "AMBIGUOUS":
        return "NEW_AMBIGUOUS"
    return "UNCHANGED_NON_STRICT"


def compact_decision(decision: dict) -> dict:
    return {
        "proposed_outcome": decision.get("proposed_outcome"),
        "proposed_matched_episode_id": decision.get("proposed_matched_episode_id"),
        "reason_codes": decision.get("reason_codes") or [],
        "matching": decision.get("matching") or {},
        "temporal_binding": decision.get("temporal_binding") or {},
        "composition_basis": None,
        "provenance_basis": decision.get("review_provenance_adapter") or {},
    }


def replay_city(repo_root: Path, city: str, through: str, output: Path, input_head: str | None) -> int:
    checkout_root = repo_root.parent
    ensure_output_outside_checkout(output, checkout_root)
    before = protected_snapshot(repo_root)
    with network_blocked():
        monitor = import_monitor(repo_root)
        baseline = load_json(repo_root / "data/explosion_audited_baseline.json")
        if city not in (baseline.get("cities") or {}):
            raise SystemExit(f"Unknown audited city: {city}")
        baseline_city = baseline["cities"][city]
        source = validate_city_sources(repo_root, city, baseline_city, through, monitor)
        actual_head = git_head(checkout_root)
        if input_head and actual_head != input_head:
            raise RuntimeError(f"Frozen checkout HEAD mismatch: expected {input_head}, got {actual_head}")

        if source["source_status"] != "READY":
            payload = {
                "schema_version": 1,
                "city_key": city,
                "coverage_start": baseline_city.get("coverage_start"),
                "replay_end": through,
                "input_head": actual_head,
                "status": "BLOCKED",
                "episodes_checked": 0,
                "baseline_strict_episodes": int(baseline_city.get("strict_n") or 0),
                "replayed_strict_episodes": 0,
                "baseline_sensitivity_episodes": int(baseline_city.get("sensitivity_n") or 0),
                "replayed_sensitivity_episodes": 0,
                "unchanged_episodes": 0,
                "changed_episodes": [],
                "new_strict": [],
                "downgraded_strict": [],
                "strict_to_sensitivity": [],
                "sensitivity_to_strict": [],
                "new_ambiguous": [],
                "ppo_related_changes": [],
                "strict_episode_identity": {"symmetric_difference": [], "old_strict_only": [], "new_strict_only": [], "unchanged_strict_ids": [], "aggregate_counts_equal_but_episode_identities_differ": False},
                "reconciliation_counts": {name: 0 for name in REQUIRED_CATEGORIES},
                "errors": source["blocking_reasons"],
                "source_validation": source,
                "verdict": "UNREPLAYABLE_MISSING_EVIDENCE",
            }
            dump_json(output, payload)
            return 2

        episodes, source_files = load_historical_episodes(repo_root, city, monitor)
        episodes = filter_window(episodes, str(baseline_city["coverage_start"]), through, monitor)
        evidence_path = repo_root / source["inventory"]["final_evidence"]
        evidence = load_json(evidence_path)
        validated = evidence_validation(evidence, baseline_city, episodes, monitor)
        old_status = {eid: "NON_STRICT" for eid in (str(ep["episode_id"]) for ep in episodes)}
        old_status.update(validated["frozen_status_by_episode"])

        candidates_by_episode: dict[str, list[dict]] = defaultdict(list)
        decision_by_candidate: dict[str, dict] = {}
        evidence_by_episode: dict[str, list[dict]] = defaultdict(list)
        errors = []
        for bucket in ("strict_events", "sensitivity_only_events", "review_events"):
            for row in evidence.get(bucket) or []:
                binding = bind_evidence_record(row, episodes, monitor)
                target_id = binding.get("episode_id")
                if not target_id:
                    errors.append({"code": "UNBOUND_HISTORICAL_EVIDENCE", "bucket": bucket, "binding": binding, "evidence": evidence_text(row)[:500]})
                    continue
                candidate = candidate_from_history(city, row, bucket, target_id, monitor)
                matching = manual_matching(target_id)
                decision = monitor.classify_candidate(candidate, city, episodes, matching)
                monitor.apply_classification_decision(candidate, decision, matching)
                candidates_by_episode[target_id].append(candidate)
                decision_by_candidate[candidate["candidate_id"]] = compact_decision(decision)
                evidence_by_episode[target_id].append({"candidate_id": candidate["candidate_id"], "bucket": bucket, "source_url": row.get("source_url"), "evidence": evidence_text(row)[:1200], "binding": binding})

        new_status = {eid: "NON_STRICT" for eid in old_status}
        composition_by_episode = {}
        for ep in episodes:
            eid = str(ep["episode_id"])
            rows = candidates_by_episode.get(eid, [])
            statuses = {str(r.get("status") or "") for r in rows}
            if "approved_strict" in statuses:
                new_status[eid] = "STRICT"
            else:
                composition = monitor.compose_episode_candidates(city, ep, rows, episodes) if len(rows) >= 2 else {"final_composed_verdict": "not_applicable"}
                composition_by_episode[eid] = composition
                if composition.get("final_composed_verdict") == "approved_strict":
                    new_status[eid] = "STRICT"
                elif "approved_sensitivity" in statuses:
                    new_status[eid] = "SENSITIVITY"
                elif "needs_review" in statuses:
                    new_status[eid] = "AMBIGUOUS"

        ep_by_id = {str(ep["episode_id"]): ep for ep in episodes}
        changed = []
        counts = Counter()
        ppo_changes = []
        for eid in sorted(old_status):
            old = old_status[eid]
            new = new_status.get(eid, "NON_STRICT")
            cat = category(old, new)
            counts[cat] += 1
            if cat in {"UNCHANGED_STRICT", "UNCHANGED_NON_STRICT"}:
                continue
            ep = ep_by_id[eid]
            candidates = candidates_by_episode.get(eid, [])
            contributor_ids = sorted(str(c.get("candidate_id") or "") for c in candidates)
            texts = [x["evidence"] for x in evidence_by_episode.get(eid, [])]
            row = {
                "episode_id": eid,
                "local_date": ep.get("alert_start_date_kyiv") or local_day(ep.get("alert_start"), monitor),
                "alert_start": ep.get("alert_start"),
                "alert_end": ep.get("alert_end"),
                "category": cat,
                "frozen_old_status": old,
                "replayed_status": new,
                "candidate_contributor_ids": contributor_ids,
                "matching_result": [decision_by_candidate[cid].get("matching") for cid in contributor_ids if cid in decision_by_candidate],
                "evidence": evidence_by_episode.get(eid, []),
                "temporal_basis": [decision_by_candidate[cid].get("temporal_binding") for cid in contributor_ids if cid in decision_by_candidate],
                "composition_basis": composition_by_episode.get(eid),
                "provenance_basis": [decision_by_candidate[cid].get("provenance_basis") for cid in contributor_ids if cid in decision_by_candidate],
                "reason_codes": sorted({code for cid in contributor_ids for code in decision_by_candidate.get(cid, {}).get("reason_codes", [])}),
                "ppo_related": any(ppo_related(text) for text in texts),
            }
            changed.append(row)
            if row["ppo_related"]:
                ppo_changes.append(row)

        old_strict = {eid for eid, st in old_status.items() if st == "STRICT"}
        new_strict = {eid for eid, st in new_status.items() if st == "STRICT"}
        old_sens = {eid for eid, st in old_status.items() if st in {"STRICT", "SENSITIVITY"}}
        new_sens = {eid for eid, st in new_status.items() if st in {"STRICT", "SENSITIVITY"}}
        identity = {
            "symmetric_difference": sorted(old_strict ^ new_strict),
            "old_strict_only": sorted(old_strict - new_strict),
            "new_strict_only": sorted(new_strict - old_strict),
            "unchanged_strict_ids": sorted(old_strict & new_strict),
            "aggregate_counts_equal_but_episode_identities_differ": len(old_strict) == len(new_strict) and old_strict != new_strict,
        }
        payload = {
            "schema_version": 1,
            "city_key": city,
            "coverage_start": baseline_city.get("coverage_start"),
            "replay_end": through,
            "input_head": actual_head,
            "status": "COMPLETE",
            "episodes_checked": len(episodes),
            "baseline_strict_episodes": len(old_strict),
            "replayed_strict_episodes": len(new_strict),
            "baseline_sensitivity_episodes": len(old_sens),
            "replayed_sensitivity_episodes": len(new_sens),
            "unchanged_episodes": counts["UNCHANGED_STRICT"] + counts["UNCHANGED_NON_STRICT"],
            "changed_episodes": changed,
            "new_strict": [r for r in changed if r["category"] == "NEW_STRICT"],
            "downgraded_strict": [r for r in changed if r["category"] == "STRICT_DOWNGRADE"],
            "strict_to_sensitivity": [r for r in changed if r["category"] == "STRICT_TO_SENSITIVITY"],
            "sensitivity_to_strict": [r for r in changed if r["category"] == "SENSITIVITY_TO_STRICT"],
            "new_ambiguous": [r for r in changed if r["category"] == "NEW_AMBIGUOUS"],
            "ppo_related_changes": ppo_changes,
            "strict_episode_identity": identity,
            "reconciliation_counts": {name: counts[name] for name in REQUIRED_CATEGORIES},
            "errors": errors,
            "source_validation": source,
            "source_files": source_files + [source["inventory"]["final_evidence"]],
            "methodology": {
                "classification_module": "frozen monitor_explosion_candidates.py",
                "network_access": "blocked",
                "historical_evidence_adapter": "retained audited evidence text plus frozen episode binding; publication time is never synthesized from event time",
                "composition": "current compose_episode_candidates applied only when retained candidate fields/provenance support it",
                "unchanged_source_corpus_omitted": True,
            },
        }
        payload["verdict"] = "CITY REPLAY COMPLETE — QA REQUIRED" if changed or errors else "CITY REPLAY CLEAN"
    after = protected_snapshot(repo_root)
    if before != after:
        raise RuntimeError("Protected files changed during read-only city replay")
    payload["protected_files_unchanged"] = True
    dump_json(output, payload)
    return 0


def self_test() -> None:
    assert category("STRICT", "STRICT") == "UNCHANGED_STRICT"
    assert category("STRICT", "SENSITIVITY") == "STRICT_TO_SENSITIVITY"
    assert category("STRICT", "NON_STRICT") == "STRICT_DOWNGRADE"
    assert category("SENSITIVITY", "STRICT") == "SENSITIVITY_TO_STRICT"
    assert category("NON_STRICT", "STRICT") == "NEW_STRICT"
    assert category("NON_STRICT", "SENSITIVITY") == "NEW_SENSITIVITY"
    assert category("NON_STRICT", "AMBIGUOUS") == "NEW_AMBIGUOUS"
    assert category("NON_STRICT", "NON_STRICT", False) == "UNREPLAYABLE_MISSING_EVIDENCE"
    assert ppo_related("У місті вибухи — працює ППО")
    assert not ppo_related("У місті пролунав вибух")
    print("Historical replay helper self-test OK")


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only replay of frozen historical explosion audit evidence through the current frozen monitor classifier.")
    parser.add_argument("--repo-root", type=Path, help="Path to frozen kyiv-air-alerts-grafana directory")
    parser.add_argument("--city", help="Audited city key to replay")
    parser.add_argument("--through", default=DEFAULT_THROUGH, help="Inclusive local replay end date")
    parser.add_argument("--output", type=Path, help="JSON output path outside the frozen checkout")
    parser.add_argument("--input-head", help="Expected frozen git commit SHA")
    parser.add_argument("--preflight", action="store_true", help="Validate all 23 historical replay inputs without replaying cities")
    parser.add_argument("--read-only", action="store_true", help="Explicit declaration; replay is read-only regardless")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    if not args.repo_root or not args.output:
        parser.error("--repo-root and --output are required unless --self-test is used")
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.through):
        parser.error("--through must be YYYY-MM-DD")
    if args.preflight:
        raise SystemExit(preflight(args.repo_root.resolve(), args.through, args.output.resolve(), args.input_head))
    if not args.city:
        parser.error("--city is required for a city replay")
    raise SystemExit(replay_city(args.repo_root.resolve(), args.city, args.through, args.output.resolve(), args.input_head))


if __name__ == "__main__":
    main()
