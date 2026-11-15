#!/usr/bin/env python3
"""Owner-approved one-shot six-feed metadata-only RSS probe. Strictly no article GETs."""
from __future__ import annotations

import hashlib
import html
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import socket
import ssl
import sys
import time
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit
import xml.etree.ElementTree as ET
import zlib

URLS = (
    "https://www.ukrinform.ua/rss/block-lastnews",
    "https://www.radiosvoboda.org/api/zrqiteuuir",
    "https://www.pravda.com.ua/rss/view_news/",
    "https://en.interfax.com.ua/news/last.rss",
    "https://espreso.tv/rss",
    "https://hromadske.radio/feed",
)
ORIGINAL_HEAD = "53c48f0b6b3ed515df34eb13c01a0872d9e65d32"
LAUNCH_PATH = Path("research/casualty_workae_direct_rss_2026_11_15/owner_go_one_shot.json")
MAX_BYTES = 2 * 1024 * 1024
MAX_GET = 6
TIMEOUT = 15
KEY_TERMS = re.compile(r"загибл|загинув|загинула|загинули|померл|померла|померли|жертв|смерт|убит|killed|dead|fatalit", re.I)
ATTACK_TERMS = re.compile(r"атак|обстр|удар|ракет|дрон|шахед|вибух|окупант|росі|військ|bomb|missile|strike|attack", re.I)


def utc_now():
    return datetime.now(timezone.utc)


def is_public(ip):
    return ipaddress.ip_address(ip).is_global


def parse_time(s):
    if not s:
        return None
    try:
        dt = parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    return dt.replace(tzinfo=timezone.utc).astimezone(timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def tag_text(elem, name, default=""):
    v = elem.findtext(name)
    return v.strip() if isinstance(v, str) else default


def scrub(s):
    return html.unescape(re.sub(r"<[^>]{0,400}>", " ", s or ""))[:6000]


def parse_feed(payload, feed_host, now):
    if b"<!DOCTYPE" in payload.upper() or b"<!ENTITY" in payload.upper():
        raise ValueError("DTD_OR_ENTITY_BLOCKED")
    root = ET.fromstring(payload)
    name = root.tag.split("}")[-1].lower()
    if name == "rss":
        ch = root.find("channel")
        if ch is None:
            raise ValueError("RSS_CHANNEL_MISSING")
        items = ch.findall("item")
        def attrs(it):
            return tag_text(it, "link"), tag_text(it, "pubDate"), tag_text(it, "title"), tag_text(it, "description")
        kind = "RSS2"
    elif name == "feed":
        ns="{http://www.w3.org/2005/Atom}"
        items = root.findall(ns + "entry")
        def attrs(it):
            links = [e.get("href") for e in it.findall(ns + "link") if e.get("rel", "alternate") == "alternate"]
            link = next((u for u in links if u), "")
            return link, tag_text(it, ns + "published") or tag_text(it, ns + "updated"), tag_text(it, ns + "title"), tag_text(it, ns + "summary")
        kind = "Atom"
    else:
        raise ValueError("NOT_RSS_OR_ATOM")
    direct=non_google=valid_link=publisher_family=relevant=recent=recent_rel=0
    dates=[]; seen=set(); sample=[]
    duplicates=0
    base_host = feed_host.removeprefix("www.").removeprefix("en.")
    for item in items:
        url, ds, title, description = attrs(item)
        u=urlsplit(url)
        host=(u.hostname or "").lower()
        https=bool(u.scheme == "https" and host and not u.username and not u.password)
        google = host == "news.google.com" or host.endswith(".news.google.com")
        if https:
            valid_link += 1
            if not google:
                non_google += 1
            if (host == base_host or host.endswith("." + base_host)) and not google:
                publisher_family += 1
                direct += 1
        if url:
            digest=hashlib.sha256(url.encode("utf-8")).hexdigest()
            if digest in seen: duplicates+=1
            else:
                seen.add(digest)
                if len(sample)<3:
                    sample.append({"url_sha256":digest,"link_host":host})
        dt=parse_time(ds)
        if dt:
            dates.append(dt)
        rel=bool(KEY_TERMS.search(scrub(title+" "+description)) and ATTACK_TERMS.search(scrub(title+" "+description)))
        if rel: relevant+=1
        if dt and now-timedelta(hours=48)<=dt<=now+timedelta(minutes=5):
            recent+=1
            if rel: recent_rel+=1
    return {
        "format":kind,"items_total":len(items),"item_https_links":valid_link,
        "item_https_non_google_links":non_google,
        "same_publisher_family_https_links":publisher_family,
        "direct_publisher_links_estimate":direct,
        "duplicate_urls_within_feed":duplicates,
        "relevant_title_summary_keyword_candidates":relevant,
        "items_with_date_within_48h":recent,
        "relevant_keyword_candidates_within_48h":recent_rel,
        "oldest_item_utc":min(dates).isoformat() if dates else None,
        "newest_item_utc":max(dates).isoformat() if dates else None,
        "dated_items":len(dates),
        "first_3_link_hashes":sample,
        "unique_url_hashes":list(sorted(seen))[:500],
        "unique_url_count":len(seen),
    }


def connect_and_fetch(url):
    p=urlsplit(url)
    host=p.hostname
    assert p.scheme=="https" and host and p.port is None and not p.username and not p.password
    iprows=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    if not iprows:
        raise ValueError("DNS_EMPTY")
    all_ip=[row[4][0] for row in iprows]
    if any(not is_public(ip) for ip in all_ip):
        raise ValueError("DNS_NON_PUBLIC_IP_BLOCKED")
    family,_,_,_,address=next((row for row in iprows if row[0]==socket.AF_INET),iprows[0])
    ip=address[0]
    ctx=ssl.create_default_context()
    class PinnedTLS(http.client.HTTPSConnection):
        def connect(self):
            sock=socket.socket(family,socket.SOCK_STREAM)
            try:
                sock.settimeout(TIMEOUT)
                sock.connect((ip,443))
                self.sock=self._context.wrap_socket(sock,server_hostname=host)
            except BaseException:
                sock.close()
                raise
    conn=PinnedTLS(host,port=443,timeout=TIMEOUT,context=ctx)
    try:
        path=p.path or "/"
        if p.query:
            path += "?"+p.query
        conn.request("GET",path,headers={
            "User-Agent":"RSS-Source-Coverage-Research/1.0 (one-shot owner-authorized; metadata only)",
            "Accept":"application/rss+xml, application/atom+xml, application/xml, text/xml; q=0.8",
            "Accept-Encoding":"identity", "Connection":"close"
        })
        response=conn.getresponse()
        status=response.status
        headers={k.lower():v for k,v in response.getheaders()}
        if 300<=status<400:
            return status,headers,None,"REDIRECT_BLOCKED"
        if status!=200:
            return status,headers,None,"HTTP_NOT_200"
        content_type=headers.get("content-type", "").split(";",1)[0].strip().lower()
        if content_type not in ("application/rss+xml","application/atom+xml","application/xml","text/xml","application/rdf+xml"):
            return status,headers,None,"UNEXPECTED_CONTENT_TYPE"
        declared=headers.get("content-length","")
        if declared.isdigit() and int(declared)>MAX_BYTES:
            return status,headers,None,"BODY_LIMIT_DECLARED"
        raw=bytearray()
        while True:
            chunk=response.read(min(65536,MAX_BYTES+1-len(raw)))
            if not chunk:break
            raw.extend(chunk)
            if len(raw)>MAX_BYTES:
                return status,headers,None,"WIRE_BODY_LIMIT"
        enc=headers.get("content-encoding","identity").strip().lower()
        if enc in ("", "identity"):
            data=bytes(raw)
        elif enc in ("gzip","deflate"):
            obj=zlib.decompressobj(16+zlib.MAX_WBITS if enc=="gzip" else zlib.MAX_WBITS)
            data=obj.decompress(bytes(raw),MAX_BYTES+1)
            if len(data)>MAX_BYTES or obj.unconsumed_tail:
                return status,headers,None,"DECOMPRESSED_BODY_LIMIT"
            data+=obj.flush(MAX_BYTES+1-len(data))
            if len(data)>MAX_BYTES or not obj.eof or obj.unused_data:
                return status,headers,None,"INVALID_OR_OVERSIZE_COMPRESSION"
        else:
            return status,headers,None,"UNSUPPORTED_ENCODING"
        return status,headers,data,None
    finally:
        conn.close()


def safe_header(headers,name):
    s=headers.get(name)
    if not s:return None
    return s[:128] if len(s)<=128 else s[:128]+"..."


def proof_out(proof):
    out=Path("/tmp/workae-one-shot")
    out.mkdir(parents=True, exist_ok=True)
    payload=json.dumps(proof,ensure_ascii=False,sort_keys=True,indent=2).encode("utf-8")+b"\n"
    (out/"rss_pilot_metadata.json").write_bytes(payload)
    manifest={"rss_pilot_metadata.json":hashlib.sha256(payload).hexdigest()}
    (out/"sha256_manifest.json").write_text(json.dumps(manifest,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    assert hashlib.sha256((out/"rss_pilot_metadata.json").read_bytes()).hexdigest()==manifest["rss_pilot_metadata.json"]
    print("ONE_SHOT_PROOF_MANIFEST_PASS",manifest["rss_pilot_metadata.json"],flush=True)


def alarm_handler(signum,frame):
    raise TimeoutError("TOTAL_15S_TIMEOUT")


def main():
    assert len(URLS)==MAX_GET and len(set(URLS))==MAX_GET
    launch=json.loads(LAUNCH_PATH.read_text(encoding="utf-8"))
    assert launch.get("owner_go_on_2026_11_15") is True
    assert launch.get("expected_parent_sha")==ORIGINAL_HEAD
    assert launch.get("six_urls")==list(URLS)
    assert launch.get("max_get")==6 and launch.get("timeout_seconds")==15
    assert launch.get("max_bytes")==MAX_BYTES
    assert launch.get("article_gets")==0 and launch.get("wip_writes") is False
    signal.signal(signal.SIGALRM,alarm_handler)
    proof={"schema":"workae-six-rss-owner-go-2026-11-15-01","github_sha":os.environ.get("GITHUB_SHA"),
           "timestamp_utc":utc_now().isoformat(),"approved_urls":len(URLS),"get_attempts":0,
           "real_rss_test":True,"article_gets":0,"wip_writes":False,"automatic_credits":0,
           "PROMOTE":"OFF","no_article_bodies_saved":True,"redirects_followed":0,
           "results":[],"stop_reason":None,"coverage_comparison_to_google":"NOT_MEASURED"}
    errors=0
    for idx,url in enumerate(URLS):
        if proof["get_attempts"]>=MAX_GET:break
        row={"source_index":idx+1,"rss_url":url,"requested_at_utc":utc_now().isoformat(),"status":None,"error":None}
        try:
            t0=time.monotonic()
            signal.setitimer(signal.ITIMER_REAL,TIMEOUT)
            # Count attempted GET before transport; no retry on any error.
            proof["get_attempts"]+=1
            status,headers,data,error=connect_and_fetch(url)
            row.update(http_status=status,content_type=safe_header(headers,"content-type"),
                       etag=safe_header(headers,"etag"),last_modified=safe_header(headers,"last-modified"),
                       content_encoding=safe_header(headers,"content-encoding"),elapsed_ms=int((time.monotonic()-t0)*1000))
            if error:
                row["error"]=error
                errors+=1
                if error!="HTTP_NOT_200":proof["stop_reason"]=error
            else:
                row["body_bytes"]=len(data)
                row["body_sha256"]=hashlib.sha256(data).hexdigest()
                row.update(parse_feed(data,urlsplit(url).hostname,utc_now()))
        except (Exception) as exc:
            # No raw content or stack traces persisted; fail closed.
            row["error"]=type(exc).__name__+":"+str(exc)[:90]
            proof["stop_reason"]=type(exc).__name__
            errors+=1
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)
            proof["results"].append(row)
            proof_out(proof)
            print("RSS_ONE_SHOT_RESULT",json.dumps({k:v for k,v in row.items() if k not in ("first_3_link_hashes","unique_url_hashes")},ensure_ascii=False,sort_keys=True),flush=True)
        if proof["stop_reason"] or errors>=3:
            if not proof["stop_reason"]:proof["stop_reason"]="THREE_SOURCE_ERRORS"
            break
    hashes={}
    for row in proof["results"]:
        for x in row.pop("unique_url_hashes",[]):
            hashes[x]=hashes.get(x,0)+1
    proof["cross_feed_duplicate_url_hashes"]=sum(n>1 for n in hashes.values())
    proof["total_unique_article_url_hashes"]=len(hashes)
    proof["result_count"]=len(proof["results"])
    proof_out(proof)
    print("RSS_ONE_SHOT_FINAL",json.dumps({k:v for k,v in proof.items() if k!="results"},ensure_ascii=False,sort_keys=True),flush=True)
    if proof["stop_reason"]:
        print("ONE_SHOT_STOPPED_SAFELY",proof["stop_reason"],flush=True)
        sys.exit(2)


def selftest():
    now=datetime(2026,11,15,12,tzinfo=timezone.utc)
    sample=b'<rss version="2.0"><channel><item><title>\xd0\x92 \xd1\x83\xd0\xb4\xd0\xb0\xd1\x80\xd1\x96 \xd0\xb7\xd0\xb0\xd0\xb3\xd0\xb8\xd0\xbd\xd1\x83\xd0\xbb\xd0\xb8 \xd1\x82\xd1\x80\xd0\xbe\xd1\x94</title><link>https://www.ukrinform.ua/news/123.html</link><pubDate>Sun, 15 Nov 2026 08:00:00 +0000</pubDate><description>\xd0\xa0\xd0\xbe\xd1\x81\xd1\x96\xd1\x8f \xd0\xb0\xd1\x82\xd0\xb0\xd0\xba\xd1\x83\xd0\xb2\xd0\xb0\xd0\xbb\xd0\xb0 \xd0\xbc\xd1\x96\xd1\x81\xd1\x82\xd0\xbe</description></item></channel></rss>'
    result=parse_feed(sample,"www.ukrinform.ua",now)
    assert result["items_total"]==1
    assert result["direct_publisher_links_estimate"]==1
    assert result["relevant_title_summary_keyword_candidates"]==1
    assert result["items_with_date_within_48h"]==1
    try:parse_feed(b'<!DOCTYPE rss [<!ENTITY x "bad">]><rss/>',"example.com",now)
    except ValueError:pass
    else:raise AssertionError("DTD was not blocked")
    print("RSS_ONE_SHOT_SELFTEST_PASS",flush=True)


if __name__=="__main__":
    if len(sys.argv)!=2 or sys.argv[1] not in ("--selftest","--run"):
        raise SystemExit("usage: workae_rss_once.py --selftest | --run")
    if sys.argv[1]=="--selftest":selftest()
    else:main()
