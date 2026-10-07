#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import hashlib
import html
import json
import math
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone, date
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote_plus, urlsplit, urlunsplit

import requests

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "kyiv-air-alerts-grafana"
SCRIPTS = APP / "scripts"
sys.path.insert(0, str(SCRIPTS))

import monitor_explosion_candidates as monitor
from historical_attack_event_sources import NetworkBounds, PublicTelegramAdapter

UTC = timezone.utc
START_POST = date(2025, 2, 13)
END_POST = date(2026, 9, 17)
END_HIST = date(2025, 2, 12)
EXPECTED_TARGET = 982
EXPECTED_POS = 145
EXPECTED_HOLDS = 57
EXPECTED_PREVIOUS_209 = 209
EXPECTED_CLASSIFIER_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
CLASSIFIER_REL = Path("kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py")
ALERTS_PATH = APP / "data" / "alerts_combined.json"
OUTPUT_PATH = ROOT / "research" / "kyiv_postcutoff_historical_backfill_shadow_2026-10-07.json"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; ukraine-air-alerts-historical-shadow-backfill/1.0)",
    "Accept-Language": "uk,en;q=0.8",
}

LABEL_MAP = {
    "STRICT": "STRICT",
    "APPROVED_STRICT": "STRICT",
    "SENSITIVITY": "SENSITIVITY",
    "APPROVED_SENSITIVITY": "SENSITIVITY",
    "NEEDS_REVIEW": "NEEDS_REVIEW",
    "REVIEW": "NEEDS_REVIEW",
    "NO_CONFIRMED_EVENT": "NO_CONFIRMED_EVENT",
    "NO_CONFIRMED": "NO_CONFIRMED_EVENT",
}

URL_RE = re.compile(r"^https?://", re.I)

def parse_dt(v):
    if not v:
        return None
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def iso(dt):
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")

def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256_file(path: Path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def git_blob(path: Path) -> str:
    import subprocess
    p = subprocess.run(
        ["git", "hash-object", str(path)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return p.stdout.strip()

def canonical_url(url: str | None) -> str:
    if not url:
        return ""
    try:
        parts = urlsplit(str(url).strip())
        host = parts.hostname.lower() if parts.hostname else ""
        scheme = parts.scheme.lower()
        netloc = host
        if parts.port:
            netloc += f":{parts.port}"
        path = re.sub(r"/+$", "", parts.path or "")
        return urlunsplit((scheme, netloc, path, parts.query, ""))
    except Exception:
        return str(url).strip()

def normalize_label(v: str | None):
    if not isinstance(v, str):
        return None
    key = re.sub(r"[^A-Z0-9]+", "_", v.strip().upper()).strip("_")
    return LABEL_MAP.get(key)

def episodes_from_alerts():
    rows = load_json(ALERTS_PATH)
    eps = monitor.load_kyiv_alert_episodes(ALERTS_PATH)
    if len(eps) != 2456:
        raise RuntimeError(f"authoritative Kyiv episode count drift: {len(eps)} != 2456")
    return eps

def local_date(ep):
    return date.fromisoformat(ep["alert_start_date_kyiv"])

def range_eps(episodes, start_d, end_d):
    return [ep for ep in episodes if start_d <= local_date(ep) <= end_d]

def rss_query_absolute(city_label: str, start_d: date, end_d: date) -> str:
    base = monitor.google_news_query(city_label)
    if "when:8d" not in base:
        raise RuntimeError("accepted Google News query family no longer contains when:8d temporal operator")
    before = end_d + timedelta(days=1)
    return base.replace("when:8d", f"after:{start_d.isoformat()} before:{before.isoformat()}")

def parse_pubdate(v):
    if not v:
        return None
    try:
        dt = parsedate_to_datetime(v)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def fetch_google_window(start_d: date, end_d: date, session: requests.Session):
    label = monitor.CITY_CONFIG["kyiv"]["label"]
    query = rss_query_absolute(label, start_d, end_d)
    url = f"{monitor.GOOGLE_NEWS_URL}?q={quote_plus(query)}&hl=uk&gl=UA&ceid=UA:uk"
    stats = {
        "family": "google_news_rss",
        "query": query,
        "window_start": start_d.isoformat(),
        "window_end": end_d.isoformat(),
        "url": url,
        "status": "OK",
        "rss_items": 0,
        "retained_candidates": 0,
        "fulltext_fetches": 0,
        "fulltext_rescues": 0,
        "error": None,
    }
    try:
        r = session.get(url, timeout=45)
        r.raise_for_status()
        root = ET.fromstring(r.content)
    except Exception as exc:
        stats["status"] = "ERROR"
        stats["error"] = f"{type(exc).__name__}: {exc}"
        return [], stats

    rows = []
    fulltext_fetches = 0
    fulltext_rescues = 0
    for item in root.findall(".//item"):
        stats["rss_items"] += 1
        title = monitor.clean_text(item.findtext("title") or "")
        description = monitor.clean_text(item.findtext("description") or "")
        link = (item.findtext("link") or "").strip()
        published = parse_pubdate(item.findtext("pubDate"))
        source_el = item.find("source")
        publisher = monitor.clean_text(source_el.text or "") if source_el is not None else ""
        publisher_url = (source_el.attrib.get("url") or "").strip() if source_el is not None else ""
        if not title or not link:
            continue
        # Preserve the accepted resolver/fulltext cap per bounded historical query window.
        fetcher = monitor.fetch_publisher_fulltext if fulltext_fetches < monitor.MAX_FULLTEXT_FETCHES_PER_CITY else None
        row, fetched, rescued = monitor.build_google_news_candidate(
            "kyiv",
            title,
            description,
            link,
            publisher,
            publisher_url,
            iso(published) if published else None,
            fulltext_fetcher=fetcher,
        )
        if fetched:
            fulltext_fetches += 1
        if rescued:
            fulltext_rescues += 1
        if row:
            row["source"] = "Google News RSS"
            row["historical_query_window"] = [start_d.isoformat(), end_d.isoformat()]
            rows.append(row)
    stats["fulltext_fetches"] = fulltext_fetches
    stats["fulltext_rescues"] = fulltext_rescues
    stats["retained_candidates"] = len(rows)
    return rows, stats

def telegram_candidate(cfg, post):
    text = str(post.get("text") or "")
    return {
        "source": f"Telegram / {cfg['label']}",
        "title": text[:240] or f"Telegram post {post.get('message_id')}",
        "url": post.get("url"),
        "publisher": cfg["label"],
        "publisher_url": f"https://t.me/{cfg['handle']}",
        "published_at": post.get("published_at"),
        "snippet": text[:1200],
        "matched_text_excerpt": text[:50000],
        "discovery_basis": "historical_public_telegram_search",
    }

def fetch_telegram_range(start_dt: datetime, end_dt: datetime):
    rows = []
    stats = []
    bounds = NetworkBounds(
        timeout_seconds=15,
        max_retries=2,
        rate_limit_seconds=0.2,
        max_telegram_pages=monitor.TELEGRAM_MAX_PAGES,
        max_neighbor_previous=3,
    )
    adapter = PublicTelegramAdapter(bounds)
    query = monitor.CITY_CONFIG["kyiv"]["label"]
    for source_key, cfg in monitor.TELEGRAM_CHANNELS.items():
        s = {
            "family": f"telegram/{cfg['handle']}",
            "query": query,
            "window_start": iso(start_dt),
            "window_end": iso(end_dt),
            "status": "OK",
            "pages": 0,
            "requests_made": 0,
            "raw_posts": 0,
            "retained_candidates": 0,
            "error": None,
        }
        try:
            posts, meta = adapter.search(
                cfg["handle"], query, start_dt, end_dt, max_pages=monitor.TELEGRAM_MAX_PAGES
            )
            s["pages"] = int(meta.get("pages") or 0)
            s["requests_made"] = int(meta.get("requests_made") or 0)
            s["raw_posts"] = len(posts)
            for post in posts:
                text = str(post.get("text") or "")
                if not monitor.city_mentioned("kyiv", text):
                    continue
                if not monitor.explosion_relevant(text):
                    continue
                rows.append(telegram_candidate(cfg, post))
            s["retained_candidates"] = len([r for r in rows if r.get("publisher")==cfg["label"]])
        except Exception as exc:
            s["status"] = "ERROR"
            s["error"] = f"{type(exc).__name__}: {exc}"
        stats.append(s)
    return rows, stats

def discover_range(name: str, episodes):
    if not episodes:
        return [], {"name": name, "errors": ["no episodes"]}
    start_d = min(local_date(ep) for ep in episodes)
    end_d = max(local_date(ep) for ep in episodes)
    session = requests.Session()
    session.headers.update(HEADERS)
    all_rows = []
    google_stats = []
    cur = start_d
    while cur <= end_d:
        win_end = min(end_d, cur + timedelta(days=7))
        rows, stat = fetch_google_window(cur, win_end, session)
        all_rows.extend(rows)
        google_stats.append(stat)
        cur = win_end + timedelta(days=1)
        time.sleep(0.15)

    tg_start = min(parse_dt(ep["alert_start"]) for ep in episodes) - timedelta(hours=3)
    tg_end = max(parse_dt(ep["alert_end"]) for ep in episodes) + timedelta(hours=72)
    tg_rows, tg_stats = fetch_telegram_range(tg_start, tg_end)
    all_rows.extend(tg_rows)

    dedup = {}
    for row in all_rows:
        key = (canonical_url(row.get("url")), str(row.get("title") or ""), str(row.get("published_at") or ""))
        dedup[key] = row
    rows = list(dedup.values())
    return rows, {
        "name": name,
        "date_start": start_d.isoformat(),
        "date_end": end_d.isoformat(),
        "candidate_count": len(rows),
        "google": google_stats,
        "telegram": tg_stats,
    }

def make_item(row, episodes):
    matching = monitor.match_candidate_to_episodes(row, episodes)
    decision = monitor.classify_candidate(row, "kyiv", episodes, matching)
    cid = monitor.candidate_id("kyiv", str(row.get("url") or ""), str(row.get("title") or ""))
    item = {
        "candidate_id": cid,
        "city_key": "kyiv",
        "source": row.get("source") or "Google News RSS",
        "publisher": row.get("publisher"),
        "url": row.get("url"),
        "resolved_url": row.get("resolved_url"),
        "title": row.get("title"),
        "snippet": row.get("snippet"),
        "published_at": row.get("published_at"),
        "discovery_basis": row.get("discovery_basis"),
        "matched_text_excerpt": row.get("matched_text_excerpt"),
        "status": decision.get("proposed_outcome"),
        "matched_episode_id": None,
        "classification_reason_codes": list(decision.get("reason_codes") or []),
        "classification_evidence": monitor.classification_evidence_payload(decision),
        "matching_outcome": matching.get("outcome"),
        "matched_episode_ids": list(matching.get("matched_episode_ids") or []),
        "matching_logical_episode_groups": [list(x) for x in matching.get("logical_episode_groups") or []],
        "matching_reason": matching.get("reason"),
        "_decision": decision,
        "_matching": matching,
    }
    if matching.get("outcome") == "unique_match" and matching.get("matched_episode_id"):
        item["matched_episode_id"] = matching.get("matched_episode_id")
    if decision.get("proposed_outcome") in {"approved_strict", "approved_sensitivity"}:
        item["matched_episode_id"] = decision.get("proposed_matched_episode_id")
    return item

def evaluate_candidates(rows, episodes):
    items = [make_item(r, episodes) for r in rows]
    by_ep = collections.defaultdict(list)
    for item in items:
        decision = item["_decision"]
        ids = set(item.get("matched_episode_ids") or [])
        for k in ("proposed_matched_episode_id",):
            if decision.get(k):
                ids.add(str(decision[k]))
        tb = decision.get("temporal_binding") or {}
        if tb.get("episode_id"):
            ids.add(str(tb["episode_id"]))
        nb = tb.get("near_boundary") or {}
        if nb.get("episode_id"):
            ids.add(str(nb["episode_id"]))
        for eid in ids:
            by_ep[eid].append(item)

    ep_map = {str(ep["episode_id"]): ep for ep in episodes}
    composed = {}
    for eid, candidates in by_ep.items():
        target = ep_map.get(eid)
        if not target or len(candidates) < 2:
            continue
        comp = monitor.compose_episode_candidates("kyiv", target, candidates, episodes)
        if comp.get("final_composed_verdict") == "approved_strict":
            composed[eid] = comp

    return items, by_ep, composed

def outcome_for_episode(eid, by_ep, composed, before):
    if eid in composed:
        return "STRICT"
    statuses = [str(x.get("status") or "") for x in by_ep.get(eid, [])]
    if "approved_strict" in statuses:
        return "STRICT"
    if "approved_sensitivity" in statuses:
        return "SENSITIVITY"
    if "needs_review" in statuses:
        return "NEEDS_REVIEW"
    return before

def primary_blocker(item):
    d = item["_decision"]
    exact = (d.get("exact_city_classification_evidence") or {}).get("present")
    strict = (d.get("strict_explosion_evidence") or {}).get("present")
    air = (d.get("air_military_context") or {}).get("present")
    same = (d.get("same_attack_context") or {}).get("present")
    temporal = d.get("temporal_binding") or {}
    if not strict:
        return "NEW_EVIDENCE_NO_QUALIFYING_EVENT"
    if not exact:
        return "QUALIFYING_EVENT_BUT_NOT_EXACT_KYIV"
    if not air:
        return "AIR_CONTEXT_INSUFFICIENT"
    if not same:
        return "SAME_ATTACK_NOT_PROVEN"
    if not (temporal.get("present") and temporal.get("episode_specific")):
        return "TEMPORAL_BINDING_AMBIGUOUS"
    if not item.get("title") and not item.get("snippet") and not item.get("matched_text_excerpt"):
        return "EVIDENCE_PAYLOAD_INCOMPLETE"
    return "OTHER"

def best_blocker(items):
    # Multiple candidates may exist for one logical alert. Report the blocker
    # from the candidate that progressed furthest through the unchanged classifier
    # gates, rather than letting a weaker sibling candidate mask stronger evidence.
    order = [
        "OTHER",
        "EVIDENCE_PAYLOAD_INCOMPLETE",
        "TEMPORAL_BINDING_AMBIGUOUS",
        "SAME_ATTACK_NOT_PROVEN",
        "AIR_CONTEXT_INSUFFICIENT",
        "QUALIFYING_EVENT_BUT_NOT_EXACT_KYIV",
        "NEW_EVIDENCE_NO_QUALIFYING_EVENT",
    ]
    found = {primary_blocker(x) for x in items}
    for x in order:
        if x in found:
            return x
    return "OTHER"

def snapshot_index(snapshot, known_ids):
    labels = collections.defaultdict(list)
    urls = collections.defaultdict(set)
    label_keys = collections.Counter()

    def rec(obj, ctx=None, parent_key=""):
        if isinstance(obj, dict):
            local_ctx = ctx
            # Direct identifiers first.
            for k, v in obj.items():
                if isinstance(v, str) and v in known_ids and ("episode" in k.casefold() or k.casefold().endswith("_id") or k.casefold() == "id"):
                    local_ctx = v
                    break
            if local_ctx:
                for k, v in obj.items():
                    if isinstance(v, str):
                        lab = normalize_label(v)
                        if lab and any(tok in k.casefold() for tok in ("class", "outcome", "status", "verdict", "state", "disposition")):
                            labels[local_ctx].append((lab, k))
                            label_keys[k] += 1
                        if URL_RE.match(v):
                            urls[local_ctx].add(canonical_url(v))
            for k, v in obj.items():
                if isinstance(k, str) and k in known_ids:
                    rec(v, k, k)
                else:
                    rec(v, local_ctx, str(k))
        elif isinstance(obj, list):
            for v in obj:
                rec(v, ctx, parent_key)
        elif isinstance(obj, str) and ctx:
            lab = normalize_label(obj)
            if lab and any(tok in parent_key.casefold() for tok in ("class", "outcome", "status", "verdict", "state", "disposition")):
                labels[ctx].append((lab, parent_key))
                label_keys[parent_key] += 1
            if URL_RE.match(obj):
                urls[ctx].add(canonical_url(obj))

    rec(snapshot)
    final = {}
    for eid, vals in labels.items():
        # Prefer explicit final/disposition/classification fields over nested candidate statuses.
        pri = [v for v in vals if any(tok in v[1].casefold() for tok in ("final", "disposition", "classification", "outcome"))]
        use = pri or vals
        labs = {v[0] for v in use}
        if "STRICT" in labs:
            final[eid] = "STRICT"
        elif "SENSITIVITY" in labs:
            final[eid] = "SENSITIVITY"
        elif "NEEDS_REVIEW" in labs:
            final[eid] = "NEEDS_REVIEW"
        elif "NO_CONFIRMED_EVENT" in labs:
            final[eid] = "NO_CONFIRMED_EVENT"
    return final, urls, dict(label_keys)

def strip_private(item):
    out = {k: v for k, v in item.items() if not k.startswith("_")}
    # Keep only durable evidence needed for audit/classifier traceability.
    out["snippet"] = str(out.get("snippet") or "")[:1200]
    out["matched_text_excerpt"] = str(out.get("matched_text_excerpt") or "")[:1200]
    return out

def is_qualifying(item):
    d = item["_decision"]
    return bool(
        (d.get("strict_explosion_evidence") or {}).get("present")
        and (d.get("exact_city_classification_evidence") or {}).get("present")
    )

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = ap.parse_args()

    if git_blob(ROOT / CLASSIFIER_REL) != EXPECTED_CLASSIFIER_BLOB:
        raise RuntimeError("authoritative classifier blob mismatch")

    # Production/read-only mutation sentinels.
    protected = [
        APP / "scripts" / "monitor_explosion_candidates.py",
        APP / "scripts" / "historical_attack_event_sources.py",
        APP / "data" / "alerts_combined.json",
        APP / "data" / "explosion_candidate_monitor_state.json",
        APP / "data" / "explosion_review_queue.json",
        ROOT / "research" / "historical_attack_event_source_registry.json",
    ]
    before_hash = {str(p.relative_to(ROOT)): sha256_file(p) for p in protected if p.exists()}

    episodes = episodes_from_alerts()
    target_eps = range_eps(episodes, START_POST, END_POST)
    hist_eps = [ep for ep in episodes if local_date(ep) <= END_HIST]
    if len(target_eps) != EXPECTED_TARGET:
        raise RuntimeError(f"target denominator drift: {len(target_eps)} != {EXPECTED_TARGET}")

    # Step 1 discovery is label-blind: run over the full historical pre-cutoff alert universe.
    cal_rows, cal_discovery = discover_range("historical_calibration_universe", hist_eps)
    cal_items, cal_by_ep, cal_composed = evaluate_candidates(cal_rows, hist_eps)

    # Labels are loaded only after calibration discovery.
    snapshot = load_json(args.snapshot)
    known_ids = {str(ep["episode_id"]) for ep in episodes}
    snap_outcomes, snap_urls, label_keys = snapshot_index(snapshot, known_ids)

    hist_ids = {str(ep["episode_id"]) for ep in hist_eps}
    target_ids = {str(ep["episode_id"]) for ep in target_eps}
    positive_ids = {eid for eid in hist_ids if snap_outcomes.get(eid) in {"STRICT", "SENSITIVITY"}}
    hold_ids = {eid for eid in hist_ids if snap_outcomes.get(eid) == "NEEDS_REVIEW"}
    previous209 = {eid for eid in target_ids if snap_outcomes.get(eid) == "NEEDS_REVIEW"}
    target_no_confirmed = {eid for eid in target_ids if snap_outcomes.get(eid) == "NO_CONFIRMED_EVENT"}

    extraction_ok = (
        len(positive_ids) == EXPECTED_POS
        and len(hold_ids) == EXPECTED_HOLDS
        and len(previous209) == EXPECTED_PREVIOUS_209
        and len(target_no_confirmed) == EXPECTED_TARGET - EXPECTED_PREVIOUS_209
    )

    if not extraction_ok:
        artifact = {
            "verdict": "KYIV POST-CUTOFF HISTORICAL BACKFILL = BLOCKED",
            "status": "BLOCKED_CONTROL_EXTRACTION",
            "target_alerts": len(target_eps),
            "calibration": {
                "positives_extracted": len(positive_ids),
                "holds_extracted": len(hold_ids),
            },
            "postcutoff": {
                "previous_review_extracted": len(previous209),
                "no_confirmed_extracted": len(target_no_confirmed),
            },
            "snapshot_label_keys": label_keys,
            "classifier": {
                "commit": "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453",
                "blob": EXPECTED_CLASSIFIER_BLOB,
            },
            "mutation_confirmation": {
                "classifier_mutations": 0,
                "parser_mutations": 0,
                "temporal_representation_mutations": 0,
                "alert_grouping_mutations": 0,
                "source_configuration_mutations": 0,
                "historical_state_mutations": 0,
                "queue_mutations": 0,
                "persistence_mutations": 0,
                "neon_queries": 0,
                "neon_writes": 0,
                "deployments": 0,
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(artifact["status"]))
        return 3

    def ep_positive_from_eval(eid, by_ep, comp):
        out = outcome_for_episode(eid, by_ep, comp, "NO_CONFIRMED_EVENT")
        return out in {"STRICT", "SENSITIVITY"}

    cal_evidence_hits = {eid for eid in positive_ids if cal_by_ep.get(eid)}
    cal_final_hits = {eid for eid in positive_ids if ep_positive_from_eval(eid, cal_by_ep, cal_composed)}
    hold_promotions = {eid for eid in hold_ids if ep_positive_from_eval(eid, cal_by_ep, cal_composed)}

    calibration = {
        "positives_tested": len(positive_ids),
        "positive_control_evidence_recall_n": len(cal_evidence_hits),
        "positive_control_evidence_recall_pct": round(100 * len(cal_evidence_hits) / len(positive_ids), 2),
        "positive_control_final_classification_recall_n": len(cal_final_hits),
        "positive_control_final_classification_recall_pct": round(100 * len(cal_final_hits) / len(positive_ids), 2),
        "holds_tested": len(hold_ids),
        "historical_hold_false_promotions": len(hold_promotions),
    }

    if hold_promotions:
        # Safety gate: do not trust or execute the post-cutoff promotion phase.
        artifact = {
            "verdict": "KYIV POST-CUTOFF HISTORICAL BACKFILL = BLOCKED",
            "status": "BLOCKED_CALIBRATION_FALSE_PROMOTIONS",
            "target_alerts": len(target_eps),
            "calibration": calibration,
            "discovery": {"calibration": cal_discovery},
            "mutation_confirmation": {
                "classifier_mutations": 0,
                "parser_mutations": 0,
                "temporal_representation_mutations": 0,
                "alert_grouping_mutations": 0,
                "source_configuration_mutations": 0,
                "historical_state_mutations": 0,
                "queue_mutations": 0,
                "persistence_mutations": 0,
                "neon_queries": 0,
                "neon_writes": 0,
                "deployments": 0,
            },
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(artifact["status"]))
        return 4

    # Step 2: full 982 target discovery, still label-blind.
    target_rows, target_discovery = discover_range("postcutoff_982", target_eps)
    target_items, target_by_ep_all, target_composed_all = evaluate_candidates(target_rows, target_eps)

    # Existing evidence is consulted only now, after discovery, for comparison/dedup and before/after accounting.
    existing_urls_global = set()
    for eid in target_ids:
        existing_urls_global.update(snap_urls.get(eid, set()))

    new_items = []
    existing_redisc = []
    for item in target_items:
        urls = {canonical_url(item.get("url")), canonical_url(item.get("resolved_url"))}
        urls.discard("")
        if urls & existing_urls_global:
            existing_redisc.append(item)
        else:
            new_items.append(item)

    # Re-evaluate using only genuinely new evidence so a backfill gain cannot be credited to pre-existing evidence.
    new_rows = []
    new_cids = {x["candidate_id"] for x in new_items}
    for row in target_rows:
        cid = monitor.candidate_id("kyiv", str(row.get("url") or ""), str(row.get("title") or ""))
        if cid in new_cids:
            new_rows.append(row)
    new_items, new_by_ep, new_composed = evaluate_candidates(new_rows, target_eps)

    ledger = []
    blocker_counts = collections.Counter()
    any_new = 0
    qualifying_new = 0
    newly_strict = 0
    newly_sensitivity = 0
    newly_confirmed = 0
    prev209_confirmed = 0
    remaining_review = 0
    remaining_no = 0

    for ep in target_eps:
        eid = str(ep["episode_id"])
        before = "NEEDS_REVIEW" if eid in previous209 else "NO_CONFIRMED_EVENT"
        ep_items = new_by_ep.get(eid, [])
        after = outcome_for_episode(eid, new_by_ep, new_composed, before)
        has_new = bool(ep_items)
        has_qual = any(is_qualifying(x) for x in ep_items)
        if has_new:
            any_new += 1
        if has_qual:
            qualifying_new += 1
        if after == "STRICT":
            newly_strict += 1
            newly_confirmed += 1
            if eid in previous209:
                prev209_confirmed += 1
        elif after == "SENSITIVITY":
            newly_sensitivity += 1
            newly_confirmed += 1
            if eid in previous209:
                prev209_confirmed += 1
        elif after == "NEEDS_REVIEW":
            remaining_review += 1
            if has_new:
                blocker_counts[best_blocker(ep_items)] += 1
        else:
            remaining_no += 1
            if has_new:
                blocker_counts[best_blocker(ep_items)] += 1

        evidence_rows = [strip_private(x) for x in ep_items]
        ledger.append({
            "alert_episode_id": eid,
            "alert_start": ep["alert_start"],
            "alert_end": ep["alert_end"],
            "whether_evidence_already_existed": eid in previous209,
            "whether_new_evidence_was_found": has_new,
            "source_family": sorted({str(x.get("source") or "") for x in evidence_rows}),
            "source_url": [x.get("url") for x in evidence_rows],
            "publication_source_timestamp": [x.get("published_at") for x in evidence_rows],
            "retained_excerpt_fulltext_status": [
                {
                    "candidate_id": x.get("candidate_id"),
                    "discovery_basis": x.get("discovery_basis"),
                    "retained_excerpt": bool(x.get("snippet") or x.get("matched_text_excerpt")),
                    "fulltext": x.get("discovery_basis") == "publisher_fulltext",
                }
                for x in evidence_rows
            ],
            "classifier_outcome_before_backfill": before,
            "classifier_outcome_after_new_evidence": after,
            "first_failing_gate_if_unresolved": (
                best_blocker(ep_items) if has_new and after not in {"STRICT", "SENSITIVITY"} else None
            ),
            "new_evidence": evidence_rows,
            "episode_level_composition": new_composed.get(eid),
        })

    prev209_still = len(previous209) - prev209_confirmed
    if remaining_review + remaining_no + newly_confirmed != EXPECTED_TARGET:
        raise RuntimeError("post-backfill accounting does not sum to 982")

    if newly_confirmed >= 25:
        verdict = "KYIV POST-CUTOFF HISTORICAL BACKFILL = MATERIAL GAIN"
    elif newly_confirmed > 0:
        verdict = "KYIV POST-CUTOFF HISTORICAL BACKFILL = SMALL GAIN"
    else:
        verdict = "KYIV POST-CUTOFF HISTORICAL BACKFILL = NO MATERIAL GAIN"

    after_hash = {str(p.relative_to(ROOT)): sha256_file(p) for p in protected if p.exists()}
    changed_protected = sorted(k for k in set(before_hash) | set(after_hash) if before_hash.get(k) != after_hash.get(k))
    if changed_protected:
        raise RuntimeError(f"protected production paths changed during shadow run: {changed_protected}")

    artifact = {
        "verdict": verdict,
        "status": "COMPLETE",
        "generated_at_utc": iso(datetime.now(UTC)),
        "scope": {
            "city": "kyiv",
            "postcutoff_start": START_POST.isoformat(),
            "postcutoff_end": END_POST.isoformat(),
            "target_alerts": EXPECTED_TARGET,
            "unit": "logical_alert_episode",
        },
        "classifier": {
            "commit": "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453",
            "blob": EXPECTED_CLASSIFIER_BLOB,
            "unchanged": True,
        },
        "discovery_contract": {
            "anti_leak": True,
            "inputs_used_for_discovery": ["city", "alert_start", "alert_end", "accepted_source_configuration", "accepted_query_family"],
            "inputs_not_used_for_discovery": ["known_positive", "previous_209_membership", "truth_url", "final_verdict"],
            "source_families": [
                "Telegram / susplinews",
                "Telegram / ukrpravda_news",
                "Google News RSS",
                "publisher fulltext recovery via authoritative monitor",
            ],
            "google_query_semantics": "authoritative google_news_query terms unchanged; only when:8d temporal operator expressed as absolute 8-day historical windows",
            "telegram_query_semantics": "accepted PublicTelegramAdapter.search using exact city label Київ",
        },
        "calibration": calibration,
        "aggregate_summary": {
            "target_alerts": EXPECTED_TARGET,
            "alerts_with_any_newly_discovered_evidence": any_new,
            "alerts_with_newly_discovered_qualifying_attack_evidence": qualifying_new,
            "newly_strict": newly_strict,
            "newly_sensitivity": newly_sensitivity,
            "newly_confirmed_alert_episodes": newly_confirmed,
            "previous_209_newly_confirmed": prev209_confirmed,
            "previous_209_still_unresolved": prev209_still,
            "all_982_remaining_review": remaining_review,
            "all_982_remaining_no_confirmed_event": remaining_no,
            "top_remaining_blockers": blocker_counts.most_common(),
            "current_kyiv_confirmed_positives": 145,
            "shadow_counterfactual_kyiv_positives_after_backfill": 145 + newly_confirmed,
            "rediscovered_existing_candidate_count_not_credited_as_new": len(existing_redisc),
        },
        "discovery": {
            "calibration": cal_discovery,
            "postcutoff": target_discovery,
        },
        "episode_ledger": ledger,
        "mutation_confirmation": {
            "classifier_mutations": 0,
            "parser_mutations": 0,
            "temporal_representation_mutations": 0,
            "alert_grouping_mutations": 0,
            "source_configuration_mutations": 0,
            "historical_state_mutations": 0,
            "queue_mutations": 0,
            "persistence_mutations": 0,
            "neon_queries": 0,
            "neon_writes": 0,
            "deployments": 0,
            "changed_protected_paths": changed_protected,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "verdict": verdict,
        "calibration": calibration,
        "aggregate_summary": artifact["aggregate_summary"],
    }, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

# push-trigger marker: workflow already present
