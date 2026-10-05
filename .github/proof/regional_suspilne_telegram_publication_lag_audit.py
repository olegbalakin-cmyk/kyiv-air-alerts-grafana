#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path.cwd() / "kyiv-air-alerts-grafana"
sys.path.insert(0, str(ROOT / "scripts"))
import monitor_explosion_candidates as monitor

UTC = timezone.utc
KYIV_TZ = ZoneInfo("Europe/Kyiv")
WINDOW_START = datetime(2026, 9, 5, 0, 0, tzinfo=UTC)
WINDOW_END = datetime(2026, 10, 5, 0, 0, tzinfo=UTC)
WINDOWS_MINUTES = (2, 5, 10, 15, 30)
MAX_PAGES_PER_CHANNEL = 300
MIN_IMMEDIATE_N_FOR_AFFIRMATIVE = 30
MIN_IMMEDIATE_CHANNELS_FOR_AFFIRMATIVE = 5
PRODUCTION_COMMIT = "c26307efcea065813870dc27901dbd225f4f3e33"
SHADOW_COMMIT = "6364ed64549263bef78beb0f0421c9a6c9f80d28"
SHADOW_BLOB = "596a6a809092707bcf5ba2cce9abc48e596e453f"
FROZEN_STATE_COMMIT = "7dc412666b123229112eb33b6824e54c4d2ab158"
FROZEN_STATE_SHA256 = "4c758a99b759e8827f4f8e3490bf6cb72f69ff2f825526a2eb18a12ecee499f1"
INVENTORY_SHA256 = "4810a913054a3cda7b53c420fe929f0b9739eec19cc3e7f82774971932216a07"
INVENTORY_PATH = Path("research/suspilne_regional_telegram_inventory_2026-10-05.json")
SHADOW_PATH = Path("research/regional_suspilne_telegram_incremental_shadow_2026-10-05.json")
STATE_PATH = Path(os.environ.get("FROZEN_STATE_PATH", "/tmp/frozen-state/kyiv-air-alerts-grafana/data/explosion_candidate_monitor_state.json"))
OUTPUT_PATH = Path(os.environ.get("OUTPUT_PATH", "/tmp/audit/research/regional_suspilne_telegram_publication_lag_audit_2026-10-05.json"))
SUMMARY_PATH = Path(os.environ.get("SUMMARY_PATH", "/tmp/audit/summary.json"))

MONTHS = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}
CLOCK_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3]):([0-5]\d)(?!\d)")
DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\s+(" + "|".join(MONTHS) + r")\b", re.I)
EVENT_TOKEN_RE = re.compile(
    r"\b(?:вибух\w*|вдар\w*|удар\w*|атак\w*|влуч\w*|приліт\w*|"
    r"ппо|збит\w*|знищ\w*|перехоп\w*|обстріл\w*|каб\w*|авіабомб\w*)\b",
    re.I,
)
ALERT_TOKEN_RE = re.compile(r"\b(?:тривог\w*|відбій\w*|загроз\w*|небезпек\w*)\b", re.I)
IMMEDIATE_RE = re.compile(
    r"(?:\bпролунав\w*\b|\bпролунали\w*\b|\bстався\b|\bсталися\b|"
    r"\bбуло\s+чутно\b|\bвдарив\w*\b|\bвдарила\w*\b|\bвдарили\w*\b|"
    r"\bвлучив\w*\b|\bвлучила\w*\b|\bвлучили\w*\b|"
    r"\батакував\w*\b|\батакувала\w*\b|\батакували\w*\b)", re.I)
LIVE_RE = re.compile(
    r"(?:\bчути\b|\bчутно\b|\блунає\w*\b|\блунають\w*\b|"
    r"\bпрацює\s+(?:сили\s+)?ппо\b|\бпрацюють\s+(?:сили\s+)?ппо\b)", re.I)
RETRO_STRONG_RE = re.compile(
    r"(?:\bраніше\b|\bнапередодні\b|\bвнаслідок\b|\bпісля\s+(?:атаки|удару|обстрілу)\b|"
    r"\бстало\s+відомо\b|\бповідомили\s+про\s+наслідки\b|\bуточнил\w*\b|"
    r"\бпідтвердил\w*\b|\бпротягом\b|\бза\s+даними\b|\бминул(?:ої|ого|у)\b)", re.I)
PART_B_RETRO_RE = re.compile(
    r"(?:\bраніше\b|\bвночі\b|\бзранку\b|\бвранці\b|\буранці\b|\бвдень\b|\бввечері\b|"
    r"\бнапередодні\b|\бвнаслідок\s+атаки\b|\бвнаслідок\s+удару\b|"
    r"\бпісля\s+(?:атаки|удару|обстрілу)\b|\бстало\s+відомо\b|"
    r"\бповідомили\s+про\s+наслідки\b|\буточнил\w*\b|\бпідтвердил\w*\b|"
    r"\бдо\s+\d+\s+зросл\w*\b|\ботримують\s+медичну\s+допомогу\s+після\s+удару\b)", re.I)


DIRECT_ATTACK_RE = re.compile(
    r"(?:\bпролунав\w*\b|\bпролунали\w*\b|\bстався\s+вибух\b|\bсталися\s+вибух\w*\b|"
    r"\bбуло\s+чутно\b|\bчули\s+(?:звук\s+)?вибух\w*\b|"
    r"\батакував\w*\b|\батакувала\w*\b|\батакували\w*\b|"
    r"\bвдарив\w*\b|\bвдарила\w*\b|\bвдарили\w*\b|"
    r"\bзавдав\w*\s+удар\w*\b|\bзавдала\w*\s+удар\w*\b|\bзавдали\w*\s+удар\w*\b|"
    r"\bвлучив\w*\b|\bвлучила\w*\b|\bвлучили\w*\b|\bвлучання\s+(?:сталося|зафіксували|було)\b|"
    r"\bпоцілив\w*\b|\bпоцілила\w*\b|\bпоцілили\w*\b)", re.I)
RETRO_CONTEXT_RE = re.compile(
    r"(?:\bяк\s+минула\s+доба\b|\bголовні\s+новини.*\bна\s+ранок\b|\bза\s+добу\b|"
    r"\bучора\b|\bвчора\b|\bнапередодні\b|\bпротягом\s+доби\b|"
    r"\bпісля\s+(?:атаки|удару|обстрілу)\b|\bвнаслідок\s+(?:ранкової|нічної|вечірньої)\s+атаки\b|"
    r"\bстало\s+відомо\b|\bуточнил\w*\b|\bпідтвердил\w*\b)", re.I | re.S)


def iso(dt):
    return monitor.iso(dt) if dt else None


def sha256_file(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def split_segments(text):
    return [" ".join(x.split()) for x in re.split(r"(?<=[.!?;])\s+|\n+", text or "") if x.strip()]


def parse_page(handle, before):
    raw = handle.lstrip("@")
    url = f"https://t.me/s/{raw}"
    if before is not None:
        url += f"?before={before}"
    last = None
    for attempt in range(4):
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (compatible; regional-publication-lag-audit/1.0)", "Accept-Language": "uk,en;q=0.7"},
                timeout=45,
            )
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            out = []
            for wrap in soup.select(".tgme_widget_message_wrap"):
                msg = wrap.select_one(".tgme_widget_message")
                time_el = wrap.select_one("time[datetime]")
                if msg is None or time_el is None:
                    continue
                data_post = str(msg.get("data-post") or "")
                if "/" not in data_post:
                    continue
                post_handle, raw_id = data_post.rsplit("/", 1)
                if not raw_id.isdigit():
                    continue
                published = monitor.parse_dt(time_el.get("datetime"))
                if not published:
                    continue
                text_el = wrap.select_one(".tgme_widget_message_text")
                text = monitor.clean_text(text_el.get_text(" ", strip=True) if text_el else "")
                fwd = wrap.select_one(".tgme_widget_message_forwarded_from")
                fwd_text = monitor.clean_text(fwd.get_text(" ", strip=True) if fwd else "")
                out.append({
                    "message_id": int(raw_id),
                    "published_at": iso(published),
                    "text": text,
                    "url": f"https://t.me/{post_handle}/{raw_id}",
                    "forwarded_from": fwd_text or None,
                    "is_forwarded": bool(fwd_text),
                })
            out.sort(key=lambda x: x["message_id"])
            return out
        except Exception as exc:
            last = exc
            if attempt < 3:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"telegram_fetch_failed:{handle}:{type(last).__name__}:{last}")


def fetch_channel_window(handle):
    before = None
    unique = {}
    pages = 0
    oldest = newest = None
    complete = False
    termination = None
    while pages < MAX_PAGES_PER_CHANNEL:
        page = parse_page(handle, before)
        pages += 1
        if not page:
            complete = True
            termination = "empty_page"
            break
        parsed = []
        for post in page:
            dt = monitor.parse_dt(post["published_at"])
            if not dt:
                continue
            parsed.append((post, dt))
            oldest = dt if oldest is None or dt < oldest else oldest
            newest = dt if newest is None or dt > newest else newest
            if WINDOW_START <= dt < WINDOW_END:
                unique[int(post["message_id"])] = post
        if not parsed:
            complete = True
            termination = "no_parseable_timestamps"
            break
        page_oldest = min(dt for _, dt in parsed)
        page_newest = max(dt for _, dt in parsed)
        if page_oldest <= WINDOW_START:
            complete = True
            termination = "reached_window_start"
            break
        if page_newest < WINDOW_START:
            complete = True
            termination = "page_before_window"
            break
        next_before = min(post["message_id"] for post, _ in parsed)
        if before is not None and next_before >= before:
            termination = "pagination_stalled"
            break
        before = next_before
        time.sleep(0.08)
    if not complete and termination is None:
        termination = "max_pages_before_window_start"
    posts = sorted(unique.values(), key=lambda x: (x["published_at"], x["message_id"]))
    return {
        "handle": handle,
        "window_complete": complete,
        "termination": termination,
        "pages_fetched": pages,
        "max_pages": MAX_PAGES_PER_CHANNEL,
        "unique_window_messages": len(posts),
        "oldest_seen": iso(oldest),
        "newest_seen": iso(newest),
        "posts": posts,
    }


def city_mentions(text):
    return [city for city in monitor.CITY_CONFIG if monitor.city_mentioned(city, text)]


def nearest_distance(pattern, segment, pos):
    vals = []
    for m in pattern.finditer(segment):
        if m.start() <= pos <= m.end():
            return 0
        vals.append(min(abs(pos - m.start()), abs(pos - m.end())))
    return min(vals) if vals else None


def explicit_date_for_segment(segment, pub_local):
    low = segment.casefold()
    dates = DATE_RE.findall(low)
    if len(dates) > 1:
        return None, "multiple_explicit_dates"
    if dates:
        day_s, month_s = dates[0]
        try:
            d = date(pub_local.year, MONTHS[month_s.casefold()], int(day_s))
        except ValueError:
            return None, "invalid_explicit_date"
        if d > pub_local.date():
            return None, "explicit_date_after_publication"
        return d, "explicit_calendar_date"
    if re.search(r"\bвчора\b", low):
        return pub_local.date() - timedelta(days=1), "relative_yesterday"
    if re.search(r"\bсьогодні\b", low):
        return pub_local.date(), "relative_today"
    return None, "explicit_clock_date_not_source_stated"


def wording_class(segment: str, full_text: str) -> str:
    low = segment.casefold()
    full_low = full_text.casefold()
    if RETRO_STRONG_RE.search(low) or RETRO_CONTEXT_RE.search(full_low):
        return "RETROSPECTIVE_OR_SUMMARY"
    if DIRECT_ATTACK_RE.search(low) or IMMEDIATE_RE.search(low):
        return "IMMEDIATE_COMPLETED_EVENT"
    if LIVE_RE.search(low) and not re.search(r"\bбуло\s+чутно\b", low):
        return "CONTEMPORANEOUS_LIVE"
    return "OTHER_OR_INDETERMINATE"


def _segment_attack_clock_candidates(segment: str) -> list[re.Match]:
    clocks = list(CLOCK_RE.finditer(segment))
    if not clocks or not (EVENT_TOKEN_RE.search(segment) or DIRECT_ATTACK_RE.search(segment)):
        return []
    if re.search(r"\bстаном\s+на\s+\d{1,2}:\d{2}\b", segment, re.I):
        return []
    if re.search(r"\b(?:тривог\w*|відбій\w*)[^.!?]{0,50}\d{1,2}:\d{2}", segment, re.I) and not re.search(r"\b(?:в той же час|одночасно)\b", segment, re.I):
        return []
    if len(clocks) == 1 and DIRECT_ATTACK_RE.search(segment):
        return clocks
    if len(clocks) == 1 and re.search(r"\b(?:в той же час|одночасно)\b", segment, re.I) and re.search(r"\bвибух\w*\b", segment, re.I):
        return clocks
    return []


def calibrate_post(city: str, handle: str, post: dict) -> tuple[list[dict], list[dict]]:
    text = str(post.get("text") or "")
    pub = monitor.parse_dt(post.get("published_at"))
    if not pub or not text or not CLOCK_RE.search(text):
        return [], []

    base = {
        "channel_region_city_key": city,
        "channel": handle,
        "message_id": int(post["message_id"]),
        "message_url": post.get("url"),
        "publication_timestamp": post.get("published_at"),
        "complete_source_text": text,
        "forwarded_from": post.get("forwarded_from"),
    }
    if post.get("is_forwarded"):
        return [], [{**base, "exclusion_reason": "forward_or_repost", "candidate_detail": None}]

    candidates = []
    for seg in split_segments(text):
        for cm in _segment_attack_clock_candidates(seg):
            candidates.append((seg, cm))
    if not candidates:
        if EVENT_TOKEN_RE.search(text) or DIRECT_ATTACK_RE.search(text):
            return [], [{**base, "exclusion_reason": "no_unambiguous_direct_attack_clock_association", "candidate_detail": None}]
        return [], []

    rows, excluded = [], []
    pub_local = pub.astimezone(KYIV_TZ)
    for seg, cm in candidates:
        event_date, date_basis = explicit_date_for_segment(seg, pub_local)
        if event_date is None:
            excluded.append({**base, "exclusion_reason": date_basis, "candidate_detail": seg})
            continue
        hour, minute = int(cm.group(1)), int(cm.group(2))
        event_local = datetime.combine(event_date, dtime(hour, minute), tzinfo=KYIV_TZ)
        event_utc = event_local.astimezone(UTC)
        lag = (pub - event_utc).total_seconds()
        if lag < 0:
            excluded.append({**base, "exclusion_reason": "explicit_clock_cannot_be_safely_date_bound_nonnegative", "candidate_detail": seg, "candidate_event_timestamp": iso(event_utc), "candidate_lag_seconds": lag})
            continue

        mentions = city_mentions(seg)
        binding_city = mentions[0] if len(mentions) == 1 else None
        wc = wording_class(seg, text)
        approx = bool(re.search(r"\b(?:близько|приблизно|орієнтовно)\b", seg.casefold()))
        rows.append({
            **base,
            "event_city_candidates": mentions,
            "binding_city": binding_city,
            "explicit_event_segment": seg,
            "explicit_event_clock": f"{hour:02d}:{minute:02d}",
            "event_timestamp": iso(event_utc),
            "event_timestamp_local": event_local.isoformat(),
            "date_binding_basis": date_basis,
            "timestamp_precision": "approximate_minute" if approx else "minute",
            "publication_lag_seconds": int(lag),
            "wording_class": wc,
            "eligibility_basis": "same_post_explicit_attack_event_clock",
        })
    return rows, excluded


def dedupe_calibration_rows(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    groups = defaultdict(list)
    for r in rows:
        seg = re.sub(r"\s+", " ", str(r.get("explicit_event_segment") or "").casefold()).strip()
        seg = CLOCK_RE.sub("<TIME>", seg)
        sig = seg[:220]
        key = (r["channel"], r["event_timestamp"], sig)
        groups[key].append(r)
    kept, dups = [], []
    for key, vals in groups.items():
        vals.sort(key=lambda r: (r["publication_timestamp"], r["message_id"]))
        kept.append(vals[0])
        for x in vals[1:]:
            dups.append({**x, "exclusion_reason": "duplicate_same_independently_timestamped_event", "kept_message_id": vals[0]["message_id"]})
    kept.sort(key=lambda r: (r["publication_timestamp"], r["channel"], r["message_id"]))
    return kept, dups

def percentile(values, q):
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return float(xs[0])
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return float(xs[lo])
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def stats(rows):
    vals = [int(r["publication_lag_seconds"]) for r in rows]
    n = len(vals)
    def share(sec):
        return (sum(v <= sec for v in vals) / n) if n else None
    return {
        "N": n,
        "median_seconds": percentile(vals, 0.50),
        "p75_seconds": percentile(vals, 0.75),
        "p90_seconds": percentile(vals, 0.90),
        "p95_seconds": percentile(vals, 0.95),
        "maximum_seconds": max(vals) if vals else None,
        "share_le_2m": share(120),
        "share_le_5m": share(300),
        "share_le_10m": share(600),
        "share_le_15m": share(900),
        "share_le_30m": share(1800),
        "percentile_stability_note": "descriptive_only_sample_small" if n < 30 else "descriptive_sample_n_ge_30",
    }


def build_logical_groups(state, cities):
    out = {}
    for city in cities:
        eps = list((((state.get("cities") or {}).get(city) or {}).get("episodes") or []))
        groups = []
        for cluster in monitor.episode_representation_clusters(eps):
            starts = [monitor.parse_dt(ep.get("alert_start")) for ep in cluster]
            ends = [monitor.parse_dt(ep.get("alert_end")) for ep in cluster]
            starts = [x for x in starts if x]
            ends = [x for x in ends if x]
            if not starts or not ends:
                continue
            groups.append({
                "logical_key": "|".join(sorted(str(ep.get("episode_id")) for ep in cluster)),
                "raw_episode_ids": sorted(str(ep.get("episode_id")) for ep in cluster),
                "intersection_start": max(starts),
                "intersection_end": min(ends),
                "envelope_start": min(starts),
                "envelope_end": max(ends),
                "raw": cluster,
            })
        out[city] = sorted(groups, key=lambda g: g["envelope_start"])
    return out


def point_binding(groups, point):
    hits = [g for g in groups if g["envelope_start"] <= point <= g["envelope_end"]]
    return {
        "status": "UNIQUE" if len(hits) == 1 else "NONE" if not hits else "AMBIGUOUS",
        "logical_key": hits[0]["logical_key"] if len(hits) == 1 else None,
        "matching_logical_keys": [g["logical_key"] for g in hits],
    }


def interval_binding(groups, start, end):
    contained = [g for g in groups if g["intersection_start"] <= start and end <= g["intersection_end"]]
    overlaps = [g for g in groups if start <= g["envelope_end"] and end >= g["envelope_start"]]
    if len(contained) == 1:
        return {"standard": "CONSERVATIVE_CONTAINMENT", "status": "UNIQUE", "logical_key": contained[0]["logical_key"], "contained_keys": [contained[0]["logical_key"]], "overlap_keys": [g["logical_key"] for g in overlaps]}
    if len(contained) == 0 and len(overlaps) == 1:
        return {"standard": "UNIQUE_OVERLAP_ONLY", "status": "UNIQUE", "logical_key": overlaps[0]["logical_key"], "contained_keys": [], "overlap_keys": [overlaps[0]["logical_key"]]}
    return {"standard": "NONE_OR_AMBIGUOUS", "status": "NONE" if not overlaps else "AMBIGUOUS", "logical_key": None, "contained_keys": [g["logical_key"] for g in contained], "overlap_keys": [g["logical_key"] for g in overlaps]}


def classify_outlier(row):
    text = (row.get("complete_source_text") or "").casefold()
    if row.get("forwarded_from"):
        return "repost_or_forward"
    if RETRO_STRONG_RE.search(text):
        return "summary_or_retrospective_wording_misclassified_as_immediate"
    if re.search(r"\b(?:повідомив|повідомила|повідомили|за\s+словами|підтвердил\w*)\b", text):
        return "official_confirmation_after_event"
    return "delayed_reporting"


def shadow_cluster_ledger(shadow, groups_by_city):
    messages = {f"{m.get('source_handle')}:{m.get('message_id')}": m for m in shadow.get("regional_message_ledger") or []}
    clusters = [c for c in shadow.get("regional_cluster_ledger") or [] if c.get("comparison_class") == "NEW_EVIDENCE_BUT_NO_SAFE_EPISODE_BINDING"]
    if len(clusters) != 8:
        raise RuntimeError(f"EXPECTED_8_FROZEN_UNBOUND_CLUSTERS_GOT_{len(clusters)}")
    rows = []
    results = {L: {"conservative_bindings": 0, "unique_overlap_only": 0, "eligible_immediate_completed_clusters": 0} for L in WINDOWS_MINUTES}
    for c in clusters:
        members = [messages[ref] for ref in c.get("member_refs") or [] if ref in messages]
        if not members:
            raise RuntimeError(f"MISSING_SHADOW_CLUSTER_MEMBERS:{c.get('cluster_id')}")
        members.sort(key=lambda m: (m.get("source_native_timestamp") or "", int(m.get("message_id") or 0)))
        rep = members[0]
        text = str(rep.get("complete_source_text") or "")
        wc = wording_class(text, text)
        immediate = wc == "IMMEDIATE_COMPLETED_EVENT"
        excluded_reason = None
        if rep.get("source_handle") is None:
            excluded_reason = "missing_source_identity"
        elif PART_B_RETRO_RE.search(text.casefold()):
            excluded_reason = "retrospective_or_delayed_reporting_construction"
        elif len(city_mentions(text)) > 1:
            excluded_reason = "cross_city_report"
        elif len(re.findall(r"\b(?:удар\w*|влуч\w*|атак\w*|вибух\w*)\b", text.casefold())) > 3 and not immediate:
            excluded_reason = "summary_covering_multiple_attacks"
        eligible = immediate and excluded_reason is None
        pub = monitor.parse_dt(rep.get("source_native_timestamp"))
        city = str(c.get("city"))
        nearby = []
        if pub:
            for g in groups_by_city.get(city, []):
                if g["envelope_start"] <= pub + timedelta(hours=3) and g["envelope_end"] >= pub - timedelta(hours=3):
                    nearby.append({
                        "logical_key": g["logical_key"],
                        "raw_episode_ids": g["raw_episode_ids"],
                        "alert_start": iso(g["envelope_start"]),
                        "alert_end": iso(g["envelope_end"]),
                        "containment_intersection_start": iso(g["intersection_start"]),
                        "containment_intersection_end": iso(g["intersection_end"]),
                    })
        counter = {}
        for L in WINDOWS_MINUTES:
            if not eligible or not pub:
                counter[str(L)] = {"eligible": False, "binding": None}
                continue
            results[L]["eligible_immediate_completed_clusters"] += 1
            b = interval_binding(groups_by_city.get(city, []), pub - timedelta(minutes=L), pub)
            counter[str(L)] = {"eligible": True, "candidate_event_interval": {"start": iso(pub - timedelta(minutes=L)), "end": iso(pub)}, "binding": b}
            if b["standard"] == "CONSERVATIVE_CONTAINMENT" and b["status"] == "UNIQUE":
                results[L]["conservative_bindings"] += 1
            elif b["standard"] == "UNIQUE_OVERLAP_ONLY" and b["status"] == "UNIQUE":
                results[L]["unique_overlap_only"] += 1
        rows.append({
            "cluster_id": c.get("cluster_id"),
            "city": city,
            "member_refs": c.get("member_refs"),
            "representative_policy": "earliest_source_native_timestamp_in_frozen_cluster",
            "channel": rep.get("source_handle"),
            "message_id": rep.get("message_id"),
            "message_timestamp": rep.get("source_native_timestamp"),
            "exact_attack_wording": text,
            "current_temporal_result": rep.get("temporal_result"),
            "current_classifier_result": rep.get("resulting_classifier_disposition"),
            "wording_class": wc,
            "immediate_completed_event": immediate,
            "automatic_exclusion_reason": excluded_reason,
            "eligible_for_counterfactual": eligible,
            "frozen_alert_episodes_around_message": nearby,
            "counterfactual_windows": counter,
            "all_frozen_member_messages": [
                {"channel": m.get("source_handle"), "message_id": m.get("message_id"), "timestamp": m.get("source_native_timestamp"), "text": m.get("complete_source_text")} for m in members
            ],
        })
    return rows, results


def main():
    if not INVENTORY_PATH.exists() or not SHADOW_PATH.exists() or not STATE_PATH.exists():
        raise RuntimeError("MISSING_FROZEN_INPUT")
    if sha256_file(INVENTORY_PATH) != INVENTORY_SHA256:
        raise RuntimeError("INVENTORY_SHA256_MISMATCH")
    if sha256_file(STATE_PATH) != FROZEN_STATE_SHA256:
        raise RuntimeError("FROZEN_STATE_SHA256_MISMATCH")

    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    shadow = json.loads(SHADOW_PATH.read_text(encoding="utf-8"))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    city_rows = list(inventory.get("city_inventory") or [])
    if len(city_rows) != 23 or inventory.get("verdict") != "SUSPILNE REGIONAL TELEGRAM INVENTORY = COMPLETE":
        raise RuntimeError("INVENTORY_NOT_ACCEPTED_23")
    if shadow.get("verdict") != "REGIONAL SUSPILNE TELEGRAM SHADOW = LOW INCREMENTAL VALUE":
        raise RuntimeError("SHADOW_NOT_ACCEPTED")
    channel_set = [{"city_key": str(r["city_key"]), "handle": str(r["official_current_handle"]), "city": r.get("city")} for r in city_rows]
    cities = [r["city_key"] for r in channel_set]
    groups_by_city = build_logical_groups(state, cities)

    health = []
    eligible = []
    excluded = []
    inspected = 0
    for idx, row in enumerate(channel_set, 1):
        city, handle = row["city_key"], row["handle"]
        fetched = fetch_channel_window(handle)
        inspected += fetched["unique_window_messages"]
        health.append({k: v for k, v in fetched.items() if k != "posts"})
        print(f"CHANNEL {idx:02d}/23 {city} {handle}: pages={fetched['pages_fetched']} messages={fetched['unique_window_messages']} complete={fetched['window_complete']}", flush=True)
        if not fetched["window_complete"]:
            raise RuntimeError(f"CALIBRATION_WINDOW_INCOMPLETE:{city}:{handle}:{fetched['termination']}")
        for post in fetched["posts"]:
            e, x = calibrate_post(city, handle, post)
            eligible.extend(e)
            excluded.extend(x)

    eligible, duplicate_exclusions = dedupe_calibration_rows(eligible)
    excluded.extend(duplicate_exclusions)

    for row in eligible:
        evt = monitor.parse_dt(row["event_timestamp"])
        binding_city = row.get("binding_city")
        row["explicit_event_time_alert_binding"] = point_binding(groups_by_city.get(binding_city, []), evt) if binding_city else {"status": "UNAVAILABLE", "logical_key": None, "matching_logical_keys": []}

    by_class = defaultdict(list)
    for row in eligible:
        by_class[row["wording_class"]].append(row)
    class_stats = {name: stats(rows) for name, rows in sorted(by_class.items())}
    immediate = by_class.get("IMMEDIATE_COMPLETED_EVENT", [])
    immediate_channels = len({r["channel"] for r in immediate})
    channel_stats = {}
    for handle in sorted({r["channel"] for r in eligible}):
        rows = [r for r in immediate if r["channel"] == handle]
        if len(rows) >= 3:
            channel_stats[handle] = stats(rows)

    outliers = []
    for row in immediate:
        if row["publication_lag_seconds"] > 900:
            outliers.append({
                "channel": row["channel"], "message_id": row["message_id"], "city": row.get("binding_city"),
                "publication_lag_seconds": row["publication_lag_seconds"], "reason": classify_outlier(row),
                "event_segment": row["explicit_event_segment"], "publication_timestamp": row["publication_timestamp"], "event_timestamp": row["event_timestamp"],
            })

    stress = {}
    for L in WINDOWS_MINUTES:
        correct = wrong = ambiguous = proposed = 0
        rows_detail = []
        stress_rows = [r for r in eligible if r.get("binding_city") and r.get("explicit_event_time_alert_binding", {}).get("status") != "UNAVAILABLE"]
        for row in stress_rows:
            pub = monitor.parse_dt(row["publication_timestamp"])
            ref = row["explicit_event_time_alert_binding"]
            cand = interval_binding(groups_by_city.get(row["binding_city"], []), pub - timedelta(minutes=L), pub)
            conservative_unique = cand["standard"] == "CONSERVATIVE_CONTAINMENT" and cand["status"] == "UNIQUE"
            outcome = "AMBIGUOUS_OR_NO_BINDING"
            if conservative_unique and ref["status"] == "UNIQUE":
                proposed += 1
                if cand["logical_key"] == ref["logical_key"]:
                    correct += 1
                    outcome = "CORRECT_SAME_EPISODE"
                else:
                    wrong += 1
                    outcome = "WRONG_EPISODE_BINDING"
            else:
                ambiguous += 1
            rows_detail.append({
                "channel": row["channel"], "message_id": row["message_id"], "city": row.get("binding_city"),
                "reference_binding": ref, "counterfactual_binding": cand, "outcome": outcome,
            })
        stress[str(L)] = {
            "eligible_calibration_rows": len(stress_rows),
            "all_lag_calibration_rows": len(eligible),
            "correct_same_episode_bindings": correct,
            "wrong_episode_bindings": wrong,
            "ambiguous_or_no_binding": ambiguous,
            "precision_among_verifiable_proposed_bindings": (correct / proposed) if proposed else None,
            "proposed_binding_standard": "CONSERVATIVE_CONTAINMENT",
            "row_ledger": rows_detail,
        }

    shadow_ledger, shadow_results = shadow_cluster_ledger(shadow, groups_by_city)
    combined = {}
    smallest = None
    for L in WINDOWS_MINUTES:
        wrong = stress[str(L)]["wrong_episode_bindings"]
        recovery = shadow_results[L]["conservative_bindings"]
        combined[str(L)] = {
            **shadow_results[L],
            "demonstrated_wrong_bindings_in_calibration": wrong,
            "zero_demonstrated_wrong_bindings": wrong == 0,
        }
        if smallest is None and recovery >= 1 and wrong == 0:
            smallest = L

    immediate_stats = stats(immediate)
    if len(immediate) < MIN_IMMEDIATE_N_FOR_AFFIRMATIVE or immediate_channels < MIN_IMMEDIATE_CHANNELS_FOR_AFFIRMATIVE:
        interpretation = "PUBLICATION_LAG_SHORT_BUT_SAMPLE_TOO_SMALL" if immediate and (immediate_stats.get("p90_seconds") or 10**9) <= 900 else "NO EVIDENCE FOR CHANGING CURRENT CONTRACT"
        recommendation = "GATHER MORE PUBLICATION-LAG CALIBRATION DATA"
    elif smallest is not None:
        interpretation = "BOUNDED_INTERVAL_LOOKS_SAFE_BUT NEEDS PROSPECTIVE PROOF"
        recommendation = "PROCEED TO BOUNDED TELEGRAM COMPLETED-EVENT TEMPORAL PROOF"
    else:
        any_wrong = any(stress[str(L)]["wrong_episode_bindings"] > 0 for L in WINDOWS_MINUTES)
        interpretation = "PUBLICATION_LAG_TOO_VARIABLE" if any_wrong else "NO EVIDENCE FOR CHANGING CURRENT CONTRACT"
        recommendation = "KEEP CURRENT TELEGRAM TEMPORAL CONTRACT"

    mutation = {
        "production Telegram source config mutations": 0,
        "classifier mutations": 0,
        "temporal parser mutations": 0,
        "temporal representation mutations": 0,
        "same-attack mutations": 0,
        "source adapter production mutations": 0,
        "historical state/queue mutations": 0,
        "review queue mutations": 0,
        "canonical alerts mutations": 0,
        "Neon/DB mutations": 0,
        "deployments": 0,
    }

    artifact = {
        "schema_version": "1.0",
        "artifact_scope": "READ_ONLY_REGIONAL_SUSPILNE_TELEGRAM_PUBLICATION_LAG_AND_COUNTERFACTUAL_AUDIT",
        "generated_at": iso(datetime.now(UTC)),
        "frozen_input_identities": {
            "production_semantic_reference": PRODUCTION_COMMIT,
            "regional_inventory_path": str(INVENTORY_PATH),
            "regional_inventory_sha256": sha256_file(INVENTORY_PATH),
            "accepted_shadow_commit": SHADOW_COMMIT,
            "accepted_shadow_path": str(SHADOW_PATH),
            "accepted_shadow_git_blob_expected": SHADOW_BLOB,
            "accepted_shadow_sha256": sha256_file(SHADOW_PATH),
            "frozen_alert_state_commit": FROZEN_STATE_COMMIT,
            "frozen_alert_state_sha256": sha256_file(STATE_PATH),
        },
        "calibration_window": {"start_utc": iso(WINDOW_START), "end_utc": iso(WINDOW_END), "duration_days": 30, "fixed_before_collection": True},
        "channel_set": channel_set,
        "fetch_method": {
            "source": "Telegram public channel HTML /s/<handle>?before=<message_id>",
            "parser": "source-native message datetime + message text; forwards detected from Telegram forwarded-from markup",
            "max_pages_per_channel": MAX_PAGES_PER_CHANNEL,
            "event_time_truth": "same-post explicit attack event clock plus source-stated calendar date or relative today/yesterday; bare clocks are excluded rather than date-bound from publication time",
            "same_channel_sequence_form_used": False,
            "calibration_scope": "all independently timestamped attack reports in the 23 accepted regional channels; not restricted to production city-matching or classifier semantics",
            "deduplication": "earliest publication retained for same-channel, same explicit event timestamp, same normalized event segment",
        },
        "messages_inspected": inspected,
        "collection_health": health,
        "eligible_calibration_ledger": eligible,
        "excluded_calibration_rows": excluded,
        "wording_class_counts": dict(sorted(Counter(r["wording_class"] for r in eligible).items())),
        "lag_statistics": class_stats,
        "immediate_completed_event_channels": immediate_channels,
        "immediate_completed_event_channel_stats_where_n_ge_3": channel_stats,
        "outlier_review_gt_15m": outliers,
        "false_binding_stress_test": stress,
        "eight_frozen_shadow_cluster_ledger": shadow_ledger,
        "counterfactual_results": combined,
        "smallest_L_with_meaningful_recovery_and_zero_demonstrated_wrong_bindings": smallest,
        "affirmative_minimum_evidence_rule_predeclared": {"minimum_immediate_completed_event_N": MIN_IMMEDIATE_N_FOR_AFFIRMATIVE, "minimum_channels": MIN_IMMEDIATE_CHANNELS_FOR_AFFIRMATIVE},
        "final_interpretation": interpretation,
        "recommendation": recommendation,
        "mutation_confirmation": mutation,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "calibration_window": artifact["calibration_window"],
        "messages_inspected": inspected,
        "independently_timestamped_eligible_attack_reports": len(eligible),
        "eligible_IMMEDIATE_COMPLETED_EVENT_N": len(immediate),
        "immediate_completed_event_channels": immediate_channels,
        "immediate_stats": immediate_stats,
        "outliers_gt_15m": len(outliers),
        "counterfactual_results": combined,
        "smallest_L": smallest,
        "interpretation": interpretation,
        "recommendation": recommendation,
        "mutation_confirmation": mutation,
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("AUDIT_SUMMARY=" + json.dumps(summary, ensure_ascii=False, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
