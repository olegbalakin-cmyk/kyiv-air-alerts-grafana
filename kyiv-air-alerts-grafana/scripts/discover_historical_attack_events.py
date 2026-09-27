#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

import monitor_explosion_candidates as monitor
from historical_attack_event_sources import (
    canonical_observation_id,
    content_hash,
    extract_linked_telegram_refs,
    fetch_exact_linked_telegram_post,
    fetch_suspilne_articles_for_days,
    fetch_targeted_secondary_article,
    fetch_telegram_neighbor_window,
    fetch_telegram_search,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ALERTS = ROOT / "data" / "explosion_metric_handoff" / "source_slices" / "lviv-replay_alerts.json"
DEFAULT_EVIDENCE = ROOT / "data" / "explosion_research" / "lviv" / "final_evidence.json"
UTC = timezone.utc
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ukraine-air-alerts-historical-attack-event-pilot/1.0)",
    "Accept-Language": "uk,en;q=0.8",
}
ATTACK_DISCOVERY_RE = re.compile(
    r"\b(?:вибух\w*|взрыв\w*|влуч\w*|попад\w*|поціл\w*|приліт\w*|прилет\w*|"
    r"удар\w*|вдар\w*|пошкод\w*|поврежд\w*|пожеж\w*|пожар\w*|загор\w*|займан\w*|"
    r"ппо|пво|протиповітр\w*|противовоздуш\w*|працю\w*|робот\w*|работ\w*|"
    r"чути|чутно|слышно)",
    re.IGNORECASE,
)
PPO_RE = re.compile(r"\b(?:ппо|пво|протиповітр\w*|противовоздуш\w*)", re.IGNORECASE)
TELEGRAM_POST_RE = re.compile(
    r"https?://(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]+)/([0-9]+)",
    re.IGNORECASE,
)
TARGETED_SECONDARY_SOURCES = (
    {
        "target_episode_id": "6cd77c20720eafece633c1ad",
        "source": "ТСН",
        "url": "https://lviv.tsn.ua/lviv/u-lvovi-hrymliat-vybukhy-3015458.html",
    },
)
TARGET_RECOVERY_EPISODES = {
    "498d07cfea5ac7e9090a08e3",
    "6cd77c20720eafece633c1ad",
}


def parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def choose_anchor(evidence: dict, episode_order: dict[str, int]) -> dict:
    candidates = []
    for row in evidence.get("strict_events") or []:
        text = " ".join(
            str(x or "")
            for x in (
                row.get("evidence"),
                (row.get("raw_record") or {}).get("notes"),
                (row.get("raw_record") or {}).get("telegram_source"),
            )
        )
        raw = row.get("raw_record") or {}
        episode_id = str(row.get("episode_id") or "")
        if not episode_id or episode_id not in episode_order or not PPO_RE.search(text):
            continue
        telegram_message_id = str(raw.get("telegram_message_id") or "")
        candidates.append(
            {
                "episode_id": episode_id,
                "event_id": row.get("event_id"),
                "source_url": row.get("source_url"),
                "telegram_source": raw.get("telegram_source"),
                "telegram_message_id": telegram_message_id or None,
                "episode_index": episode_order[episode_id],
                "has_direct_telegram_provenance": bool(telegram_message_id and raw.get("telegram_source")),
            }
        )
    if not candidates:
        raise RuntimeError("No retained PPO control found for deterministic pilot anchor")
    candidates.sort(
        key=lambda x: (
            0 if x["has_direct_telegram_provenance"] else 1,
            x["episode_index"],
            str(x["event_id"] or ""),
        )
    )
    return candidates[0]


def select_episode_window(episodes: list[dict], anchor_episode_id: str, limit: int) -> list[dict]:
    if limit < 1:
        raise ValueError("limit must be positive")
    if limit > len(episodes):
        limit = len(episodes)
    idx = next(i for i, ep in enumerate(episodes) if str(ep["episode_id"]) == anchor_episode_id)
    left = limit // 2
    start = max(0, idx - left)
    end = start + limit
    if end > len(episodes):
        end = len(episodes)
        start = max(0, end - limit)
    selected = episodes[start:end]
    if len(selected) != limit or anchor_episode_id not in {str(x["episode_id"]) for x in selected}:
        raise AssertionError("deterministic episode selection failed")
    return selected


def classifier_row(channel: str, label: str, post: dict) -> dict:
    text = str(post.get("text") or "")
    return {
        "source": f"Telegram / {label}",
        "title": text[:240] or f"Telegram post {post['message_id']}",
        "url": post["url"],
        "publisher": label,
        "publisher_url": f"https://t.me/{channel}",
        "published_at": post["published_at"],
        "snippet": text[:1200],
        "discovery_basis": "historical_public_telegram_search",
    }


def matched_terms(text: str) -> list[str]:
    low = monitor.normalize_evidence_text(text)
    terms = []
    for event_type in monitor.ATTACK_EVENT_TYPE_ORDER:
        if event_type in monitor.attack_event_types(low):
            terms.append(event_type)
    if monitor.air_defense_context_signal(low):
        terms.append("air_defense_context")
    if monitor.air_defense_action_signal(low):
        terms.append("air_defense_action")
    if monitor.interception_claim_signal(low):
        terms.append("interception_claim")
    return terms


def retained_control_ids(evidence: dict, selected_ids: set[str]) -> list[str]:
    ids = []
    for row in evidence.get("strict_events") or []:
        episode_id = str(row.get("episode_id") or "")
        if episode_id in selected_ids:
            ids.append(episode_id)
    return sorted(set(ids))


def build_pilot(
    alerts_path: Path,
    evidence_path: Path,
    city_key: str,
    max_episodes: int,
    channel: str,
    channel_label: str,
    max_pages: int,
    sleep_seconds: float,
) -> dict:
    alerts_doc = load_json(alerts_path)
    evidence = load_json(evidence_path)
    if str(alerts_doc.get("city_key") or "") != city_key:
        raise RuntimeError("alert corpus city mismatch")
    if str(evidence.get("city_key") or "") != city_key:
        raise RuntimeError("evidence corpus city mismatch")

    episodes = list(alerts_doc.get("episodes") or [])
    if len(episodes) != int(alerts_doc.get("episode_count") or len(episodes)):
        raise RuntimeError("alert corpus count mismatch")
    episode_order = {str(ep["episode_id"]): i for i, ep in enumerate(episodes)}
    anchor = choose_anchor(evidence, episode_order)
    selected = select_episode_window(episodes, anchor["episode_id"], max_episodes)
    selected_ids = {str(ep["episode_id"]) for ep in selected}

    search_start = min(parse_dt(ep["alert_start"]) for ep in selected) - timedelta(hours=3)
    search_end = max(parse_dt(ep["alert_end"]) for ep in selected) + timedelta(hours=72)
    local_days = sorted({str(ep["alert_start_date_kyiv"]) for ep in selected})
    articles, fetch_meta = fetch_suspilne_articles_for_days(local_days, sleep_seconds)
    retained_controls_by_url = {
        str(row.get("source_url") or ""): str(row.get("episode_id") or "")
        for row in (evidence.get("strict_events") or [])
        if str(row.get("episode_id") or "") in selected_ids and row.get("source_url")
    }
    network_session = requests.Session()
    network_session.headers.update(HEADERS)
    linked_telegram_seen = set()
    linked_telegram_fetches = []
    linked_telegram_posts = []
    linked_neighbor_fetches = []
    targeted_secondary_fetches = []
    targeted_secondary_articles = []

    observations = []
    for article in articles:
        text = " ".join(x for x in (str(article.get("title") or ""), str(article.get("text") or "")) if x)
        if not monitor.city_mentioned(city_key, text):
            continue
        if not ATTACK_DISCOVERY_RE.search(text):
            continue
        row = {
            "source": "Suspilne Lviv archive",
            "title": str(article.get("title") or "")[:240],
            "url": article["url"],
            "publisher": "Суспільне Львів",
            "publisher_url": "https://suspilne.media/lviv/",
            "published_at": article.get("published_at"),
            "snippet": str(article.get("text") or "")[:1200],
            "matched_text_excerpt": str(article.get("text") or "")[:50000],
            "discovery_basis": "historical_source_local_html",
        }
        matching = monitor.match_candidate_to_episodes(row, selected)
        decision = monitor.classify_candidate(row, city_key, selected, matching)
        obs_id = hashlib.sha256(("html|" + article["url"]).encode("utf-8")).hexdigest()[:24]
        temporal = decision.get("temporal_binding") or {}
        article_observation = {
                "observation_id": obs_id,
                "source_type": "source_local_html",
                "source": "Суспільне Львів",
                "source_url": article["url"],
                "telegram_channel": None,
                "telegram_message_id": None,
                "source_timestamp": article.get("published_at"),
                "event_timestamp_if_stated": temporal.get("event_time"),
                "excerpt": str(article.get("text") or "")[:1200],
                "matched_terms": matched_terms(text),
                "event_types_supported": list(decision.get("event_types") or []),
                "air_defense_context": bool(decision.get("air_defense_context")),
                "air_defense_action": bool(decision.get("air_defense_action")),
                "interception_claim": bool(decision.get("interception_claim")),
                "exact_city_binding": decision.get("exact_city_classification_evidence"),
                "air_attack_context": decision.get("air_military_context"),
                "same_attack_context": decision.get("same_attack_context"),
                "temporal_binding": temporal,
                "classification_outcome": decision.get("proposed_outcome"),
                "classification_episode_id": decision.get("proposed_matched_episode_id"),
                "classification_reason_codes": list(decision.get("reason_codes") or []),
                "content_hash": content_hash(article["url"], article.get("published_at"), text),
                "provenance": {
                    "retrieval_method": "suspilne.media/lviv/archive/YYYY/M/D/ bounded date-local crawl",
                    "query": article.get("archive_local_day"),
                    "classifier": "monitor_explosion_candidates.py current branch version",
                },
            }
        observations.append(article_observation)

        retained_episode_id = retained_controls_by_url.get(article["url"])
        if (
            retained_episode_id in TARGET_RECOVERY_EPISODES
            and decision.get("proposed_outcome") != "approved_strict"
        ):
            for ref in (article.get("telegram_links") or [])[:6]:
                key = (str(ref["channel"]).casefold(), int(ref["message_id"]))
                if key in linked_telegram_seen or len(linked_telegram_seen) >= 12:
                    continue
                linked_telegram_seen.add(key)
                post, meta = fetch_exact_linked_telegram_post(
                    network_session, str(ref["channel"]), int(ref["message_id"])
                )
                linked_telegram_fetches.append({
                    "parent_article_url": article["url"],
                    "retained_episode_id": retained_episode_id,
                    "channel": ref["channel"],
                    "message_id": ref["message_id"],
                    **meta,
                })
                if post:
                    post["parent_article_url"] = article["url"]
                    post["retained_episode_id"] = retained_episode_id
                    linked_telegram_posts.append(post)
                    neighbors, neighbor_meta = fetch_telegram_neighbor_window(
                        network_session, str(ref["channel"]), int(ref["message_id"]), previous_count=3
                    )
                    linked_neighbor_fetches.append({
                        "parent_article_url": article["url"],
                        "retained_episode_id": retained_episode_id,
                        "channel": ref["channel"],
                        "center_message_id": ref["message_id"],
                        **neighbor_meta,
                    })
                    for neighbor in neighbors:
                        neighbor["parent_article_url"] = article["url"]
                        neighbor["retained_episode_id"] = retained_episode_id
                        linked_telegram_posts.append(neighbor)
                time.sleep(sleep_seconds)

    linked_post_dedup = {}
    for post in linked_telegram_posts:
        key = (str(post.get("channel") or "").casefold(), int(post.get("message_id") or 0))
        linked_post_dedup[key] = post
    linked_telegram_posts = sorted(
        linked_post_dedup.values(),
        key=lambda row: (str(row.get("published_at") or ""), str(row.get("channel") or ""), int(row.get("message_id") or 0)),
    )

    linked_candidate_rows = []
    linked_candidate_decisions = {}
    for post in linked_telegram_posts:
        text = str(post.get("text") or "")
        if not monitor.city_mentioned(city_key, text) or not ATTACK_DISCOVERY_RE.search(text):
            continue
        row = classifier_row(str(post["channel"]), str(post["channel"]), post)
        row["discovery_basis"] = "article_linked_public_telegram_exact_post"
        row["candidate_id"] = canonical_observation_id(str(post["channel"]), int(post["message_id"]))
        row["city_key"] = city_key
        matching = monitor.match_candidate_to_episodes(row, selected)
        active = monitor.exact_active_episodes_at(parse_dt(post["published_at"]), selected)
        active_ids = [str(ep.get("episode_id") or "") for ep in active]
        if len(active_ids) == 1:
            row["matched_episode_id"] = active_ids[0]
        decision = monitor.classify_candidate(row, city_key, selected, matching)
        row["status"] = str(decision.get("proposed_outcome") or "needs_review")
        linked_candidate_rows.append(row)
        linked_candidate_decisions[row["candidate_id"]] = decision
        temporal = decision.get("temporal_binding") or {}
        observations.append({
            "observation_id": row["candidate_id"],
            "source_type": "article_linked_public_telegram",
            "source": f"Telegram / {post['channel']}",
            "source_url": post["url"],
            "telegram_channel": post["channel"],
            "telegram_message_id": int(post["message_id"]),
            "source_timestamp": post["published_at"],
            "event_timestamp_if_stated": temporal.get("event_time"),
            "excerpt": text[:1200],
            "matched_terms": matched_terms(text),
            "event_types_supported": list(decision.get("event_types") or []),
            "air_defense_context": bool(decision.get("air_defense_context")),
            "air_defense_action": bool(decision.get("air_defense_action")),
            "interception_claim": bool(decision.get("interception_claim")),
            "exact_city_binding": decision.get("exact_city_classification_evidence"),
            "air_attack_context": decision.get("air_military_context"),
            "same_attack_context": decision.get("same_attack_context"),
            "temporal_binding": temporal,
            "classification_outcome": decision.get("proposed_outcome"),
            "classification_episode_id": decision.get("proposed_matched_episode_id"),
            "classification_reason_codes": list(decision.get("reason_codes") or []),
            "content_hash": content_hash(post["channel"], post["message_id"], post["published_at"], text),
            "provenance": {
                "retrieval_method": "exact public Telegram post linked from retained Suspilne article",
                "parent_article_url": post["parent_article_url"],
                "retained_episode_id": post["retained_episode_id"],
                "retrieval_url": post.get("retrieval_url"),
                "classifier": "monitor_explosion_candidates.py current branch version",
            },
        })

    composition_diagnostics = {}
    for episode_id in sorted(TARGET_RECOVERY_EPISODES & selected_ids):
        target_episode = next((ep for ep in selected if str(ep.get("episode_id") or "") == episode_id), None)
        candidates = [row for row in linked_candidate_rows if str(row.get("matched_episode_id") or "") == episode_id]
        if target_episode and candidates:
            composition = monitor.compose_episode_candidates(city_key, target_episode, candidates, selected)
        else:
            composition = {
                "target_episode_id": episode_id,
                "city_key": city_key,
                "final_composed_verdict": "no_composed_strict",
                "reason_codes": ["NO_LINKED_TELEGRAM_CANDIDATES_FOR_TARGET"],
            }
        composition_diagnostics[episode_id] = {
            "candidate_ids": [str(row.get("candidate_id") or "") for row in candidates],
            "candidates": [
                {
                    "candidate_id": str(row.get("candidate_id") or ""),
                    "url": row.get("url"),
                    "published_at": row.get("published_at"),
                    "text": str(row.get("title") or ""),
                    "decision": {
                        "outcome": linked_candidate_decisions.get(str(row.get("candidate_id") or ""), {}).get("proposed_outcome"),
                        "temporal_binding": linked_candidate_decisions.get(str(row.get("candidate_id") or ""), {}).get("temporal_binding"),
                        "strict_explosion": linked_candidate_decisions.get(str(row.get("candidate_id") or ""), {}).get("strict_explosion_evidence"),
                        "air_context": linked_candidate_decisions.get(str(row.get("candidate_id") or ""), {}).get("air_military_context"),
                        "same_attack": linked_candidate_decisions.get(str(row.get("candidate_id") or ""), {}).get("same_attack_context"),
                        "reason_codes": linked_candidate_decisions.get(str(row.get("candidate_id") or ""), {}).get("reason_codes"),
                    },
                }
                for row in candidates
            ],
            "composition": composition,
        }

    for source_cfg in TARGETED_SECONDARY_SOURCES:
        if source_cfg["target_episode_id"] not in selected_ids:
            continue
        try:
            article, meta = fetch_targeted_secondary_article(network_session, source_cfg)
            targeted_secondary_fetches.append({**meta, "target_episode_id": source_cfg["target_episode_id"], "resolved": True})
            targeted_secondary_articles.append(article)
        except Exception as exc:
            targeted_secondary_fetches.append({
                "url": source_cfg["url"],
                "target_episode_id": source_cfg["target_episode_id"],
                "resolved": False,
                "error": f"{type(exc).__name__}: {exc}",
            })

    for article in targeted_secondary_articles:
        text = " ".join(x for x in (str(article.get("title") or ""), str(article.get("text") or "")) if x)
        row = {
            "source": f"Targeted secondary HTML / {article['source']}",
            "title": str(article.get("title") or "")[:240],
            "url": article["url"],
            "publisher": article["source"],
            "publisher_url": article["url"],
            "published_at": article.get("published_at"),
            "snippet": str(article.get("text") or "")[:1200],
            "matched_text_excerpt": str(article.get("text") or "")[:5000],
            "discovery_basis": "targeted_secondary_html_preflight",
        }
        matching = monitor.match_candidate_to_episodes(row, selected)
        decision = monitor.classify_candidate(row, city_key, selected, matching)
        temporal = decision.get("temporal_binding") or {}
        observations.append({
            "observation_id": hashlib.sha256(("targeted-html|" + article["url"]).encode("utf-8")).hexdigest()[:24],
            "source_type": "targeted_secondary_html_preflight",
            "source": article["source"],
            "source_url": article["url"],
            "telegram_channel": None,
            "telegram_message_id": None,
            "source_timestamp": article.get("published_at"),
            "event_timestamp_if_stated": temporal.get("event_time"),
            "excerpt": str(article.get("text") or "")[:1200],
            "matched_terms": matched_terms(text),
            "event_types_supported": list(decision.get("event_types") or []),
            "air_defense_context": bool(decision.get("air_defense_context")),
            "air_defense_action": bool(decision.get("air_defense_action")),
            "interception_claim": bool(decision.get("interception_claim")),
            "exact_city_binding": decision.get("exact_city_classification_evidence"),
            "air_attack_context": decision.get("air_military_context"),
            "same_attack_context": decision.get("same_attack_context"),
            "temporal_binding": temporal,
            "classification_outcome": decision.get("proposed_outcome"),
            "classification_episode_id": decision.get("proposed_matched_episode_id"),
            "classification_reason_codes": list(decision.get("reason_codes") or []),
            "content_hash": content_hash(article["url"], article.get("published_at"), text),
            "provenance": {
                "retrieval_method": "exact-URL targeted secondary HTML preflight",
                "target_episode_id": article["target_episode_id"],
                "source_family_onboarded": False,
                "classifier": "monitor_explosion_candidates.py current branch version",
            },
        })

    observations.sort(key=lambda x: ((x.get("source_timestamp") or ""), x["source_url"]))
    by_episode: dict[str, list[dict]] = {str(ep["episode_id"]): [] for ep in selected}
    for obs in observations:
        episode_id = str(obs.get("classification_episode_id") or "")
        if episode_id in by_episode:
            by_episode[episode_id].append(obs)

    canonical_events = []
    episode_results = []
    for ep in selected:
        episode_id = str(ep["episode_id"])
        ep_obs = by_episode[episode_id]
        strict_obs = [x for x in ep_obs if x["classification_outcome"] == "approved_strict"]
        sensitivity_obs = [x for x in ep_obs if x["classification_outcome"] == "approved_sensitivity"]
        confirmed_event_types = []
        sensitivity_event_types = []
        for obs in strict_obs:
            for event_type in obs["event_types_supported"]:
                if event_type not in confirmed_event_types:
                    confirmed_event_types.append(event_type)
        for obs in strict_obs + sensitivity_obs:
            for event_type in obs["event_types_supported"]:
                if event_type not in sensitivity_event_types:
                    sensitivity_event_types.append(event_type)
        event_types = list(confirmed_event_types)
        for obs in strict_obs:
            canonical_events.append(
                {
                    "canonical_event_id": hashlib.sha256(
                        f"{city_key}|{episode_id}|{obs['observation_id']}".encode("utf-8")
                    ).hexdigest()[:24],
                    "episode_id": episode_id,
                    "event_types": list(obs["event_types_supported"]),
                    "observation_ids": [obs["observation_id"]],
                    "deduplication_status": "observation_level_unmerged_pilot",
                    "ambiguity_flag": len(strict_obs) > 1,
                }
            )
        episode_results.append(
            {
                **ep,
                "has_confirmed_event": bool(strict_obs),
                "confirmed_event_count": len(strict_obs),
                "event_types": event_types,
                "confirmed_event_types": confirmed_event_types,
                "sensitivity_event_types": sensitivity_event_types,
                "air_defense_context": any(bool(x.get("air_defense_context")) for x in ep_obs),
                "air_defense_action": any(bool(x.get("air_defense_action")) for x in ep_obs),
                "interception_claim": any(bool(x.get("interception_claim")) for x in ep_obs),
                "event_positive_strict": bool(strict_obs),
                "event_positive_sensitivity": bool(strict_obs or sensitivity_obs),
                "strict_observation_ids": [x["observation_id"] for x in strict_obs],
                "sensitivity_observation_ids": [x["observation_id"] for x in sensitivity_obs],
            }
        )

    controls = retained_control_ids(evidence, selected_ids)
    discovered_strict_ids = {
        row["episode_id"] for row in episode_results if row["has_confirmed_event"]
    }
    anchor_rediscovered = anchor["episode_id"] in discovered_strict_ids
    retained_controls_rediscovered = sorted(set(controls) & discovered_strict_ids)
    newly_strict_episode_ids = sorted(discovered_strict_ids - set(controls))
    target_recovery = {}
    for episode_id in sorted(TARGET_RECOVERY_EPISODES & selected_ids):
        target_obs = [
            obs for obs in observations
            if obs.get("classification_episode_id") == episode_id
            or (obs.get("provenance") or {}).get("retained_episode_id") == episode_id
            or (obs.get("provenance") or {}).get("target_episode_id") == episode_id
        ]
        strict_target_obs = [obs for obs in target_obs if obs.get("classification_outcome") == "approved_strict"]
        target_recovery[episode_id] = {
            "recovered_strict": episode_id in discovered_strict_ids,
            "strict_observation_ids": [obs["observation_id"] for obs in strict_target_obs],
            "strict_source_types": sorted({str(obs.get("source_type") or "") for obs in strict_target_obs}),
            "observation_count": len(target_obs),
        }
    target_recovery_clean = all(row["recovered_strict"] for row in target_recovery.values())

    return {
        "schema_version": 1,
        "kind": "historical_attack_event_discovery_pilot",
        "generated_at": iso(datetime.now(UTC)),
        "city_key": city_key,
        "city": monitor.CITY_CONFIG[city_key]["label"],
        "scope": {
            "max_alert_episodes": max_episodes,
            "selected_episode_count": len(selected),
            "network_source": "suspilne.media/lviv source-local date archives",
            "historical_baseline_mutated": False,
            "final_evidence_mutated": False,
            "live_metric_mutated": False,
            "dashboard_mutated": False,
            "production_mutated": False,
        },
        "selection": {
            "rule": "READY city with smallest historical episode universe; 40-episode centered window around earliest retained PPO control with direct Telegram provenance",
            "anchor": anchor,
            "window_start_episode_id": selected[0]["episode_id"],
            "window_end_episode_id": selected[-1]["episode_id"],
            "window_start": selected[0]["alert_start"],
            "window_end": selected[-1]["alert_end"],
        },
        "retrieval": {
            **fetch_meta,
            "search_window_start": iso(search_start),
            "search_window_end": iso(search_end),
            "rate_limit_sleep_seconds": sleep_seconds,
            "timeout_seconds": 15,
            "fallback_telegram_source_not_used": f"@{channel}",
            "fallback_reason": "public Telegram search did not provide sufficient historical depth in first pilot attempt",
            "article_linked_telegram": {
                "unique_exact_posts_requested": len(linked_telegram_seen),
                "resolved_posts": len(linked_telegram_posts),
                "resolved_post_diagnostics": [
                    {
                        "channel": post.get("channel"),
                        "message_id": post.get("message_id"),
                        "url": post.get("url"),
                        "published_at": post.get("published_at"),
                        "retained_episode_id": post.get("retained_episode_id"),
                        "parent_article_url": post.get("parent_article_url"),
                        "text_excerpt": str(post.get("text") or "")[:300],
                        "city_mentioned": monitor.city_mentioned(city_key, str(post.get("text") or "")),
                        "attack_discovery_match": bool(ATTACK_DISCOVERY_RE.search(str(post.get("text") or ""))),
                        "active_episode_ids_at_post_time": [
                            str(ep.get("episode_id") or "")
                            for ep in monitor.exact_active_episodes_at(parse_dt(post["published_at"]), selected)
                        ],
                    }
                    for post in linked_telegram_posts
                ],
                "fetches": linked_telegram_fetches,
                "neighbor_fetches": linked_neighbor_fetches,
                "composition_diagnostics": composition_diagnostics,
            },
            "targeted_secondary_html": {
                "configured_sources": len(TARGETED_SECONDARY_SOURCES),
                "resolved_articles": len(targeted_secondary_articles),
                "fetches": targeted_secondary_fetches,
                "source_family_onboarded": False,
            },
        },
        "event_taxonomy": list(monitor.ATTACK_EVENT_TYPE_ORDER),
        "episode_results": episode_results,
        "canonical_events": canonical_events,
        "evidence_observations": observations,
        "recovery_preflight": {
            "target_episode_ids": sorted(TARGET_RECOVERY_EPISODES & selected_ids),
            "results": target_recovery,
            "all_target_controls_recovered_strict": target_recovery_clean,
            "classifier_semantic_widening_used": False,
            "targeted_secondary_source_family_onboarded": False,
        },
        "controls": {
            "retained_strict_control_episode_ids_in_window": controls,
            "retained_control_count": len(controls),
            "rediscovered_strict_control_episode_ids": retained_controls_rediscovered,
            "rediscovered_strict_control_count": len(retained_controls_rediscovered),
            "anchor_rediscovered_strict": anchor_rediscovered,
            "newly_strict_episode_ids_vs_retained_controls": newly_strict_episode_ids,
        },
        "summary": {
            "selected_episode_count": len(selected),
            "retrieved_city_attack_observation_count": len(observations),
            "approved_strict_observation_count": sum(
                1 for x in observations if x["classification_outcome"] == "approved_strict"
            ),
            "approved_sensitivity_observation_count": sum(
                1 for x in observations if x["classification_outcome"] == "approved_sensitivity"
            ),
            "needs_review_observation_count": sum(
                1 for x in observations if x["classification_outcome"] == "needs_review"
            ),
            "rejected_observation_count": sum(
                1 for x in observations if x["classification_outcome"] == "rejected"
            ),
            "event_positive_episode_count": len(discovered_strict_ids),
            "event_positive_episode_share": round(len(discovered_strict_ids) / len(selected), 6),
        },
        "metric_rule": "An alert episode contributes at most 1 to the numerator when has_confirmed_event=true. Multiple observations/events do not inflate the numerator.",
        "verdict": (
            "HISTORICAL ATTACK-EVENT DISCOVERY PILOT CLEAN"
            if observations and anchor_rediscovered and target_recovery_clean and not newly_strict_episode_ids
            else "HISTORICAL ATTACK-EVENT DISCOVERY PILOT BLOCKED"
        ),
    }


def self_test() -> None:
    fake = [
        {"episode_id": f"e{i}", "alert_start": f"2026-01-{i+1:02d}T00:00:00Z", "alert_end": f"2026-01-{i+1:02d}T01:00:00Z"}
        for i in range(10)
    ]
    selected = select_episode_window(fake, "e5", 5)
    assert [x["episode_id"] for x in selected] == ["e3", "e4", "e5", "e6", "e7"]
    assert matched_terms("У Львові влучання пошкодило будинок і спричинило пожежу") == ["impact", "damage", "fire"]
    fake_html = '<a href="https://t.me/andriysadovyi/3345">x</a><a href="https://telegram.me/test_channel/42">y</a>'
    refs = extract_linked_telegram_refs(BeautifulSoup(fake_html, "html.parser"))
    assert [(x["channel"], x["message_id"]) for x in refs] == [("andriysadovyi", 3345), ("test_channel", 42)]
    print("Historical attack-event pilot helper self-test OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="lviv")
    parser.add_argument("--max-episodes", type=int, default=40)
    parser.add_argument("--alerts", type=Path, default=DEFAULT_ALERTS)
    parser.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    parser.add_argument("--channel", default="suspilnenews")
    parser.add_argument("--channel-label", default="СУСПІЛЬНЕ НОВИНИ")
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return
    if not args.output:
        parser.error("--output is required")
    if args.city != "lviv":
        parser.error("This first pilot is intentionally locked to lviv")

    result = build_pilot(
        args.alerts,
        args.evidence,
        args.city,
        args.max_episodes,
        args.channel,
        args.channel_label,
        args.max_pages,
        args.sleep_seconds,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": result["verdict"],
        "summary": result["summary"],
        "controls": result["controls"],
        "recovery_preflight": result.get("recovery_preflight"),
        "retrieval": result["retrieval"],
    }, ensure_ascii=False, indent=2))
    if result["verdict"].endswith("BLOCKED"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
