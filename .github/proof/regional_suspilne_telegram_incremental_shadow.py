#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path.cwd() / "kyiv-air-alerts-grafana"
sys.path.insert(0, str(ROOT / "scripts"))

import monitor_explosion_candidates as monitor

UTC = timezone.utc
PRODUCTION_CODE_COMMIT = os.environ.get("PRODUCTION_CODE_COMMIT", "")
WINDOW_START_UTC = os.environ.get("WINDOW_START_UTC", "")
WINDOW_END_UTC = os.environ.get("WINDOW_END_UTC", "")
PROOF_WORKFLOW_COMMIT = os.environ.get("PROOF_WORKFLOW_COMMIT", "")
ACTIONS_RUN_ID = os.environ.get("GITHUB_RUN_ID", "")
ACTIONS_RUN_ATTEMPT = os.environ.get("GITHUB_RUN_ATTEMPT", "")
LIVE_STATE_COMMIT = os.environ.get("LIVE_STATE_COMMIT", "")
LIVE_STATE_SHA256 = os.environ.get("LIVE_STATE_SHA256", "")
INVENTORY_GIT_BLOB = os.environ.get("INVENTORY_GIT_BLOB", "")
INVENTORY_SHA256 = os.environ.get("INVENTORY_SHA256", "")
MONITOR_BLOB = os.environ.get("MONITOR_BLOB", "")
OUTPUT_PATH = Path(os.environ.get("OUTPUT_PATH", "/tmp/regional_suspilne_telegram_incremental_shadow_2026-10-05.json"))
SUMMARY_PATH = Path(os.environ.get("SUMMARY_PATH", "/tmp/regional_suspilne_telegram_incremental_shadow_summary.json"))
INVENTORY_PATH = Path("research/suspilne_regional_telegram_inventory_2026-10-05.json")

REQUIRED_COMPARISON_CLASSES = {
    "DUPLICATE_OF_EXISTING_TELEGRAM_EVIDENCE",
    "DUPLICATE_OF_EXISTING_RSS_EVIDENCE",
    "NEW_EVIDENCE_FOR_ALREADY_COVERED_EPISODE",
    "NEW_EVIDENCE_FOR_PREVIOUSLY_UNCOVERED_EPISODE",
    "NEW_EVIDENCE_BUT_NO_SAFE_EPISODE_BINDING",
    "NOT_QUALIFYING_ATTACK_EVIDENCE",
}

VERDICT_HIGH = "REGIONAL SUSPILNE TELEGRAM SHADOW = HIGH INCREMENTAL VALUE"
VERDICT_MODERATE = "REGIONAL SUSPILNE TELEGRAM SHADOW = MODERATE INCREMENTAL VALUE"
VERDICT_LOW = "REGIONAL SUSPILNE TELEGRAM SHADOW = LOW INCREMENTAL VALUE"
VERDICT_INSUFFICIENT = "REGIONAL SUSPILNE TELEGRAM SHADOW = INSUFFICIENT SAMPLE"
VERDICT_BLOCKED = "REGIONAL SUSPILNE TELEGRAM SHADOW = BLOCKED"

REC_INTEGRATE = "INTEGRATE REGIONAL SUSPILNE TELEGRAM SOURCES"
REC_SELECTIVE = "INTEGRATE SELECTIVE REGIONAL SUSPILNE TELEGRAM SOURCES"
REC_MORE = "GATHER MORE SHADOW DATA"
REC_NONE = "NO MATERIAL INCREMENTAL VALUE"


def clean(value) -> str:
    return " ".join(str(value or "").split())


def parse_required_dt(value: str, name: str) -> datetime:
    dt = monitor.parse_dt(value)
    if not dt:
        raise RuntimeError(f"INVALID_{name}")
    return dt


def iso(dt: datetime) -> str:
    return monitor.iso(dt)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def norm_text(value: str) -> str:
    return clean(monitor.normalize_evidence_text(value))


def token_set(value: str) -> set[str]:
    return set(re.findall(r"[\w'-]{3,}", norm_text(value), flags=re.UNICODE))


def parse_ts(value: str | None) -> datetime | None:
    return monitor.parse_dt(value)


def time_delta_seconds(a: str | None, b: str | None) -> float | None:
    da, db = parse_ts(a), parse_ts(b)
    if not da or not db:
        return None
    return abs((da - db).total_seconds())


def near_duplicate(a: dict, b: dict) -> bool:
    if a.get("city") != b.get("city"):
        return False
    ta = str(a.get("normalized_classification_text") or "")
    tb = str(b.get("normalized_classification_text") or "")
    if not ta or not tb:
        return False
    if ta == tb:
        return True
    dt = time_delta_seconds(a.get("published_at"), b.get("published_at"))
    if dt is None or dt > 3 * 3600:
        return False
    shorter, longer = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    if len(shorter) >= 80 and shorter in longer and len(shorter) / max(1, len(longer)) >= 0.62:
        return True
    sa, sb = token_set(ta), token_set(tb)
    if not sa or not sb:
        return False
    jaccard = len(sa & sb) / max(1, len(sa | sb))
    return jaccard >= 0.78


def fetch_telegram_window(handle: str, start: datetime, end: datetime) -> dict:
    raw_handle = handle.lstrip("@")
    max_pages = int(getattr(monitor, "TELEGRAM_MAX_PAGES", 8))
    before = None
    pages = 0
    retries = 0
    raw_window_encounters = 0
    unique: dict[int, dict] = {}
    readable = False
    window_complete = False
    termination = None
    errors: list[str] = []
    oldest_seen: datetime | None = None
    newest_seen: datetime | None = None
    collection_started = monitor.now_utc()

    while pages < max_pages:
        page = None
        last_exc = None
        for attempt in range(3):
            try:
                page, _ = monitor.telegram_page(raw_handle, before)
                readable = True
                retries += attempt
                break
            except Exception as exc:
                last_exc = exc
                if attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
        if page is None:
            errors.append(f"{type(last_exc).__name__}: {last_exc}" if last_exc else "unknown_telegram_fetch_error")
            termination = "fetch_error"
            break

        pages += 1
        if not page:
            window_complete = True
            termination = "empty_page"
            break

        parsed: list[tuple[dict, datetime]] = []
        for post in page:
            dt = parse_ts(post.get("published_at"))
            if not dt:
                continue
            parsed.append((post, dt))
            oldest_seen = dt if oldest_seen is None or dt < oldest_seen else oldest_seen
            newest_seen = dt if newest_seen is None or dt > newest_seen else newest_seen
            if start <= dt <= end:
                raw_window_encounters += 1
                unique[int(post["message_id"])] = post

        if not parsed:
            window_complete = True
            termination = "no_parseable_timestamps"
            break

        page_oldest = min(dt for _, dt in parsed)
        page_newest = max(dt for _, dt in parsed)
        if page_oldest <= start:
            window_complete = True
            termination = "reached_window_start"
            break
        if page_newest < start:
            window_complete = True
            termination = "page_entirely_before_window"
            break

        next_before = min(int(post["message_id"]) for post, _ in parsed)
        if before is not None and next_before >= before:
            errors.append("pagination_did_not_advance")
            termination = "pagination_stalled"
            break
        before = next_before

    if pages >= max_pages and not window_complete and not errors:
        termination = "max_pages_before_window_start"

    collection_finished = monitor.now_utc()
    rows = sorted(unique.values(), key=lambda r: (r.get("published_at") or "", int(r.get("message_id") or 0)))
    return {
        "handle": handle,
        "readable": readable,
        "window_complete": window_complete,
        "pages_fetched": pages,
        "max_pages": max_pages,
        "retries": retries,
        "raw_window_message_encounters": raw_window_encounters,
        "unique_window_messages": len(rows),
        "oldest_seen": iso(oldest_seen) if oldest_seen else None,
        "newest_seen": iso(newest_seen) if newest_seen else None,
        "collection_started_at": iso(collection_started),
        "collection_finished_at": iso(collection_finished),
        "termination": termination,
        "errors": errors,
        "posts": rows,
    }


def telegram_candidate_row(post: dict, label: str, handle: str) -> dict:
    text = str(post.get("text") or "")
    return {
        "source": f"Telegram / {label}",
        "title": text[:240] or f"Telegram post {post.get('message_id')}",
        "url": str(post.get("url") or f"https://t.me/{handle.lstrip('@')}/{post.get('message_id') or ''}"),
        "publisher": label,
        "publisher_url": f"https://t.me/{handle.lstrip('@')}",
        "published_at": post.get("published_at"),
        "snippet": text[:1200],
    }


def logical_support(decision: dict, matching: dict) -> dict:
    temporal = dict(decision.get("temporal_binding") or {})
    temporal_groups = [sorted(str(x) for x in group if x) for group in (temporal.get("logical_episode_groups") or []) if group]
    matching_groups = [sorted(str(x) for x in group if x) for group in (matching.get("logical_episode_groups") or []) if group]
    groups = temporal_groups if len(temporal_groups) == 1 else matching_groups if len(matching_groups) == 1 else []
    if len(groups) == 1:
        members = groups[0]
        return {
            "unique_logical_episode": True,
            "logical_episode_key": "|".join(members),
            "raw_episode_ids": members,
            "basis": "temporal_binding" if len(temporal_groups) == 1 else "publication_window_matching",
        }
    return {
        "unique_logical_episode": False,
        "logical_episode_key": None,
        "raw_episode_ids": [],
        "basis": "ambiguous_or_unbound",
        "temporal_group_count": len(temporal_groups),
        "matching_group_count": len(matching_groups),
    }


def semantic_gate_summary(decision: dict) -> dict:
    ev = decision.get("candidate_evidence") or {}
    exact = bool((ev.get("exact_city") or {}).get("present"))
    attack = bool((ev.get("strict_explosion") or {}).get("present"))
    air = bool((ev.get("air_military_context") or {}).get("present"))
    same = bool((ev.get("same_attack_context") or {}).get("present"))
    disposition = str(decision.get("proposed_outcome") or "needs_review")
    qualifying = bool(exact and attack and air and same and disposition != "rejected")
    return {
        "city_match": exact,
        "attack_event": attack,
        "air_context": air,
        "same_attack": same,
        "qualifying_attack_evidence": qualifying,
    }


def classify_row(row: dict, city: str, episodes: list[dict]) -> dict:
    matching = monitor.match_candidate_to_episodes(row, episodes)
    decision = monitor.classify_candidate(row, city, episodes, matching)
    gates = semantic_gate_summary(decision)
    support = logical_support(decision, matching)
    text = monitor.classification_text(row)
    return {
        "city": city,
        "row": row,
        "matching": matching,
        "decision": decision,
        "gates": gates,
        "support": support,
        "normalized_classification_text": norm_text(text),
        "published_at": row.get("published_at"),
    }


def baseline_record(kind: str, classified: dict) -> dict:
    row = classified["row"]
    decision = classified["decision"]
    return {
        "source_kind": kind,
        "city": classified["city"],
        "url": row.get("url"),
        "publisher": row.get("publisher"),
        "published_at": row.get("published_at"),
        "title": row.get("title"),
        "snippet": row.get("snippet"),
        "matched_text_excerpt": row.get("matched_text_excerpt"),
        "discovery_basis": row.get("discovery_basis"),
        "qualifying_attack_evidence": bool(classified["gates"]["qualifying_attack_evidence"]),
        "semantic_gates": classified["gates"],
        "logical_alert_support": classified["support"],
        "classifier_disposition": decision.get("proposed_outcome"),
        "proposed_matched_episode_id": decision.get("proposed_matched_episode_id"),
        "temporal_result": decision.get("temporal_binding"),
        "normalized_classification_text": classified["normalized_classification_text"],
    }


def regional_record(city: str, handle: str, post: dict, collected_at: str, classified: dict) -> dict:
    decision = classified["decision"]
    ev = decision.get("candidate_evidence") or {}
    gates = classified["gates"]
    return {
        "source_handle": handle,
        "message_id": int(post.get("message_id") or 0),
        "canonical_telegram_url": post.get("url"),
        "source_native_timestamp": post.get("published_at"),
        "complete_source_text": str(post.get("text") or ""),
        "mapped_city": city,
        "collection_timestamp": collected_at,
        "city_match_result": ev.get("exact_city") or {},
        "attack_event_result": ev.get("strict_explosion") or {},
        "air_context_result": ev.get("air_military_context") or {},
        "same_attack_result": ev.get("same_attack_context") or {},
        "temporal_result": ev.get("temporal_binding") or {},
        "episode_logical_alert_support": classified["support"],
        "resulting_classifier_disposition": decision.get("proposed_outcome"),
        "proposed_matched_episode_id": decision.get("proposed_matched_episode_id"),
        "sensitivity_basis": decision.get("sensitivity_basis"),
        "qualifying_attack_evidence": bool(gates["qualifying_attack_evidence"]),
        "semantic_gate_summary": gates,
        "normalized_classification_text": classified["normalized_classification_text"],
        "classification_input_contract": {
            "title_chars": 240,
            "snippet_chars": 1200,
            "complete_source_text_retained_separately": True,
        },
        "comparison_class": None,
        "regional_cluster_id": None,
    }


def best_binding(member_records: list[dict]) -> str:
    outcomes = {str(x.get("resulting_classifier_disposition") or "") for x in member_records}
    if "approved_strict" in outcomes:
        return "STRICT"
    if "approved_sensitivity" in outcomes:
        return "SENSITIVITY"
    return "REVIEW"


def cluster_regional_qualifying(records: list[dict]) -> list[dict]:
    by_key: dict[tuple[str, str], list[dict]] = defaultdict(list)
    unbound_by_city: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        support = rec.get("episode_logical_alert_support") or {}
        key = support.get("logical_episode_key")
        if key:
            by_key[(rec["mapped_city"], str(key))].append(rec)
        else:
            unbound_by_city[rec["mapped_city"]].append(rec)

    groups: list[list[dict]] = list(by_key.values())
    for city, items in sorted(unbound_by_city.items()):
        parent = list(range(len(items)))

        def find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def union(i: int, j: int) -> None:
            a, b = find(i), find(j)
            if a != b:
                if a < b:
                    parent[b] = a
                else:
                    parent[a] = b

        cmp_items = [
            {
                "city": city,
                "normalized_classification_text": rec.get("normalized_classification_text"),
                "published_at": rec.get("source_native_timestamp"),
            }
            for rec in items
        ]
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if near_duplicate(cmp_items[i], cmp_items[j]):
                    union(i, j)
        tmp: dict[int, list[dict]] = defaultdict(list)
        for i, rec in enumerate(items):
            tmp[find(i)].append(rec)
        groups.extend(tmp.values())

    clusters = []
    for members in groups:
        members = sorted(members, key=lambda x: (x.get("source_native_timestamp") or "", x.get("message_id") or 0))
        city = members[0]["mapped_city"]
        keys = sorted({str((m.get("episode_logical_alert_support") or {}).get("logical_episode_key")) for m in members if (m.get("episode_logical_alert_support") or {}).get("logical_episode_key")})
        logical_key = keys[0] if len(keys) == 1 else None
        identity = city + "|" + (logical_key or "UNBOUND") + "|" + "|".join(
            f"{m['source_handle']}:{m['message_id']}" for m in members
        )
        cluster_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        for member in members:
            member["regional_cluster_id"] = cluster_id
        clusters.append({
            "cluster_id": cluster_id,
            "city": city,
            "member_count": len(members),
            "member_refs": [f"{m['source_handle']}:{m['message_id']}" for m in members],
            "logical_episode_key": logical_key,
            "logical_episode_raw_ids": sorted({rid for m in members for rid in ((m.get("episode_logical_alert_support") or {}).get("raw_episode_ids") or [])}),
            "logical_episode_support_basis": sorted({str((m.get("episode_logical_alert_support") or {}).get("basis") or "") for m in members}),
            "best_binding": best_binding(members),
            "comparison_class": None,
            "duplicate_baseline_refs": [],
            "member_records": members,
        })
    return sorted(clusters, key=lambda x: (x["city"], x.get("logical_episode_key") or "", x["cluster_id"]))


def classify_cluster_against_baseline(cluster: dict, baseline: list[dict]) -> None:
    city = cluster["city"]
    members = cluster["member_records"]
    city_base = [b for b in baseline if b.get("city") == city and b.get("qualifying_attack_evidence")]
    duplicates_tg = []
    duplicates_rss = []
    for member in members:
        probe = {
            "city": city,
            "normalized_classification_text": member.get("normalized_classification_text"),
            "published_at": member.get("source_native_timestamp"),
        }
        for base in city_base:
            other = {
                "city": city,
                "normalized_classification_text": base.get("normalized_classification_text"),
                "published_at": base.get("published_at"),
            }
            if near_duplicate(probe, other):
                ref = {"source_kind": base.get("source_kind"), "url": base.get("url"), "published_at": base.get("published_at")}
                if base.get("source_kind") == "telegram":
                    duplicates_tg.append(ref)
                else:
                    duplicates_rss.append(ref)

    baseline_keys = {
        str((b.get("logical_alert_support") or {}).get("logical_episode_key"))
        for b in city_base
        if (b.get("logical_alert_support") or {}).get("logical_episode_key")
    }
    logical_key = cluster.get("logical_episode_key")
    if duplicates_tg:
        category = "DUPLICATE_OF_EXISTING_TELEGRAM_EVIDENCE"
        dup = duplicates_tg
    elif duplicates_rss:
        category = "DUPLICATE_OF_EXISTING_RSS_EVIDENCE"
        dup = duplicates_rss
    elif logical_key and logical_key in baseline_keys:
        category = "NEW_EVIDENCE_FOR_ALREADY_COVERED_EPISODE"
        dup = []
    elif logical_key:
        category = "NEW_EVIDENCE_FOR_PREVIOUSLY_UNCOVERED_EPISODE"
        dup = []
    else:
        category = "NEW_EVIDENCE_BUT_NO_SAFE_EPISODE_BINDING"
        dup = []
    assert category in REQUIRED_COMPARISON_CLASSES
    cluster["comparison_class"] = category
    cluster["duplicate_baseline_refs"] = dup[:20]
    for member in members:
        member["comparison_class"] = category


def outcome_counts_for_incremental_episode_clusters(clusters: list[dict]) -> dict:
    by_episode: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in clusters:
        if c.get("comparison_class") != "NEW_EVIDENCE_FOR_PREVIOUSLY_UNCOVERED_EPISODE":
            continue
        key = c.get("logical_episode_key")
        if key:
            by_episode[(c["city"], str(key))].append(c)
    out = Counter()
    for _, rows in by_episode.items():
        bindings = {r.get("best_binding") for r in rows}
        if "STRICT" in bindings:
            out["STRICT"] += 1
        elif "SENSITIVITY" in bindings:
            out["SENSITIVITY"] += 1
        else:
            out["REVIEW"] += 1
    return {"strict": out["STRICT"], "sensitivity": out["SENSITIVITY"], "review": out["REVIEW"]}


def decide_verdict(blockers: list[str], qualifying_messages: int, unique_clusters: int, uncovered_episodes: int, strict: int, sensitivity: int) -> tuple[str, str]:
    if blockers:
        return VERDICT_BLOCKED, REC_MORE
    if qualifying_messages < 5 or unique_clusters < 3:
        return VERDICT_INSUFFICIENT, REC_MORE
    safe = strict + sensitivity
    if uncovered_episodes >= 4 and safe >= 2:
        return VERDICT_HIGH, REC_INTEGRATE
    if uncovered_episodes >= 1:
        return VERDICT_MODERATE, REC_SELECTIVE
    return VERDICT_LOW, REC_NONE


def main() -> None:
    start = parse_required_dt(WINDOW_START_UTC, "WINDOW_START_UTC")
    end = parse_required_dt(WINDOW_END_UTC, "WINDOW_END_UTC")
    if not start < end:
        raise RuntimeError("INVALID_WINDOW_ORDER")
    if (end - start) != timedelta(hours=12):
        raise RuntimeError("WINDOW_MUST_BE_EXACTLY_12_HOURS")
    if PRODUCTION_CODE_COMMIT != "c26307efcea065813870dc27901dbd225f4f3e33":
        raise RuntimeError("UNEXPECTED_PRODUCTION_CODE_COMMIT")

    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    if inventory.get("verdict") != "SUSPILNE REGIONAL TELEGRAM INVENTORY = COMPLETE":
        raise RuntimeError("INVENTORY_VERDICT_NOT_ACCEPTED")
    if inventory.get("production_monitor_commit_inspected") != PRODUCTION_CODE_COMMIT:
        raise RuntimeError("INVENTORY_PRODUCTION_COMMIT_MISMATCH")
    city_inventory = list(inventory.get("city_inventory") or [])
    if len(city_inventory) != 23:
        raise RuntimeError(f"INVENTORY_CITY_COUNT_{len(city_inventory)}")
    handles = [str(row.get("official_current_handle") or "") for row in city_inventory]
    if len(set(handles)) != 23 or any(not h.startswith("@") for h in handles):
        raise RuntimeError("INVENTORY_HANDLE_IDENTITY_INVALID")
    city_keys = [str(row.get("city_key") or "") for row in city_inventory]
    if len(set(city_keys)) != 23 or any(city not in monitor.CITY_CONFIG for city in city_keys):
        raise RuntimeError("INVENTORY_CITY_KEYS_NOT_PRODUCTION_CITY_CONFIG")

    state = monitor.load_json(monitor.STATE_FILE, {})
    if not isinstance(state, dict) or state.get("schema_version") != 1:
        raise RuntimeError("INVALID_LIVE_STATE")
    episodes_by_city = {
        city: list(((state.get("cities") or {}).get(city) or {}).get("episodes") or [])
        for city in city_keys
    }

    run_collected_at = iso(monitor.now_utc())
    regional_fetches: dict[str, dict] = {}
    regional_records: list[dict] = []
    blockers: list[str] = []

    for idx, inv in enumerate(city_inventory, 1):
        city = str(inv["city_key"])
        handle = str(inv["official_current_handle"])
        label = str(inv.get("regional_suspilne_brand") or inv.get("city") or handle)
        fetch = fetch_telegram_window(handle, start, end)
        regional_fetches[city] = {k: v for k, v in fetch.items() if k != "posts"}
        print(f"REGIONAL {idx:02d}/23 {city} {handle}: readable={fetch['readable']} complete={fetch['window_complete']} messages={fetch['unique_window_messages']}", flush=True)
        if not fetch["readable"]:
            blockers.append(f"regional_unreadable:{city}:{handle}")
        if not fetch["window_complete"]:
            blockers.append(f"regional_window_incomplete:{city}:{handle}:{fetch.get('termination')}")
        for post in fetch["posts"]:
            row = telegram_candidate_row(post, label, handle)
            classified = classify_row(row, city, episodes_by_city[city])
            regional_records.append(regional_record(city, handle, post, fetch["collection_finished_at"], classified))

    baseline_records: list[dict] = []
    baseline_telegram_fetches: dict[str, dict] = {}
    prod_handles = []
    for source_key, cfg in monitor.TELEGRAM_CHANNELS.items():
        handle = "@" + str(cfg["handle"]).lstrip("@")
        prod_handles.append({"source_key": source_key, "handle": handle, "label": cfg["label"], "baseline_after": cfg.get("baseline_after")})
        fetch = fetch_telegram_window(handle, start, end)
        baseline_telegram_fetches[source_key] = {k: v for k, v in fetch.items() if k != "posts"}
        print(f"BASELINE TELEGRAM {source_key} {handle}: readable={fetch['readable']} complete={fetch['window_complete']} messages={fetch['unique_window_messages']}", flush=True)
        if not fetch["readable"]:
            blockers.append(f"baseline_telegram_unreadable:{source_key}:{handle}")
        if not fetch["window_complete"]:
            blockers.append(f"baseline_telegram_window_incomplete:{source_key}:{handle}:{fetch.get('termination')}")
        for post in fetch["posts"]:
            text = str(post.get("text") or "")
            if not monitor.explosion_relevant(text):
                continue
            row = telegram_candidate_row(post, str(cfg["label"]), handle)
            for city in city_keys:
                if not monitor.city_mentioned(city, text):
                    continue
                classified = classify_row(row, city, episodes_by_city[city])
                baseline_records.append(baseline_record("telegram", classified))

    rss_collection: dict[str, dict] = {}
    for idx, city in enumerate(city_keys, 1):
        rows = None
        stats = None
        last_exc = None
        attempts = 0
        for attempt in range(2):
            attempts = attempt + 1
            try:
                rows, _, stats = monitor.search_city_news(city, start, end)
                last_exc = None
                break
            except Exception as exc:
                last_exc = exc
                if attempt == 0:
                    time.sleep(2)
        if rows is None:
            msg = f"{type(last_exc).__name__}: {last_exc}" if last_exc else "unknown_rss_error"
            rss_collection[city] = {"success": False, "attempts": attempts, "error": msg}
            blockers.append(f"rss_collection_failed:{city}:{msg}")
            print(f"BASELINE RSS {idx:02d}/23 {city}: ERROR {msg}", flush=True)
            continue
        exact_rows = []
        excluded_outside = 0
        excluded_missing_time = 0
        for row in rows:
            published = parse_ts(row.get("published_at"))
            if not published:
                excluded_missing_time += 1
                continue
            if not (start <= published <= end):
                excluded_outside += 1
                continue
            exact_rows.append(row)
            classified = classify_row(row, city, episodes_by_city[city])
            kind = "rss_publisher_fulltext" if row.get("discovery_basis") == "publisher_fulltext" else "rss_title_snippet"
            baseline_records.append(baseline_record(kind, classified))
        rss_collection[city] = {
            "success": True,
            "attempts": attempts,
            "rows_returned_before_exact_window_filter": len(rows),
            "rows_in_exact_window": len(exact_rows),
            "excluded_outside_exact_window": excluded_outside,
            "excluded_missing_publication_time": excluded_missing_time,
            "search_stats": stats or {},
        }
        print(f"BASELINE RSS {idx:02d}/23 {city}: rows={len(exact_rows)}", flush=True)

    qualifying_regional = [r for r in regional_records if r["qualifying_attack_evidence"]]
    nonqualifying_regional = [r for r in regional_records if not r["qualifying_attack_evidence"]]
    for rec in nonqualifying_regional:
        rec["comparison_class"] = "NOT_QUALIFYING_ATTACK_EVIDENCE"

    clusters = cluster_regional_qualifying(qualifying_regional)
    for cluster in clusters:
        classify_cluster_against_baseline(cluster, baseline_records)

    cluster_ledger = []
    for cluster in clusters:
        row = dict(cluster)
        row.pop("member_records", None)
        cluster_ledger.append(row)

    category_counts = Counter(c["comparison_class"] for c in clusters)
    incremental_clusters = [c for c in clusters if c["comparison_class"] in {"NEW_EVIDENCE_FOR_PREVIOUSLY_UNCOVERED_EPISODE", "NEW_EVIDENCE_BUT_NO_SAFE_EPISODE_BINDING"}]
    already_covered_clusters = [c for c in clusters if c["comparison_class"] in {"DUPLICATE_OF_EXISTING_TELEGRAM_EVIDENCE", "DUPLICATE_OF_EXISTING_RSS_EVIDENCE", "NEW_EVIDENCE_FOR_ALREADY_COVERED_EPISODE"}]
    uncovered_episode_keys = sorted({(c["city"], str(c["logical_episode_key"])) for c in clusters if c["comparison_class"] == "NEW_EVIDENCE_FOR_PREVIOUSLY_UNCOVERED_EPISODE" and c.get("logical_episode_key")})
    regional_episode_keys = sorted({(c["city"], str(c["logical_episode_key"])) for c in clusters if c.get("logical_episode_key")})
    new_outcomes = outcome_counts_for_incremental_episode_clusters(clusters)
    no_safe_binding_clusters = [c for c in incremental_clusters if c.get("best_binding") == "REVIEW"]

    city_output = {}
    for inv in city_inventory:
        city = str(inv["city_key"])
        handle = str(inv["official_current_handle"])
        city_records = [r for r in regional_records if r["mapped_city"] == city]
        city_clusters = [c for c in clusters if c["city"] == city]
        city_uncovered_keys = {(c["city"], str(c["logical_episode_key"])) for c in city_clusters if c["comparison_class"] == "NEW_EVIDENCE_FOR_PREVIOUSLY_UNCOVERED_EPISODE" and c.get("logical_episode_key")}
        city_outcomes = outcome_counts_for_incremental_episode_clusters(city_clusters)
        city_output[city] = {
            "regional_channel": handle,
            "messages_observed_in_window": len(city_records),
            "qualifying_attack_evidence": sum(1 for r in city_records if r["qualifying_attack_evidence"]),
            "unique_attack_clusters": len(city_clusters),
            "clusters_already_covered_by_production": sum(1 for c in city_clusters if c in already_covered_clusters),
            "incremental_clusters": sum(1 for c in city_clusters if c in incremental_clusters),
            "previously_uncovered_episodes_gaining_evidence": len(city_uncovered_keys),
            "new_STRICT": city_outcomes["strict"],
            "new_SENSITIVITY": city_outcomes["sensitivity"],
            "new_REVIEW": city_outcomes["review"],
            "no_safe_binding_cases": sum(1 for c in city_clusters if c in no_safe_binding_clusters),
        }

    raw_regional_messages = sum(int(v.get("raw_window_message_encounters") or 0) for v in regional_fetches.values())
    unique_regional_items = len(regional_records)
    channels_readable = sum(1 for v in regional_fetches.values() if v.get("readable"))
    channels_failed = 23 - channels_readable
    aggregate = {
        "channels_attempted": 23,
        "channels_successfully_readable": channels_readable,
        "channels_failed_or_unreadable": channels_failed,
        "channels_with_complete_window": sum(1 for v in regional_fetches.values() if v.get("window_complete")),
        "raw_regional_messages": raw_regional_messages,
        "qualifying_attack_messages": len(qualifying_regional),
        "unique_regional_evidence": unique_regional_items,
        "unique_logical_attack_clusters": len(clusters),
        "unique_logical_alert_episodes_supported_by_regional_evidence": len(regional_episode_keys),
        "clusters_already_covered_by_production": len(already_covered_clusters),
        "incremental_clusters": len(incremental_clusters),
        "previously_uncovered_logical_alert_episodes_gaining_evidence": len(uncovered_episode_keys),
        "new_STRICT": new_outcomes["strict"],
        "new_SENSITIVITY": new_outcomes["sensitivity"],
        "new_REVIEW": new_outcomes["review"],
        "new_evidence_without_safe_binding": len(no_safe_binding_clusters),
        "comparison_class_counts": dict(sorted(category_counts.items())),
        "baseline_qualifying_evidence_items": sum(1 for b in baseline_records if b.get("qualifying_attack_evidence")),
        "baseline_total_classified_items": len(baseline_records),
        "city_distribution_of_incremental_gains": {
            city: {
                "incremental_clusters": row["incremental_clusters"],
                "previously_uncovered_episodes_gaining_evidence": row["previously_uncovered_episodes_gaining_evidence"],
                "new_STRICT": row["new_STRICT"],
                "new_SENSITIVITY": row["new_SENSITIVITY"],
                "new_REVIEW": row["new_REVIEW"],
                "no_safe_binding_cases": row["no_safe_binding_cases"],
            }
            for city, row in city_output.items()
            if row["incremental_clusters"] or row["previously_uncovered_episodes_gaining_evidence"]
        },
    }

    verdict, recommendation = decide_verdict(
        blockers,
        aggregate["qualifying_attack_messages"],
        aggregate["unique_logical_attack_clusters"],
        aggregate["previously_uncovered_logical_alert_episodes_gaining_evidence"],
        aggregate["new_STRICT"],
        aggregate["new_SENSITIVITY"],
    )

    artifact = {
        "schema_version": "1.0",
        "artifact_scope": "PROOF_ONLY_NON_PERSISTING_LIVE_REGIONAL_SUSPILNE_TELEGRAM_INCREMENTAL_COVERAGE_SHADOW",
        "generated_at": run_collected_at,
        "proof_integrity": {
            "production_semantic_commit": PRODUCTION_CODE_COMMIT,
            "production_monitor_blob": MONITOR_BLOB,
            "inventory_path": str(INVENTORY_PATH),
            "inventory_git_blob": INVENTORY_GIT_BLOB,
            "inventory_sha256": INVENTORY_SHA256,
            "inventory_library_origin_preserved_as_exact_json_copy": True,
            "proof_workflow_commit": PROOF_WORKFLOW_COMMIT,
            "actions_run_id": ACTIONS_RUN_ID,
            "actions_run_attempt": ACTIONS_RUN_ATTEMPT,
            "live_state_branch": "multicity-wip-2026-09-16",
            "live_state_commit": LIVE_STATE_COMMIT,
            "live_state_sha256": LIVE_STATE_SHA256,
            "parallel_14_window_panel_reused": False,
            "parallel_14_window_panel_artifacts_read": False,
            "parallel_14_window_panel_source_set_modified": False,
            "production_monitor_main_called": False,
            "database_environment_required": False,
        },
        "observation_window": {
            "window_start_utc": iso(start),
            "window_end_utc": iso(end),
            "duration_seconds": int((end - start).total_seconds()),
            "window_frozen_before_live_collection": True,
            "same_interval_used_for_baseline_and_regional": True,
        },
        "baseline_source_identity": {
            "production_telegram_channels": prod_handles,
            "rss_discovery_query_families": [str(x[0]) for x in monitor.GOOGLE_NEWS_QUERY_FAMILIES],
            "rss_discovery_implementation": "monitor.search_city_news",
            "google_news_resolver_implementation": "frozen production monitor helper",
            "source_set_commit": PRODUCTION_CODE_COMMIT,
        },
        "regional_source_identity": [
            {
                "city_key": str(row["city_key"]),
                "city": row.get("city"),
                "handle": str(row["official_current_handle"]),
                "canonical_url": row.get("canonical_url"),
            }
            for row in city_inventory
        ],
        "methodology": {
            "telegram_fetch_helper": "monitor.telegram_page",
            "telegram_page_limit": int(getattr(monitor, "TELEGRAM_MAX_PAGES", 8)),
            "regional_channel_discovery_performed": False,
            "classification_helper": "monitor.classify_candidate",
            "episode_matching_helper": "monitor.match_candidate_to_episodes",
            "temporal_parser_semantics_modified": False,
            "message_time_substituted_for_event_time": False,
            "logical_episode_support_priority": ["classifier temporal logical group", "publication-window matching logical group"],
            "unbound_cluster_dedup": "same-city near-duplicate only; <=3h and exact/containment/Jaccard>=0.78",
            "baseline_duplicate_priority": ["production Telegram near-duplicate", "production RSS near-duplicate", "already-covered logical episode"],
            "primary_metric_definition": "unique logical alert episodes absent from qualifying production-baseline evidence that gain qualifying regional evidence with one logical episode support",
            "secondary_metric_definition": "primary episodes whose best regional classifier disposition is STRICT or SENSITIVITY",
            "verdict_thresholds": {
                "BLOCKED": "any regional/baseline Telegram incomplete/unreadable window or any city RSS collection failure",
                "INSUFFICIENT_SAMPLE": "otherwise qualifying regional messages <5 or unique regional clusters <3",
                "HIGH_INCREMENTAL_VALUE": "otherwise >=4 previously uncovered logical episodes and >=2 STRICT+SENSITIVITY",
                "MODERATE_INCREMENTAL_VALUE": "otherwise >=1 previously uncovered logical episode",
                "LOW_INCREMENTAL_VALUE": "otherwise 0 previously uncovered logical episodes",
            },
        },
        "collection_health": {
            "blockers": blockers,
            "regional_telegram": regional_fetches,
            "baseline_telegram": baseline_telegram_fetches,
            "baseline_rss": rss_collection,
        },
        "raw_and_deduplicated_denominators": {
            "raw_regional_messages": raw_regional_messages,
            "unique_regional_evidence_items": unique_regional_items,
            "qualifying_regional_messages": len(qualifying_regional),
            "deduplicated_logical_attack_clusters": len(clusters),
            "unique_logical_alert_episodes": len(regional_episode_keys),
        },
        "city_level": city_output,
        "aggregate": aggregate,
        "regional_message_ledger": regional_records,
        "regional_cluster_ledger": cluster_ledger,
        "baseline_evidence_ledger": baseline_records,
        "mutation_confirmation": {
            "status": "PENDING_WORKFLOW_POSTRUN_GUARD"
        },
        "verdict": verdict,
        "recommendation": recommendation,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "workflow_commit": PROOF_WORKFLOW_COMMIT,
        "actions_run_id": ACTIONS_RUN_ID,
        "window_start_utc": iso(start),
        "window_end_utc": iso(end),
        "channels_readable": channels_readable,
        "channels_attempted": 23,
        "qualifying_regional_messages": aggregate["qualifying_attack_messages"],
        "unique_regional_clusters": aggregate["unique_logical_attack_clusters"],
        "incremental_clusters": aggregate["incremental_clusters"],
        "previously_uncovered_episodes_gaining_evidence": aggregate["previously_uncovered_logical_alert_episodes_gaining_evidence"],
        "new_STRICT": aggregate["new_STRICT"],
        "new_SENSITIVITY": aggregate["new_SENSITIVITY"],
        "new_REVIEW": aggregate["new_REVIEW"],
        "city_distribution_of_incremental_gain": aggregate["city_distribution_of_incremental_gains"],
        "verdict": verdict,
        "recommendation": recommendation,
        "blockers": blockers,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SHADOW_SUMMARY=" + json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
