#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path.cwd() / "kyiv-air-alerts-grafana"
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor

OUT_DIR = Path("/tmp/telegram-vs-rss-temporal-audit")
OUT_DIR.mkdir(parents=True, exist_ok=True)

SOURCE_KEYS = ("telegram", "rss_title_snippet", "rss_publisher_fulltext")
CLOCK_RE = re.compile(r"(?<!\d)(?:[01]?\d|2[0-3])[:.][0-5]\d(?!\d)")
RANGE_RE = re.compile(
    r"\b(?:з|від)\s*(?:[01]?\d|2[0-3])[:.][0-5]\d\s*(?:до|по)\s*(?:[01]?\d|2[0-3])[:.][0-5]\d\b",
    re.IGNORECASE,
)
AFTER_RE = re.compile(r"\bпісля\s+\d{1,2}(?:(?:[:.]\d{2})|\s+ранку|\s+вечора|\s+ночі)?\b", re.IGNORECASE)
ASOF_RE = re.compile(r"\bстаном\s+на\s+(?:[01]?\d|2[0-3])[:.][0-5]\d\b", re.IGNORECASE)
OFFSET_RE = re.compile(r"\b(?:вже\s+)?за\s+\d{1,3}\s+хвилин\w*\b", re.IGNORECASE)
DAYPART_RE = re.compile(
    r"\b(?:сьогодні|учора|вчора|вночі|уночі|цієї\s+ночі|вранці|зранку|вдень|увечері|вечері|"
    r"нічн\w*|ранков\w*|денн\w*|вечірн\w*)\b",
    re.IGNORECASE,
)
DATE_RE = re.compile(
    r"\b(?:\d{1,2}[./-]\d{1,2}(?:[./-]\d{2,4})?|\d{1,2}\s+"
    r"(?:січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня))\b",
    re.IGNORECASE,
)
COMPLETED_RE = re.compile(
    r"\b(?:сталося|відбулося|зафіксовано|пролунав\w*|було\s+чути|чули|почули|"
    r"влучил\w*|влучан\w*|пошкоджен\w*|пошкоджено|загинул\w*|постраждал\w*|"
    r"внаслідок|після\s+(?:нічн\w*|ранков\w*|денн\w*|вечірн\w*)\s+атак\w*)\b",
    re.IGNORECASE,
)
CUMULATIVE_RE = re.compile(
    r"\b(?:протягом\s+(?:цього\s+)?дня|цілий\s+день|за\s+(?:минулий\s+)?(?:день|добу)|"
    r"добов\w*\s+(?:зведен\w*|підсум\w*)|підсумк\w*\s+(?:дня|доби)|"
    r"загалом|усього|всього)\b",
    re.IGNORECASE,
)

def clean(value: str | None) -> str:
    return " ".join(str(value or "").split())

def sha_text(value: str | None) -> str | None:
    value = str(value or "")
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else None

def host_of(url: str | None) -> str:
    return (urlparse(str(url or "")).hostname or "").casefold()

def source_text_excerpt(value: str | None, limit: int = 500) -> str | None:
    value = clean(value)
    return value[:limit] if value else None

def temporal_features(text: str | None, *, source_row: dict | None = None) -> dict:
    value = clean(text)
    low = monitor.normalize_evidence_text(value)
    explicit_clocks = sorted(set(m.group(0) for m in CLOCK_RE.finditer(value)))
    explicit_interval = bool(RANGE_RE.search(value) or AFTER_RE.search(value) or ASOF_RE.search(value) or OFFSET_RE.search(value))
    alert_relation = bool(monitor.explicit_alert_relation(value))
    live_wording = bool(monitor.contemporaneous_live_wording(value))
    retrospective = bool(monitor.retrospective_or_cumulative_wording(value) or COMPLETED_RE.search(value))
    cumulative = bool(CUMULATIVE_RE.search(value))
    broad = bool(DAYPART_RE.search(value) or DATE_RE.search(value))
    broad_only = bool(broad and not explicit_clocks and not explicit_interval)
    accepted_live_wording = bool(source_row and monitor.trusted_live_source(source_row) and live_wording)
    any_temporal = bool(
        explicit_clocks
        or explicit_interval
        or alert_relation
        or live_wording
        or retrospective
        or cumulative
        or broad
    )
    return {
        "any_temporal_language": any_temporal,
        "explicit_clock": bool(explicit_clocks),
        "explicit_clock_tokens": explicit_clocks[:20],
        "explicit_interval": explicit_interval,
        "accepted_contemporaneous_live_wording": accepted_live_wording,
        "live_wording_pattern_present": live_wording,
        "explicit_alert_relation": alert_relation,
        "broad_daypart_or_date_only": broad_only,
        "retrospective_or_completed": retrospective,
        "cumulative_or_summary": cumulative,
    }

def candidate_temporal(decision: dict) -> dict:
    return dict(((decision.get("candidate_evidence") or {}).get("temporal_binding") or {}))

def semantic_gates(decision: dict) -> dict:
    ev = decision.get("candidate_evidence") or {}
    gates = {
        "exact_city": bool((ev.get("exact_city") or {}).get("present")),
        "attack_event": bool((ev.get("strict_explosion") or {}).get("present")),
        "air_military_context": bool((ev.get("air_military_context") or {}).get("present")),
        "same_attack_context": bool((ev.get("same_attack_context") or {}).get("present")),
    }
    gates["semantically_strong"] = all(gates.values())
    return gates

def strict_temporal_binding(temporal: dict) -> bool:
    return bool(
        temporal.get("present")
        and temporal.get("episode_specific")
        and temporal.get("episode_id")
    )

def ambiguous_temporal(temporal: dict) -> bool:
    code = str(temporal.get("code") or "")
    supported = list(temporal.get("supported_episode_ids") or [])
    return bool(
        "AMBIGUOUS" in code
        or "MULTIPLE_EPISODES" in code
        or (not strict_temporal_binding(temporal) and len(supported) > 1)
    )

def current_parser_recognized_temporal(temporal: dict) -> bool:
    code = str(temporal.get("code") or "")
    return bool(code and code != "NO_STRICT_TEMPORAL_BINDING")

def logical_cluster_map(episodes: list[dict]) -> tuple[dict[str, str], dict[str, list[str]]]:
    by_episode = {}
    members = {}
    for cluster in monitor.episode_representation_clusters(episodes):
        ids = sorted(str(ep.get("episode_id") or "") for ep in cluster if ep.get("episode_id"))
        if not ids:
            continue
        key = "|".join(ids)
        members[key] = ids
        for episode_id in ids:
            by_episode[episode_id] = key
    return by_episode, members

def analysis_cluster_key(matching: dict, temporal: dict, by_episode: dict[str, str]) -> str | None:
    episode_id = str(temporal.get("episode_id") or "")
    if episode_id and episode_id in by_episode:
        return by_episode[episode_id]
    groups = [list(g) for g in (matching.get("logical_episode_groups") or []) if g]
    if matching.get("outcome") == "unique_match" and len(groups) == 1:
        ids = sorted(str(x) for x in groups[0])
        return "|".join(ids)
    return None

def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    pos = (len(xs) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return xs[lo] * (1 - frac) + xs[hi] * frac

def lag_summary(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "median_seconds": None, "p25_seconds": None, "p75_seconds": None, "min_seconds": None, "max_seconds": None}
    xs = sorted(values)
    return {
        "n": len(xs),
        "median_seconds": statistics.median(xs),
        "p25_seconds": percentile(xs, 0.25),
        "p75_seconds": percentile(xs, 0.75),
        "min_seconds": min(xs),
        "max_seconds": max(xs),
    }

def parse_article_metadata(raw_html: str) -> dict:
    out = {"published": [], "updated": [], "other_time": []}
    try:
        soup = monitor.BeautifulSoup(raw_html, "html.parser")
    except Exception:
        return out

    for meta in soup.find_all("meta"):
        key = clean(meta.get("property") or meta.get("name") or meta.get("itemprop")).casefold()
        value = clean(meta.get("content"))
        if not key or not value:
            continue
        if key in {"article:published_time", "og:published_time", "datepublished", "date", "pubdate", "publishdate"}:
            out["published"].append(value)
        elif key in {"article:modified_time", "og:updated_time", "datemodified", "last-modified", "lastmodified"}:
            out["updated"].append(value)

    for time_el in soup.find_all("time"):
        value = clean(time_el.get("datetime"))
        if value:
            out["other_time"].append(value)

    for script in soup.find_all("script"):
        script_type = clean(script.get("type")).casefold()
        if "ld+json" not in script_type:
            continue
        raw = script.string or script.get_text("", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        stack = payload if isinstance(payload, list) else [payload]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                for key, value in item.items():
                    low = str(key).casefold()
                    if low == "datepublished" and isinstance(value, (str, int, float)):
                        out["published"].append(str(value))
                    elif low == "datemodified" and isinstance(value, (str, int, float)):
                        out["updated"].append(str(value))
                    elif isinstance(value, (dict, list)):
                        stack.append(value)
            elif isinstance(item, list):
                stack.extend(item)

    for key in out:
        out[key] = sorted(set(clean(v) for v in out[key] if clean(v)))[:20]
    return out

def body_for_url(fulltext_cache: dict, url: str | None) -> tuple[str | None, str | None, dict]:
    rec = fulltext_cache.get(str(url or ""))
    if not rec:
        return None, None, {}
    return rec.get("body"), rec.get("resolved_url"), dict(rec.get("article_metadata") or {})

def counterfactual_fulltext_decision(row: dict, body: str | None, city: str, episodes: list[dict]) -> dict | None:
    if not body:
        return None
    excerpt = monitor.matched_text_excerpt(body)
    if not excerpt:
        return None
    cf = dict(row)
    cf["discovery_basis"] = "publisher_fulltext"
    cf["matched_text_excerpt"] = excerpt
    matching = monitor.match_candidate_to_episodes(cf, episodes)
    return monitor.classify_candidate(cf, city, episodes, matching)

started = monitor.now_utc()
state = monitor.load_json(monitor.STATE_FILE, {})
if not isinstance(state, dict) or state.get("schema_version") != 1:
    raise SystemExit("INVALID_MONITOR_STATE")
shadow_state = copy.deepcopy(state)
due = monitor.due_checks(shadow_state, started)
due_cities = sorted(due)

network_log: list[dict] = []
original_session_request = monitor.requests.sessions.Session.request

def traced_request(session_self, method=None, request_url=None, *args, **kwargs):
    if request_url is None:
        request_url = kwargs.pop("url", None)
    rec = {
        "method": str(method or kwargs.get("method") or "").upper(),
        "request_url": str(request_url or ""),
        "request_host": host_of(request_url),
    }
    try:
        response = original_session_request(session_self, method, request_url, *args, **kwargs)
        rec.update({
            "status_code": int(response.status_code),
            "final_url": str(response.url or ""),
            "final_host": host_of(response.url),
            "content_type": str((response.headers or {}).get("Content-Type") or ""),
        })
        final_host = str(rec.get("final_host") or "")
        ctype = str(rec.get("content_type") or "").casefold()
        if final_host and not monitor.google_host(final_host) and "html" in ctype:
            try:
                rec["article_metadata"] = parse_article_metadata(response.text)
            except Exception:
                rec["article_metadata"] = {}
        network_log.append(rec)
        return response
    except Exception as exc:
        rec.update({
            "exception_type": type(exc).__name__,
            "exception_message": str(exc)[:500],
        })
        network_log.append(rec)
        raise

monitor.requests.sessions.Session.request = traced_request

raw_tg_unique: dict[tuple[str, int], dict] = {}
raw_tg_page_encounters = 0
original_telegram_page = monitor.telegram_page

def recorded_telegram_page(handle: str, before: int | None = None):
    global raw_tg_page_encounters
    posts, url = original_telegram_page(handle, before)
    raw_tg_page_encounters += len(posts)
    for post in posts:
        raw_tg_unique[(handle, int(post["message_id"]))] = {
            "handle": handle,
            "message_id": int(post["message_id"]),
            "published_at": post.get("published_at"),
            "url": post.get("url"),
            "text_hash": sha_text(post.get("text")),
            "text_chars": len(str(post.get("text") or "")),
        }
    return posts, url

monitor.telegram_page = recorded_telegram_page

fulltext_cache: dict[str, dict] = {}
fulltext_fetch_ledger: list[dict] = []
original_fulltext_fetch = monitor.fetch_publisher_fulltext

def recording_fulltext_fetch(rss_url: str):
    start_index = len(network_log)
    body, resolved_url = original_fulltext_fetch(rss_url)
    calls = network_log[start_index:]
    metadata = {"published": [], "updated": [], "other_time": []}
    for call in calls:
        host = str(call.get("final_host") or call.get("request_host") or "")
        if not host or monitor.google_host(host):
            continue
        article_meta = call.get("article_metadata") or {}
        for key in metadata:
            metadata[key].extend(article_meta.get(key) or [])
    for key in metadata:
        metadata[key] = sorted(set(metadata[key]))[:20]
    rec = {
        "body": body,
        "resolved_url": resolved_url,
        "body_hash": sha_text(body),
        "body_chars": len(body or ""),
        "article_metadata": metadata,
    }
    fulltext_cache[str(rss_url)] = rec
    if resolved_url:
        fulltext_cache.setdefault(str(resolved_url), rec)
    fulltext_fetch_ledger.append({
        "rss_url": rss_url,
        "resolved_url": resolved_url,
        "resolved_host": host_of(resolved_url),
        "body_chars": len(body or ""),
        "body_hash": sha_text(body),
        "article_metadata": metadata,
        "network_request_count": len(calls),
        "success": bool(body and resolved_url),
    })
    return body, resolved_url

monitor.fetch_publisher_fulltext = recording_fulltext_fetch

raw_rss_unique: dict[tuple, dict] = {}
raw_rss_item_encounters = 0
rss_build_ledger: list[dict] = []
original_build = monitor.build_google_news_candidate

def recorded_build(city_key, title, description, link, publisher, publisher_url, published_at, fulltext_fetcher=None):
    global raw_rss_item_encounters
    raw_rss_item_encounters += 1
    key = (city_key, link, title, published_at)
    raw_rss_unique[key] = {
        "city": city_key,
        "rss_url": link,
        "title_hash": sha_text(title),
        "description_hash": sha_text(description),
        "publisher": publisher,
        "published_at": published_at,
    }
    row, fetched, rescued = original_build(
        city_key,
        title,
        description,
        link,
        publisher,
        publisher_url,
        published_at,
        fulltext_fetcher=fulltext_fetcher,
    )
    rss_build_ledger.append({
        "city": city_key,
        "rss_url": link,
        "publisher": publisher,
        "published_at": published_at,
        "fulltext_fetch_attempted": bool(fetched),
        "rescued": bool(rescued),
        "candidate_emitted": bool(row),
        "discovery_basis": (row or {}).get("discovery_basis"),
    })
    return row, fetched, rescued

monitor.build_google_news_candidate = recorded_build

telegram_errors = monitor.refresh_telegram_cache(shadow_state, started)

telegram_rows_by_city: dict[str, list[dict]] = {}
rss_rows_by_city: dict[str, list[dict]] = {}
search_stats: dict[str, dict] = {}
search_errors: dict[str, str] = {}

for city in due_cities:
    city_due = due[city]
    earliest = min(monitor.parse_dt(ep.get("alert_start")) or started for ep, _ in city_due)
    telegram_rows_by_city[city] = monitor.telegram_candidates_for_city(shadow_state, city, earliest, started)
    try:
        rows, query_url, stats = monitor.search_city_news(city, earliest, started)
        rss_rows_by_city[city] = rows
        search_stats[city] = {
            "due_checks": len(city_due),
            "earliest_due_episode_start": monitor.iso(earliest),
            "query_url": query_url,
            "query_family_result_counts": stats.get("query_family_result_counts") or {},
            "results_after_family_merge": int(stats.get("results_after_family_merge") or 0),
            "discovery_fulltext_fetches": int(stats.get("fulltext_fetches") or 0),
            "discovery_fulltext_rescues": int(stats.get("fulltext_rescued_candidates") or 0),
        }
    except Exception as exc:
        rss_rows_by_city[city] = []
        search_errors[city] = f"{type(exc).__name__}: {exc}"
        search_stats[city] = {
            "due_checks": len(city_due),
            "earliest_due_episode_start": monitor.iso(earliest),
            "error": search_errors[city],
        }

# Restore build instrumentation before analysis. Network tracing/fulltext recording
# remain active only so durability enrichment follows the same existing source path.
monitor.build_google_news_candidate = original_build
monitor.telegram_page = original_telegram_page

# Map source-native Telegram messages from the in-memory refreshed cache.
telegram_native_by_url: dict[str, str] = {}
telegram_source_key_by_url: dict[str, str] = {}
for source_key, cfg in monitor.TELEGRAM_CHANNELS.items():
    for post in ((shadow_state.get("telegram") or {}).get(source_key) or {}).get("posts", []):
        url = str(post.get("url") or "")
        if url:
            telegram_native_by_url[url] = str(post.get("text") or "")
            telegram_source_key_by_url[url] = source_key

candidate_ledger: list[dict] = []
aggregate: dict[str, Counter] = {key: Counter() for key in SOURCE_KEYS}
city_breakdown: dict[str, dict[str, Counter]] = {
    city: {key: Counter() for key in SOURCE_KEYS} for city in due_cities
}
channel_breakdown: dict[str, Counter] = defaultdict(Counter)
publisher_breakdown: dict[str, Counter] = defaultdict(Counter)
lag_values: dict[str, list[float]] = {"telegram": [], "rss_title_snippet": [], "rss_publisher_fulltext": []}
cluster_members: dict[str, dict[str, list[dict]]] = defaultdict(lambda: {"telegram": [], "rss": []})
cluster_metadata: dict[str, dict] = {}
durability_ledger: list[dict] = []
durability_cache: dict = {}

def register_candidate(
    *,
    city: str,
    row: dict,
    representation: str,
    source_family: str,
    source_native_text: str | None = None,
    body_text: str | None = None,
    article_metadata: dict | None = None,
    durability_counterfactual: dict | None = None,
) -> dict:
    episodes = monitor.tracked_episodes_for_city(shadow_state, city)
    matching = monitor.match_candidate_to_episodes(row, episodes)
    decision = monitor.classify_candidate(row, city, episodes, matching)
    gates = semantic_gates(decision)
    temporal = candidate_temporal(decision)
    strict = strict_temporal_binding(temporal)

    official_text = monitor.classification_text(row)
    evidence_text = source_native_text if source_family == "telegram" and source_native_text else (body_text if body_text else official_text)
    features = temporal_features(evidence_text, source_row=row)
    official_features = temporal_features(official_text, source_row=row)
    native_or_body_extra_temporal = bool(
        features["any_temporal_language"] and not official_features["any_temporal_language"]
    )

    by_episode, cluster_defs = logical_cluster_map(episodes)
    cluster_key = analysis_cluster_key(matching, temporal, by_episode)
    if cluster_key:
        cluster_metadata.setdefault(cluster_key, {
            "city": city,
            "episode_ids": cluster_defs.get(cluster_key) or cluster_key.split("|"),
        })

    cid = monitor.candidate_id(city, row["url"], row["title"])
    parser_recognized = current_parser_recognized_temporal(temporal)
    current_usable = strict
    temporal_present_not_usable = bool(features["any_temporal_language"] and not current_usable)
    unsupported_by_current_parser = bool(
        features["any_temporal_language"]
        and not current_usable
        and not parser_recognized
    )

    explicit_lag_seconds = None
    if gates["semantically_strong"] and temporal.get("evidence_type") == "explicit_event_time" and temporal.get("event_time"):
        published = monitor.parse_dt(row.get("published_at"))
        event_time = monitor.parse_dt(temporal.get("event_time"))
        if published and event_time:
            explicit_lag_seconds = (published - event_time).total_seconds()
            lag_values[representation].append(explicit_lag_seconds)

    metric = aggregate[representation]
    metric["candidate_rows"] += 1
    cmetric = city_breakdown[city][representation]
    cmetric["candidate_rows"] += 1

    if gates["semantically_strong"]:
        for target in (metric, cmetric):
            target["semantically_strong_candidates"] += 1
            target["any_temporal_language"] += int(features["any_temporal_language"])
            target["explicit_clocks"] += int(features["explicit_clock"])
            target["explicit_intervals"] += int(features["explicit_interval"])
            target["accepted_contemporaneous_live_wording"] += int(features["accepted_contemporaneous_live_wording"])
            target["broad_daypart_or_date_only"] += int(features["broad_daypart_or_date_only"])
            target["retrospective_or_completed"] += int(features["retrospective_or_completed"])
            target["cumulative_or_summary"] += int(features["cumulative_or_summary"])
            target["strict_episode_specific_bindings"] += int(strict)
            target["ambiguous_multi_episode_temporal"] += int(ambiguous_temporal(temporal))
            target["no_strict_temporal_binding"] += int(not strict)
            target["current_policy_usable"] += int(current_usable)
            target["temporal_information_present_but_not_currently_usable"] += int(temporal_present_not_usable)
            target["temporal_information_present_but_not_recognized_by_current_parser"] += int(unsupported_by_current_parser)
            target["official_representation_any_temporal_language"] += int(official_features["any_temporal_language"])
            target["source_native_or_body_adds_temporal_language"] += int(native_or_body_extra_temporal)
            target["accepted_contemporaneous_live_binding"] += int(
                strict and str(temporal.get("code") or "") == "TEMPORAL_CONTEMPORANEOUS_LIVE_WORDING"
            )

        if source_family == "telegram":
            channel = str(row.get("publisher") or row.get("source") or "unknown")
            ch = channel_breakdown[channel]
            ch["semantically_strong_candidates"] += 1
            ch["strict_episode_specific_bindings"] += int(strict)
            ch["completed_event_no_safe_binding"] += int(
                features["retrospective_or_completed"] and not strict
            )
        else:
            publisher = str(row.get("publisher") or host_of(row.get("resolved_url")) or "unknown")
            pb = publisher_breakdown[publisher]
            pb["semantically_strong_candidates"] += 1
            pb["strict_episode_specific_bindings"] += int(strict)

        if cluster_key:
            family_key = "telegram" if source_family == "telegram" else "rss"
            cluster_members[cluster_key][family_key].append({
                "candidate_id": cid,
                "representation": representation,
                "strict": strict,
                "temporal_code": temporal.get("code"),
                "event_time": temporal.get("event_time"),
                "published_at": row.get("published_at"),
                "explicit_event_time": bool(temporal.get("evidence_type") == "explicit_event_time" and temporal.get("event_time")),
            })

    durability_cf_temporal = None
    if durability_counterfactual:
        durability_cf_temporal = candidate_temporal(durability_counterfactual)

    entry = {
        "city": city,
        "candidate_id": cid,
        "source_family": source_family,
        "representation": representation,
        "source": row.get("source"),
        "publisher_or_channel": row.get("publisher"),
        "url": row.get("url"),
        "resolved_url": row.get("resolved_url"),
        "published_at": row.get("published_at"),
        "feed_publication_timestamp": row.get("published_at") if source_family == "rss" else None,
        "article_publication_timestamps": list((article_metadata or {}).get("published") or []),
        "article_update_timestamps": list((article_metadata or {}).get("updated") or []),
        "source_text_excerpt": source_text_excerpt(evidence_text),
        "source_text_hash": sha_text(evidence_text),
        "source_text_chars": len(str(evidence_text or "")),
        "semantic_gates": gates,
        "temporal_features": features,
        "official_representation_temporal_features": official_features,
        "current_temporal_binding": {
            "present": bool(temporal.get("present")),
            "code": temporal.get("code"),
            "evidence_type": temporal.get("evidence_type"),
            "episode_specific": bool(temporal.get("episode_specific")),
            "episode_id": temporal.get("episode_id"),
            "supported_episode_ids": list(temporal.get("supported_episode_ids") or []),
            "event_time": temporal.get("event_time"),
            "event_interval": temporal.get("event_interval"),
            "message_time": temporal.get("message_time"),
        },
        "strict_episode_specific_binding": strict,
        "current_policy_usable": current_usable,
        "temporal_information_present_but_not_currently_usable": temporal_present_not_usable,
        "temporal_information_present_but_not_recognized_by_current_parser": unsupported_by_current_parser,
        "matching": {
            "outcome": matching.get("outcome"),
            "matched_episode_ids": list(matching.get("matched_episode_ids") or []),
            "logical_episode_groups": [list(g) for g in matching.get("logical_episode_groups") or []],
            "reason": matching.get("reason"),
        },
        "analysis_logical_alert_cluster": cluster_key,
        "explicit_event_time_lag_seconds": explicit_lag_seconds,
        "durability_counterfactual_temporal_binding": (
            {
                "present": bool(durability_cf_temporal.get("present")),
                "code": durability_cf_temporal.get("code"),
                "evidence_type": durability_cf_temporal.get("evidence_type"),
                "episode_specific": bool(durability_cf_temporal.get("episode_specific")),
                "episode_id": durability_cf_temporal.get("episode_id"),
                "event_time": durability_cf_temporal.get("event_time"),
                "event_interval": durability_cf_temporal.get("event_interval"),
            }
            if durability_cf_temporal
            else None
        ),
    }
    candidate_ledger.append(entry)
    return {
        "decision": decision,
        "gates": gates,
        "temporal": temporal,
        "strict": strict,
        "entry": entry,
        "matching": matching,
    }

# Telegram: primary classification remains the exact production adapter row.
# Source-native full message text is still inspected for temporal-information
# presence so adapter truncation is not mistaken for source absence.
for city in due_cities:
    for raw in telegram_rows_by_city.get(city, []):
        row = {**raw, "source": raw.get("source") or "Telegram"}
        native_text = telegram_native_by_url.get(str(row.get("url") or "")) or monitor.classification_text(row)
        register_candidate(
            city=city,
            row=row,
            representation="telegram",
            source_family="telegram",
            source_native_text=native_text,
        )

# RSS official representations from the normal production discovery path.
rss_analysis_cache: dict[tuple[str, str], dict] = {}
for city in due_cities:
    episodes = monitor.tracked_episodes_for_city(shadow_state, city)
    durability_network_fetches = 0
    for raw in rss_rows_by_city.get(city, []):
        row = {**raw, "source": raw.get("source") or "Google News RSS"}
        representation = (
            "rss_publisher_fulltext"
            if row.get("discovery_basis") == "publisher_fulltext"
            else "rss_title_snippet"
        )
        body, resolved_url, article_metadata = body_for_url(fulltext_cache, row.get("url"))

        # First classify official input to determine durability eligibility.
        matching = monitor.match_candidate_to_episodes(row, episodes)
        decision = monitor.classify_candidate(row, city, episodes, matching)
        gates = semantic_gates(decision)
        cf_decision = None
        durability_rec = None

        if representation == "rss_title_snippet" and gates["semantically_strong"]:
            persisted_row = row
            fetched = False
            enriched = False
            if durability_network_fetches < monitor.MAX_FULLTEXT_FETCHES_PER_CITY:
                persisted_row, fetched, enriched = monitor.enrich_rss_candidate_for_durability(
                    row,
                    decision,
                    fulltext_fetcher=recording_fulltext_fetch,
                    fetch_cache=durability_cache,
                )
                if fetched:
                    durability_network_fetches += 1
            body, resolved_url, article_metadata = body_for_url(fulltext_cache, row.get("url"))
            if body:
                cf_decision = counterfactual_fulltext_decision(row, body, city, episodes)
            durability_rec = {
                "city": city,
                "candidate_id": monitor.candidate_id(city, row["url"], row["title"]),
                "eligible_under_current_durability_rule": bool(monitor.rss_durability_enrichment_eligible(row, decision)),
                "network_fetch_performed": bool(fetched),
                "capture_succeeded": bool(enriched and body),
                "resolved_url": resolved_url,
                "resolved_host": host_of(resolved_url),
                "body_chars": len(body or ""),
                "body_hash": sha_text(body),
                "body_temporal_features": temporal_features(body, source_row=row) if body else None,
                "article_metadata": article_metadata,
                "counterfactual_parser_temporal_binding": (
                    {
                        "present": bool(candidate_temporal(cf_decision).get("present")),
                        "code": candidate_temporal(cf_decision).get("code"),
                        "evidence_type": candidate_temporal(cf_decision).get("evidence_type"),
                        "episode_specific": bool(candidate_temporal(cf_decision).get("episode_specific")),
                        "episode_id": candidate_temporal(cf_decision).get("episode_id"),
                        "event_time": candidate_temporal(cf_decision).get("event_time"),
                        "event_interval": candidate_temporal(cf_decision).get("event_interval"),
                    }
                    if cf_decision
                    else None
                ),
            }
            durability_ledger.append(durability_rec)

        register_candidate(
            city=city,
            row=row,
            representation=representation,
            source_family="rss",
            body_text=(body if representation == "rss_publisher_fulltext" else None),
            article_metadata=article_metadata,
            durability_counterfactual=cf_decision,
        )

monitor.fetch_publisher_fulltext = original_fulltext_fetch
monitor.requests.sessions.Session.request = original_session_request

# Unique strict logical-cluster binding counts.
for representation in SOURCE_KEYS:
    strict_clusters = {
        entry["analysis_logical_alert_cluster"]
        for entry in candidate_ledger
        if entry["representation"] == representation
        and entry["semantic_gates"]["semantically_strong"]
        and entry["strict_episode_specific_binding"]
        and entry["analysis_logical_alert_cluster"]
    }
    aggregate[representation]["unique_alert_episode_bindings"] = len(strict_clusters)

matched_clusters = []
outcome_counts = Counter()
matched_lag_rows = []
for cluster_key, families in sorted(cluster_members.items()):
    if not families["telegram"] or not families["rss"]:
        continue
    tg_strict = any(x["strict"] for x in families["telegram"])
    rss_strict = any(x["strict"] for x in families["rss"])
    if tg_strict and rss_strict:
        outcome = "BOTH_TEMPORAL_BINDING"
    elif tg_strict:
        outcome = "TELEGRAM_ONLY_TEMPORAL_BINDING"
    elif rss_strict:
        outcome = "RSS_ONLY_TEMPORAL_BINDING"
    else:
        outcome = "NEITHER_TEMPORAL_BINDING"
    outcome_counts[outcome] += 1

    def rank(item: dict) -> tuple:
        code = str(item.get("temporal_code") or "")
        explicit = int(bool(item.get("explicit_event_time")))
        interval = int("INTERVAL" in code)
        live = int(code == "TEMPORAL_CONTEMPORANEOUS_LIVE_WORDING")
        return (int(bool(item.get("strict"))), explicit, interval, live, code)

    best_tg = max(families["telegram"], key=rank)
    best_rss = max(families["rss"], key=rank)
    matched_clusters.append({
        "logical_alert_cluster": cluster_key,
        "city": (cluster_metadata.get(cluster_key) or {}).get("city"),
        "episode_ids": (cluster_metadata.get(cluster_key) or {}).get("episode_ids") or cluster_key.split("|"),
        "best_telegram_temporal_evidence": best_tg,
        "best_rss_temporal_evidence": best_rss,
        "telegram_strict_episode_binding": tg_strict,
        "rss_strict_episode_binding": rss_strict,
        "outcome": outcome,
        "telegram_semantically_strong_candidate_count": len(families["telegram"]),
        "rss_semantically_strong_candidate_count": len(families["rss"]),
    })

    tg_explicit = [x for x in families["telegram"] if x.get("explicit_event_time")]
    rss_explicit = [x for x in families["rss"] if x.get("explicit_event_time")]
    if tg_explicit and rss_explicit:
        tg_earliest = min(x["published_at"] for x in tg_explicit if x.get("published_at"))
        rss_earliest = min(x["published_at"] for x in rss_explicit if x.get("published_at"))
        tg_dt = monitor.parse_dt(tg_earliest)
        rss_dt = monitor.parse_dt(rss_earliest)
        if tg_dt and rss_dt:
            delta = (rss_dt - tg_dt).total_seconds()
            matched_lag_rows.append({
                "logical_alert_cluster": cluster_key,
                "city": (cluster_metadata.get(cluster_key) or {}).get("city"),
                "telegram_earliest_publication_or_message_timestamp": tg_earliest,
                "rss_earliest_publication_timestamp": rss_earliest,
                "rss_minus_telegram_seconds": delta,
                "earlier_source": "telegram" if delta > 0 else ("rss" if delta < 0 else "tie"),
            })

def finalize_metrics(counter: Counter) -> dict:
    sem = int(counter["semantically_strong_candidates"])
    strict = int(counter["strict_episode_specific_bindings"])
    clocks_or_intervals = int(counter["explicit_clocks"] + counter["explicit_intervals"])
    return {
        "candidate_rows": int(counter["candidate_rows"]),
        "semantically_strong_candidates": sem,
        "any_temporal_language": int(counter["any_temporal_language"]),
        "explicit_clocks": int(counter["explicit_clocks"]),
        "explicit_intervals": int(counter["explicit_intervals"]),
        "explicit_clock_or_interval": clocks_or_intervals,
        "accepted_contemporaneous_live_wording": int(counter["accepted_contemporaneous_live_wording"]),
        "accepted_contemporaneous_live_binding": int(counter["accepted_contemporaneous_live_binding"]),
        "broad_daypart_or_date_only": int(counter["broad_daypart_or_date_only"]),
        "retrospective_or_completed": int(counter["retrospective_or_completed"]),
        "cumulative_or_summary": int(counter["cumulative_or_summary"]),
        "strict_episode_specific_bindings": strict,
        "unique_alert_episode_bindings": int(counter["unique_alert_episode_bindings"]),
        "ambiguous_multi_episode_temporal": int(counter["ambiguous_multi_episode_temporal"]),
        "no_strict_temporal_binding": int(counter["no_strict_temporal_binding"]),
        "current_policy_usable": int(counter["current_policy_usable"]),
        "temporal_information_present_but_not_currently_usable": int(counter["temporal_information_present_but_not_currently_usable"]),
        "temporal_information_present_but_not_recognized_by_current_parser": int(counter["temporal_information_present_but_not_recognized_by_current_parser"]),
        "source_native_or_body_adds_temporal_language": int(counter["source_native_or_body_adds_temporal_language"]),
        "binding_rate": (strict / sem) if sem else None,
        "explicit_clock_or_interval_rate": (clocks_or_intervals / sem) if sem else None,
        "accepted_contemporaneous_live_binding_rate": (
            int(counter["accepted_contemporaneous_live_binding"]) / sem
        ) if sem else None,
    }

per_source = {key: finalize_metrics(aggregate[key]) for key in SOURCE_KEYS}

# Telegram decomposition required by the audit.
telegram_decomposition = Counter()
for entry in candidate_ledger:
    if entry["representation"] != "telegram" or not entry["semantic_gates"]["semantically_strong"]:
        continue
    temporal = entry["current_temporal_binding"]
    features = entry["temporal_features"]
    if temporal.get("evidence_type") == "explicit_event_time":
        telegram_decomposition["EXPLICIT_EVENT_TIME"] += 1
    elif temporal.get("code") == "TEMPORAL_CONTEMPORANEOUS_LIVE_WORDING":
        telegram_decomposition["CONTEMPORANEOUS_LIVE_WORDING"] += 1
    elif features["retrospective_or_completed"] and not entry["strict_episode_specific_binding"]:
        telegram_decomposition["NO_SAFE_BINDING_COMPLETED_EVENT"] += 1
    elif features["broad_daypart_or_date_only"] or features["cumulative_or_summary"]:
        telegram_decomposition["BROAD_OR_RETROSPECTIVE"] += 1
    else:
        telegram_decomposition["OTHER_CURRENT_TEMPORAL_CATEGORY"] += 1

# Durability-captured body is capture-only and not part of official classification.
durability_metrics = Counter()
for row in durability_ledger:
    if not row["eligible_under_current_durability_rule"]:
        continue
    durability_metrics["eligible_semantically_strong_title_snippet_candidates"] += 1
    durability_metrics["network_fetches"] += int(row["network_fetch_performed"])
    durability_metrics["capture_successes"] += int(row["capture_succeeded"])
    body_features = row.get("body_temporal_features") or {}
    durability_metrics["body_any_temporal_language"] += int(bool(body_features.get("any_temporal_language")))
    cf = row.get("counterfactual_parser_temporal_binding") or {}
    cf_strict = bool(cf.get("present") and cf.get("episode_specific") and cf.get("episode_id"))
    durability_metrics["counterfactual_parser_strict_bindings"] += int(cf_strict)
    durability_metrics["body_temporal_present_but_counterfactual_not_strict"] += int(
        bool(body_features.get("any_temporal_language")) and not cf_strict
    )

matched_total = sum(outcome_counts.values())
matched_summary = {
    "matched_logical_alert_clusters": matched_total,
    "outcomes": {
        key: {
            "count": int(outcome_counts[key]),
            "share": (outcome_counts[key] / matched_total) if matched_total else None,
        }
        for key in (
            "TELEGRAM_ONLY_TEMPORAL_BINDING",
            "RSS_ONLY_TEMPORAL_BINDING",
            "BOTH_TEMPORAL_BINDING",
            "NEITHER_TEMPORAL_BINDING",
        )
    },
    "telegram_cluster_binding_rate": (
        sum(int(x["telegram_strict_episode_binding"]) for x in matched_clusters) / matched_total
    ) if matched_total else None,
    "rss_cluster_binding_rate": (
        sum(int(x["rss_strict_episode_binding"]) for x in matched_clusters) / matched_total
    ) if matched_total else None,
}

matched_lag_summary = {
    "clusters_with_explicit_event_time_in_both": len(matched_lag_rows),
    "telegram_earlier": sum(1 for x in matched_lag_rows if x["earlier_source"] == "telegram"),
    "rss_earlier": sum(1 for x in matched_lag_rows if x["earlier_source"] == "rss"),
    "tie": sum(1 for x in matched_lag_rows if x["earlier_source"] == "tie"),
    "rss_minus_telegram_seconds": lag_summary([float(x["rss_minus_telegram_seconds"]) for x in matched_lag_rows]),
}

per_city = {}
for city in due_cities:
    per_city[city] = {
        key: finalize_metrics(city_breakdown[city][key])
        for key in SOURCE_KEYS
    }

def finalize_group_breakdown(source: dict[str, Counter]) -> dict:
    out = {}
    for name, c in sorted(source.items(), key=lambda kv: (-kv[1]["semantically_strong_candidates"], kv[0])):
        sem = int(c["semantically_strong_candidates"])
        strict = int(c["strict_episode_specific_bindings"])
        out[name] = {
            "semantically_strong_candidates": sem,
            "strict_episode_specific_bindings": strict,
            "binding_rate": (strict / sem) if sem else None,
            **({"completed_event_no_safe_binding": int(c["completed_event_no_safe_binding"])} if "completed_event_no_safe_binding" in c else {}),
        }
    return out

telegram_candidate_cities = sorted(city for city in due_cities if telegram_rows_by_city.get(city))
rss_candidate_cities = sorted(city for city in due_cities if rss_rows_by_city.get(city))
both_candidate_cities = sorted(set(telegram_candidate_cities).intersection(rss_candidate_cities))

network_hosts = Counter()
network_errors = []
for call in network_log:
    host = str(call.get("final_host") or call.get("request_host") or "")
    if host:
        network_hosts[host] += 1
    if call.get("exception_type") or (call.get("status_code") is not None and int(call["status_code"]) >= 400):
        network_errors.append({
            "method": call.get("method"),
            "request_host": call.get("request_host"),
            "final_host": call.get("final_host"),
            "status_code": call.get("status_code"),
            "exception_type": call.get("exception_type"),
            "exception_message": call.get("exception_message"),
        })

finished = monitor.now_utc()
proof = {
    "schema": "telegram_vs_rss_temporal_attribution_live_audit_v1",
    "execution": {
        "repo": os.environ.get("GITHUB_REPOSITORY"),
        "proof_branch": os.environ.get("GITHUB_REF_NAME"),
        "production_code_commit": os.environ.get("PRODUCTION_CODE_COMMIT"),
        "proof_tooling_commit": os.environ.get("GITHUB_SHA"),
        "actions_run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
        "started_at": monitor.iso(started),
        "finished_at": monitor.iso(finished),
        "observation_window": "exactly one natural bounded live observation; no repeat polling for sample improvement",
        "observed_city_set": due_cities,
        "accepted_frozen_kyiv_checkpoint_untouched": "3 STRICT / 0 SENSITIVITY / 7 REVIEW / 0 unsupported STRICT",
    },
    "denominator_contract": {
        "SEMANTICALLY_STRONG": "candidate_evidence exact_city + strict_explosion/accepted attack-event + air_military_context + same_attack_context all present under current classifier",
        "strict_episode_specific_binding": "candidate temporal_binding present=true, episode_specific=true, and episode_id non-null",
        "cluster_assignment_for_comparison": "strict temporal episode when available; otherwise unique publication-window match used only to assign the source document to a logical alert cluster, never as event-time proof",
        "telegram_primary_binding_input": "actual production adapter candidate row; full source-native message inspected separately for temporal-information presence",
        "rss_durability_body": "capture-only counterfactual; never fed into official title/snippet classification",
    },
    "source_availability": {
        "configured_telegram_channels": [
            {"key": key, "handle": cfg["handle"], "label": cfg["label"]}
            for key, cfg in monitor.TELEGRAM_CHANNELS.items()
        ],
        "cities_due": due_cities,
        "cities_with_telegram_candidate_rows": telegram_candidate_cities,
        "cities_with_rss_candidate_rows": rss_candidate_cities,
        "cities_with_both_candidate_sources": both_candidate_cities,
    },
    "raw_observations": {
        "telegram_page_item_encounters": raw_tg_page_encounters,
        "telegram_unique_source_native_messages_observed": len(raw_tg_unique),
        "rss_feed_item_encounters_across_query_families": raw_rss_item_encounters,
        "rss_unique_feed_items_by_city_url_title_time": len(raw_rss_unique),
        "rss_publisher_fulltext_fetch_attempts": len(fulltext_fetch_ledger),
        "network_request_count": len(network_log),
        "network_request_hosts": dict(sorted(network_hosts.items())),
        "network_errors": network_errors,
    },
    "per_source_aggregate_metrics": per_source,
    "telegram_temporal_decomposition": {k: int(v) for k, v in sorted(telegram_decomposition.items())},
    "rss_durability_capture_only": {
        **{k: int(v) for k, v in sorted(durability_metrics.items())},
        "counterfactual_parser_binding_rate_over_eligible": (
            durability_metrics["counterfactual_parser_strict_bindings"]
            / durability_metrics["eligible_semantically_strong_title_snippet_candidates"]
        ) if durability_metrics["eligible_semantically_strong_title_snippet_candidates"] else None,
    },
    "matched_alert_cluster_comparison": matched_summary,
    "explicit_time_lag_analysis": {
        "telegram": lag_summary(lag_values["telegram"]),
        "rss_title_snippet": lag_summary(lag_values["rss_title_snippet"]),
        "rss_publisher_fulltext": lag_summary(lag_values["rss_publisher_fulltext"]),
        "matched_source_publication_timing": matched_lag_summary,
    },
    "city_breakdown": per_city,
    "telegram_channel_breakdown": finalize_group_breakdown(channel_breakdown),
    "rss_publisher_breakdown": finalize_group_breakdown(publisher_breakdown),
    "candidate_level_ledger": sorted(candidate_ledger, key=lambda x: (x["city"], x["representation"], x["candidate_id"])),
    "matched_alert_cluster_ledger": matched_clusters,
    "matched_source_lag_ledger": matched_lag_rows,
    "durability_capture_ledger": durability_ledger,
    "fulltext_fetch_ledger": fulltext_fetch_ledger,
    "discovery_stats": search_stats,
    "telegram_errors": telegram_errors,
    "rss_search_errors": search_errors,
    "safety": {
        "monitor_main_called": False,
        "state_or_queue_write_function_called": False,
        "database_environment_expected": False,
        "public_web_research_used": False,
        "manual_event_search_used": False,
        "repeat_polling_used": False,
        "full_article_bodies_persisted_in_artifact": False,
    },
}

result_path = OUT_DIR / "telegram_vs_rss_temporal_attribution_live_audit_v1.json"
result_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
digest = hashlib.sha256(result_path.read_bytes()).hexdigest()
(OUT_DIR / "telegram_vs_rss_temporal_attribution_live_audit_v1.sha256").write_text(
    f"{digest}  {result_path.name}\n",
    encoding="utf-8",
)

summary = {
    "production_code_commit": os.environ.get("PRODUCTION_CODE_COMMIT"),
    "proof_tooling_commit": os.environ.get("GITHUB_SHA"),
    "actions_run_id": int(os.environ.get("GITHUB_RUN_ID", "0")),
    "started_at": monitor.iso(started),
    "finished_at": monitor.iso(finished),
    "observed_city_set": due_cities,
    "raw_observations": proof["raw_observations"],
    "source_availability": proof["source_availability"],
    "per_source_aggregate_metrics": per_source,
    "telegram_temporal_decomposition": proof["telegram_temporal_decomposition"],
    "rss_durability_capture_only": proof["rss_durability_capture_only"],
    "matched_alert_cluster_comparison": matched_summary,
    "explicit_time_lag_analysis": proof["explicit_time_lag_analysis"],
    "telegram_channel_breakdown": proof["telegram_channel_breakdown"],
    "rss_publisher_breakdown": proof["rss_publisher_breakdown"],
    "rss_search_errors": search_errors,
    "telegram_errors": telegram_errors,
    "json_sha256": digest,
}
(OUT_DIR / "summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)

print("AUDIT_JSON_SHA256=" + digest)
print("AUDIT_CITIES=" + json.dumps(due_cities, ensure_ascii=False))
print("AUDIT_SOURCE_METRICS=" + json.dumps(per_source, ensure_ascii=False, sort_keys=True))
print("AUDIT_MATCHED_CLUSTERS=" + json.dumps(matched_summary, ensure_ascii=False, sort_keys=True))
print("AUDIT_TELEGRAM_DECOMPOSITION=" + json.dumps(proof["telegram_temporal_decomposition"], ensure_ascii=False, sort_keys=True))
print("AUDIT_DURABILITY=" + json.dumps(proof["rss_durability_capture_only"], ensure_ascii=False, sort_keys=True))
print("AUDIT_LAG=" + json.dumps(proof["explicit_time_lag_analysis"], ensure_ascii=False, sort_keys=True))
print("AUDIT_TG_ERRORS=" + json.dumps(telegram_errors, ensure_ascii=False, sort_keys=True))
print("AUDIT_RSS_ERRORS=" + json.dumps(search_errors, ensure_ascii=False, sort_keys=True))
