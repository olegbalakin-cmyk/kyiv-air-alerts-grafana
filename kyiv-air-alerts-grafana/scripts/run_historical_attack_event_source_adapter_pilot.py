#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import monitor_explosion_candidates as monitor
from historical_attack_event_sources import (
    NetworkBounds,
    PublicTelegramAdapter,
    canonical_observation_id,
    content_hash,
)

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_ROOT = ROOT.parent
RESEARCH = CHECKOUT_ROOT / "research"
UTC = timezone.utc
KYIV_TZ = ZoneInfo("Europe/Kyiv")
ACTIVE_EXCLUSIONS = {"lviv", "kyiv", "sumy", "cherkasy", "zaporizhzhia"}
TASK_STARTING_HEAD = os.getenv("TASK_STARTING_HEAD") or None
WORKFLOW_RUN_ID = os.getenv("GITHUB_WORKFLOW_RUN_ID") or None

PROTECTED_RELATIVE = [
    "data/explosion_audited_baseline.json",
    "data/explosion_review_queue.json",
    "data/explosion_candidate_monitor_state.json",
    "data/explosion_candidate_monitor_last_run.json",
    "data/explosions_test.json",
    "data/dashboard_data.json",
]
DISCOVERY_RE = re.compile(
    r"(?:взрыв|вибух|пво|ппо|ракет|дрон|бпла|беспил|безпіл|удар|"
    r"попад|влуч|прилет|приліт|пожар|пожеж|поврежд|пошкод|атак)",
    re.IGNORECASE,
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=CHECKOUT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def git_blob_for_path(path: Path) -> str:
    return git("hash-object", str(path.relative_to(CHECKOUT_ROOT)))


def protected_paths() -> list[Path]:
    paths = [ROOT / rel for rel in PROTECTED_RELATIVE]
    paths.extend(sorted((ROOT / "data" / "explosion_research").glob("*/final_evidence.json")))
    return paths


def protected_blobs() -> dict[str, str]:
    return {
        str(path.relative_to(CHECKOUT_ROOT)).replace(os.sep, "/"): git_blob_for_path(path)
        for path in protected_paths()
        if path.exists()
    }


def run_json_command(args: list[str]) -> tuple[dict | None, str, int]:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    text = proc.stdout
    start = text.find("{")
    payload = None
    if start >= 0:
        try:
            payload = json.loads(text[start:])
        except json.JSONDecodeError:
            payload = None
    return payload, text, proc.returncode


def parse_control_start(row: dict) -> datetime | None:
    raw = row.get("alert_start") or row.get("alert_start_kyiv")
    if not raw:
        return None
    text = str(raw).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            dt = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KYIV_TZ)
    return dt.astimezone(UTC)


def bind_control(row: dict, episodes: list[dict]) -> dict:
    start = parse_control_start(row)
    if start is None:
        return {"episode_id": None, "method": "missing_control_start", "delta_seconds": None}
    matches = []
    for ep in episodes:
        ep_start = monitor.parse_dt(ep.get("alert_start"))
        if not ep_start:
            continue
        delta = abs((ep_start - start).total_seconds())
        if delta <= 90:
            matches.append((delta, str(ep.get("episode_id") or "")))
    matches.sort()
    if len(matches) == 1:
        return {"episode_id": matches[0][1], "method": "alert_start_within_90s", "delta_seconds": matches[0][0]}
    return {
        "episode_id": None,
        "method": "ambiguous_or_unmatched_control_start",
        "delta_seconds": matches[0][0] if matches else None,
        "candidate_episode_ids": [x[1] for x in matches],
    }


def select_window(episodes: list[dict], anchor_id: str, limit: int) -> list[dict]:
    limit = max(1, min(limit, len(episodes)))
    idx = next(i for i, ep in enumerate(episodes) if str(ep["episode_id"]) == anchor_id)
    start = max(0, idx - limit // 2)
    end = start + limit
    if end > len(episodes):
        end = len(episodes)
        start = max(0, end - limit)
    out = episodes[start:end]
    if anchor_id not in {str(ep["episode_id"]) for ep in out}:
        raise RuntimeError("anchor missing from deterministic window")
    return out


def public_telegram_controls(evidence: dict, episodes: list[dict]) -> list[dict]:
    episode_order = {str(ep["episode_id"]): i for i, ep in enumerate(episodes)}
    rows = []
    for row in evidence.get("strict_events") or []:
        url = str(row.get("source_url") or "")
        parsed = urlparse(url)
        if parsed.netloc.casefold() not in {"t.me", "telegram.me"}:
            continue
        binding = bind_control(row, episodes)
        episode_id = binding.get("episode_id")
        if not episode_id:
            continue
        path = parsed.path.strip("/").split("/")
        if path and path[0] == "s":
            path = path[1:]
        channel = path[0] if path else ""
        before = None
        values = parse_qs(parsed.query).get("before") or []
        if values and str(values[0]).isdigit():
            before = int(values[0])
        rows.append({
            "episode_id": episode_id,
            "episode_index": episode_order[episode_id],
            "source_url": url,
            "channel": channel,
            "before_message_id": before,
            "basis": row.get("basis") or row.get("decision"),
            "evidence": row.get("evidence"),
            "binding": binding,
            "raw_control": row,
        })
    rows.sort(
        key=lambda x: (
            0 if str(x.get("basis") or "").startswith("strict_exact_time") else 1,
            x["episode_index"],
            x["source_url"],
        )
    )
    return rows


def retained_controls(evidence: dict, episodes: list[dict], selected_ids: set[str]) -> list[dict]:
    out = []
    for row in evidence.get("strict_events") or []:
        binding = bind_control(row, episodes)
        eid = binding.get("episode_id")
        if eid in selected_ids:
            out.append({
                "episode_id": eid,
                "source_url": row.get("source_url"),
                "evidence": row.get("evidence"),
                "basis": row.get("basis") or row.get("decision"),
                "binding": binding,
                "raw_control": row,
            })
    out.sort(key=lambda x: (x["episode_id"], str(x.get("source_url") or "")))
    return out


def source_city_mentioned(city_key: str, text: str) -> bool:
    """Discovery-only source recognition; classifier city semantics stay untouched."""
    if monitor.city_mentioned(city_key, text):
        return True
    low = " ".join(str(text or "").casefold().replace("’", "'").split())
    if city_key == "sevastopol":
        return "севастопол" in low
    return False


def source_matched_terms(text: str) -> list[str]:
    low = str(text or "").casefold()
    families = {
        "explosion_discovery": ("взрыв", "вибух"),
        "impact_arrival_discovery": ("прилет", "приліт", "попад", "влуч"),
        "strike_discovery": ("удар",),
        "damage_discovery": ("поврежд", "пошкод"),
        "fire_discovery": ("пожар", "пожеж", "загор"),
        "air_defense_context": ("пво", "ппо", "противовоздуш", "протиповітр"),
    }
    return [
        label
        for label, stems in families.items()
        if any(stem in low for stem in stems)
    ]


def candidate_from_post(post: dict) -> dict:
    text = str(post.get("text") or "")
    return {
        "candidate_id": canonical_observation_id(str(post["channel"]), int(post["message_id"])),
        "source": f"Telegram / {post['channel']}",
        "title": text[:240] or f"Telegram post {post['message_id']}",
        "url": post["url"],
        "publisher": post["channel"],
        "publisher_url": f"https://t.me/{post['channel']}",
        "published_at": post["published_at"],
        "snippet": text[:1200],
        "matched_text_excerpt": text[:5000],
        "discovery_basis": str(post.get("discovery_basis") or "historical_public_telegram"),
    }


def observation_from_post(post: dict, selected: list[dict]) -> dict:
    row = candidate_from_post(post)
    matching = monitor.match_candidate_to_episodes(row, selected)
    decision = monitor.classify_candidate(row, "sevastopol", selected, matching)
    temporal = decision.get("temporal_binding") or {}
    event_types = list(decision.get("event_types") or [])
    return {
        "observation_id": row["candidate_id"],
        "source_type": "public_telegram",
        "source": row["source"],
        "source_url": row["url"],
        "telegram_channel": post["channel"],
        "telegram_message_id": int(post["message_id"]),
        "source_timestamp": post["published_at"],
        "event_timestamp_if_stated": temporal.get("event_time"),
        "excerpt": str(post.get("text") or "")[:1200],
        "matched_terms": source_matched_terms(str(post.get("text") or "")),
        "event_types_supported": event_types,
        "exact_city_binding": decision.get("exact_city_classification_evidence"),
        "air_attack_context": decision.get("air_military_context"),
        "same_attack_context": decision.get("same_attack_context"),
        "temporal_binding": temporal,
        "classification_outcome": decision.get("proposed_outcome"),
        "classification_episode_id": decision.get("proposed_matched_episode_id"),
        "classification_reason_codes": list(decision.get("reason_codes") or []),
        "content_hash": content_hash(
            post["channel"],
            post["message_id"],
            post["published_at"],
            post.get("text"),
        ),
        "provenance": {
            "retrieval_method": post.get("discovery_basis"),
            "retrieval_url": post.get("retrieval_url"),
            "source_family_onboarded": True,
            "classifier": "monitor_explosion_candidates.py current branch version",
            "raw_metadata": {
                "telegram_channel": post["channel"],
                "telegram_message_id": post["message_id"],
            },
            "candidate_matching": matching,
        },
    }


def current_candidates(inventory: dict, replay_status: dict) -> list[dict]:
    ready = set((inventory.get("readiness") or {}).get("READY_FOR_AUTONOMOUS_PPO_DISCOVERY") or [])
    candidates = []
    for city in sorted(ready - ACTIVE_EXCLUSIONS):
        state = (replay_status.get("cities") or {}).get(city) or {}
        expected = int(state.get("expected_alert_episodes") or 0)
        reconstructed = int(state.get("reconstructed_alert_episodes") or 0)
        evidence_path = ROOT / "data" / "explosion_research" / city / "final_evidence.json"
        if (
            state.get("source_status") != "READY"
            or state.get("status") != "READY"
            or expected <= 0
            or expected != reconstructed
            or not evidence_path.exists()
        ):
            continue
        evidence = load_json(evidence_path)
        strict = evidence.get("strict_events") or []
        if not strict:
            continue
        if city == "sevastopol":
            episodes = monitor.load_sevastopol_alert_episodes(ROOT / "data" / "sevastopol_events.json")
        else:
            source_slice = ROOT / "data" / "explosion_metric_handoff" / "source_slices" / f"{city}-replay_alerts.json"
            if not source_slice.exists():
                continue
            doc = load_json(source_slice)
            episodes = list(doc.get("episodes") or [])
        public_controls = public_telegram_controls(evidence, episodes)
        if not public_controls:
            continue
        candidates.append({
            "city_key": city,
            "episode_universe": expected,
            "reconstructed_episode_universe": reconstructed,
            "replay_status": state.get("status"),
            "retained_strict_controls": len(strict),
            "deterministic_public_source": {
                "source_type": "public_telegram",
                "channel": public_controls[0]["channel"],
                "source_url": public_controls[0]["source_url"],
            },
        })
    return sorted(candidates, key=lambda x: (x["episode_universe"], x["city_key"]))


def lviv_regression(tmp_dir: Path) -> dict:
    old_path = RESEARCH / "historical_attack_event_discovery_pilot_lviv_2026-09-27.json"
    old_blob = git_blob_for_path(old_path)
    new_path = tmp_dir / "lviv_regression.json"
    proc = subprocess.run(
        [
            sys.executable,
            "scripts/discover_historical_attack_events.py",
            "--city",
            "lviv",
            "--max-episodes",
            "40",
            "--output",
            str(new_path),
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if not new_path.exists():
        return {
            "passed": False,
            "return_code": proc.returncode,
            "old_blob": old_blob,
            "error": proc.stdout[-4000:],
        }
    doc = load_json(new_path)
    controls = doc.get("controls") or {}
    summary = doc.get("summary") or {}
    observations = doc.get("evidence_observations") or []
    rel = [
        x for x in observations
        if x.get("classification_episode_id") == "498d07cfea5ac7e9090a08e3"
        and x.get("classification_outcome") == "approved_strict"
    ]
    rel_codes = sorted({(x.get("temporal_binding") or {}).get("code") for x in rel})
    tsn = [
        x for x in observations
        if x.get("classification_episode_id") == "6cd77c20720eafece633c1ad"
        and x.get("classification_outcome") == "approved_strict"
        and x.get("source_type") == "targeted_secondary_html_preflight"
    ]
    passed = (
        proc.returncode == 0
        and summary.get("selected_episode_count") == 40
        and controls.get("retained_control_count") == 7
        and controls.get("rediscovered_strict_control_count") == 7
        and controls.get("newly_strict_episode_ids_vs_retained_controls") == []
        and summary.get("event_positive_episode_count") == 7
        and "TEMPORAL_RELATIVE_ALERT_CHRONOLOGY" in rel_codes
        and bool(tsn)
        and all((x.get("provenance") or {}).get("source_family_onboarded") is False for x in tsn)
    )
    new_bytes = new_path.read_bytes()
    new_blob = hashlib.sha1(f"blob {len(new_bytes)}\0".encode() + new_bytes).hexdigest()
    return {
        "passed": passed,
        "return_code": proc.returncode,
        "old_blob": old_blob,
        "new_blob": new_blob,
        "behaviorally_equivalent": passed,
        "expected_provenance_only_differences": [
            "generated_at changes",
            "bounded retry adapter metadata may differ only if a network retry occurs",
        ],
        "selected_episode_count": summary.get("selected_episode_count"),
        "retained_control_count": controls.get("retained_control_count"),
        "rediscovered_strict_control_count": controls.get("rediscovered_strict_control_count"),
        "newly_strict_episode_ids": controls.get("newly_strict_episode_ids_vs_retained_controls"),
        "event_positive_episode_count": summary.get("event_positive_episode_count"),
        "relative_chronology_codes": rel_codes,
        "targeted_secondary_control_recovered": bool(tsn),
        "targeted_secondary_source_family_onboarded": any(
            (x.get("provenance") or {}).get("source_family_onboarded") is True for x in tsn
        ),
        "stdout_tail": proc.stdout[-2000:],
    }


def run_sevastopol_pilot(max_episodes: int, output_path: Path) -> dict:
    evidence_path = ROOT / "data" / "explosion_research" / "sevastopol" / "final_evidence.json"
    evidence = load_json(evidence_path)
    episodes = monitor.load_sevastopol_alert_episodes(ROOT / "data" / "sevastopol_events.json")
    direct_controls = public_telegram_controls(evidence, episodes)
    if not direct_controls:
        return {
            "schema_version": 1,
            "kind": "historical_attack_event_discovery_pilot",
            "city_key": "sevastopol",
            "verdict": "HISTORICAL ATTACK-EVENT DISCOVERY PILOT BLOCKED — DETERMINISTIC_SOURCE_PATH_DOES_NOT_EXIST",
        }

    anchor = direct_controls[0]
    selected = select_window(episodes, anchor["episode_id"], max_episodes)
    selected_ids = {str(ep["episode_id"]) for ep in selected}
    controls = retained_controls(evidence, episodes, selected_ids)
    search_start = min(monitor.parse_dt(ep["alert_start"]) for ep in selected) - timedelta(hours=3)
    search_end = max(monitor.parse_dt(ep["alert_end"]) for ep in selected) + timedelta(hours=72)

    bounds = NetworkBounds(
        timeout_seconds=15,
        max_retries=2,
        rate_limit_seconds=0.2,
        max_telegram_pages=60,
        max_neighbor_previous=3,
    )
    adapter = PublicTelegramAdapter(bounds)
    posts = {}
    diagnostics = {"retained_page_fetches": [], "searches": []}

    retained_pages = sorted({
        (c["channel"], c["before_message_id"])
        for c in direct_controls
        if c["episode_id"] in selected_ids and c.get("channel") and c.get("before_message_id")
    })
    for channel, before_id in retained_pages:
        try:
            rows, meta = adapter.fetch_before_page(
                channel,
                before_id,
                min_time=search_start,
                max_time=search_end,
            )
            diagnostics["retained_page_fetches"].append({
                "channel": channel,
                "before_message_id": before_id,
                **meta,
            })
            for post in rows:
                post["discovery_basis"] = "retained_public_telegram_bounded_page"
                posts[(post["channel"].casefold(), post["message_id"])] = post
        except Exception as exc:
            diagnostics["retained_page_fetches"].append({
                "channel": channel,
                "before_message_id": before_id,
                "resolved": False,
                "error": f"{type(exc).__name__}: {exc}",
            })

    channels = sorted({c["channel"] for c in direct_controls if c.get("channel")})
    for channel in channels:
        try:
            rows, meta = adapter.search(
                channel,
                "Севастополь",
                search_start,
                search_end,
                max_pages=60,
            )
            diagnostics["searches"].append(meta)
            for post in rows:
                post["discovery_basis"] = "bounded_public_telegram_search"
                posts[(post["channel"].casefold(), post["message_id"])] = post
        except Exception as exc:
            diagnostics["searches"].append({
                "channel": channel,
                "query": "Севастополь",
                "resolved": False,
                "error": f"{type(exc).__name__}: {exc}",
            })

    all_posts = sorted(posts.values(), key=lambda x: (x["published_at"], x["message_id"]))
    candidate_posts = [
        post for post in all_posts
        if DISCOVERY_RE.search(str(post.get("text") or ""))
        and source_city_mentioned("sevastopol", str(post.get("text") or ""))
    ]
    observations = [observation_from_post(post, selected) for post in candidate_posts]
    observations.sort(key=lambda x: (x.get("source_timestamp") or "", x["observation_id"]))

    by_episode = {str(ep["episode_id"]): [] for ep in selected}
    for obs in observations:
        eid = str(obs.get("classification_episode_id") or "")
        if eid in by_episode:
            by_episode[eid].append(obs)

    canonical_events = []
    episode_results = []
    event_positive = set()
    for ep in selected:
        eid = str(ep["episode_id"])
        ep_obs = by_episode[eid]
        strict_obs = [x for x in ep_obs if x.get("classification_outcome") == "approved_strict"]
        sensitivity_obs = [x for x in ep_obs if x.get("classification_outcome") == "approved_sensitivity"]
        if strict_obs:
            event_positive.add(eid)
        event_types = sorted({t for obs in strict_obs for t in (obs.get("event_types_supported") or [])})
        for obs in strict_obs:
            canonical_events.append({
                "canonical_event_id": hashlib.sha256(
                    f"sevastopol|{eid}|{obs['observation_id']}".encode("utf-8")
                ).hexdigest()[:24],
                "episode_id": eid,
                "event_types": list(obs.get("event_types_supported") or []),
                "observation_ids": [obs["observation_id"]],
                "deduplication_status": "observation_level_unmerged_pilot",
                "ambiguity_flag": len(strict_obs) > 1,
            })
        episode_results.append({
            "episode_id": eid,
            "alert_start": ep.get("alert_start"),
            "alert_end": ep.get("alert_end"),
            "has_confirmed_event": bool(strict_obs),
            "confirmed_event_count": len(strict_obs),
            "event_types": event_types,
            "strict_observation_ids": [x["observation_id"] for x in strict_obs],
            "sensitivity_observation_ids": [x["observation_id"] for x in sensitivity_obs],
        })

    retained_ids = sorted({x["episode_id"] for x in controls})
    rediscovered = sorted(set(retained_ids) & event_positive)
    missed = sorted(set(retained_ids) - event_positive)
    new_ids = sorted(event_positive - set(retained_ids))

    def control_clock_tokens(control_row: dict) -> set[str]:
        raw = (control_row.get("raw_control") or {}).get("event_time") or (control_row.get("raw_control") or {}).get("event_time_kyiv") or ""
        tokens = set()
        for hour, minute in re.findall(r"(?<!\\d)([0-2]?\\d)[:.]([0-5]\\d)", str(raw)):
            hh = f"{int(hour):02d}"
            tokens.add(f"{hh}:{minute}")
            tokens.add(f"{hh}.{minute}")
        return tokens

    missed_diag = []
    for eid in missed:
        control_rows = [x for x in controls if x["episode_id"] == eid]
        source_urls = sorted({str(x.get("source_url") or "") for x in control_rows})
        obs_for_episode = by_episode.get(eid) or []
        retrieval_bound_obs = []
        target_clock_tokens = set()
        for control_row in control_rows:
            target_clock_tokens.update(control_clock_tokens(control_row))
        for obs in observations:
            matching = (obs.get("provenance") or {}).get("candidate_matching") or {}
            candidate_ids = set(matching.get("matched_episode_ids") or [])
            if matching.get("matched_episode_id"):
                candidate_ids.add(str(matching.get("matched_episode_id")))
            excerpt = str(obs.get("excerpt") or "")
            clock_match = bool(target_clock_tokens and any(token in excerpt for token in target_clock_tokens))
            if eid in candidate_ids or clock_match:
                retrieval_bound_obs.append(obs)
        is_crimeanwind = any("t.me" in url and "Crimeanwind" in url for url in source_urls)
        if obs_for_episode or retrieval_bound_obs:
            code = "CURRENT_RULE_DOWNGRADE"
        elif is_crimeanwind:
            code = "SOURCE_NOT_DISCOVERED"
        else:
            code = "SOURCE_FAMILY_COVERAGE_GAP"
        missed_diag.append({
            "episode_id": eid,
            "gap_code": code,
            "retained_source_urls": source_urls,
            "retained_event_clock_tokens": sorted(target_clock_tokens),
            "retrieved_observation_ids": sorted({
                x["observation_id"] for x in (obs_for_episode + retrieval_bound_obs)
            }),
        })

    newly_strict = []
    for eid in new_ids:
        strict_obs = [
            x for x in by_episode.get(eid, [])
            if x.get("classification_outcome") == "approved_strict"
        ]
        newly_strict.append({
            "episode_id": eid,
            "classification": "valid newly discovered historical event",
            "observation_ids": [x["observation_id"] for x in strict_obs],
            "source_urls": [x["source_url"] for x in strict_obs],
            "reason_codes": [x["classification_reason_codes"] for x in strict_obs],
        })

    counts = {
        "selected_alert_episodes": len(selected),
        "retrieved_observations": len(observations),
        "strict_observations": sum(x.get("classification_outcome") == "approved_strict" for x in observations),
        "sensitivity_observations": sum(x.get("classification_outcome") == "approved_sensitivity" for x in observations),
        "needs_review_observations": sum(x.get("classification_outcome") == "needs_review" for x in observations),
        "rejected_observations": sum(x.get("classification_outcome") == "rejected" for x in observations),
        "event_positive_episode_count": len(event_positive),
        "pilot_event_positive_share": round(len(event_positive) / len(selected), 6) if selected else 0,
        "retained_controls_in_window": len(retained_ids),
        "rediscovered_controls": len(rediscovered),
        "missed_controls": len(missed),
    }
    event_types_observed = sorted({
        t for obs in observations for t in (obs.get("event_types_supported") or [])
    })

    verdict = (
        "HISTORICAL ATTACK-EVENT DISCOVERY PILOT COMPLETE"
        if observations
        else "HISTORICAL ATTACK-EVENT DISCOVERY PILOT BLOCKED — SOURCE_NOT_DISCOVERED"
    )
    doc = {
        "schema_version": 1,
        "kind": "historical_attack_event_discovery_pilot",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "city_key": "sevastopol",
        "city": monitor.CITY_CONFIG["sevastopol"]["label"],
        "starting_head": git("rev-parse", "HEAD"),
        "workflow_run_id": WORKFLOW_RUN_ID,
        "selection": {
            "rule": "complete corpus + no active blocker + retained positive control + deterministic autonomous public source; prefer smallest episode universe; tie-break city_key",
            "anchor": {
                "episode_id": anchor["episode_id"],
                "episode_index": anchor["episode_index"],
                "source_url": anchor["source_url"],
                "source_type": "public_telegram",
                "channel": anchor["channel"],
                "before_message_id": anchor["before_message_id"],
                "basis": anchor["basis"],
                "evidence": anchor["evidence"],
            },
            "selected_episode_count": len(selected),
            "window_start_episode_id": selected[0]["episode_id"],
            "window_end_episode_id": selected[-1]["episode_id"],
            "window_start": selected[0]["alert_start"],
            "window_end": selected[-1]["alert_end"],
        },
        "source_adapters_used": ["PublicTelegramAdapter"],
        "retrieval_diagnostics": {
            **diagnostics,
            "search_window_start": search_start.isoformat().replace("+00:00", "Z"),
            "search_window_end": search_end.isoformat().replace("+00:00", "Z"),
            "raw_posts_retrieved": len(all_posts),
            "candidate_posts_after_city_and_attack_discovery_filter": len(candidate_posts),
            "network_bounds": {
                "user_agent": "explicit adapter User-Agent",
                "timeout_seconds": 15,
                "max_retries": 2,
                "rate_limit_seconds": 0.2,
                "max_search_pages": 60,
                "retained_before_page_requests": len(retained_pages),
                "unbounded_history_crawl": False,
                "telegram_api_credentials": False,
            },
        },
        "evidence_observations": observations,
        "canonical_event_candidates": canonical_events,
        "episode_level_results": episode_results,
        "control_recovery": {
            "retained_control_episode_ids": retained_ids,
            "rediscovered_control_episode_ids": rediscovered,
            "missed_control_episode_ids": missed,
            "missed_control_diagnostics": missed_diag,
        },
        "newly_strict_cases": newly_strict,
        "event_types_observed": event_types_observed,
        "qa_summary": counts,
        "metric_rule": "Binary per alert episode: has_confirmed_event contributes at most 1 to the public numerator. Pilot share is QA-only.",
        "baseline_mutated": False,
        "production_metric_mutated": False,
        "verdict": verdict,
    }
    dump_json(output_path, doc)
    return doc


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city-key", default="auto")
    parser.add_argument("--max-episodes", type=int, default=40)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    out = args.output_dir
    out.mkdir(parents=True, exist_ok=True)

    workflow_input_head = git("rev-parse", "HEAD")
    before_blobs = protected_blobs()
    blocker = None

    worker_self = subprocess.run(
        [sys.executable, "scripts/discover_historical_attack_events.py", "--self-test"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    classifier_self = subprocess.run(
        [sys.executable, "scripts/monitor_explosion_candidates.py", "--self-test"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    audit, audit_text, audit_rc = run_json_command(
        [sys.executable, "scripts/audit_attack_event_classifier.py"]
    )
    lviv = lviv_regression(out)

    if worker_self.returncode != 0:
        blocker = "SOURCE_ADAPTER_SELF_TEST_FAILED"
    elif classifier_self.returncode != 0:
        blocker = "CLASSIFIER_SELF_TEST_FAILED"
    elif not audit or audit_rc != 0 or audit.get("uncontrolled_drift_count") != 0 or audit.get("approved_regression_count") != 0:
        blocker = "CLASSIFIER_CONTROL_REPLAY_REGRESSION"
    elif not lviv.get("passed"):
        blocker = "LVIV_BEHAVIORAL_REGRESSION"

    inventory = load_json(RESEARCH / "historical_ppo_source_inventory.json")
    replay_status = load_json(RESEARCH / "historical_replay_status_current.json")
    candidates = current_candidates(inventory, replay_status)
    selected_city = candidates[0]["city_key"] if candidates else None

    if blocker is None:
        if not selected_city:
            blocker = "NO_ELIGIBLE_NEXT_CITY"
        elif args.city_key not in {"auto", selected_city}:
            blocker = f"REQUESTED_CITY_DOES_NOT_MATCH_DETERMINISTIC_SELECTION:{args.city_key}:{selected_city}"
        elif selected_city != "sevastopol":
            blocker = f"UNSUPPORTED_SELECTED_CITY_WITHOUT_VALIDATED_ADAPTER:{selected_city}"

    if blocker is None:
        pilot_repo_path = RESEARCH / f"historical_attack_event_discovery_pilot_{selected_city}_2026-09-27.json"
        pilot_tmp = out / "pilot.json"
        pilot = run_sevastopol_pilot(args.max_episodes, pilot_tmp)
        if "BLOCKED" in str(pilot.get("verdict") or ""):
            blocker = str(pilot.get("verdict"))
    else:
        pilot_repo_path = RESEARCH / "historical_attack_event_discovery_pilot_diagnostic_2026-09-27.json"
        pilot = {
            "schema_version": 1,
            "kind": "historical_attack_event_discovery_pilot_diagnostic",
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "starting_head": workflow_input_head,
            "workflow_run_id": WORKFLOW_RUN_ID,
            "blocker": blocker,
            "eligible_candidates": candidates,
            "selected_city": selected_city,
            "verdict": f"HISTORICAL ATTACK-EVENT DISCOVERY PILOT BLOCKED — {blocker}",
        }
        dump_json(out / "pilot.json", pilot)

    after_blobs = protected_blobs()
    protected_clean = before_blobs == after_blobs
    if not protected_clean and blocker is None:
        blocker = "PROTECTED_FILES_CHANGED"

    refactor = {
        "schema_version": 1,
        "kind": "historical_attack_event_source_adapter_refactor",
        "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "task_starting_head": TASK_STARTING_HEAD,
        "workflow_input_head": workflow_input_head,
        "files_inspected_for_duplicate_adapter_functionality": [
            "kyiv-air-alerts-grafana/scripts/discover_historical_attack_events.py",
            "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py",
            ".github/workflows/historical-attack-event-discovery-pilot.yml",
            "research/historical_ppo_source_inventory.json",
            "research/historical_replay_status_current.json",
            "research/historical_replay_source_retention/index.json",
        ],
        "reusable_adapters": [
            "SourceLocalHtmlArchiveAdapter",
            "PublicTelegramAdapter",
            "ExactUrlHtmlPreflightAdapter",
        ],
        "files_changed_for_refactor": [
            "kyiv-air-alerts-grafana/scripts/historical_attack_event_sources.py",
            "kyiv-air-alerts-grafana/scripts/discover_historical_attack_events.py",
            "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_source_adapter_pilot.py",
            ".github/workflows/historical-attack-event-discovery-pilot.yml",
        ],
        "before_structure": "Lviv pilot worker owned source-local HTML, linked public Telegram, exact-URL HTML retrieval and classifier orchestration in one script.",
        "after_structure": "Reusable adapters own bounded discover/fetch/parse/normalize/provenance primitives; the existing worker and pilot runner hand observations to monitor_explosion_candidates.py for all classification.",
        "network_bounds": {
            "explicit_user_agent": True,
            "timeout_seconds": 15,
            "max_retries": 2,
            "rate_limit_seconds": 0.2,
            "max_archive_articles_per_day": 80,
            "max_telegram_pages": 100,
            "max_neighbor_previous": 3,
            "bounded_pagination": True,
            "canonical_source_deduplication": True,
            "telegram_public_web_only": True,
            "telegram_api_credentials": False,
        },
        "evidence_observation_contract": [
            "observation_id",
            "source_type",
            "source",
            "source_url",
            "telegram_channel",
            "telegram_message_id",
            "source_timestamp",
            "event_timestamp_if_stated",
            "excerpt",
            "matched_terms",
            "event_types_supported",
            "exact_city_binding",
            "air_attack_context",
            "same_attack_context",
            "temporal_binding",
            "classification_outcome",
            "classification_episode_id",
            "classification_reason_codes",
            "content_hash",
            "provenance",
        ],
        "source_adapter_self_test": {
            "return_code": worker_self.returncode,
            "passed": worker_self.returncode == 0,
            "stdout": worker_self.stdout[-2000:],
        },
        "classifier_self_test": {
            "return_code": classifier_self.returncode,
            "passed": classifier_self.returncode == 0,
            "stdout": classifier_self.stdout[-2000:],
        },
        "classifier_control_replay": audit or {
            "return_code": audit_rc,
            "stdout_tail": audit_text[-4000:],
        },
        "lviv_regression": lviv,
        "protected_blobs_before": before_blobs,
        "protected_blobs_after": after_blobs,
        "protected_files_unchanged": protected_clean,
        "excluded_active_parallel_work_cities": sorted(ACTIVE_EXCLUSIONS),
        "eligible_next_city_candidates": candidates,
        "deterministic_city_selection": {
            "rule": "complete current corpus; no active blocker; retained positive control; deterministic autonomous public source; smallest episode universe; tie-break city_key",
            "selected_city": selected_city,
        },
        "pilot_workflow_run_id": WORKFLOW_RUN_ID,
        "blocker": blocker,
        "verdict": (
            "ATTACK-EVENT SOURCE ADAPTER REFACTOR CLEAN"
            if blocker is None and protected_clean
            else f"ATTACK-EVENT SOURCE ADAPTER REFACTOR BLOCKED — {blocker or 'PROTECTED_FILES_CHANGED'}"
        ),
    }
    dump_json(out / "refactor.json", refactor)
    (out / "pilot_repo_path.txt").write_text(
        str(pilot_repo_path.relative_to(CHECKOUT_ROOT)).replace(os.sep, "/") + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "refactor_verdict": refactor["verdict"],
        "selected_city": selected_city,
        "pilot_verdict": pilot.get("verdict"),
        "classifier_control_replay": {
            "evaluated_candidates": (audit or {}).get("evaluated_candidates"),
            "changed_candidate_count": (audit or {}).get("changed_candidate_count"),
            "uncontrolled_drift_count": (audit or {}).get("uncontrolled_drift_count"),
            "approved_regression_count": (audit or {}).get("approved_regression_count"),
        },
        "lviv_regression": {
            "passed": lviv.get("passed"),
            "rediscovered": lviv.get("rediscovered_strict_control_count"),
            "retained": lviv.get("retained_control_count"),
        },
        "pilot_summary": pilot.get("qa_summary"),
        "protected_files_unchanged": protected_clean,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
