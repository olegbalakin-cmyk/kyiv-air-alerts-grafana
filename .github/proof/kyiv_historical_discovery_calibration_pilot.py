#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

UTC = timezone.utc
KYIV_TZ = ZoneInfo("Europe/Kyiv")
AUTH_COMMIT = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
AUTH_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
AUTH_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
SNAP_COMMIT = "efefa399e69eadd3d7fc8393ac1553cfde35f138"
SNAP_PATH = "research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json"
SNAP_BLOB = "8a2f6bd33f879be9db978da59c12c34e61f6f843"
OLD_EVIDENCE_RECALL = 13 / 145
OLD_FINAL_RECALL = 3 / 145

SOURCE_ORDER = [
    ("VA_Kyiv", "telegram", "VA_Kyiv"),
    ("KyivCityOfficial", "telegram", "KyivCityOfficial"),
    ("vitaliy_klitschko", "telegram", "vitaliy_klitschko"),
    ("dsns_kyiv", "telegram", "dsns_kyiv"),
    ("kpszsu", "telegram", "kpszsu"),
    ("suspilnenews", "telegram", "suspilnenews"),
    ("suspilne_kyiv", "telegram", "suspilne_kyiv"),
    ("suspilne.media/kyiv", "web", "suspilne.media/kyiv"),
    ("generic_search", "search", None),
]

VOCAB = [
    "Київ вибух", "Київ вибухи", "Київ атака", "Київ обстріл",
    "Київ ППО", "Київ уламки", "Київ влучання", "Київ БпЛА",
    "Київ дрон", "Київ шахед", "Київ ракета", "Київ балістика",
]
QUERY_TERMS = [
    "вибух", "вибухи", "атака", "обстріл", "ППО", "уламки",
    "влучання", "БпЛА", "дрон", "шахед", "ракета", "балістика",
]
ATTACK_RE = re.compile(
    r"(вибух|атак|обстріл|ппо|уламк|влуч|бпла|безпілот|дрон|шахед|ракет|баліст)",
    re.I,
)
FIXED_TG = {x[2].casefold() for x in SOURCE_ORDER if x[1] == "telegram"}
ALLOWED_FIXED_DOMAINS = {"suspilne.media", "www.suspilne.media"}
MAX_RESULTS_PER_QUERY = 30
HTTP_TIMEOUT = 20
UA = "Mozilla/5.0 (compatible; kyiv-historical-discovery-calibration/1.0)"

class Blocked(RuntimeError):
    pass

def sh(args, *, cwd=None, check=True):
    p = subprocess.run([str(x) for x in args], cwd=cwd, text=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode:
        raise Blocked("COMMAND_FAILED:" + " ".join(map(str,args)) + "\n" + p.stderr[-3000:])
    return p

def git(*args):
    return sh(["git", *args]).stdout.strip()

def git_bytes(ref, path):
    p = subprocess.run(["git", "show", f"{ref}:{path}"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise Blocked(f"GIT_SHOW_FAILED:{ref}:{path}:{p.stderr.decode('utf-8','replace')[-1000:]}")
    return p.stdout

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def canonical_json_bytes(obj) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",",":")) + "\n").encode("utf-8")

def parse_dt(value):
    if not value:
        return None
    text = str(value).strip().replace("Z","+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        try:
            dt = parsedate_to_datetime(str(value))
        except Exception:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def iso(dt):
    return dt.astimezone(UTC).isoformat().replace("+00:00","Z")

def clean_text(value):
    return " ".join(BeautifulSoup(str(value or ""), "html.parser").get_text(" ", strip=True).split())

def host_of(url):
    try:
        return urlparse(str(url or "")).netloc.casefold().split(":")[0]
    except Exception:
        return ""

def canonical_url(url):
    return str(url or "").strip().split("#",1)[0]

def tg_identity(url):
    m = re.search(r"https?://(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z0-9_]+)/(\d+)", str(url or ""), re.I)
    if not m:
        return None
    return m.group(1), int(m.group(2))

class HTTP:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language":"uk,en;q=0.7"})
        self.stats = Counter()
        self.cache = {}

    def get(self, url, *, timeout=HTTP_TIMEOUT):
        if url in self.cache:
            self.stats["cache_hits"] += 1
            return self.cache[url]
        self.stats["requests"] += 1
        last = None
        for attempt in range(2):
            try:
                r = self.s.get(url, timeout=timeout, allow_redirects=True)
                r.raise_for_status()
                self.cache[url] = r
                return r
            except requests.RequestException as exc:
                last = exc
                self.stats["errors"] += 1
                if attempt == 0:
                    time.sleep(0.25)
        raise last

def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise Blocked(f"CANNOT_IMPORT:{path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def prepare_authoritative_monitor(tmp: Path):
    subprocess.run(["git","fetch","--no-tags","origin",AUTH_COMMIT], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if git("rev-parse", f"{AUTH_COMMIT}:{AUTH_PATH}") != AUTH_BLOB:
        raise Blocked("AUTHORITATIVE_CLASSIFIER_BLOB_MISMATCH")
    wt = tmp / "auth"
    sh(["git","worktree","add","--detach",str(wt),AUTH_COMMIT])
    scripts = wt / "kyiv-air-alerts-grafana" / "scripts"
    sys.path.insert(0, str(scripts))
    mod = load_module(scripts / "monitor_explosion_candidates.py", "kyiv_calibration_authoritative_classifier")
    return mod, wt

def load_full_kyiv_episodes():
    subprocess.run(["git","fetch","--no-tags","origin",SNAP_COMMIT], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if git("rev-parse", f"{SNAP_COMMIT}:{SNAP_PATH}") != SNAP_BLOB:
        raise Blocked("SNAPSHOT_BLOB_MISMATCH")
    doc = json.loads(git_bytes(SNAP_COMMIT, SNAP_PATH))
    rows = [r for r in (doc.get("classifications") or []) if str(r.get("city_key") or "") == "kyiv"]
    if len(rows) != 2456:
        raise Blocked(f"KYIV_EPISODE_COUNT:{len(rows)}")
    episodes = [{
        "episode_id": str(r["historical_episode_id"]),
        "city_key": "kyiv",
        "city": "Київ",
        "alert_start": str(r["alert_start_utc_microseconds"]),
        "alert_end": str(r["alert_end_utc_microseconds"]),
    } for r in rows]
    episodes.sort(key=lambda x:(x["alert_start"],x["episode_id"]))
    return episodes

def google_news_query(site_filter, start: datetime, end: datetime):
    # Date operators are intentionally calendar-day coarse; exact publication filtering follows.
    after = (start.astimezone(KYIV_TZ).date() - timedelta(days=1)).isoformat()
    before = (end.astimezone(KYIV_TZ).date() + timedelta(days=1)).isoformat()
    attack = " OR ".join(f'"{t}"' for t in QUERY_TERMS)
    q = f'"Київ" ({attack}) after:{after} before:{before}'
    if site_filter:
        q += f" site:{site_filter}"
    return "https://news.google.com/rss/search?q=" + quote_plus(q) + "&hl=uk&gl=UA&ceid=UA:uk"

def parse_google_rss(raw: bytes):
    root = ET.fromstring(raw)
    out = []
    for item in root.findall(".//item")[:MAX_RESULTS_PER_QUERY]:
        title = clean_text(item.findtext("title") or "")
        link = item.findtext("link") or ""
        pub = item.findtext("pubDate") or ""
        desc = clean_text(item.findtext("description") or "")
        source = item.findtext("source") or ""
        out.append({"title":title,"link":link,"pubDate":pub,"description":desc,"source":source})
    return out

def outbound_links_from_google_html(html_text):
    soup = BeautifulSoup(html_text or "", "html.parser")
    urls = []
    for a in soup.select("a[href]"):
        href = str(a.get("href") or "")
        if href.startswith("http"):
            urls.append(href)
        elif href.startswith("./articles/"):
            continue
    return urls

def resolve_google_result(http: HTTP, item):
    link = str(item.get("link") or "")
    if not link:
        return None, "EMPTY_SEARCH_LINK"
    try:
        r = http.get(link)
    except requests.RequestException as exc:
        return None, f"SEARCH_RESOLVE_FAILED:{type(exc).__name__}"
    final = canonical_url(str(r.url))
    if host_of(final) not in {"news.google.com","www.google.com","google.com"}:
        return final, None
    # RSS redirect pages can retain a Google URL; inspect outbound anchors.
    for candidate in outbound_links_from_google_html(r.text):
        h = host_of(candidate)
        if h and "google." not in h and h != "news.google.com":
            return canonical_url(candidate), None
    return None, "SEARCH_HIT_SNIPPET_ONLY"

def fetch_telegram_post(http: HTTP, url, expected_channel=None):
    ident = tg_identity(url)
    if not ident:
        return None, "TELEGRAM_URL_UNRESOLVED"
    channel, mid = ident
    if expected_channel and channel.casefold() != expected_channel.casefold():
        return None, "TELEGRAM_CHANNEL_MISMATCH"
    attempts = [f"https://t.me/s/{channel}/{mid}", f"https://t.me/{channel}/{mid}?embed=1&mode=tme"]
    for u in attempts:
        try:
            r = http.get(u)
        except requests.RequestException:
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        wraps = soup.select(".tgme_widget_message_wrap, .tgme_widget_message")
        for wrap in wraps:
            msg = wrap.select_one(".tgme_widget_message") if "tgme_widget_message_wrap" in (wrap.get("class") or []) else wrap
            if not msg:
                continue
            post = str(msg.get("data-post") or "")
            m = re.search(r"/(\d+)$", post)
            if not m or int(m.group(1)) != mid:
                continue
            t = wrap.select_one("time[datetime]") or msg.select_one("time[datetime]")
            tx = wrap.select_one(".tgme_widget_message_text") or msg.select_one(".tgme_widget_message_text")
            text = " ".join(tx.stripped_strings) if tx else ""
            if not t:
                continue
            return {
                "url": f"https://t.me/{channel}/{mid}",
                "published_at": iso(parse_dt(t.get("datetime"))),
                "title": text[:240],
                "text": text,
                "publisher": "Telegram",
                "telegram_channel": channel,
                "telegram_message_id": mid,
            }, None
    return None, "FULLTEXT_RECOVERY_FAILED"

def extract_article(http: HTTP, url):
    try:
        r = http.get(url)
    except requests.RequestException as exc:
        return None, f"FULLTEXT_RECOVERY_FAILED:{type(exc).__name__}"
    ctype = str(r.headers.get("content-type") or "").casefold()
    if "html" not in ctype and ctype:
        return None, "FULLTEXT_RECOVERY_FAILED:NON_HTML"
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup.find_all(("script","style","nav","header","footer","aside","form","svg","noscript")):
        tag.decompose()
    title_node = soup.select_one("h1") or soup.select_one('meta[property="og:title"]')
    title = ""
    if title_node:
        title = title_node.get("content") if title_node.name == "meta" else " ".join(title_node.stripped_strings)
    published = None
    for sel, attr in [('meta[property="article:published_time"]',"content"),('time[datetime]',"datetime")]:
        n = soup.select_one(sel)
        if n and n.get(attr):
            published = parse_dt(n.get(attr))
            if published: break
    container = soup.find("article") or soup.find("main")
    if container is not None:
        text = " ".join(container.get_text(" ", strip=True).split())
    else:
        text = " ".join(" ".join(p.stripped_strings) for p in soup.find_all("p"))
        text = " ".join(text.split())
    text = text[:50000]
    if not (title or text):
        return None, "FULLTEXT_RECOVERY_FAILED:EMPTY"
    return {
        "url": canonical_url(str(r.url)),
        "published_at": iso(published) if published else None,
        "title": title,
        "text": text,
        "publisher": host_of(str(r.url)),
    }, None

def make_candidate(source_family, native, discovery_basis, search_meta):
    url = str(native.get("url") or "")
    text = str(native.get("text") or "")
    title = str(native.get("title") or "") or text[:240]
    seed = f'{source_family}|{url}|{native.get("published_at")}|{title}'
    row = {
        "candidate_id": hashlib.sha256(seed.encode("utf-8")).hexdigest()[:24],
        "city_key": "kyiv",
        "source": source_family,
        "url": url,
        "resolved_url": url,
        "title": title,
        "snippet": text[:1200],
        "matched_text_excerpt": text[:50000],
        "publisher": native.get("publisher") or source_family,
        "publisher_url": url,
        "published_at": native.get("published_at"),
        "discovery_basis": discovery_basis,
    }
    if native.get("telegram_channel"):
        row["telegram_channel"] = native["telegram_channel"]
        row["telegram_message_id"] = native["telegram_message_id"]
    return row, {
        "source_family": source_family,
        "candidate_url": url,
        "publication_time": native.get("published_at"),
        "fulltext_obtained": bool(text),
        "search_meta": search_meta,
    }

def native_in_window(native, start, end):
    pub = parse_dt(native.get("published_at"))
    if pub is None:
        # Keep undated publisher-native content only when search was date-bounded.
        return True
    return start <= pub <= end

def discover_via_google(http: HTTP, family, kind, handle, sanitized_ep):
    start = parse_dt(sanitized_ep["alert_start"]) - timedelta(hours=6)
    end = parse_dt(sanitized_ep["alert_end"]) + timedelta(hours=24)
    if kind == "telegram":
        site = f"t.me/{handle}"
    elif kind == "web":
        site = "suspilne.media/kyiv"
    else:
        site = None
    query_url = google_news_query(site, start, end)
    diagnostic = {"query_url":query_url,"search_hits":0,"resolve_failures":[]}
    try:
        rss = http.get(query_url)
        items = parse_google_rss(rss.content)
    except Exception as exc:
        diagnostic["technical_error"] = f"{type(exc).__name__}:{exc}"
        return [], diagnostic
    diagnostic["search_hits"] = len(items)
    found = {}
    outside = []
    for item in items:
        resolved, err = resolve_google_result(http, item)
        if not resolved:
            diagnostic["resolve_failures"].append({"link":item.get("link"),"reason":err})
            continue
        if kind == "telegram":
            ident = tg_identity(resolved)
            if not ident or ident[0].casefold() != handle.casefold():
                continue
            native, ferr = fetch_telegram_post(http, resolved, handle)
        else:
            ident = tg_identity(resolved)
            if ident:
                # Generic layer can expose fixed-source Telegram; resolve as native.
                if kind == "search" and ident[0].casefold() in FIXED_TG:
                    native, ferr = fetch_telegram_post(http, resolved, ident[0])
                else:
                    outside.append(resolved)
                    continue
            else:
                h = host_of(resolved)
                if kind == "web" and h not in ALLOWED_FIXED_DOMAINS:
                    continue
                if kind == "search" and h not in ALLOWED_FIXED_DOMAINS:
                    outside.append(resolved)
                    continue
                native, ferr = extract_article(http, resolved)
        if not native:
            diagnostic["resolve_failures"].append({"link":resolved,"reason":ferr})
            continue
        if not native_in_window(native,start,end):
            continue
        # Candidate discovery is generic and attack-vocabulary bounded.
        combined = f'{native.get("title","")} {native.get("text","")}'
        if not ATTACK_RE.search(combined) or not re.search(r"\bКи(їв|єв)", combined, re.I):
            continue
        row, meta = make_candidate(family, native, "fixed_generic_attack_search", {
            "query_family":"generic_attack_vocabulary",
            "source_filter":site,
        })
        found[row["candidate_id"]] = (row, meta)
    diagnostic["outside_fixed_source_set"] = sorted(set(outside))
    return list(found.values()), diagnostic


def fixed_family_for_url(url):
    ident = tg_identity(url)
    if ident:
        handle = ident[0].casefold()
        for family, kind, configured in SOURCE_ORDER:
            if kind == "telegram" and configured and handle == configured.casefold():
                return family, "telegram", configured
        return None
    if host_of(url) in ALLOWED_FIXED_DOMAINS and "/kyiv/" in (urlparse(url).path.casefold() + "/"):
        return "suspilne.media/kyiv", "web", "suspilne.media/kyiv"
    return None

def fixed_aggregate_query(start, end):
    after = (start.astimezone(KYIV_TZ).date() - timedelta(days=1)).isoformat()
    before = (end.astimezone(KYIV_TZ).date() + timedelta(days=1)).isoformat()
    attack = " OR ".join(f'"{t}"' for t in QUERY_TERMS)
    sites = [
        "site:t.me/VA_Kyiv",
        "site:t.me/KyivCityOfficial",
        "site:t.me/vitaliy_klitschko",
        "site:t.me/dsns_kyiv",
        "site:t.me/kpszsu",
        "site:t.me/suspilnenews",
        "site:t.me/suspilne_kyiv",
        "site:suspilne.media/kyiv",
    ]
    q = f'"Київ" ({attack}) (' + " OR ".join(sites) + f') after:{after} before:{before}'
    return "https://news.google.com/rss/search?q=" + quote_plus(q) + "&hl=uk&gl=UA&ceid=UA:uk"

def discover_fixed_aggregate(http, sanitized_ep):
    start = parse_dt(sanitized_ep["alert_start"]) - timedelta(hours=6)
    end = parse_dt(sanitized_ep["alert_end"]) + timedelta(hours=24)
    query_url = fixed_aggregate_query(start, end)
    diagnostic = {"query_url":query_url,"search_hits":0,"resolve_failures":[]}
    per_family = {family:[] for family,_,_ in SOURCE_ORDER if family != "generic_search"}
    try:
        rss = http.get(query_url)
        items = parse_google_rss(rss.content)
    except Exception as exc:
        diagnostic["technical_error"] = f"{type(exc).__name__}:{exc}"
        return per_family, diagnostic
    diagnostic["search_hits"] = len(items)
    seen = set()
    for item in items:
        resolved, err = resolve_google_result(http, item)
        if not resolved:
            diagnostic["resolve_failures"].append({"link":item.get("link"),"reason":err})
            continue
        faminfo = fixed_family_for_url(resolved)
        if not faminfo:
            continue
        family, kind, handle = faminfo
        if kind == "telegram":
            native, ferr = fetch_telegram_post(http, resolved, handle)
        else:
            native, ferr = extract_article(http, resolved)
        if not native:
            diagnostic["resolve_failures"].append({"link":resolved,"reason":ferr})
            continue
        if not native_in_window(native,start,end):
            continue
        combined = f'{native.get("title","")} {native.get("text","")}'
        if not ATTACK_RE.search(combined) or not re.search(r"\bКи(їв|єв)", combined, re.I):
            continue
        row, meta = make_candidate(family, native, "fixed_source_aggregate_generic_attack_search", {
            "query_family":"generic_attack_vocabulary",
            "source_filter":"aggregate_fixed_source_set",
        })
        key=(family,row["candidate_id"])
        if key in seen:
            continue
        seen.add(key)
        per_family[family].append((row,meta))
    return per_family, diagnostic

def context_episodes(all_eps, target_ep):
    # Matching context is derived only from alert start/end, never from truth evidence.
    st = parse_dt(target_ep["alert_start"]) - timedelta(hours=12)
    en = parse_dt(target_ep["alert_end"]) + timedelta(hours=36)
    return [
        copy.deepcopy(e) for e in all_eps
        if parse_dt(e["alert_end"]) >= st and parse_dt(e["alert_start"]) <= en
    ]

def classify_episode(mon, all_eps, target_ep, candidates):
    ctx = context_episodes(all_eps, target_ep)
    target_id = target_ep["episode_id"]
    classifier_rows = []
    records = []
    invocations = 0
    for row, meta in candidates:
        work = copy.deepcopy(row)
        try:
            matching = mon.match_candidate_to_episodes(work, ctx)
            decision = mon.classify_candidate(work, "kyiv", ctx, matching)
            invocations += 1
            if hasattr(mon, "apply_classification_decision"):
                mon.apply_classification_decision(work, decision, matching)
            classifier_rows.append(work)
            rec = {
                **meta,
                "evidence_passed_to_authoritative_classifier": True,
                "classifier_outcome": decision.get("proposed_outcome"),
                "classifier_episode_id": decision.get("proposed_matched_episode_id"),
                "reason_codes": list(decision.get("reason_codes") or []),
                "temporal_binding": copy.deepcopy(decision.get("temporal_binding") or {}),
                "exact_city_present": bool((decision.get("exact_city_classification_evidence") or {}).get("present")),
            }
        except Exception as exc:
            rec = {
                **meta,
                "evidence_passed_to_authoritative_classifier": False,
                "classifier_error": f"{type(exc).__name__}:{exc}",
            }
        records.append(rec)

    direct_strict = any(
        r.get("classifier_outcome") == "approved_strict" and r.get("classifier_episode_id") == target_id
        for r in records
    )
    direct_sens = any(
        r.get("classifier_outcome") == "approved_sensitivity" and r.get("classifier_episode_id") == target_id
        for r in records
    )
    review = any(r.get("classifier_outcome") == "needs_review" for r in records)
    composed = None
    target = next((e for e in ctx if e["episode_id"] == target_id), None)
    if not direct_strict and target is not None and len(classifier_rows) >= 2 and hasattr(mon,"compose_episode_candidates"):
        try:
            composed = mon.compose_episode_candidates("kyiv", target, classifier_rows, ctx)
        except Exception as exc:
            composed = {"error":f"{type(exc).__name__}:{exc}"}
    composed_verdict = str((composed or {}).get("final_composed_verdict") or "")
    if direct_strict or composed_verdict == "approved_strict":
        final = "STRICT_EVENT_POSITIVE"
    elif direct_sens or composed_verdict == "approved_sensitivity":
        final = "SENSITIVITY_EVENT_POSITIVE"
    elif review or composed_verdict == "needs_review":
        final = "NEEDS_REVIEW"
    else:
        final = "NO_CONFIRMED_EVENT"
    return final, records, composed, invocations

def primary_miss(source_diags, candidate_records, final):
    if final in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}:
        return None, None
    all_hits = sum(int((d or {}).get("search_hits") or 0) for d in source_diags.values())
    all_candidates = len(candidate_records)
    resolve_failures = [x for d in source_diags.values() for x in ((d or {}).get("resolve_failures") or [])]
    if all_hits == 0:
        return "NO_SOURCE_HIT", None
    if all_candidates == 0 and resolve_failures:
        if all("SNIPPET" in str(x.get("reason") or "") or "RESOLVE" in str(x.get("reason") or "") for x in resolve_failures):
            return "SEARCH_HIT_SNIPPET_ONLY", None
        return "FULLTEXT_RECOVERY_FAILED", None
    codes = Counter()
    for r in candidate_records:
        for c in r.get("reason_codes") or []:
            codes[str(c)] += 1
        tc = str((r.get("temporal_binding") or {}).get("code") or "")
        if tc:
            codes[tc] += 1
    joined = " ".join(codes)
    if "NO_EXACT_CITY" in joined:
        return "EXACT_CITY_INSUFFICIENT", None
    if "NO_AIR" in joined or "AIR_CONTEXT_NOT_LINKED" in joined:
        return "AIR_CONTEXT_INSUFFICIENT", None
    if "NO_STRICT_EXPLOSION" in joined or "NO_ATTACK" in joined:
        return "ATTACK_EVENT_WORDING_INSUFFICIENT", None
    if "SAME_ATTACK" in joined or "MULTI_INCIDENT" in joined:
        return "SAME_ATTACK_INSUFFICIENT", None
    if "TEMPORAL" in joined or "MATCH_NONE" in joined or "MATCH_AMBIGUOUS" in joined:
        return "TEMPORAL_BINDING_INSUFFICIENT", None
    if any(r.get("classifier_outcome") == "needs_review" for r in candidate_records):
        return "CLASSIFIER_REVIEW", None
    return "OTHER", {"reason_codes":dict(codes),"resolve_failure_count":len(resolve_failures)}

def run_one(mon, http, all_eps, ep):
    # ep is guaranteed sanitized: only episode_id/city_key/alert_start/alert_end.
    per_source_candidates = {family:[] for family,_,_ in SOURCE_ORDER}
    source_diags = {}
    all_candidates = {}
    outside = set()

    # One date-bounded query spans the complete fixed source set; native URLs
    # are then attributed back to the exact source family before fulltext fetch.
    fixed_map, fixed_diag = discover_fixed_aggregate(http, ep)
    for family, _, _ in SOURCE_ORDER:
        if family == "generic_search":
            continue
        cands = fixed_map.get(family) or []
        per_source_candidates[family] = cands
        source_diags[family] = {
            **fixed_diag,
            "aggregate_fixed_source_query": True,
            "family_candidate_count": len(cands),
        }
        for row, meta in cands:
            all_candidates[(family,row["candidate_id"])] = (row,meta)

    # Generic search is a separate discovery layer. Only fixed-source native
    # results count in primary metrics; other publishers are recorded outside.
    generic_cands, generic_diag = discover_via_google(http, "generic_search", "search", None, ep)
    per_source_candidates["generic_search"] = generic_cands
    source_diags["generic_search"] = generic_diag
    for u in generic_diag.get("outside_fixed_source_set") or []:
        outside.add(u)
    for row, meta in generic_cands:
        all_candidates[("generic_search",row["candidate_id"])] = (row,meta)

    final, records, composed, invocations = classify_episode(mon, all_eps, ep, list(all_candidates.values()))
    miss, miss_detail = primary_miss(source_diags, records, final)
    source_summary = {}
    for family, _, _ in SOURCE_ORDER:
        fam_records = [r for r in records if r.get("source_family") == family]
        fam_positive = any(
            r.get("classifier_outcome") in {"approved_strict","approved_sensitivity"}
            and r.get("classifier_episode_id") == ep["episode_id"]
            for r in fam_records
        )
        source_summary[family] = {
            "candidate_count": len(per_source_candidates.get(family) or []),
            "usable_evidence": any(bool(r.get("fulltext_obtained")) and r.get("evidence_passed_to_authoritative_classifier") for r in fam_records),
            "positive_reproduced": fam_positive,
        }
    return {
        "episode_id": ep["episode_id"],
        "alert_start": ep["alert_start"],
        "alert_end": ep["alert_end"],
        "sources_queried": [x[0] for x in SOURCE_ORDER],
        "candidate_urls_found": sorted({r.get("candidate_url") for r in records if r.get("candidate_url")}),
        "candidate_records": records,
        "source_family_results": source_summary,
        "source_diagnostics": source_diags,
        "outside_fixed_source_set": sorted(outside),
        "authoritative_classifier_invocations": invocations,
        "final_alert_level_verdict": final,
        "composition": composed,
        "primary_miss_class": miss,
        "primary_miss_detail": miss_detail,
    }

def metrics(rows):
    pos = [r for r in rows if r["truth_label"] in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}]
    holds = [r for r in rows if r["truth_label"] == "HOLD_CONTROL"]
    cand = sum(bool(r["result"]["candidate_urls_found"]) for r in pos)
    usable = sum(any(x.get("fulltext_obtained") and x.get("evidence_passed_to_authoritative_classifier")
                     for x in r["result"]["candidate_records"]) for r in pos)
    final = sum(r["result"]["final_alert_level_verdict"] in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"} for r in pos)
    strict = sum(r["result"]["final_alert_level_verdict"] == "STRICT_EVENT_POSITIVE" for r in pos)
    sens = sum(r["result"]["final_alert_level_verdict"] == "SENSITIVITY_EVENT_POSITIVE" for r in pos)
    hold_prom = sum(r["result"]["final_alert_level_verdict"] in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"} for r in holds)
    return {
        "positive_n":len(pos),"hold_n":len(holds),
        "candidate_n":cand,"candidate_recall":cand/len(pos) if pos else 0,
        "usable_n":usable,"usable_evidence_recall":usable/len(pos) if pos else 0,
        "final_positive_n":final,"final_positive_recall":final/len(pos) if pos else 0,
        "strict_reproduced":strict,"sensitivity_reproduced":sens,
        "unsupported_hold_promotions":hold_prom,
    }

def source_attribution(rows):
    positive_rows = [r for r in rows if r["truth_label"] in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}]
    hold_rows = [r for r in rows if r["truth_label"] == "HOLD_CONTROL"]
    out = {}
    previously_found = set()
    for family, _, _ in SOURCE_ORDER:
        cand_ids = {r["episode_id"] for r in positive_rows if r["result"]["source_family_results"][family]["candidate_count"] > 0}
        usable_ids = {r["episode_id"] for r in positive_rows if r["result"]["source_family_results"][family]["usable_evidence"]}
        positive_ids = {r["episode_id"] for r in positive_rows if r["result"]["source_family_results"][family]["positive_reproduced"]}
        hold_cand = {r["episode_id"] for r in hold_rows if r["result"]["source_family_results"][family]["candidate_count"] > 0}
        hold_prom = {
            r["episode_id"] for r in hold_rows
            if r["result"]["source_family_results"][family]["positive_reproduced"]
        }
        unique = positive_ids - previously_found
        out[family] = {
            "positives_with_any_candidate":len(cand_ids),
            "positives_with_usable_evidence":len(usable_ids),
            "positives_finally_reproduced":len(positive_ids),
            "holds_with_any_candidate":len(hold_cand),
            "holds_promoted":len(hold_prom),
            "unique_positives_found_by_this_source_and_no_earlier_source":len(unique),
            "marginal_gain_over_preceding_source_set":len(unique),
        }
        previously_found |= positive_ids
    return out

def period_metrics(rows):
    buckets = defaultdict(list)
    for r in rows:
        buckets[str(r["result"]["alert_start"])[:4]].append(r)
    return {year:metrics(rr) for year,rr in sorted(buckets.items())}

def run_cohort(mon,http,all_eps,split_rows,cohort):
    rows = []
    for idx, truth_row in enumerate([x for x in split_rows if x["cohort"] == cohort], 1):
        sanitized = {k:truth_row[k] for k in ("episode_id","city_key","alert_start","alert_end")}
        result = run_one(mon,http,all_eps,sanitized)
        # Truth is joined only after discovery+classification returns.
        rows.append({
            "episode_id":truth_row["episode_id"],
            "truth_label":truth_row["truth_label"],
            "result":result,
        })
        print(f"[{cohort} {idx}] {truth_row['episode_id']} -> {result['final_alert_level_verdict']} candidates={len(result['candidate_urls_found'])}", flush=True)
    return rows

def pct(x): return round(100*x, 3)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split",required=True)
    ap.add_argument("--strategy",required=True)
    ap.add_argument("--blind",required=True)
    ap.add_argument("--run-id",required=True)
    a = ap.parse_args()

    split_raw = Path(a.split).read_bytes()
    split = json.loads(split_raw)
    if split.get("verdict") != "KYIV HISTORICAL DISCOVERY SPLIT = FROZEN":
        raise Blocked("SPLIT_NOT_FROZEN")
    split_rows = list(split.get("episodes") or [])
    counts = split.get("counts") or {}
    if (counts.get("development_positives"),counts.get("development_holds"),counts.get("blind_positives"),counts.get("blind_holds")) != (48,19,97,38):
        raise Blocked("SPLIT_COUNTS_INVALID")

    tmp = Path(tempfile.mkdtemp(prefix="kyiv-discovery-calibration-"))
    try:
        mon, wt = prepare_authoritative_monitor(tmp)
        all_eps = load_full_kyiv_episodes()
        http = HTTP()

        # Development run. No old URLs, evidence text, publisher identities, or truth labels
        # enter run_one(); only sanitized episode identity + alert bounds.
        development = run_cohort(mon,http,all_eps,split_rows,"development")
        dev_metrics = metrics(development)
        dev_attr = source_attribution(development)

        strategy = {
            "schema_version":1,
            "kind":"kyiv_historical_discovery_frozen_strategy",
            "generated_at":iso(datetime.now(UTC)),
            "workflow_run_id":str(a.run_id),
            "split_sha256":sha256(split_raw),
            "authoritative_classifier":{
                "commit":AUTH_COMMIT,"path":AUTH_PATH,"blob":AUTH_BLOB,
                "semantics_modified":False,
            },
            "fixed_source_order":[x[0] for x in SOURCE_ORDER],
            "fixed_source_definitions":[{
                "family":fam,"type":kind,"identity":handle
            } for fam,kind,handle in SOURCE_ORDER],
            "fixed_generic_attack_vocabulary":VOCAB,
            "query_terms":QUERY_TERMS,
            "retrieval_window":{"start_offset_hours":-6,"end_offset_hours":24},
            "telegram_retrieval_method":"one Google News-style date-bounded aggregate query over all fixed Telegram/web sources, then exact native-URL family attribution and original public t.me post fetch; separate generic-search query retained for marginal gain",
            "publisher_resolution_rule":"Search result is discovery only; resolved source-native content required. Fixed web publisher is suspline.media/kyiv. Other publishers are OUTSIDE_FIXED_SOURCE_SET.",
            "fulltext_extraction_method":"source-native HTML article/main/p fallback; original Telegram post text for t.me",
            "candidate_deduplication":"source_family + deterministic native candidate_id",
            "candidate_ranking":"Google News RSS order within each fixed aggregate or generic query; native publication time retained; capped at 30 results/query",
            "maximum_candidates_per_episode":"bounded by 2 search queries (aggregate fixed-source + generic) x 30 search results before native filtering",
            "development_iterations":[{
                "iteration":1,
                "strategy_change_after_iteration":"NONE — initial compliant fixed strategy frozen unchanged",
                "metrics":dev_metrics,
                "source_attribution":dev_attr,
            }],
            "blindness_audit":{
                "discovery_input_fields":["episode_id","city_key","alert_start","alert_end"],
                "truth_label_entered_discovery":False,
                "old_evidence_urls_used":False,
                "old_candidate_urls_used":False,
                "old_telegram_message_ids_used":False,
                "review_provenance_used":False,
                "historical_candidate_text_used":False,
                "attack_event_text_used":False,
                "truth_source_mappings_used":False,
                "status":"PASS",
            },
            "development_results":development,
            "development_metrics":dev_metrics,
            "development_source_attribution":dev_attr,
            "frozen_before_blind":True,
        }
        strategy_bytes = canonical_json_bytes(strategy)
        Path(a.strategy).parent.mkdir(parents=True,exist_ok=True)
        Path(a.strategy).write_bytes(strategy_bytes)
        frozen_strategy_sha = sha256(strategy_bytes)
        print("FROZEN_STRATEGY_SHA256="+frozen_strategy_sha, flush=True)

        # Blind run exactly once, after durable strategy bytes have been written.
        blind_rows = run_cohort(mon,http,all_eps,split_rows,"blind")
        if sha256(Path(a.strategy).read_bytes()) != frozen_strategy_sha:
            raise Blocked("FROZEN_STRATEGY_MUTATED_DURING_BLIND")
        bm = metrics(blind_rows)
        ba = source_attribution(blind_rows)
        miss_counts = Counter(
            r["result"]["primary_miss_class"] for r in blind_rows
            if r["truth_label"] in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}
            and r["result"]["primary_miss_class"]
        )
        dominant = miss_counts.most_common(1)[0][0] if miss_counts else None

        major_failures = {}
        for fam,_,_ in SOURCE_ORDER:
            tech = sum(
                1 for r in blind_rows
                if (r["result"]["source_diagnostics"].get(fam) or {}).get("technical_error")
            )
            major_failures[fam] = {
                "episodes_with_technical_error":tech,
                "invalidates_major_source_family": tech == len(blind_rows) and len(blind_rows) > 0,
            }
        unresolved_major = any(x["invalidates_major_source_family"] for x in major_failures.values())
        go = (
            bm["candidate_recall"] >= .60 and
            bm["usable_evidence_recall"] >= .50 and
            bm["final_positive_recall"] >= .40 and
            bm["unsupported_hold_promotions"] == 0 and
            not unresolved_major
        )
        decision = "GO TO UNKNOWN-ALERT PILOT" if go else "NO-GO — DISCOVERY REDESIGN STILL REQUIRED"
        verdict = "KYIV HISTORICAL DISCOVERY BLIND PILOT = GO" if go else "KYIV HISTORICAL DISCOVERY BLIND PILOT = NO-GO"

        fixed_family_positive_union = {
            r["episode_id"] for r in blind_rows
            if r["truth_label"] in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}
            and any(
                r["result"]["source_family_results"][fam]["positive_reproduced"]
                for fam,_,_ in SOURCE_ORDER if fam != "generic_search"
            )
        }
        generic_positive = {
            r["episode_id"] for r in blind_rows
            if r["truth_label"] in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}
            and r["result"]["source_family_results"]["generic_search"]["positive_reproduced"]
        }
        generic_marginal = len(generic_positive - fixed_family_positive_union)

        best_family = max(
            (fam for fam,_,_ in SOURCE_ORDER),
            key=lambda f:(ba[f]["positives_finally_reproduced"],ba[f]["positives_with_usable_evidence"],-SOURCE_ORDER.index(next(x for x in SOURCE_ORDER if x[0]==f))),
        )

        blind_artifact = {
            "schema_version":1,
            "kind":"kyiv_historical_discovery_blind_pilot",
            "generated_at":iso(datetime.now(UTC)),
            "workflow_run_id":str(a.run_id),
            "verdict":verdict,
            "decision":decision,
            "frozen_strategy_sha256":frozen_strategy_sha,
            "split_sha256":sha256(split_raw),
            "blindness_leakage_audit":strategy["blindness_audit"],
            "fixed_source_families":[x[0] for x in SOURCE_ORDER],
            "development_metrics":dev_metrics,
            "blind_metrics":bm,
            "blind_source_attribution":ba,
            "best_performing_source_family":best_family,
            "combined_fixed_source_reproduced":len(fixed_family_positive_union),
            "combined_fixed_source_recall":len(fixed_family_positive_union)/97,
            "generic_search_marginal_gain":generic_marginal,
            "blind_miss_class_counts":dict(miss_counts),
            "dominant_blind_miss_class":dominant,
            "blind_period_breakdown":period_metrics(blind_rows),
            "source_family_technical_failures":major_failures,
            "old_strategy_baseline":{
                "rediscovered_evidence":"13/145",
                "usable_evidence_recall":OLD_EVIDENCE_RECALL,
                "final_positives":"3/145",
                "final_positive_recall":OLD_FINAL_RECALL,
            },
            "new_vs_old":{
                "usable_evidence_absolute_percentage_points":pct(bm["usable_evidence_recall"]-OLD_EVIDENCE_RECALL),
                "usable_evidence_relative_multiple":round(bm["usable_evidence_recall"]/OLD_EVIDENCE_RECALL,3) if OLD_EVIDENCE_RECALL else None,
                "final_positive_absolute_percentage_points":pct(bm["final_positive_recall"]-OLD_FINAL_RECALL),
                "final_positive_relative_multiple":round(bm["final_positive_recall"]/OLD_FINAL_RECALL,3) if OLD_FINAL_RECALL else None,
            },
            "go_thresholds":{
                "candidate_recall_min":.60,
                "usable_evidence_recall_min":.50,
                "final_positive_recall_min":.40,
                "unsupported_hold_promotions_required":0,
                "no_major_source_family_technical_failure_required":True,
                "lowered_after_results":False,
            },
            "blind_episode_results":blind_rows,
            "network_diagnostics":{"http":dict(http.stats)},
            "mutation_confirmation":{
                "historical_backfill_started":False,
                "unknown_alert_pilot_started":False,
                "Neon_writes":0,
                "production_mutations":0,
                "live_pipeline_modifications":0,
                "canonical_classification_mutations":0,
                "review_queue_mutations":0,
                "allowed_branch_artifacts_only":True,
            },
        }
        Path(a.blind).write_text(json.dumps(blind_artifact,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        print("BLIND_SUMMARY="+json.dumps({
            "verdict":verdict,"decision":decision,
            "candidate_recall":bm["candidate_recall"],
            "usable_recall":bm["usable_evidence_recall"],
            "final_recall":bm["final_positive_recall"],
            "hold_promotions":bm["unsupported_hold_promotions"],
            "dominant_miss":dominant,
            "best_source":best_family,
        },ensure_ascii=False,separators=(",",":")), flush=True)
    finally:
        try:
            if 'wt' in locals():
                sh(["git","worktree","remove","--force",str(wt)],check=False)
        finally:
            shutil.rmtree(tmp,ignore_errors=True)

if __name__ == "__main__":
    try:
        main()
    except Blocked as exc:
        print("PILOT_BLOCKED="+str(exc),file=sys.stderr)
        raise SystemExit(2)