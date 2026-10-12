#!/usr/bin/env python3
"""Exactly one RSS GET and at most one publisher/article GET. Never used by production."""
import hashlib
import json
import shutil
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
import requests
from casualty_prospective_validate_offline import validate, item_fields, legacy_url, same_publisher, public_url


ROOT = Path("research/casualty_prospective_rss_publisher_2026-10-12")
ROOT.mkdir(parents=True, exist_ok=False)
for folder in ("raw", "metadata", "parsed", "derived"):
    (ROOT / folder).mkdir()
S = requests.Session()
S.headers.update({"User-Agent": "ukraine-air-alerts-casualty-monitor/1.0",
                  "Accept-Language": "uk,en;q=0.7", "Accept": "application/rss+xml,application/xml,text/xml,*/*;q=0.8"})
S.trust_env = False
query = ('"Харків" (загинув OR загиблі OR загинули OR помер OR померла) '
         '(дрон OR БПЛА OR шахед OR ракета OR КАБ OR авіаудар OR повітряна атака) when:8d')
url = ("https://news.google.com/rss/search?q=" +
       urllib.parse.quote_plus(query) + "&hl=uk&gl=UA&ceid=UA:uk")


def canonical(obj):
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True,
                       indent=2) + "\n").encode("utf-8")


def write(path, obj):
    (ROOT / path).write_bytes(canonical(obj))


def utc():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def capture(target, body_path, timeout=45):
    assert public_url(target), "Unsafe target URL"
    clock = {"timestamp_format": "UTC ISO-8601 microsecond text",
             "meaning": "client-side request-start and full-body-read completion observations",
             "accuracy": "not independently calibrated",
             "text_resolution": "microseconds; not asserted hardware accuracy",
             "monotonic_clock": "time.monotonic_ns elapsed duration; not absolute UTC"}
    start = utc()
    mono = time.monotonic_ns()
    data, response, error = None, None, None
    try:
        response = S.get(target, timeout=timeout, allow_redirects=True,
                         stream=True)
        response.raw.decode_content = False
        # Enforce one body read; preserve HTTP response entity as surfaced by requests.raw.
        data = response.raw.read(5_000_001)
        if len(data) > 5_000_000:
            data = None
            error = "BODY_SIZE_LIMIT_EXCEEDED; response discarded, no complete raw proof"
    except requests.RequestException as exc:
        error = type(exc).__name__ + ": " + str(exc)[:500]
    end = utc()
    elapsed = time.monotonic_ns() - mono
    headers = {}
    redirects = []
    final_url = None
    status = None
    if response is not None:
        status = response.status_code
        final_url = response.url
        headers = {k.lower(): v for k, v in response.headers.items()}
        prev = target
        for hop in response.history:
            redirects.append({"from_url": prev, "status": hop.status_code,
                              "location_header": hop.headers.get("Location"),
                              "to_url": urllib.parse.urljoin(hop.url,hop.headers.get("Location",""))})
            prev = urllib.parse.urljoin(hop.url,hop.headers.get("Location",""))
    if data is not None:
        (ROOT / body_path).write_bytes(data)
    return {"requested_url": target, "final_url": final_url,
            "request_start_utc": start, "response_complete_utc": end,
            "elapsed_monotonic_ns": elapsed, "clock_contract": clock,
            "status": status, "headers": headers, "redirects": redirects,
            "body_complete": data is not None, "body_path": body_path if data is not None else None,
            "body_bytes": len(data) if data is not None else None,
            "sha256": hashlib.sha256(data).hexdigest() if data is not None else None,
            "error": error}


rss = capture(url, "raw/rss_response_body.bin")
selected = {"present": False, "item_index_zero_based": None, "item": None, "selection_rule": "first RSS item with title and URL"}
linkage = {"state": "NO_RSS_ITEM", "attempt_url": None, "resolution_method": None,
           "publisher_http_observed": False, "confidence": "NOT_OBSERVABLE",
           "note": "No publisher HTTP version is established without a public original publisher response."}
attempt = None
if rss["status"] == 200 and rss["body_path"]:
    body = (ROOT / rss["body_path"]).read_bytes()
    try:
        import gzip
        if (rss["headers"].get("content-encoding") or "").lower() == "gzip":
            body = gzip.decompress(body)
        xml = ET.fromstring(body)
        items = xml.findall(".//item")
        for index, item in enumerate(items):
            fields = item_fields(item)
            if fields["title"] and fields["url"]:
                selected = {"present": True, "item_index_zero_based": index,
                            "item": fields, "selection_rule": "first RSS item with title and URL"}
                source_url = fields["url"]
                publisher_url = fields["publisher_url"]
                embedded = legacy_url(source_url, publisher_url)
                article_url = embedded if embedded else source_url
                method = "embedded_legacy_rss_url" if embedded else "rss_item_link_redirect_follow"
                if public_url(article_url):
                    attempt = capture(article_url, "raw/article_attempt_body.bin", timeout=30)
                    verified = bool(attempt["status"] == 200 and attempt["body_path"] and
                                    publisher_url and attempt["final_url"] and
                                    same_publisher(attempt["final_url"], publisher_url))
                    if verified:
                        (ROOT / "raw/article_attempt_body.bin").rename(ROOT / "raw/publisher_body.bin")
                        attempt["body_path"] = "raw/publisher_body.bin"
                    linkage.update({"state": "PUBLISHER_HTTP_OBSERVED" if verified else "ARTICLE_UNVERIFIED",
                                    "attempt_url": article_url, "resolution_method": method,
                                    "publisher_http_observed": verified,
                                    "confidence": "SAME_PUBLISHER_DOMAIN_HTTP_VERSION" if verified else "UNVERIFIED",
                                    "publisher_home": publisher_url,
                                    "final_url": attempt["final_url"],
                                    "note": "Domain match establishes HTTP publisher site, not originality, earliest availability or monitor discovery." if verified else "An attempted redirect did not establish an unambiguous original publisher URL or usable publisher body."})
                else:
                    linkage.update({"state": "NOT_ATTEMPTED",
                                    "note": "Item article link failed the public HTTPS address restriction."})
                break
    except (ET.ParseError, ValueError, OSError) as exc:
        linkage["state"] = "RSS_XML_PARSE_ERROR"
        linkage["note"] = type(exc).__name__ + ": " + str(exc)[:400]

obs = {
    "schema": 1, "source_contract": {
        "code_ref": "multicity-wip-2026-09-16:kyiv-air-alerts-grafana/scripts/monitor_casualty_candidates.py",
        "code_function": "google_news_query/search_city_news",
        "city_key": "kharkiv", "search_query": query,
        "exact_requested_url": url, "request_count_limit": "one RSS and at most one article attempt"
    }, "rss": rss, "article_attempt": attempt,
    "scope_limit": "Transport proof only: NOT earliest public timestamp, historical latency, completeness, or G1."
}
write("metadata/observations.json", obs)
write("parsed/selected_rss_item.json", selected)
write("derived/source_article_linkage.json", linkage)
shutil.copyfile(Path(__file__).with_name("casualty_prospective_validate_offline.py"), ROOT / "validate_offline.py")
(ROOT / "README.md").write_text(
    "# Isolated prospective RSS and publisher observation\n\n"
    "Single bounded live observation. Original response entity bytes are held in raw/, never "
    "inferred from XML, requests.text or a web search. HTTP framing and TLS packets are not captured. "
    "Redirect headers are metadata. Raw responses may be content-encoded and no transcoding is performed. "
    "Captured at client-side UTC wall clocks with microsecond formatting, not independently calibrated. "
    "Historical first availability and production ingestion are NOT OBSERVABLE.\n\n"
    "Verify: python validate_offline.py --root .\n", encoding="utf-8")
files = {}
for p in sorted(ROOT.rglob("*")):
    if p.is_file():
        key = p.relative_to(ROOT).as_posix()
        files[key] = {"bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
write("metadata/manifest.json", {"schema": 1, "hash_algorithm": "SHA-256", "files": files,
                                  "manifest_scope": "all proof members except self and verification report"})
report = {"pass_A": validate(ROOT), "pass_B": validate(ROOT)}
report["ab_equivalent"] = report["pass_A"] == report["pass_B"]
report["verdict"] = ("PROVEN" if report["ab_equivalent"] and
                     linkage["publisher_http_observed"] else "PARTIAL")
write("derived/AB_VERIFICATION_REPORT.json", report)
print(json.dumps({"rss_status": rss["status"], "rss_bytes": rss["body_bytes"],
                  "rss_sha256": rss["sha256"],
                  "item": selected["item"] if selected["present"] else None,
                  "publisher_http_observed": linkage["publisher_http_observed"],
                  "article_attempt_status": attempt["status"] if attempt else None,
                  "ab_equal": report["ab_equivalent"],
                  "verdict": report["verdict"]}, ensure_ascii=False))
