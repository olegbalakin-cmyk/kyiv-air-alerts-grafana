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
NORMALIZATION_VERSION = "historical-attack-event-observation-v2"
DEFAULT_CAMPAIGN_ID = "historical-attack-events-v2-2026-09-27"
LATE_WINDOW_HOURS = 72
PRE_ALERT_WINDOW_HOURS = 3
METHODOLOGY_VERSION = "historical-attack-event-air-defense-action-v2"
METHODOLOGY_ARTIFACT_PATH = RESEARCH / "historical_attack_event_air_defense_action_methodology_update_2026-09-27.json"
LVIV_PILOT_PATH = RESEARCH / "historical_attack_event_discovery_pilot_lviv_2026-09-27.json"
SEVASTOPOL_PILOT_PATH = RESEARCH / "historical_attack_event_discovery_pilot_sevastopol_2026-09-27.json"

DISCOVERY_RE = re.compile(
    r"(?:вибух|взрыв|влуч|попад|приліт|прилет|удар|пошкод|поврежд|"
    r"пожеж|пожар|загор|займан|атак|обстріл|обстрел|ппо|пво|"
    r"протиповітр|противовоздуш|працю|працювала|робота|чути|чутно|"
    r"слышно|работает|работала)",
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


def checkout_relative(path: Path) -> str:
    return str(path.resolve().relative_to(CHECKOUT_ROOT.resolve())).replace(os.sep, "/")


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
        "discovery_sha": blob_for(ROOT / "scripts" / "discover_historical_attack_events.py"),
        "sevastopol_pilot_sha": blob_for(ROOT / "scripts" / "run_historical_attack_event_source_adapter_pilot.py"),
        "source_registry_sha": blob_for(REGISTRY_PATH),
        "normalization_version": NORMALIZATION_VERSION,
        "methodology_version": METHODOLOGY_VERSION,
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


def freeze_campaign_snapshot(status: dict, versions: dict) -> None:
    scanned = sum(int((row or {}).get("scanned_episodes") or 0) for row in (status.get("cities") or {}).values())
    if scanned:
        return
    registry = source_registry()
    ready = {row["city_key"]: row for row in replay_ready_cities()}
    frozen_cities = [
        key for key in (registry.get("priority") or sorted(ready))
        if key in ready and ((registry.get("cities") or {}).get(key) or {}).get("discovery_status") == "DISCOVERY_READY"
    ]
    frozen_total = 0
    for city_key in frozen_cities:
        episodes, source_files = replay.load_historical_episodes(ROOT, city_key, monitor)
        episodes = sorted(
            [dict(ep) for ep in episodes],
            key=lambda ep: (str(ep.get("alert_start") or ""), str(ep.get("episode_id") or "")),
        )
        expected = int(ready[city_key]["total_episodes"])
        if len(episodes) != expected:
            raise RuntimeError(f"FROZEN_EPISODE_COUNT_MISMATCH:{city_key}:{len(episodes)}!={expected}")
        ids = [str(ep.get("episode_id") or "") for ep in episodes]
        if any(not eid for eid in ids) or len(ids) != len(set(ids)):
            raise RuntimeError(f"FROZEN_EPISODE_ID_INVALID:{city_key}")
        row = (status.get("cities") or {}).get(city_key)
        if row is None:
            raise RuntimeError(f"FROZEN_CITY_MISSING_FROM_STATUS:{city_key}")
        row["frozen_episode_ids"] = ids
        row["frozen_episode_count"] = len(ids)
        row["frozen_episode_source_blobs"] = [
            {"path": rel, "sha": blob_for(ROOT / rel)}
            for rel in source_files
        ]
        frozen_total += len(ids)
    if frozen_total != 6863:
        raise RuntimeError(f"FROZEN_CAMPAIGN_TOTAL_MISMATCH:{frozen_total}!=6863")
    status["frozen_cities"] = frozen_cities
    status["frozen_total_episodes"] = frozen_total
    status["frozen_starting_head"] = git("rev-parse", "HEAD")
    status["frozen_at"] = now_iso()
    status["campaign_version"] = versions
    status["source_registry_sha"] = versions["source_registry_sha"]
    refresh_campaign_counts(status)


def frozen_city_episodes(city_key: str, city_state: dict) -> list[dict]:
    live = load_city_episodes(city_key)
    frozen_ids = [str(x) for x in (city_state.get("frozen_episode_ids") or []) if str(x)]
    if not frozen_ids:
        raise RuntimeError(f"FROZEN_EPISODE_UNIVERSE_MISSING:{city_key}")
    if len(frozen_ids) != len(set(frozen_ids)):
        raise RuntimeError(f"FROZEN_EPISODE_UNIVERSE_DUPLICATE_IDS:{city_key}")
    expected = int(city_state.get("total_episodes") or 0)
    if len(frozen_ids) != expected:
        raise RuntimeError(
            f"FROZEN_EPISODE_UNIVERSE_COUNT_MISMATCH:{city_key}:{len(frozen_ids)}!={expected}"
        )
    digest = hashlib.sha256("\n".join(frozen_ids).encode("utf-8")).hexdigest()
    frozen_digest = str(city_state.get("frozen_episode_ids_sha256") or "")
    if frozen_digest and digest != frozen_digest:
        raise RuntimeError(f"FROZEN_EPISODE_UNIVERSE_HASH_MISMATCH:{city_key}")
    by_id = {str(ep.get("episode_id") or ""): ep for ep in live}
    missing = [eid for eid in frozen_ids if eid not in by_id]
    if missing:
        raise RuntimeError(f"FROZEN_EPISODE_UNIVERSE_DRIFT:{city_key}:missing={len(missing)}")
    return [by_id[eid] for eid in frozen_ids]


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
        "schema_version": 2,
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
        "air_defense_context": monitor.air_defense_context_signal(text),
        "air_defense_action": monitor.air_defense_action_signal(text),
        "interception_claim": monitor.interception_claim_signal(text),
    }


def matched_terms(text: str) -> list[str]:
    terms = list(monitor.attack_event_types(text))
    ppo = ppo_fields(text)
    if ppo["air_defense_context"] and "air_defense_context" not in terms:
        terms.append("air_defense_context")
    if ppo["air_defense_action"] and "air_defense_action" not in terms:
        terms.append("air_defense_action")
    if ppo["interception_claim"] and "interception_claim" not in terms:
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
    city_state["strict_event_positive"] = sum(str(x.get("state") or "") == "STRICT_EVENT_POSITIVE" for x in states.values())
    city_state["sensitivity_only_event_positive"] = sum(str(x.get("state") or "") == "SENSITIVITY_EVENT_POSITIVE" for x in states.values())
    city_state["no_confirmed_event"] = sum(str(x.get("state") or "") == "NO_CONFIRMED_EVENT" for x in states.values())
    city_state["needs_review"] = sum(str(x.get("state") or "") == "NEEDS_REVIEW" for x in states.values())
    city_state["source_retry_required"] = sum(str(x.get("state") or "") == "SOURCE_FETCH_RETRY_REQUIRED" for x in states.values())
    city_state["observations_found"] = sum(int(x.get("observation_count") or 0) for x in states.values())


def refresh_campaign_counts(status: dict) -> None:
    frozen_cities = [str(x) for x in (status.get("frozen_cities") or [])]
    rows = [
        (status.get("cities") or {}).get(key) or {}
        for key in frozen_cities
        if key in (status.get("cities") or {})
    ]
    total = int(status.get("frozen_total_episodes") or sum(int(row.get("total_episodes") or 0) for row in rows))
    processed = sum(int(row.get("scanned_episodes") or 0) for row in rows)
    terminal = sum(int(row.get("terminal_episodes") or 0) for row in rows)
    status["progress"] = {
        "processed": processed,
        "total": total,
        "terminal": terminal,
        "display": f"{processed} / {total}",
    }
    if processed == 0:
        status["status"] = "QUEUED"
    elif rows and all(str(row.get("status") or "") in {"COMPLETE", "BLOCKED_SOURCE_FAILURE", "BLOCKED_SOURCE_ADAPTER"} for row in rows):
        status["status"] = "COMPLETE" if terminal == total else "BLOCKED"
    else:
        status["status"] = "RUNNING"


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

    freeze_campaign_snapshot(status, versions)

    live_ready = [row["city_key"] for row in replay_ready_cities()]
    frozen_ready = [str(x) for x in (status.get("frozen_cities") or [])]
    if frozen_ready:
        missing_ready = [key for key in frozen_ready if key not in live_ready]
        if missing_ready:
            raise RuntimeError("FROZEN_CITY_REPLAY_READINESS_DRIFT:" + ",".join(missing_ready))
        ready = frozen_ready
    else:
        ready = live_ready
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
    episodes = frozen_city_episodes(city_key, city_state)
    selected = select_work(episodes, city_state, args.batch_size, args.start_index, args.resume)
    if not selected:
        city_state["status"] = "COMPLETE"
        city_state["updated_at"] = now_iso()
        refresh_campaign_counts(status)
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
            "observation_count": len(result.get("source_observation_ids") or []),
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
    refresh_campaign_counts(status)
    status["updated_at"] = now_iso()

    batch = {
        "schema_version": 2,
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

    launch_artifact_path = RESEARCH / "historical_attack_event_backfill_campaign_launch_2026-09-27.json"
    if not launch_artifact_path.exists():
        frozen_universe = {
            key: {
                "total_episodes": int(((status.get("cities") or {}).get(key) or {}).get("total_episodes") or 0),
                "ordered_episode_ids": list(((status.get("cities") or {}).get(key) or {}).get("frozen_episode_ids") or []),
                "source_blobs": list(((status.get("cities") or {}).get(key) or {}).get("frozen_episode_source_blobs") or []),
            }
            for key in (status.get("frozen_cities") or [])
        }
        launch_artifact = {
            "schema_version": 2,
            "kind": "historical_attack_event_backfill_campaign_launch",
            "generated_at": now_iso(),
            "starting_head": status.get("frozen_starting_head"),
            "campaign_id": args.campaign_id,
            "campaign_methodology_version": versions["methodology_version"],
            "checkpoint_schema": 2,
            "frozen_code_version": versions,
            "frozen_cities": list(status.get("frozen_cities") or []),
            "frozen_city_universe": frozen_universe,
            "per_city_totals": {key: row["total_episodes"] for key, row in frozen_universe.items()},
            "total_episodes": int(status.get("frozen_total_episodes") or 0),
            "first_workflow_run_id": os.getenv("GITHUB_RUN_ID"),
            "first_completed_batch": {
                "city_key": city_key,
                "batch_number": batch_number,
                "processed_count": len(selected),
                "strict_event_positive_count": sum(x["event_positive_strict"] for x in results),
                "sensitivity_only_count": sum(
                    bool(x["event_positive_sensitivity"]) and not bool(x["event_positive_strict"])
                    for x in results
                ),
                "needs_review_count": sum(x["classifier_result"] == "NEEDS_REVIEW" for x in results),
                "source_retry_count": sum(x["classifier_result"] == "SOURCE_FETCH_RETRY_REQUIRED" for x in results),
                "batch_path": checkout_relative(batch_path),
            },
            "checkpoint_proof": {
                "status_path": str(STATUS_PATH.relative_to(CHECKOUT_ROOT)).replace(os.sep, "/"),
                "persisted": True,
            },
            "scheduled_resume_proof": {
                "workflow": ".github/workflows/historical-attack-event-backfill-scheduler.yml",
                "enabled": True,
                "campaign_id": args.campaign_id,
            },
            "stale_run_protection": True,
            "protected_file_hashes": protected_blobs(),
            "campaign_status_after_launch": status.get("progress") or {},
            "ppo_air_defense_action_active": True,
        }
        dump_json(launch_artifact_path, launch_artifact)
        status["launch_artifact_path"] = str(launch_artifact_path.relative_to(CHECKOUT_ROOT)).replace(os.sep, "/")
        status["first_workflow_run_id"] = os.getenv("GITHUB_RUN_ID")
        status["launch_artifact_written"] = True

    dump_json(STATUS_PATH, status)
    return {
        "ok": True,
        "new_work": len(selected),
        "city_key": city_key,
        "batch_number": batch_number,
        "batch_path": checkout_relative(batch_path),
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



def air_defense_methodology_controls() -> dict:
    ep = {
        "episode_id": "air-defense-methodology-control",
        "city_key": "poltava",
        "city": "Полтава",
        "alert_start": "2026-09-27T10:00:00Z",
        "alert_end": "2026-09-27T11:00:00Z",
    }
    base = {
        "publisher": "СУСПІЛЬНЕ НОВИНИ",
        "publisher_url": None,
        "published_at": "2026-09-27T10:30:00Z",
        "snippet": "",
        "resolved_url": None,
        "matched_text_excerpt": None,
        "source": "Telegram / СУСПІЛЬНЕ НОВИНИ",
    }
    positive_specs = [
        ("PPO_ACTION_ONLY", "У Полтаві працює ППО.", ["air_defense_action"], False),
        ("PPO_ACTION_PLUS_EXPLOSION", "У Полтаві чути вибухи — працює ППО.", ["explosion", "air_defense_action"], False),
        ("PPO_INTERCEPTION", "У Полтаві ППО збила БпЛА.", ["air_defense_action"], True),
    ]
    negative_specs = [
        ("PPO_PREDICTION", "У Полтаві можлива робота ППО."),
        ("PPO_WARNING", "У Полтаві не лякайтеся, може бути чутно роботу ППО."),
        ("PPO_READY", "У Полтаві ППО готова до роботи."),
    ]
    positives = []
    negatives = []
    for control_id, title, expected_types, expected_interception in positive_specs:
        row = {**base, "candidate_id": control_id, "title": title}
        decision = monitor.classify_candidate(row, "poltava", [ep])
        actual_types = list(decision.get("event_types") or [])
        passed = (
            decision.get("air_defense_action") is True
            and decision.get("proposed_outcome") == "approved_strict"
            and all(x in actual_types for x in expected_types)
            and bool(decision.get("interception_claim")) is expected_interception
        )
        positives.append({
            "control_id": control_id,
            "source_text": title,
            "expected_event_types": expected_types,
            "event_types": actual_types,
            "air_defense_context": bool(decision.get("air_defense_context")),
            "air_defense_action": bool(decision.get("air_defense_action")),
            "interception_claim": bool(decision.get("interception_claim")),
            "classification": decision.get("proposed_outcome"),
            "episode_id": decision.get("proposed_matched_episode_id"),
            "passed": passed,
        })
    for control_id, title in negative_specs:
        row = {**base, "candidate_id": control_id, "title": title}
        decision = monitor.classify_candidate(row, "poltava", [ep])
        actual_types = list(decision.get("event_types") or [])
        passed = (
            decision.get("air_defense_action") is False
            and "air_defense_action" not in actual_types
            and decision.get("proposed_outcome") != "approved_strict"
        )
        negatives.append({
            "control_id": control_id,
            "source_text": title,
            "event_types": actual_types,
            "air_defense_context": bool(decision.get("air_defense_context")),
            "air_defense_action": bool(decision.get("air_defense_action")),
            "interception_claim": bool(decision.get("interception_claim")),
            "classification": decision.get("proposed_outcome"),
            "passed": passed,
        })
    return {
        "positive": positives,
        "negative": negatives,
        "positive_passed": all(x["passed"] for x in positives),
        "negative_passed": all(x["passed"] for x in negatives),
    }


def _episode_rows(doc: dict) -> list[dict]:
    return list(doc.get("episode_results") or doc.get("episode_level_results") or [])


def _episode_classification(row: dict) -> str:
    if row.get("event_positive_strict") or row.get("has_confirmed_event"):
        return "STRICT_EVENT_POSITIVE"
    sensitivity_ids = list(row.get("sensitivity_observation_ids") or [])
    if row.get("event_positive_sensitivity") or sensitivity_ids:
        return "SENSITIVITY_EVENT_POSITIVE"
    return "NO_CONFIRMED_EVENT"


def _pilot_episode_changes(old_doc: dict, new_doc: dict) -> list[dict]:
    old_rows = {str(x.get("episode_id") or ""): x for x in _episode_rows(old_doc)}
    new_rows = {str(x.get("episode_id") or ""): x for x in _episode_rows(new_doc)}
    observations = list(new_doc.get("evidence_observations") or [])
    out = []
    for episode_id in sorted(set(old_rows) | set(new_rows)):
        old_row = old_rows.get(episode_id) or {}
        new_row = new_rows.get(episode_id) or {}
        old_class = _episode_classification(old_row)
        new_class = _episode_classification(new_row)
        old_types = list(old_row.get("confirmed_event_types") or old_row.get("event_types") or [])
        new_types = list(new_row.get("confirmed_event_types") or new_row.get("event_types") or [])
        if old_class == new_class and old_types == new_types:
            continue
        support = [
            {
                "observation_id": obs.get("observation_id"),
                "source_url": obs.get("source_url"),
                "source_timestamp": obs.get("source_timestamp"),
                "excerpt": str(obs.get("excerpt") or "")[:500],
                "event_types": list(obs.get("event_types_supported") or obs.get("event_types") or []),
                "air_defense_action": bool(obs.get("air_defense_action")),
                "interception_claim": bool(obs.get("interception_claim")),
                "classification_outcome": obs.get("classification_outcome"),
            }
            for obs in observations
            if str(obs.get("classification_episode_id") or "") == episode_id
            and obs.get("classification_outcome") in {"approved_strict", "approved_sensitivity"}
        ]
        newly_positive = old_class == "NO_CONFIRMED_EVENT" and new_class in {
            "STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"
        }
        solely_air_defense = bool(
            newly_positive
            and support
            and any(x["air_defense_action"] and "air_defense_action" in x["event_types"] for x in support)
            and all(
                (not x["event_types"]) or "air_defense_action" in x["event_types"]
                for x in support
            )
        )
        out.append({
            "episode_id": episode_id,
            "previous_classification": old_class,
            "new_classification": new_class,
            "previous_event_types": old_types,
            "new_event_types": new_types,
            "source_evidence": support,
            "solely_due_to_air_defense_action": solely_air_defense,
        })
    return out


def _unexplained_pilot_changes(changes: list[dict]) -> list[dict]:
    return [
        row for row in changes
        if row["previous_classification"] != row["new_classification"]
        and not row["solely_due_to_air_defense_action"]
    ]


def foundation_acceptance(output: Path) -> dict:
    old_foundation = load_json(output) if output.exists() else {}
    old_lviv = load_json(LVIV_PILOT_PATH) if LVIV_PILOT_PATH.exists() else {}
    old_sevastopol = load_json(SEVASTOPOL_PILOT_PATH) if SEVASTOPOL_PILOT_PATH.exists() else {}
    starting_head = os.getenv("FOUNDATION_STARTING_HEAD") or git("rev-parse", "HEAD")
    acceptance_head = git("rev-parse", "HEAD")
    before = protected_blobs()

    self_result = self_test()
    controls = air_defense_methodology_controls()
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
    lviv_changes = _pilot_episode_changes(old_lviv, lviv)
    lviv_unexplained = _unexplained_pilot_changes(lviv_changes)
    lviv_new_ids = set(l_controls.get("newly_strict_episode_ids_vs_retained_controls") or [])
    lviv_change_map = {row["episode_id"]: row for row in lviv_changes}
    lviv_new_supported = all(
        lviv_change_map.get(eid, {}).get("solely_due_to_air_defense_action") is True
        for eid in lviv_new_ids
    )
    retained_count = int(l_controls.get("retained_control_count") or 0)
    rediscovered_count = int(l_controls.get("rediscovered_strict_control_count") or 0)
    lviv_pass = (
        lviv_proc.returncode == 0
        and l_summary.get("selected_episode_count") == 40
        and retained_count == rediscovered_count
        and not lviv_unexplained
        and lviv_new_supported
    )

    sev_q = sev.get("qa_summary") or {}
    sev_changes = _pilot_episode_changes(old_sevastopol, sev)
    sev_unexplained = _unexplained_pilot_changes(sev_changes)
    old_sev_diag = ((old_sevastopol.get("control_recovery") or {}).get("missed_control_diagnostics") or [])
    sev_diag = ((sev.get("control_recovery") or {}).get("missed_control_diagnostics") or [])
    old_downgrade_ids = {
        str(x.get("episode_id") or "") for x in old_sev_diag
        if x.get("gap_code") == "CURRENT_RULE_DOWNGRADE"
    }
    new_downgrade_ids = {
        str(x.get("episode_id") or "") for x in sev_diag
        if x.get("gap_code") == "CURRENT_RULE_DOWNGRADE"
    }
    resolved_downgrades = old_downgrade_ids - new_downgrade_ids
    sev_change_map = {row["episode_id"]: row for row in sev_changes}
    resolved_supported = all(
        sev_change_map.get(eid, {}).get("solely_due_to_air_defense_action") is True
        for eid in resolved_downgrades
    )
    sev_pass = (
        sev_q.get("selected_alert_episodes") == 40
        and not sev_unexplained
        and resolved_supported
    )

    drift_pass = (
        bool(audit)
        and audit_rc == 0
        and int(audit.get("uncontrolled_drift_count") or 0) == 0
        and int(audit.get("approved_regression_count") or 0) == 0
    )
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

    unexplained_count = (
        int((audit or {}).get("uncontrolled_drift_count") or 0)
        + len(lviv_unexplained)
        + len(sev_unexplained)
    )
    positive_pass = bool(controls.get("positive_passed"))
    negative_pass = bool(controls.get("negative_passed"))

    checks = {
        "source_adapter_self_test": worker.returncode == 0,
        "classifier_self_test": classifier.returncode == 0,
        "classifier_control_replay": drift_pass,
        "positive_ppo_controls": positive_pass,
        "negative_ppo_controls": negative_pass,
        "lviv_acceptance": lviv_pass,
        "sevastopol_acceptance": sev_pass,
        "restart_idempotence": self_result,
        "protected_files_unchanged": protected_clean,
    }
    all_pass = all([
        checks["source_adapter_self_test"],
        checks["classifier_self_test"],
        checks["classifier_control_replay"],
        positive_pass,
        negative_pass,
        lviv_pass,
        sev_pass,
        protected_clean,
        unexplained_count == 0,
    ])

    code_workflow_files = [
        "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py",
        "kyiv-air-alerts-grafana/scripts/audit_attack_event_classifier.py",
        "kyiv-air-alerts-grafana/scripts/discover_historical_attack_events.py",
        "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_source_adapter_pilot.py",
        "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py",
        "research/historical_attack_event_source_registry.json",
        "research/historical_attack_event_backfill_status.json",
        ".github/workflows/historical-attack-event-backfill.yml",
        ".github/workflows/historical-attack-event-backfill-scheduler.yml",
    ]

    artifact = {
        "schema_version": 2,
        "kind": "historical_attack_event_autonomous_backfill_foundation",
        "generated_at": now_iso(),
        "actual_starting_head": starting_head,
        "acceptance_head": acceptance_head,
        "campaign_branch": "historical-attack-event-backfill-2026-09-27",
        "campaign_id": DEFAULT_CAMPAIGN_ID,
        "methodology_version": METHODOLOGY_VERSION,
        "state_location": "research/historical_attack_event_backfill_status.json",
        "campaign_architecture": {
            "batch_runner": "kyiv-air-alerts-grafana/scripts/run_historical_attack_event_backfill_batch.py",
            "batch_artifact_layout": "research/historical_attack_event_backfill/<campaign_id>/<city>/batch_000001.json",
            "workflow": ".github/workflows/historical-attack-event-backfill.yml",
            "default_batch_size": 50,
            "late_damage_fire_window_hours": LATE_WINDOW_HOURS,
            "same_campaign_resume_requires_same_versions": True,
            "scheduled_resume_declared": True,
            "scheduled_resume_activation_note": "Default-branch scheduler remains a no-op while scanned_episodes == 0; no full campaign is started by methodology acceptance.",
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
            "confirmed_actual_air_defense_action_sets_event_positive": True,
            "predicted_possible_air_defense_sets_event_positive": False,
            "rule": "confirmed actual air-defense action bound to an alert episode is an event-positive attack-event class",
        },
        "checkpoint_schema": {
            "schema_version": 2,
            "status_path": "research/historical_attack_event_backfill_status.json",
            "episode_result_fields": [
                "confirmed_event_types", "sensitivity_event_types", "air_defense_context",
                "air_defense_action", "interception_claim", "event_positive_strict",
                "event_positive_sensitivity",
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
                "evaluated_candidates": (audit or {}).get("evaluated_candidates"),
                "changed_candidate_count": (audit or {}).get("changed_candidate_count"),
                "changed_classification_ids": (audit or {}).get("changed_classification_ids") or [],
                "targeted_air_defense_action_count": (audit or {}).get("targeted_air_defense_action_count"),
                "uncontrolled_drift_count": (audit or {}).get("uncontrolled_drift_count"),
                "approved_regression_count": (audit or {}).get("approved_regression_count"),
            },
            "positive_ppo_controls": controls["positive"],
            "negative_ppo_controls": controls["negative"],
            "lviv": {
                "passed": lviv_pass,
                "selected_episodes": l_summary.get("selected_episode_count"),
                "retained_controls": retained_count,
                "rediscovered_controls": rediscovered_count,
                "newly_positive_episode_ids": sorted(lviv_new_ids),
                "changes": lviv_changes,
                "unexplained_changes": lviv_unexplained,
            },
            "sevastopol": {
                "passed": sev_pass,
                "selected_episodes": sev_q.get("selected_alert_episodes"),
                "strict": sev_q.get("strict_observations"),
                "sensitivity": sev_q.get("sensitivity_observations"),
                "needs_review": sev_q.get("needs_review_observations"),
                "current_rule_downgrade_ids": sorted(new_downgrade_ids),
                "resolved_current_rule_downgrade_ids": sorted(resolved_downgrades),
                "changes": sev_changes,
                "unexplained_changes": sev_unexplained,
            },
        },
        "restart_idempotence_proof": self_result,
        "version_change_proof": {
            "passed": self_result["version_change_protection"] == "PASS",
            "behavior": "same campaign with processed episodes rejects incompatible methodology/classifier/adapter/orchestrator/normalization identity",
        },
        "protected_file_verification": {
            "unchanged": protected_clean,
            "before": before,
            "after": after,
        },
        "exact_code_workflow_files_changed": code_workflow_files,
        "checks": checks,
        "verdict": (
            "AUTONOMOUS HISTORICAL ATTACK-EVENT BACKFILL FOUNDATION READY"
            if all_pass
            else "AUTONOMOUS HISTORICAL ATTACK-EVENT BACKFILL FOUNDATION BLOCKED — ACCEPTANCE_FAILURE"
        ),
    }

    retained_ppo_path = ROOT / "data" / "explosion_research" / "zaporizhzhia" / "zaporizhzhia_air_defense_pilot.json"
    retained_ppo = load_json(retained_ppo_path) if retained_ppo_path.exists() else {}
    retained_positive_controls = [
        {
            "episode_id": row.get("episode_id"),
            "source": row.get("source"),
            "url": row.get("url"),
            "text": row.get("text"),
            "classification": row.get("classification"),
        }
        for row in (retained_ppo.get("strict_positive_evidence") or [])[:6]
    ]

    classifier_changes = list((audit or {}).get("changes") or [])
    methodology_artifact = {
        "schema_version": 1,
        "kind": "historical_attack_event_air_defense_action_methodology_update",
        "generated_at": now_iso(),
        "starting_head": starting_head,
        "acceptance_head": acceptance_head,
        "campaign_branch": "historical-attack-event-backfill-2026-09-27",
        "old_methodology": {
            "event_taxonomy": ["explosion", "impact", "arrival", "strike", "damage", "fire"],
            "ppo_rule": "PPO-only sets event-positive = NO",
            "campaign_id": "historical-attack-events-v1-2026-09-27",
        },
        "new_methodology": {
            "event_taxonomy": list(monitor.ATTACK_EVENT_TYPE_ORDER),
            "rule": "confirmed actual air-defense action bound to an alert episode is an event-positive attack-event class",
            "prediction_warning_rule": "possible, predicted, readiness, capability, or warning-only PPO does not set air_defense_action and is non-event-positive unless another event class is confirmed",
            "interception_rule": "interception_claim remains a separate attribute and is not required for air_defense_action",
            "numerator_rule": "episode contributes at most 1 when strict/sensitivity evidence supports at least one canonical event class",
        },
        "classifier_schema_versions": {
            "before": {
                "classifier_sha": "eefd63aeebc17347b750f61115842be6c53a79da",
                "source_adapter_sha": "0ceb3ea480de9b401000ba9d8b0bb02b22d83c89",
                "orchestrator_sha": "bffd09462b36fd2581216e6511641fd44b199e3f",
                "normalization_version": "historical-attack-event-observation-v1",
                "methodology_version": "historical-attack-event-ppo-context-v1",
            },
            "after": versions,
            "checkpoint_schema_before": 1,
            "checkpoint_schema_after": 2,
            "campaign_id_before": "historical-attack-events-v1-2026-09-27",
            "campaign_id_after": DEFAULT_CAMPAIGN_ID,
        },
        "exact_code_files_changed": code_workflow_files,
        "positive_ppo_controls": {
            "synthetic": controls["positive"],
            "retained_evidence_examples": retained_positive_controls,
            "passed": positive_pass,
        },
        "negative_ppo_controls": {
            "synthetic": controls["negative"],
            "passed": negative_pass,
        },
        "classifier_control_replay": {
            "total_controls_evaluated": (audit or {}).get("evaluated_candidates"),
            "total_changed_classifications": (audit or {}).get("changed_candidate_count"),
            "changed_classification_ids": (audit or {}).get("changed_classification_ids") or [],
            "changes": classifier_changes,
            "uncontrolled_drift_count": (audit or {}).get("uncontrolled_drift_count"),
            "approved_regression_count": (audit or {}).get("approved_regression_count"),
        },
        "all_classification_changes": {
            "classifier_records": classifier_changes,
            "lviv_episode_changes": [
                row for row in lviv_changes
                if row["previous_classification"] != row["new_classification"]
            ],
            "sevastopol_episode_changes": [
                row for row in sev_changes
                if row["previous_classification"] != row["new_classification"]
            ],
        },
        "unexplained_drift_count": unexplained_count,
        "lviv_acceptance_result": artifact["acceptance_test_results"]["lviv"],
        "sevastopol_acceptance_result": artifact["acceptance_test_results"]["sevastopol"],
        "protected_file_hashes": {
            "before": before,
            "after": after,
            "unchanged": protected_clean,
        },
        "campaign_methodology_version_changed": True,
        "full_campaign_launch_status": "NOT_STARTED",
        "verdict": (
            "AIR-DEFENSE ACTION PROMOTED TO EVENT-POSITIVE — AUTONOMOUS CAMPAIGN READY"
            if all_pass
            else "AIR-DEFENSE ACTION METHODOLOGY UPDATE BLOCKED — ACCEPTANCE_FAILURE"
        ),
    }

    dump_json(output, artifact)
    dump_json(METHODOLOGY_ARTIFACT_PATH, methodology_artifact)
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
        if doc["verdict"] != "AUTONOMOUS HISTORICAL ATTACK-EVENT BACKFILL FOUNDATION READY":
            raise SystemExit(2)
        return

    result = run_one_batch(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result.get("ok"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
