#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import monitor_explosion_candidates as monitor
import replay_explosion_history as replay
import run_historical_attack_event_source_adapter_pilot as pilot_runner
from historical_attack_event_sources import (
    NetworkBounds,
    PublicTelegramAdapter,
    SourceLocalHtmlArchiveAdapter,
    canonical_observation_id,
    content_hash,
)

ROOT = Path(__file__).resolve().parents[1]
CHECKOUT_ROOT = ROOT.parent
RESEARCH = CHECKOUT_ROOT / "research"
REGISTRY_PATH = RESEARCH / "historical_attack_event_source_registry.json"
STATUS_PATH = RESEARCH / "historical_attack_event_backfill_status.json"
REPLAY_STATUS_PATH = RESEARCH / "historical_replay_status_current.json"
UTC = timezone.utc
KYIV_TZ = ZoneInfo("Europe/Kyiv")
NORMALIZATION_VERSION = "historical-attack-event-observation-v1"
DEFAULT_CAMPAIGN_ID = "historical-attack-events-v1-2026-09-27"
LATE_WINDOW_HOURS = 72
PRE_ALERT_WINDOW_HOURS = 3

DISCOVERY_RE = re.compile(
    r"(?:вибух|взрыв|влуч|попад|приліт|прилет|удар|пошкод|поврежд|"
    r"пожеж|пожар|загор|займан|атак|обстріл|обстрел|ппо|пво|"
    r"протиповітр|противовоздуш)",
    re.IGNORECASE,
)
AIR_DEFENSE_RE = re.compile(r"(?:\bппо\b|\bпво\b|протиповітр\w*|противовоздуш\w*)", re.IGNORECASE)
AIR_DEFENSE_ACTION_RE = re.compile(
    r"(?:працю\w*.{0,25}(?:ппо|протиповітр)|робот\w*.{0,25}(?:ппо|пво)|"
    r"(?:ппо|пво).{0,25}(?:працю\w*|работ\w*))",
    re.IGNORECASE,
)
INTERCEPTION_RE = re.compile(
    r"(?:збит\w*|знищен\w*|перехоп\w*|сбит\w*|уничтожен\w*|перехвачен\w*)",
    re.IGNORECASE,
)

PROTECTED_RELATIVE = [
    "data/explosion_audited_baseline.json",
    "data/explosion_review_queue.json",
    "data/explosion_candidate_monitor_state.json",
    "data/explosion_candidate_monitor_last_run.json",
    "data/explosions_test.json",
    "data/dashboard_data.json",
]


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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


def blob_for(path: Path) -> str:
    return git("hash-object", str(path.relative_to(CHECKOUT_ROOT)))


def version_identity() -> dict:
    return {
        "classifier_sha": blob_for(ROOT / "scripts" / "monitor_explosion_candidates.py"),
        "source_adapter_sha": blob_for(ROOT / "scripts" / "historical_attack_event_sources.py"),
        "orchestrator_sha": blob_for(Path(__file__).resolve()),
        "normalization_version": NORMALIZATION_VERSION,
    }


def protected_paths() -> list[Path]:
    paths = [ROOT / rel for rel in PROTECTED_RELATIVE]
    paths.extend(sorted((ROOT / "data" / "explosion_research").glob("*/final_evidence.json")))
    return [p for p in paths if p.exists()]


def protected_blobs() -> dict[str, str]:
    return {
        str(path.relative_to(CHECKOUT_ROOT)).replace(os.sep, "/"): blob_for(path)
        for path in protected_paths()
    }


def replay_ready_cities() -> list[dict]:
    doc = load_json(REPLAY_STATUS_PATH)
    out = []
    for key, row in sorted((doc.get("cities") or {}).items()):
        expected = int(row.get("expected_alert_episodes") or 0)
        reconstructed = int(row.get("reconstructed_alert_episodes") or 0)
        if row.get("source_status") == "READY" and expected > 0 and expected == reconstructed:
            out.append({
                "city_key": key,
                "total_episodes": expected,
                "replay_status": row.get("status"),
                "manual_qa_count": int(row.get("manual_qa_count") or 0),
            })
    return out


def source_registry() -> dict:
    return load_json(REGISTRY_PATH)


def load_city_episodes(city_key: str) -> list[dict]:
    episodes, _ = replay.load_historical_episodes(ROOT, city_key, monitor)
    return sorted(
        [dict(ep) for ep in episodes],
        key=lambda ep: (str(ep.get("alert_start") or ""), str(ep.get("episode_id") or "")),
    )


def campaign_status_template(campaign_id: str, versions: dict) -> dict:
    ready = {row["city_key"]: row for row in replay_ready_cities()}
    registry = source_registry()
    cities = {}
    for city_key, row in ready.items():
        cfg = (registry.get("cities") or {}).get(city_key) or {}
        discovery_ready = cfg.get("discovery_status") == "DISCOVERY_READY"
        cities[city_key] = {
            "total_episodes": row["total_episodes"],
            "discovery_ready": discovery_ready,
            "scanned_episodes": 0,
            "terminal_episodes": 0,
            "retryable_episodes": 0,
            "qa_episodes": 0,
            "last_completed_batch": 0,
            "campaign_version": versions,
            "classifier_sha": versions["classifier_sha"],
            "adapter_sha": versions["source_adapter_sha"],
            "updated_at": now_iso(),
            "status": "QUEUED" if discovery_ready else "BLOCKED_SOURCE_ADAPTER",
            "episode_states": {},
        }
    return {
        "schema_version": 1,
        "campaign_id": campaign_id,
        "campaign_branch": "historical-attack-event-backfill-2026-09-27",
        "campaign_version": versions,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "cities": cities,
    }


def ensure_compatible_version(status: dict, campaign_id: str, versions: dict) -> None:
    scanned = sum(int((row or {}).get("scanned_episodes") or 0) for row in (status.get("cities") or {}).values())
    if status.get("campaign_id") != campaign_id and scanned:
        raise RuntimeError("CAMPAIGN_ID_CHANGE_REQUIRES_NEW_STATUS_OR_EXPLICIT_RESCAN")
    old = status.get("campaign_version") or {}
    if old and old != versions and scanned:
        raise RuntimeError("VERSION_CHANGE_REQUIRES_NEW_CAMPAIGN_OR_EXPLICIT_RESCAN")


def terminal_state(value: str) -> bool:
    return value in {
        "STRICT_EVENT_POSITIVE",
        "SENSITIVITY_EVENT_POSITIVE",
        "NO_CONFIRMED_EVENT",
        "NEEDS_REVIEW",
        "SOURCE_ADAPTER_REQUIRED",
    }


def select_work(episodes: list[dict], city_state: dict, batch_size: int, start_index: int | None, resume: bool) -> list[dict]:
    if start_index is not None and not resume:
        return episodes[start_index:start_index + batch_size]
    states = city_state.get("episode_states") or {}
    out = []
    for ep in episodes:
        eid = str(ep.get("episode_id") or "")
        state = str((states.get(eid) or {}).get("state") or "")
        if terminal_state(state):
            continue
        out.append(ep)
        if len(out) >= batch_size:
            break
    return out


def local_days_for_batch(episodes: list[dict]) -> list[str]:
    days: set[date] = set()
    for ep in episodes:
        start = monitor.parse_dt(ep.get("alert_start"))
        end = monitor.parse_dt(ep.get("alert_end"))
        if not start or not end:
            continue
        cur = start.astimezone(KYIV_TZ).date()
        last = (end + timedelta(hours=LATE_WINDOW_HOURS)).astimezone(KYIV_TZ).date()
        while cur <= last:
            days.add(cur)
            cur += timedelta(days=1)
    if len(days) > 220:
        raise RuntimeError(f"BOUNDED_ARCHIVE_DAY_LIMIT_EXCEEDED:{len(days)}")
    return [d.isoformat() for d in sorted(days)]


def ppo_fields(text: str) -> dict:
    return {
        "air_defense_context": bool(AIR_DEFENSE_RE.search(text)),
        "air_defense_action": bool(AIR_DEFENSE_ACTION_RE.search(text)),
        "interception_claim": bool(INTERCEPTION_RE.search(text)),
    }


def matched_terms(text: str) -> list[str]:
    terms = list(monitor.attack_event_types(text))
    ppo = ppo_fields(text)
    if ppo["air_defense_context"]:
        terms.append("air_defense_context")
    if ppo["interception_claim"]:
        terms.append("interception_claim")
    return terms


def classify_row(city_key: str, row: dict, episodes: list[dict], *, source_family: str, source_type: str,
                 source_timestamp: str | None, excerpt: str, source_url: str,
                 telegram_channel: str | None = None, telegram_message_id: int | None = None,
                 retrieval_provenance: dict | None = None) -> dict:
    matching = monitor.match_candidate_to_episodes(row, episodes)
    if source_type.endswith("telegram") and source_timestamp:
        active = monitor.exact_active_episodes_at(monitor.parse_dt(source_timestamp), episodes)
        if len(active) == 1:
            row["matched_episode_id"] = str(active[0].get("episode_id") or "")
    decision = monitor.classify_candidate(row, city_key, episodes, matching)
    temporal = decision.get("temporal_binding") or {}
    if telegram_channel and telegram_message_id is not None:
        observation_id = canonical_observation_id(telegram_channel, telegram_message_id)
        c_hash = content_hash(telegram_channel, telegram_message_id, source_timestamp, excerpt)
    else:
        observation_id = hashlib.sha256(f"{source_type}|{source_url}".encode("utf-8")).hexdigest()[:24]
        c_hash = content_hash(source_url, source_timestamp, excerpt)
    out = {
        "observation_id": observation_id,
        "source_family": source_family,
        "source_type": source_type,
        "source_url": source_url,
        "telegram_channel": telegram_channel,
        "telegram_message_id": telegram_message_id,
        "source_timestamp": source_timestamp,
        "event_timestamp_if_stated": temporal.get("event_time"),
        "excerpt": excerpt[:1200],
        "content_hash": c_hash,
        "matched_discovery_terms": matched_terms(excerpt),
        "event_types": list(decision.get("event_types") or []),
        "exact_city_evidence": decision.get("exact_city_classification_evidence"),
        "aerial_war_context": decision.get("air_military_context"),
        "same_attack_context": decision.get("same_attack_context"),
        "temporal_binding": temporal,
        "classifier_reason_codes": list(decision.get("reason_codes") or []),
        "classification_outcome": decision.get("proposed_outcome"),
        "classification_episode_id": decision.get("proposed_matched_episode_id"),
        "candidate_matching": matching,
        "retrieval_provenance": retrieval_provenance or {},
    }
    out.update(ppo_fields(excerpt))
    return out


def html_candidate(city_key: str, family: dict, article: dict) -> dict:
    text = " ".join(x for x in (str(article.get("title") or ""), str(article.get("text") or "")) if x)
    return {
        "source": family["source_family"],
        "title": str(article.get("title") or "")[:240],
        "url": article["url"],
        "publisher": family.get("publisher") or family["source_family"],
        "publisher_url": family.get("domain"),
        "published_at": article.get("published_at"),
        "snippet": str(article.get("text") or "")[:1200],
        "matched_text_excerpt": str(article.get("text") or "")[:50000],
        "discovery_basis": "historical_source_local_html",
        "city_key": city_key,
        "_classification_text": text,
    }


def telegram_candidate(city_key: str, family: dict, post: dict, basis: str) -> dict:
    text = str(post.get("text") or "")
    return {
        "source": f"Telegram / {family.get('publisher') or post.get('channel')}",
        "title": text[:240] or f"Telegram post {post.get('message_id')}",
        "url": post["url"],
        "publisher": family.get("publisher") or post.get("channel"),
        "publisher_url": f"https://t.me/{post.get('channel')}",
        "published_at": post.get("published_at"),
        "snippet": text[:1200],
        "matched_text_excerpt": text,
        "discovery_basis": basis,
        "candidate_id": canonical_observation_id(str(post.get("channel")), int(post.get("message_id"))),
        "city_key": city_key,
    }


def dedupe_observations(rows: list[dict]) -> list[dict]:
    seen = {}
    for row in rows:
        if row.get("telegram_channel") and row.get("telegram_message_id") is not None:
            key = ("telegram", str(row["telegram_channel"]).casefold(), int(row["telegram_message_id"]))
        else:
            key = ("web", str(row.get("source_url") or ""), str(row.get("content_hash") or ""))
        seen[key] = row
    return sorted(seen.values(), key=lambda x: (str(x.get("source_timestamp") or ""), str(x.get("observation_id") or "")))


def discover_batch(city_key: str, episodes: list[dict], cfg: dict) -> tuple[list[dict], dict, bool]:
    observations: list[dict] = []
    diagnostics = []
    enabled = [x for x in (cfg.get("source_families") or []) if x.get("enabled")]
    coverage_complete = True
    bounds = NetworkBounds(timeout_seconds=15, max_retries=2, rate_limit_seconds=0.2, max_telegram_pages=60, max_neighbor_previous=3)

    for family in enabled:
        family_ok = True
        meta = {"source_family": family.get("source_family"), "adapter_type": family.get("adapter_type")}
        try:
            if family.get("adapter_type") == "SourceLocalHtmlArchiveAdapter":
                adapter = SourceLocalHtmlArchiveAdapter("suspilne", family["section"], bounds)
                days = local_days_for_batch(episodes)
                articles, fetch_meta = adapter.fetch_days(days)
                meta["fetch"] = fetch_meta
                meta["late_window_hours"] = LATE_WINDOW_HOURS
                linked_seen = set()
                tg = PublicTelegramAdapter(bounds)
                for article in articles:
                    row = html_candidate(city_key, family, article)
                    text = str(row.get("_classification_text") or "")
                    if not monitor.city_mentioned(city_key, text) or not DISCOVERY_RE.search(text):
                        continue
                    observations.append(classify_row(
                        city_key, row, episodes,
                        source_family=family["source_family"],
                        source_type="source_local_html",
                        source_timestamp=article.get("published_at"),
                        excerpt=text,
                        source_url=article["url"],
                        retrieval_provenance={
                            "adapter": "SourceLocalHtmlArchiveAdapter",
                            "archive_local_day": article.get("archive_local_day"),
                            "archive_url": (article.get("raw_metadata") or {}).get("archive_url"),
                            "late_window_hours": LATE_WINDOW_HOURS,
                        },
                    ))
                    for ref in (article.get("telegram_links") or [])[:6]:
                        key = (str(ref.get("channel") or "").casefold(), int(ref.get("message_id") or 0))
                        if key in linked_seen or len(linked_seen) >= int(family.get("max_linked_telegram_posts") or 12):
                            continue
                        linked_seen.add(key)
                        post, pmeta = tg.fetch_exact_post(str(ref["channel"]), int(ref["message_id"]))
                        linked_posts = []
                        if post:
                            linked_posts.append(post)
                            neighbors, nmeta = tg.fetch_neighbor_window(str(ref["channel"]), int(ref["message_id"]), previous_count=3)
                            linked_posts.extend(neighbors)
                        else:
                            nmeta = None
                        for linked in linked_posts:
                            ltext = str(linked.get("text") or "")
                            if not monitor.city_mentioned(city_key, ltext) or not DISCOVERY_RE.search(ltext):
                                continue
                            crow = telegram_candidate(city_key, family, linked, "article_linked_public_telegram")
                            observations.append(classify_row(
                                city_key, crow, episodes,
                                source_family=family["source_family"],
                                source_type="article_linked_public_telegram",
                                source_timestamp=linked.get("published_at"),
                                excerpt=ltext,
                                source_url=linked["url"],
                                telegram_channel=str(linked["channel"]),
                                telegram_message_id=int(linked["message_id"]),
                                retrieval_provenance={
                                    "adapter": "PublicTelegramAdapter",
                                    "parent_article_url": article["url"],
                                    "exact_post_fetch": pmeta,
                                    "neighbor_fetch": nmeta,
                                },
                            ))
                meta["linked_telegram_posts_requested"] = len(linked_seen)

            elif family.get("adapter_type") == "PublicTelegramAdapter":
                adapter = PublicTelegramAdapter(bounds)
                start = min(monitor.parse_dt(ep.get("alert_start")) for ep in episodes) - timedelta(hours=PRE_ALERT_WINDOW_HOURS)
                end = max(monitor.parse_dt(ep.get("alert_end")) for ep in episodes) + timedelta(hours=LATE_WINDOW_HOURS)
                posts = {}
                searches = []
                for query in family.get("queries") or [family.get("city_query")]:
                    if not query:
                        continue
                    rows, smeta = adapter.search(
                        family["channel"], str(query), start, end,
                        max_pages=int(family.get("max_pages") or 60),
                    )
                    searches.append(smeta)
                    for post in rows:
                        posts[(str(post["channel"]).casefold(), int(post["message_id"]))] = post
                meta["searches"] = searches
                meta["late_window_hours"] = LATE_WINDOW_HOURS
                for post in posts.values():
                    text = str(post.get("text") or "")
                    if not monitor.city_mentioned(city_key, text) or not DISCOVERY_RE.search(text):
                        continue
                    row = telegram_candidate(city_key, family, post, "bounded_public_telegram_search")
                    observations.append(classify_row(
                        city_key, row, episodes,
                        source_family=family["source_family"],
                        source_type="public_telegram",
                        source_timestamp=post.get("published_at"),
                        excerpt=text,
                        source_url=post["url"],
                        telegram_channel=str(post["channel"]),
                        telegram_message_id=int(post["message_id"]),
                        retrieval_provenance={
                            "adapter": "PublicTelegramAdapter",
                            "query_window_start": start.isoformat().replace("+00:00", "Z"),
                            "query_window_end": end.isoformat().replace("+00:00", "Z"),
                            "late_window_hours": LATE_WINDOW_HOURS,
                        },
                    ))
            else:
                raise RuntimeError(f"UNSUPPORTED_ADAPTER:{family.get('adapter_type')}")
        except Exception as exc:
            family_ok = False
            coverage_complete = False
            meta["error"] = f"{type(exc).__name__}: {exc}"
        meta["resolved"] = family_ok
        diagnostics.append(meta)

    if not enabled:
        coverage_complete = False
    return dedupe_observations(observations), {"source_families": diagnostics}, coverage_complete


def retained_strict_ids(city_key: str, episodes: list[dict]) -> set[str]:
    path = ROOT / "data" / "explosion_research" / city_key / "final_evidence.json"
    if not path.exists():
        return set()
    doc = load_json(path)
    out = set()
    for row in doc.get("strict_events") or []:
        eid = str(row.get("episode_id") or "")
        if not eid:
            try:
                eid = str((replay.bind_evidence_record(row, episodes, monitor) or {}).get("episode_id") or "")
            except Exception:
                eid = ""
        if eid:
            out.add(eid)
    return out


def observation_episode_refs(obs: dict) -> set[str]:
    refs = set()
    if obs.get("classification_episode_id"):
        refs.add(str(obs["classification_episode_id"]))
    matching = obs.get("candidate_matching") or {}
    if matching.get("matched_episode_id"):
        refs.add(str(matching["matched_episode_id"]))
    refs.update(str(x) for x in (matching.get("matched_episode_ids") or []) if x)
    return refs


def residual_qa(obs_rows: list[dict]) -> list[str]:
    out = set()
    for obs in obs_rows:
        codes = " ".join(str(x) for x in (obs.get("classifier_reason_codes") or []))
        temporal_code = str((obs.get("temporal_binding") or {}).get("code") or "")
        if "AMBIGUOUS" in temporal_code or "MATCH_AMBIGUOUS" in codes:
            out.add("TEMPORAL_AMBIGUITY")
        exact = obs.get("exact_city_evidence") or {}
        if obs.get("classification_outcome") == "needs_review" and not exact.get("present"):
            out.add("CITY_AMBIGUITY")
        if "MULTI_INCIDENT" in codes or "AIR_CONTEXT_NOT_LINKED_TO_EVENT" in codes:
            out.add("MULTI_INCIDENT_CONTEXT_RISK")
        if not obs.get("source_url"):
            out.add("SOURCE_REFERENCE_INCOMPLETE")
        if "PROVENANCE" in codes:
            out.add("PROVENANCE_REQUIRED")
    return sorted(out)


def episode_results(city_key: str, episodes: list[dict], observations: list[dict], coverage_complete: bool) -> list[dict]:
    frozen_strict = retained_strict_ids(city_key, episodes)
    out = []
    for ep in episodes:
        eid = str(ep.get("episode_id") or "")
        related = [obs for obs in observations if eid in observation_episode_refs(obs)]
        strict = [obs for obs in related if obs.get("classification_outcome") == "approved_strict" and str(obs.get("classification_episode_id") or "") == eid]
        sensitivity = [obs for obs in related if obs.get("classification_outcome") == "approved_sensitivity" and str(obs.get("classification_episode_id") or "") == eid]
        review = [obs for obs in related if obs.get("classification_outcome") == "needs_review"]
        qa = set(residual_qa(related))
        if eid in frozen_strict and not strict and related:
            qa.add("CURRENT_RULE_DOWNGRADE")
        if not coverage_complete:
            state = "SOURCE_FETCH_RETRY_REQUIRED"
            qa.add("SOURCE_FETCH_RETRY_REQUIRED")
        elif strict:
            state = "STRICT_EVENT_POSITIVE"
        elif sensitivity:
            state = "SENSITIVITY_EVENT_POSITIVE"
        elif review or qa:
            state = "NEEDS_REVIEW"
        else:
            state = "NO_CONFIRMED_EVENT"
        strict_types = sorted({t for obs in strict for t in (obs.get("event_types") or [])})
        sensitivity_types = sorted({t for obs in strict + sensitivity for t in (obs.get("event_types") or [])})
        out.append({
            "episode_id": eid,
            "city": city_key,
            "alert_start": ep.get("alert_start"),
            "alert_end": ep.get("alert_end"),
            "discovery_coverage_status": "COMPLETE_FOR_CONFIGURED_FAMILIES" if coverage_complete else "SOURCE_FETCH_RETRY_REQUIRED",
            "source_observation_ids": [obs["observation_id"] for obs in related],
            "event_types_found": sorted({t for obs in related for t in (obs.get("event_types") or [])}),
            "classifier_result": state,
            "qa_reasons": sorted(qa),
            "air_defense_context": any(bool(obs.get("air_defense_context")) for obs in related),
            "air_defense_action": any(bool(obs.get("air_defense_action")) for obs in related),
            "interception_claim": any(bool(obs.get("interception_claim")) for obs in related),
            "event_positive_strict": bool(strict),
            "event_positive_sensitivity": bool(strict or sensitivity),
            "confirmed_event_types": strict_types,
            "sensitivity_event_types": sensitivity_types,
        })
    return out


def refresh_city_counts(city_state: dict) -> None:
    states = city_state.get("episode_states") or {}
    city_state["scanned_episodes"] = len(states)
    city_state["terminal_episodes"] = sum(terminal_state(str(x.get("state") or "")) for x in states.values())
    city_state["retryable_episodes"] = sum(str(x.get("state") or "") == "SOURCE_FETCH_RETRY_REQUIRED" for x in states.values())
    city_state["qa_episodes"] = sum(bool(x.get("qa_reasons")) for x in states.values())


def run_one_batch(args) -> dict:
    versions = version_identity()
    registry = source_registry()
    status = load_json(STATUS_PATH) if STATUS_PATH.exists() else campaign_status_template(args.campaign_id, versions)
    ensure_compatible_version(status, args.campaign_id, versions)
    if status.get("campaign_id") != args.campaign_id:
        status = campaign_status_template(args.campaign_id, versions)
    if status.get("campaign_version") != versions:
        status["campaign_version"] = versions
        for row in (status.get("cities") or {}).values():
            row["campaign_version"] = versions
            row["classifier_sha"] = versions["classifier_sha"]
            row["adapter_sha"] = versions["source_adapter_sha"]

    ready = [row["city_key"] for row in replay_ready_cities()]
    if args.city_key == "auto":
        priority = registry.get("priority") or sorted(ready)
        city_key = next((
            key for key in priority
            if key in ready
            and ((registry.get("cities") or {}).get(key) or {}).get("discovery_status") == "DISCOVERY_READY"
            and ((status.get("cities") or {}).get(key) or {}).get("status") not in {"COMPLETE", "BLOCKED_SOURCE_ADAPTER", "BLOCKED_SOURCE_FAILURE"}
        ), None)
        if city_key is None:
            return {"ok": True, "new_work": 0, "reason": "NO_ELIGIBLE_WORK", "campaign_id": args.campaign_id}
    else:
        city_key = args.city_key

    cfg = (registry.get("cities") or {}).get(city_key) or {}
    if cfg.get("discovery_status") != "DISCOVERY_READY":
        return {"ok": False, "new_work": 0, "city_key": city_key, "reason": "SOURCE_ADAPTER_REQUIRED"}

    city_state = (status.get("cities") or {}).get(city_key)
    if not city_state:
        raise RuntimeError(f"CITY_NOT_REPLAY_READY:{city_key}")
    episodes = load_city_episodes(city_key)
    selected = select_work(episodes, city_state, args.batch_size, args.start_index, args.resume)
    if not selected:
        city_state["status"] = "COMPLETE"
        city_state["updated_at"] = now_iso()
        status["updated_at"] = now_iso()
        dump_json(STATUS_PATH, status)
        return {"ok": True, "new_work": 0, "city_key": city_key, "reason": "CITY_COMPLETE"}

    observations, retrieval, coverage_complete = discover_batch(city_key, selected, cfg)
    results = episode_results(city_key, selected, observations, coverage_complete)
    batch_number = int(city_state.get("last_completed_batch") or 0) + 1

    for result in results:
        eid = result["episode_id"]
        prior = (city_state.get("episode_states") or {}).get(eid) or {}
        attempts = int(prior.get("attempts") or 0)
        if result["classifier_result"] == "SOURCE_FETCH_RETRY_REQUIRED":
            attempts += 1
        city_state.setdefault("episode_states", {})[eid] = {
            "state": result["classifier_result"],
            "qa_reasons": result["qa_reasons"],
            "attempts": attempts,
            "batch": batch_number,
            "updated_at": now_iso(),
        }

    city_state["last_completed_batch"] = batch_number
    refresh_city_counts(city_state)
    blocked_retry = any(
        str(x.get("state") or "") == "SOURCE_FETCH_RETRY_REQUIRED" and int(x.get("attempts") or 0) >= args.max_retries
        for x in (city_state.get("episode_states") or {}).values()
    )
    if city_state["terminal_episodes"] >= city_state["total_episodes"]:
        city_state["status"] = "COMPLETE"
    elif blocked_retry:
        city_state["status"] = "BLOCKED_SOURCE_FAILURE"
    else:
        city_state["status"] = "RUNNING"
    city_state["updated_at"] = now_iso()
    status["updated_at"] = now_iso()

    batch = {
        "schema_version": 1,
        "campaign_id": args.campaign_id,
        "campaign_version": versions,
        "city_key": city_key,
        "batch_number": batch_number,
        "batch_size": args.batch_size,
        "late_damage_fire_window_hours": LATE_WINDOW_HOURS,
        "source_registry_blob": blob_for(REGISTRY_PATH),
        "generated_at": now_iso(),
        "episode_results": results,
        "observations": observations,
        "retrieval_diagnostics": retrieval,
        "protected_data_mutated": False,
    }
    batch_path = args.output_dir / args.campaign_id / city_key / f"batch_{batch_number:06d}.json"
    dump_json(batch_path, batch)
    dump_json(STATUS_PATH, status)
    return {
        "ok": True,
        "new_work": len(selected),
        "city_key": city_key,
        "batch_number": batch_number,
        "batch_path": str(batch_path.relative_to(CHECKOUT_ROOT)).replace(os.sep, "/"),
        "status_path": str(STATUS_PATH.relative_to(CHECKOUT_ROOT)).replace(os.sep, "/"),
        "city_status": city_state["status"],
        "strict_positive": sum(x["event_positive_strict"] for x in results),
        "sensitivity_positive": sum(x["event_positive_sensitivity"] for x in results),
        "retryable": sum(x["classifier_result"] == "SOURCE_FETCH_RETRY_REQUIRED" for x in results),
        "qa": sum(bool(x["qa_reasons"]) for x in results),
    }


def run_json_command(args: list[str]) -> tuple[dict | None, str, int]:
    proc = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    text = proc.stdout
    start = text.find("{")
    payload = None
    if start >= 0:
        try:
            payload = json.loads(text[start:])
        except json.JSONDecodeError:
            payload = None
    return payload, text, proc.returncode


def self_test() -> dict:
    episodes = [{"episode_id": f"e{i}", "alert_start": f"2026-01-0{i+1}T00:00:00Z"} for i in range(5)]
    state = {"episode_states": {}, "last_completed_batch": 0}
    first = select_work(episodes, state, 2, None, True)
    assert [x["episode_id"] for x in first] == ["e0", "e1"]
    for ep in first:
        state["episode_states"][ep["episode_id"]] = {"state": "NO_CONFIRMED_EVENT"}
    resumed = select_work(episodes, state, 2, None, True)
    assert [x["episode_id"] for x in resumed] == ["e2", "e3"]
    for ep in resumed:
        state["episode_states"][ep["episode_id"]] = {"state": "NO_CONFIRMED_EVENT"}
    third = select_work(episodes, state, 2, None, True)
    assert [x["episode_id"] for x in third] == ["e4"]
    state["episode_states"]["e4"] = {"state": "NO_CONFIRMED_EVENT"}
    assert select_work(episodes, state, 2, None, True) == []

    duplicate = {
        "observation_id": "a",
        "source_url": "https://example.invalid/a",
        "content_hash": "x",
        "source_timestamp": "2026-01-01T00:00:00Z",
    }
    assert len(dedupe_observations([dict(duplicate), dict(duplicate)])) == 1

    base = {
        "campaign_id": "c1",
        "campaign_version": {"classifier_sha": "a"},
        "cities": {"x": {"scanned_episodes": 1}},
    }
    version_blocked = False
    try:
        ensure_compatible_version(base, "c1", {"classifier_sha": "b"})
    except RuntimeError as exc:
        version_blocked = "VERSION_CHANGE" in str(exc)
    assert version_blocked

    uninterrupted = {ep["episode_id"]: "NO_CONFIRMED_EVENT" for ep in episodes}
    resumed_final = {eid: row["state"] for eid, row in state["episode_states"].items()}
    assert uninterrupted == resumed_final
    return {
        "restart_proof": "PASS",
        "completed_batch_rerun": False,
        "unfinished_work_resumed": True,
        "duplicate_observations": 0,
        "uninterrupted_equivalence": True,
        "second_resume_new_work": 0,
        "idempotence": "PASS",
        "version_change_protection": "PASS",
    }


def foundation_acceptance(output: Path) -> dict:
    before = protected_blobs()
    self_result = self_test()
    worker = subprocess.run(
        [sys.executable, "scripts/discover_historical_attack_events.py", "--self-test"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    classifier = subprocess.run(
        [sys.executable, "scripts/monitor_explosion_candidates.py", "--self-test"],
        cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
    )
    audit, audit_text, audit_rc = run_json_command([sys.executable, "scripts/audit_attack_event_classifier.py"])

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        lviv_path = tmp / "lviv.json"
        lviv_proc = subprocess.run(
            [sys.executable, "scripts/discover_historical_attack_events.py", "--city", "lviv", "--max-episodes", "40", "--output", str(lviv_path)],
            cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        lviv = load_json(lviv_path) if lviv_path.exists() else {}
        sev_path = tmp / "sevastopol.json"
        sev = pilot_runner.run_sevastopol_pilot(40, sev_path)

    l_controls = lviv.get("controls") or {}
    l_summary = lviv.get("summary") or {}
    lviv_pass = (
        lviv_proc.returncode == 0
        and l_summary.get("selected_episode_count") == 40
        and l_controls.get("retained_control_count") == 7
        and l_controls.get("rediscovered_strict_control_count") == 7
        and l_controls.get("newly_strict_episode_ids_vs_retained_controls") == []
        and l_summary.get("event_positive_episode_count") == 7
    )
    sev_q = sev.get("qa_summary") or {}
    sev_diag = ((sev.get("control_recovery") or {}).get("missed_control_diagnostics") or [])
    sev_downgrades = sum(x.get("gap_code") == "CURRENT_RULE_DOWNGRADE" for x in sev_diag)
    sev_pass = (
        sev_q.get("selected_alert_episodes") == 40
        and sev_q.get("strict_observations") == 0
        and sev_q.get("sensitivity_observations") == 0
        and sev_q.get("needs_review_observations") == 4
        and sev_downgrades == 3
    )
    drift_pass = bool(audit) and audit_rc == 0 and int(audit.get("uncontrolled_drift_count") or 0) == 0 and int(audit.get("approved_regression_count") or 0) == 0
    after = protected_blobs()
    protected_clean = before == after

    ready = replay_ready_cities()
    registry = source_registry()
    ready_keys = [x["city_key"] for x in ready]
    discovery_ready = [
        key for key in ready_keys
        if ((registry.get("cities") or {}).get(key) or {}).get("discovery_status") == "DISCOVERY_READY"
    ]
    adapter_required = [key for key in ready_keys if key not in discovery_ready]
    eligible = sum(x["total_episodes"] for x in ready if x["city_key"] in discovery_ready)
    versions = version_identity()

    checks = {
        "source_adapter_self_test": worker.returncode == 0,
        "classifier_self_test": classifier.returncode == 0,
        "classifier_control_replay": drift_pass,
        "lviv_acceptance": lviv_pass,
        "sevastopol_acceptance": sev_pass,
        "restart_idempotence": self_result,
        "protected_files_unchanged": protected_clean,
    }
    all_pass = all([
        checks["source_adapter_self_test"],
        checks["classifier_self_test"],
        checks["classifier_control_replay"],
        checks["lviv_acceptance"],
        checks["sevastopol_acceptance"],
        protected_clean,
    ])

    artifact = {
        "schema_version": 1,
        "kind": "historical_attack_event_autonomous_backfill_foundation",
        "generated_at": now_iso(),
        "actual_starting_head": os.getenv("FOUNDATION_STARTING_HEAD") or git("rev-parse", "HEAD^"),
        "campaign_branch": "historical-attack-event-backfill-2026-09-27",
        "campaign_id": DEFAULT_CAMPAIGN_ID,
        "state_location": "research/historical_attack_event_backfill_status.json",
        "campaign_architecture": {
            "batch_runner": "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py",
            "batch_artifact_layout": "research/historical_attack_event_backfill/<campaign_id>/<city>/batch_000001.json",
            "workflow": ".github/workflows/historical-attack-event-backfill.yml",
            "default_batch_size": 50,
            "late_damage_fire_window_hours": LATE_WINDOW_HOURS,
            "same_campaign_resume_requires_same_versions": True,
            "scheduled_resume_declared": True,
            "scheduled_resume_activation_note": "GitHub cron executes the workflow only after this workflow exists on the repository default branch; the campaign branch itself remains isolated and no full campaign is started by this foundation task.",
        },
        "code_version_identity": versions,
        "source_registry": {
            "path": "research/historical_attack_event_source_registry.json",
            "blob_sha": blob_for(REGISTRY_PATH),
        },
        "replay_ready_cities": ready,
        "discovery_ready_cities": discovery_ready,
        "source_adapter_required_cities": adapter_required,
        "total_episodes_currently_eligible_for_autonomous_scan": eligible,
        "event_taxonomy": list(monitor.ATTACK_EVENT_TYPE_ORDER),
        "ppo_contract": {
            "air_defense_context_separate": True,
            "air_defense_action_separate": True,
            "interception_claim_separate": True,
            "ppo_only_sets_event_positive": False,
        },
        "checkpoint_schema": {
            "status_path": "research/historical_attack_event_backfill_status.json",
            "per_city_fields": [
                "total_episodes", "discovery_ready", "scanned_episodes", "terminal_episodes",
                "retryable_episodes", "qa_episodes", "last_completed_batch", "campaign_version",
                "classifier_sha", "adapter_sha", "updated_at", "status", "episode_states",
            ],
            "terminal_states": ["STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE", "NO_CONFIRMED_EVENT", "NEEDS_REVIEW"],
            "retryable_state": "SOURCE_FETCH_RETRY_REQUIRED",
            "blocked_state": "SOURCE_ADAPTER_REQUIRED",
        },
        "workflow_design": {
            "manual_workflow_dispatch": True,
            "scheduled_resume": True,
            "concurrency_protection": True,
            "no_force_push": True,
            "stale_writer_guard": True,
            "batch_checkpoint_atomic_commit": True,
            "full_campaign_started": False,
        },
        "acceptance_test_results": {
            "classifier_drift": {
                "passed": drift_pass,
                "uncontrolled_drift_count": (audit or {}).get("uncontrolled_drift_count"),
                "approved_regression_count": (audit or {}).get("approved_regression_count"),
                "stdout_tail": audit_text[-1200:],
            },
            "lviv": {
                "passed": lviv_pass,
                "selected_episodes": l_summary.get("selected_episode_count"),
                "retained_controls": l_controls.get("retained_control_count"),
                "rediscovered_controls": l_controls.get("rediscovered_strict_control_count"),
                "new_unsupported_strict": l_controls.get("newly_strict_episode_ids_vs_retained_controls"),
            },
            "sevastopol": {
                "passed": sev_pass,
                "selected_episodes": sev_q.get("selected_alert_episodes"),
                "strict": sev_q.get("strict_observations"),
                "sensitivity": sev_q.get("sensitivity_observations"),
                "needs_review": sev_q.get("needs_review_observations"),
                "current_rule_downgrades": sev_downgrades,
            },
        },
        "restart_idempotence_proof": self_result,
        "version_change_proof": {
            "passed": self_result["version_change_protection"] == "PASS",
            "behavior": "same campaign with processed episodes rejects incompatible classifier/adapter/orchestrator/normalization identity",
        },
        "protected_file_verification": {
            "unchanged": protected_clean,
            "before": before,
            "after": after,
        },
        "exact_code_workflow_files_changed": [
            "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py",
            "research/historical_attack_event_source_registry.json",
            "research/historical_attack_event_backfill_status.json",
            ".github/workflows/historical-attack-event-backfill.yml",
            "research/historical_attack_event_autonomous_backfill_foundation_2026-09-27.json",
        ],
        "checks": checks,
        "verdict": (
            "AUTONOMOUS HISTORICAL ATTACK-EVENT BACKFILL FOUNDATION READY"
            if all_pass
            else "AUTONOMOUS HISTORICAL ATTACK-EVENT BACKFILL FOUNDATION BLOCKED — ACCEPTANCE_FAILURE"
        ),
    }
    dump_json(output, artifact)
    return artifact


def main() -> None:
    parser = argparse.ArgumentParser(description="Restart-safe historical attack-event discovery batch runner.")
    parser.add_argument("--campaign-id", default=DEFAULT_CAMPAIGN_ID)
    parser.add_argument("--city-key", default="auto")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--start-index", type=int)
    parser.add_argument("--output-dir", type=Path, default=RESEARCH / "historical_attack_event_backfill")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--resume", dest="resume", action="store_true")
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.set_defaults(resume=True)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--foundation-acceptance", action="store_true")
    parser.add_argument("--foundation-output", type=Path, default=RESEARCH / "historical_attack_event_autonomous_backfill_foundation_2026-09-27.json")
    args = parser.parse_args()

    if args.batch_size < 1 or args.batch_size > 200:
        raise SystemExit("batch-size must be 1..200")
    if args.self_test:
        print(json.dumps(self_test(), ensure_ascii=False, indent=2))
        return
    if args.foundation_acceptance:
        doc = foundation_acceptance(args.foundation_output)
        print(json.dumps({"verdict": doc["verdict"], "output": str(args.foundation_output)}, ensure_ascii=False, indent=2))
        return

    result = run_one_batch(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
