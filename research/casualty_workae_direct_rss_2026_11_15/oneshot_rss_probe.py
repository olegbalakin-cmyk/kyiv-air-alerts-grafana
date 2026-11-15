#!/usr/bin/env python3
"""One-shot metadata probe for the six owner-authorized Work AE feeds.

Research receipt ONLY: reuse Work AC's pinned HTTPS/SSRF/bounded transport
and Work AD's existing relevance/date helpers; do not build a new RSS pipeline.
No article GET, no persisted RSS XML, article text, personal data or WIP writes.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit
import hashlib
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
import casualty_workac_capture as ac  # Existing pinned TLS, public DNS and 2 MiB bounded transport
import monitor_casualty_candidates as monitor  # Existing exact 23-city and relevance filters

FEEDS = (
    ("Укрінформ", "https://www.ukrinform.ua/rss/block-lastnews",
     ("ukrinform.ua", "www.ukrinform.ua")),
    ("Радіо Свобода", "https://www.radiosvoboda.org/api/zrqiteuuir",
     ("radiosvoboda.org", "www.radiosvoboda.org")),
    ("Українська правда", "https://www.pravda.com.ua/rss/view_news/",
     ("pravda.com.ua", "www.pravda.com.ua")),
    ("Інтерфакс-Україна", "https://en.interfax.com.ua/news/last.rss",
     ("en.interfax.com.ua", "interfax.com.ua", "www.interfax.com.ua")),
    ("Еспресо", "https://espreso.tv/rss",
     ("espreso.tv", "www.espreso.tv")),
    ("Громадське радіо", "https://hromadske.radio/feed",
     ("hromadske.radio", "www.hromadske.radio")),
)
assert len(FEEDS) == 6 and len(set(url for _,url,_ in FEEDS)) == 6
assert ac.MAX_BYTES == 2 * 1024 * 1024
assert monitor.MAX_RSS_GETS == 23 and ac.MAX_ARTICLE_GETS == 10
MAX_REQUESTS = 6
TIMEOUT_SECONDS = 15
STOP_CODES = ("NONPUBLIC_DNS_IP", "UNSAFE_DNS_ADDRESS_FAMILY",
              "NONPUBLIC_IP", "IP_LITERAL_NOT_ALLOWED",
              "BODY_LIMIT_EXCEEDED", "DECOMPRESSED_BODY_LIMIT_EXCEEDED",
              "UNSAFE_URL")
OUT = Path(os.environ.get("WORKAE_PILOT_OUT", "/tmp/workae-rss-pilot"))
UTC = timezone.utc


def sha(value: str | bytes) -> str:
    return sha256(value.encode("utf-8") if isinstance(value, str) else value).hexdigest()


def dt_rfc822(value: str | None):
    if not value:
        return None
    try:
        d = parsedate_to_datetime(value)
        return d.astimezone(UTC) if d.tzinfo else None
    except (TypeError, ValueError, OverflowError):
        return None


def dt_iso(value: str | None):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return d.astimezone(UTC) if d.tzinfo else None
    except (TypeError, ValueError):
        return None


def iso(t: datetime | None):
    return t.astimezone(UTC).isoformat().replace("+00:00","Z") if t else None


def validated_original(url: str, publisher_hosts):
    """Metadata validation only; never attempts article HTTP."""
    if not url or re.search(r"[\x00-\x20\x7f\\]", url) or len(url) > 2048:
        return False, False, None
    try:
        p = urlsplit(url)
        h = (p.hostname or "").lower()
        safe = (p.scheme == "https" and h in publisher_hosts and
                p.username is None and p.password is None and
                p.port in (None, 443) and not p.fragment)
        allowed = False
        if safe:
            try:
                ac.allowed_article_url(url)  # syntactic + static Work AC allowlist; NO DNS / GET
                allowed = True
            except (ac.CaptureBlocked, ValueError):
                allowed = False
        return bool(safe), allowed, h
    except ValueError:
        return False, False, None


def request_feed(url: str, deadline: float):
    # Enforce the literal owner-approved six URL allowlist and no other HTTP.
    assert url in {x[1] for x in FEEDS}
    p = urlsplit(url)
    if (p.scheme != "https" or p.username or p.password or p.fragment
        or p.port not in (None, 443) or not p.hostname
        or re.search(r"[\x00-\x20\x7f\\]",url)):
        raise RuntimeError("UNSAFE_AUTHORIZED_URL")
    conn = ac.PinnedHTTPS(p.hostname, deadline)
    try:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("BEFORE_GET_DEADLINE")
        # One GET, no redirects, no retries, proxy, auth or cookies.
        conn.request("GET", (p.path or "/") + (("?" + p.query) if p.query else ""),
                     headers={"User-Agent":"casualty-workae-one-shot-read-only/1.0",
                              "Accept":"application/rss+xml,application/atom+xml,application/xml,text/xml",
                              "Accept-Encoding":"gzip,deflate,identity",
                              "Connection":"close"})
        if conn.sock:
            conn.sock.settimeout(max(0.1, min(8, deadline - time.monotonic())))
        response = conn.getresponse()
        status = int(response.status)
        headers = {k.lower():v for k,v in response.getheaders()
                   if k.lower() in ("content-type","content-encoding","etag",
                                    "last-modified","content-length","location")}
        if status != 200:
            return status, headers, None, None
        if headers.get("content-length","").isdigit() and int(headers["content-length"]) > ac.MAX_BYTES:
            raise ac.CaptureBlocked("BODY_LIMIT_EXCEEDED")
        compression = headers.get("content-encoding","identity").strip().lower()
        if compression not in ("identity","gzip","deflate",""):
            raise ac.CaptureBlocked("UNSUPPORTED_CONTENT_ENCODING")
        wire = ac._read_bounded(response, conn, deadline)
        decoded = ac._decode_limited(wire, compression)
        if b"<!doctype" in decoded.lower() or b"<!entity" in decoded.lower():
            raise RuntimeError("UNTRUSTED_XML_DTD")
        if time.monotonic() > deadline:
            raise TimeoutError("TOTAL_DEADLINE_EXCEEDED")
        return status, headers, wire, decoded
    finally:
        conn.close()


def inspect_xml(document: bytes, publisher_hosts: tuple[str, ...], now: datetime):
    """Read only existing RSS2 item tags or Atom *metadata*, never full articles."""
    root = ET.fromstring(document)
    is_rss = root.tag == "rss" and root.find("channel") is not None
    is_atom = root.tag == "{http://www.w3.org/2005/Atom}feed"
    if not (is_rss or is_atom):
        raise ValueError("NOT_RSS2_OR_ATOM")
    records = []
    ns = "{http://www.w3.org/2005/Atom}"
    if is_rss:
        items = root.findall("./channel/item")
        for item in items:
            records.append((item.findtext("title") or "", item.findtext("description") or "",
                            (item.findtext("link") or "").strip(),
                            dt_rfc822(item.findtext("pubDate"))))
    else:
        items = root.findall(f"{ns}entry")
        for item in items:
            link_el = next((x for x in item.findall(f"{ns}link")
                            if x.attrib.get("rel","alternate") == "alternate"
                            and x.attrib.get("href")), None)
            if link_el is None:
                link_el = item.find(f"{ns}link")
            link = ((link_el.attrib.get("href") or "").strip()
                    if link_el is not None else "")
            published = dt_iso(item.findtext(f"{ns}published")) or dt_iso(item.findtext(f"{ns}updated"))
            records.append((item.findtext(f"{ns}title") or "",
                            item.findtext(f"{ns}summary") or "",
                            link, published))
    snapshots = []
    cities_seen = set()
    counts = Counter()
    dates = []
    for title,desc,link,published in records:
        direct, workac, host = validated_original(link,publisher_hosts)
        combined = " ".join((title,desc))
        relevant_terms = monitor.relevant_news(combined)
        cities = [k for k in monitor.CITY_CONFIG if monitor.city_mentioned(k,combined)]
        relevant = bool(relevant_terms and cities)
        cities_seen.update(cities if relevant else [])
        if direct: counts["direct_links"] += 1
        if workac: counts["links_allowlisted_workac"] += 1
        if published:
            dates.append(published)
            age=now-published
            if timedelta(0) <= age <= timedelta(hours=24): counts["within_24h"] += 1
            if timedelta(0) <= age <= timedelta(hours=48): counts["within_48h"] += 1
            if timedelta(0) <= age <= timedelta(hours=8): counts["within_8h"] += 1
        else: counts["invalid_or_missing_dates"] += 1
        if relevant:
            counts["relevant_23city_keyword_hits"] += 1
            if direct: counts["relevant_direct_links"] += 1
        # Only hashed URL/title identifiers + categorical metadata; NO article text or PII.
        snapshots.append({
            "link_sha256":sha(link) if link else None,
            "has_link": bool(link),
            "is_direct_publisher_url":direct,
            "workac_article_host_allowlisted":workac,
            "publisher_host": host if host in publisher_hosts else None,
            "published_at_utc":iso(published),
            "relevant_by_existing_workad_filter":relevant,
            "relevant_city_keys":cities if relevant else [],
            "headline_sha256":sha(title) if title else None,
        })
    oldest = min(dates) if dates else None
    newest = max(dates) if dates else None
    counts["items"] = len(records)
    counts["distinct_article_url_hashes"] = len(set(x["link_sha256"] for x in snapshots if x["link_sha256"]))
    return {
        "format":"RSS2" if is_rss else "Atom",
        "item_count":len(records),
        "counts":dict(counts),
        "oldest_item_utc":iso(oldest), "newest_item_utc":iso(newest),
        "feed_span_hours":round((newest-oldest).total_seconds()/3600,2) if newest and oldest else None,
        "earliest_before_8h":bool(oldest and oldest <= now-timedelta(hours=8)),
        "earliest_before_48h":bool(oldest and oldest <= now-timedelta(hours=48)),
        "relevant_city_keys":sorted(cities_seen),
        "item_metadata":snapshots,
    }


def main():
    if os.environ.get("GITHUB_RUN_ATTEMPT") != "1" or os.environ.get("WORKAE_GO_APPROVED") != "yes-one-shot-6-feeds":
        raise SystemExit("NOT_AUTHORIZED_ONE_SHOT")
    OUT.mkdir(parents=True,exist_ok=True)
    began=datetime.now(UTC)
    evidence={"schema":"casualty-workae-one-shot-receipt-v1",
              "source_code_head_approved":"53c48f0b6b3ed515df34eb13c01a0872d9e65d32",
              "pilot_code_head":os.environ.get("GITHUB_SHA"),
              "actions_run_id":os.environ.get("GITHUB_RUN_ID"),
              "owner_go":"six_literal_RSS_urls_one_get_each",
              "started_at_utc":iso(began),
              "rss_request_attempt_limit":6,
              "per_request_total_timeout_seconds":15,
              "wire_and_decoded_bytes_limit":2*1024*1024,
              "redirect_follow":False,"automatic_retries":0,"article_gets":0,
              "active_wip_writes":0,"automatic_credits":0,
              "PROMOTE":"OFF","publication_allowed":False,
              "get_attempts":0,
              "feeds":[],
              "comparable_google_news_window":False,
              "incremental_google_news_coverage":"NOT_MEASURED",
              "notes":["Source bodies and article texts are not persisted.",
                       "RSS item headlines are hashed, not retained.",
                       "RSS metadata alone cannot establish fatality evidence cards or incident identity.",
                       "Direct publisher URLs not checked by article GET.",
                       "24/48h keyword hits are not proof of unique fatal attacks."]}
    cross=defaultdict(list)
    for index,(name,url,publisher_hosts) in enumerate(FEEDS,1):
        assert evidence["get_attempts"] < MAX_REQUESTS
        item={"order":index,"medium":name,"feed_url":url,
              "http_status":None,"content_type":None,
              "etag_present":False,"last_modified_present":False,
              "raw_sha256":None,"xml_sha256":None,
              "wire_bytes":None,"decoded_bytes":None,
              "redirect_response":False,"location_host":None,
              "error":None}
        evidence["get_attempts"]+=1  # Count even DNS/timeouts; never retry.
        deadline=time.monotonic()+TIMEOUT_SECONDS
        try:
            status,headers,wire,body=request_feed(url,deadline)
            item["http_status"]=status
            item["content_type"]=headers.get("content-type")
            item["etag_present"]=bool(headers.get("etag"))
            item["last_modified_present"]=bool(headers.get("last-modified"))
            item["http_content_length"]=headers.get("content-length")
            if 300 <= status <= 399:
                item["redirect_response"]=True
                location=headers.get("location")
                if location:
                    try: item["location_host"]=urlsplit(location).hostname
                    except ValueError: pass
            if status != 200:
                item["error"]="NON_200_NO_REDIRECT_FOLLOW"
            else:
                item["raw_sha256"]=sha(wire)
                item["xml_sha256"]=sha(body)
                item["wire_bytes"]=len(wire)
                item["decoded_bytes"]=len(body)
                item.update(inspect_xml(body,publisher_hosts,began))
                for entry in item.pop("item_metadata"):
                    if entry["link_sha256"]:
                        cross[entry["link_sha256"]].append((index,entry["relevant_by_existing_workad_filter"]))
                # Retain only bounded metadata hashes for relevant hits, not every feed item.
                item["relevant_link_sha256"]=[
                    x for x,entries in cross.items()
                    if any(i==index and rel for i,rel in entries)
                ][:300]
                mime=(item["content_type"] or "").split(";",1)[0].strip().lower()
                item["content_type_expected_xml"]=mime in {
                    "application/rss+xml","application/atom+xml","application/xml","text/xml"}
        except Exception as exc:
            item["error"]=type(exc).__name__+":"+str(exc)[:120]
            if any(code in item["error"] for code in STOP_CODES):
                evidence["stop_reason"]="SECURITY_OR_RESPONSE_BOUND"
        item["elapsed_seconds"]=round(TIMEOUT_SECONDS-max(0,deadline-time.monotonic()),3)
        evidence["feeds"].append(item)
        # Save after each attempt, even when a later feed fails. No XML stored.
        evidence["finished_at_utc"]=iso(datetime.now(UTC))
        (OUT/"pilot_receipt.json").write_text(
            json.dumps(evidence,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        if evidence.get("stop_reason"):
            break
    evidence["duplicates_same_url_across_feeds"]=sum(
        len(set(i for i,_ in matches))>1 for matches in cross.values())
    evidence["duplicates_extra_feed_occurrences"]=sum(
        max(0,len(set(i for i,_ in matches))-1) for matches in cross.values())
    evidence["completed_all_6_attempts"]=evidence["get_attempts"]==6
    evidence["finished_at_utc"]=iso(datetime.now(UTC))
    output=json.dumps(evidence,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
    (OUT/"pilot_receipt.json").write_text(output,encoding="utf-8")
    manifest={"pilot_receipt.json":sha(output)}
    (OUT/"sha256_manifest.json").write_text(json.dumps(manifest,indent=2,sort_keys=True)+"\n")
    assert sha((OUT/"pilot_receipt.json").read_bytes())==manifest["pilot_receipt.json"]
    assert evidence["article_gets"] == evidence["automatic_credits"] == evidence["active_wip_writes"] == 0
    assert evidence["get_attempts"]<=6
    print("WORKAE_ONE_SHOT_PILOT_COMPLETED",json.dumps({
        "attempts":evidence["get_attempts"],
        "status_by_feed":[{"url":x["feed_url"],"status":x["http_status"],
                           "format":x.get("format"),"items":x.get("item_count"),
                           "error":x["error"]} for x in evidence["feeds"]],
        "proof_sha256":manifest["pilot_receipt.json"],"auto_credits":0,
        "PROMOTE":"OFF"
    },ensure_ascii=False))
if __name__=="__main__":
    main()
