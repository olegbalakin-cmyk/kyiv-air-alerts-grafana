#!/usr/bin/env python3
"""One-off, strictly allowlisted research HTTP capture; metadata only.

Owner authorization: 2026-11-12 chat. Exactly 11 frozen PR #96 candidates
plus 4 official police confirmations. No production writes, no article archiving.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import (
    HTTPRedirectHandler, Request, build_opener,
)

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "research/casualty_zaporizhzhia_source_recovery_2026_11_12/source_capture_request_queue.json"
OUTPUT = Path(__file__).with_name("capture_receipts.json")
QUEUE_BLOB_SHA1 = "a6cc94e92550dd826bbcf465df716644c712dbe6"
DIRECT = {
    "43a268ae2e19123554d6d476": "https://zprz.city/news/view/rosiyani-vdarili-dronami-po-zaporizhzhyu-zaginula-27richna-zhinka-poranilo-ditinu-ta-58richnu-zhitelku-foto",
    "7c3ac3280ba7ad4b9c10f3b1": "https://www.ukrinform.ua/amp/rubric-regions/4177207-armia-rf-zavdala-udaru-po-zaporizzu-zaginuli-dvoe-ludej.html",
    "dcdd2fe28fd1464e7fbabdc1": "https://mig.com.ua/vorozhyy-udar-po-pryvatnomu-budynku-v-zaporizhzhi-zahynuly-troye-lyudey/",
    "24654383bd30cc0f4e29c95f": "https://zprz.city/news/view/u-zaporizhzhi-raketa-vbila-tsilu-rodinu-troe-zagiblih-ta-poranena-vnaslidok-atak-rf-foto-video-1",
    "103256b72707ad66d91f6aae": "https://www.zabor.zp.ua/new/u-zaporizhzhi-pislya-udaru-po-bagatopoverkhivtsi-zaginuv-cholovik-kvartira-vigorila-vshchent",
    "cb222eea2a20aa1db2d67d5d": "https://www.zabor.zp.ua/new/u-zaporizhzhi-pislya-udaru-po-bagatopoverkhivtsi-zaginuv-cholovik-kvartira-vigorila-vshchent",
    "89a03da642500bf4def8ec9c": "https://shelter.in.ua/viyna/rosiyskyy-dron-vdaryv-po-budynku-v-zaporizzi-pid-zavalamy-mohly-zalyshatysia-dvoye-liudey",
    "05affefbcbb9f27a322ff5d3": "https://www.radiosvoboda.org/a/news-zaporizhzhia-dvoie-zahyblyh/33864729.html/",
    "db8ada77be0650fbf7c686cd": "https://interfax.com.ua/news/general/1210246.html",
    "7f57e0e0e4743e98c8a88186": "https://1news.zp.ua/vorog-zapustyv-shahed-po-shevchenkivskomu-rayonu-zaporizhzhya-zagynula-lyudyna-shhe-odna-poranena-foto-video/",
    "a3e25aad501f5f76e30ae65e": "https://spravzhne.media/ukr/war/1790493970-rankova-ataka-na-zaporizhzhya-zaginula-lyudina-e-poraneniy",
}
OFFICIAL = {
    "police_2026_10_18": "https://zp.npu.gov.ua/news/na-zaporizhzhi-unaslidok-vorozhykh-udariv-zahynula-zhinka-chetvero-liudei-otrymaly-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv-rosiiskoi-armii",
    "police_2026_10_22": "https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv",
    "police_2026_09_26": "https://zp.npu.gov.ua/news/pid-ranok-rosiiany-vdaryly-po-zaporizhzhiu-shakhedamy-zahynuly-dvi-zhinky-poraneni-cholovik-i-dytyna-politseiski-nadaly-dopomohu-postrazhdalym-ta-dokumentuiut-voiennyi-zlochyn",
    "police_2026_09_27": "https://zp.npu.gov.ua/news/na-zaporizhzhi-odna-liudyna-zahynula-chotyry-poraneno-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv-rf",
}
MAX_UNIQUE_TARGETS = 14
MAX_BODY = 2_000_000
ALLOWED_HOSTS = {urlsplit(url).hostname for url in set(DIRECT.values()) | set(OFFICIAL.values())}
ALLOWED_HOSTS |= {
    host[4:] if host.startswith("www.") else "www." + host
    for host in tuple(ALLOWED_HOSTS)
}

def permitted(url: str) -> bool:
    p = urlsplit(url)
    return (
        p.scheme == "https"
        and p.hostname in ALLOWED_HOSTS
        and p.username is None
        and p.password is None
        and p.port in (None, 443)
    )

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

OPENER = build_opener(NoRedirect)
HEADERS = {
    "User-Agent": "KyivCasualtyResearch/1.0 (+https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana)",
    "Accept-Language": "uk,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml;q=0.9",
}

def capture(url: str) -> dict:
    receipt = {
        "requested_url": url,
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "redirect_chain": [],
        "resolved_url": None,
        "http_status": None,
        "response_sha256": None,
        "response_bytes": None,
        "content_type": None,
        "page_title": None,
        "status": "BLOCKED",
    }
    current = url
    for hop in range(4):
        if not permitted(current):
            receipt["reason"] = "REDIRECT_OUTSIDE_EXACT_ALLOWLIST"
            return receipt
        req = Request(current, headers=HEADERS, method="GET")
        try:
            response = OPENER.open(req, timeout=16)
        except HTTPError as exc:
            response = exc
        except (OSError, URLError, ValueError) as exc:
            receipt["reason"] = "TRANSPORT_" + type(exc).__name__
            return receipt
        with response:
            status = response.status if getattr(response, "status", None) else response.code
            location = response.headers.get("Location")
            receipt["redirect_chain"].append({
                "request_url": current,
                "http_status": int(status),
                "location": location if status in (301, 302, 303, 307, 308) else None,
            })
            if status in (301, 302, 303, 307, 308):
                if not location or hop == 3:
                    receipt["reason"] = "REDIRECT_UNRESOLVED_OR_LIMIT"
                    return receipt
                current = urljoin(current, location)
                continue
            receipt["http_status"] = int(status)
            receipt["resolved_url"] = current
            receipt["content_type"] = response.headers.get("Content-Type")
            if status != 200:
                receipt["reason"] = "HTTP_" + str(status)
                return receipt
            raw = response.read(MAX_BODY + 1)
            if len(raw) > MAX_BODY:
                receipt["reason"] = "CONTENT_SIZE_LIMIT"
                return receipt
            receipt["response_bytes"] = len(raw)
            receipt["response_sha256"] = hashlib.sha256(raw).hexdigest()
            if "html" not in (receipt["content_type"] or "").lower():
                receipt["reason"] = "NON_HTML_CONTENT"
                return receipt
            sample = raw.decode("utf-8", errors="replace")
            mt = re.search(r"<title\b[^>]*>(.*?)</title\s*>", sample, re.I | re.S)
            if mt:
                receipt["page_title"] = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", mt.group(1)))).strip()[:220]
            receipt["status"] = "HTTP_200_HASHED"
            return receipt
    receipt["reason"] = "REDIRECT_LIMIT"
    return receipt

def main() -> None:
    b = QUEUE.read_bytes()
    actual_blob = hashlib.sha1(b"blob " + str(len(b)).encode() + b"\0" + b).hexdigest()
    if actual_blob != QUEUE_BLOB_SHA1:
        raise SystemExit("Frozen PR #96 queue Git blob changed; no HTTP permitted")
    data = json.loads(b.decode("utf-8"))
    ids = [x["candidate_id"] for x in data["source_requests"]]
    if len(ids) != 11 or len(set(ids)) != 11 or set(ids) != set(DIRECT):
        raise SystemExit("Unexpected candidate IDs; no HTTP permitted")
    targets = list(dict.fromkeys(DIRECT[x] for x in ids))
    targets += list(OFFICIAL.values())
    if len(targets) != MAX_UNIQUE_TARGETS or len(set(targets)) != MAX_UNIQUE_TARGETS:
        raise SystemExit("Unexpected HTTP target count; no HTTP permitted")
    all_receipts = {}
    for n, url in enumerate(targets):
        if n:
            time.sleep(1.0)
        r = capture(url)
        all_receipts[url] = r
        print(f"target={n+1}/{len(targets)} status={r['status']} code={r['http_status']} bytes={r['response_bytes']}")
    output = {
        "checkpoint": "CASUALTY-ZAP11-OWNER-APPROVED-HTTP-2026-11-12",
        "owner_approval": "2026-11-12 chat: exactly 11 frozen candidates and necessary official confirmations",
        "input_queue_git_blob_sha1": actual_blob,
        "target_count": len(targets),
        "candidate_count": len(ids),
        "requested_candidate_urls": {item: DIRECT[item] for item in ids},
        "source_receipts": list(all_receipts.values()),
        "candidate_receipt_index": {item: targets.index(DIRECT[item]) for item in ids},
        "official_receipt_index": {label: targets.index(url) for label, url in OFFICIAL.items()},
        "raw_article_text_stored": False,
        "no_production_publication": True,
        "note": "Receipt SHA-256 is for the exact HTTP response bytes fetched; 200/hashed is not factual confirmation.",
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(f"CAPTURE_DONE receipts={len(targets)} candidates={len(ids)} passed={sum(r['status']=='HTTP_200_HASHED' for r in all_receipts.values())}")

if __name__ == "__main__":
    main()
