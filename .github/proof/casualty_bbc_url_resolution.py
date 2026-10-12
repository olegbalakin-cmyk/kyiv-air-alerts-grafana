#!/usr/bin/env python3
"""One-item, non-production, frozen-Git Google News -> BBC URL proof.

The only source-side network operation this program can make is ONE POST to the
Google News Fbv4je batch endpoint, if the saved wrapper contains signed params.
No publisher requests, no RSS refresh, no retries, no cookie forwarding.
"""
import datetime as dt
import gzip
import hashlib
import html
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import re
import subprocess
import time
from urllib import error, parse, request
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path("research/google_news_bbc_url_resolution_2026-10-12")
SOURCE = "8334442092a24f5eace79c1d9212610d33e53655"
ACCEPTED = "4a7d6ec41289e532cda7047d2d433e654cac5de3"
REFERENCE_PROOF = "3319e986854ac5a242435039d0ffcf28b97f7435"
REFERENCE_CODE = "c26307efcea065813870dc27901dbd225f4f3e33"
REFERENCE_CODE_SHA256 = "94b7011ebc9a5b69fbf547f33e14598e7e9ec28db517514990334e57a5bcd65c"
PREFIX = "research/casualty_prospective_rss_publisher_2026-10-12"
ZIP_SHA = "786edbd21e51ddcde0f68cd5f2fed6debbeff7fa034532fa86c3022ef8d26389"
RSS_SHA = "0d615960a3af6e3d92ea1fb5dee7e8ed8049160e8924714d317e9e87ff3c21c5"
HTML_SHA = "9049878431e531ca05f12d16bcec21128aed73892fee3cbfeb314ceaba7992ac"
RPC = "https://news.google.com/_/DotsSplashUi/data/batchexecute?rpcids=Fbv4je"
BBC_ALLOWED = ("bbc.com", "bbc.co.uk")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_bytes(rel, data):
    f = ROOT / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(data)


def write_json(rel, obj):
    write_bytes(rel, (json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def git_blob(ref, file):
    return subprocess.run(
        ["git", "show", f"{ref}:{file}"], stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, check=True,
    ).stdout


class Nodes(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.signed = []
        self.article_href = []
        self.canonicals = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if "data-n-a-ts" in d or "data-n-a-sg" in d:
            self.signed.append({
                "tag": tag, "ts": d.get("data-n-a-ts"), "sg": d.get("data-n-a-sg"),
            })
        if tag == "link" and d.get("rel", "").casefold() == "canonical":
            self.canonicals.append(d.get("href", ""))
        if tag == "a" and d.get("href"):
            self.article_href.append(d["href"])


def normalize_url(value):
    try:
        p = parse.urlsplit(value.strip())
        return p if p.scheme.lower() in ("http", "https") and p.hostname else None
    except (ValueError, AttributeError):
        return None


def is_bbc(value):
    p = normalize_url(value)
    if not p:
        return False
    host = p.hostname.lower().rstrip(".")
    return any(host == b or host.endswith("." + b) for b in BBC_ALLOWED)


def validate_bbc_article(value):
    p = normalize_url(value)
    if not p or p.scheme.lower() != "https" or not is_bbc(value):
        return "non_https_or_non_bbc_publisher"
    if p.username or p.password or p.fragment:
        return "credentials_or_fragment"
    if p.port not in (None, 443):
        return "nonstandard_port"
    path = parse.unquote(p.path).strip("/")
    segments = [x for x in path.split("/") if x]
    if len(segments) < 2:
        return "homepage_or_section_not_article"
    if path.lower().startswith(("account/", "login/", "sport/live/", "weather/")):
        return "non_article_path"
    return None


def offline_links(wrapper):
    # Strings in JS can encode backslash-escaped forward slashes and unicode escapes.
    views = [
        html.unescape(wrapper),
        html.unescape(wrapper.replace("\\/", "/").replace("\\u003a", ":").replace("\\u002f", "/")),
    ]
    out = {}
    for name, view in zip(("direct_html", "html_with_js_escapes"), views):
        for match in re.finditer(r"https?://[^\s\"'<>\\\(\)\[\]{}]+", view):
            u = match.group(0).rstrip(".,;!&#")
            if not is_bbc(u):
                continue
            d = out.setdefault(u, {"url": u, "methods": [], "classification": None})
            if name not in d["methods"]:
                d["methods"].append(name)
    for u, v in out.items():
        v["classification"] = "BBC_ARTICLE_SHAPED_UNATTRIBUTED" if validate_bbc_article(u) is None else "BBC_HOME_OR_NON_ARTICLE"
    return sorted(out.values(), key=lambda x: x["url"])


def batch_request(article_id, timestamp, signature):
    # Byte-for-byte equivalent JSON structure to the inspected Oct-4 resolver.
    context = [
        ["en-US", "US", ["FINANCE_TOP_INDICES", "WEB_TEST_1_0_0"],
         None, None, 1, 1, "US:en", None, 180, None, None, None,
         None, None, 0, None, None, [1608992183, 723341000]],
        "en-US", "US", 1, [2, 3, 4, 8], 1, 0, "655000234", 0, 0, None, 0,
    ]
    arg = json.dumps(["garturlreq", context, article_id, timestamp, signature],
                     ensure_ascii=False, separators=(",", ":"))
    return parse.urlencode({
        "f.req": json.dumps([[["Fbv4je", arg, None, "generic"]]],
                            ensure_ascii=False, separators=(",", ":"))
    }).encode("utf-8")


def parse_rpc_response(raw):
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return [], "NON_UTF8_RESPONSE"
    if text.startswith(")]}'"):
        text = text.split("\n", 1)[1] if "\n" in text else ""
    urls, failures = [], []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("["):
            continue
        try:
            rows = json.loads(line)
        except json.JSONDecodeError:
            failures.append("NON_JSON_ARRAY_LINE")
            continue
        for row in (rows if isinstance(rows, list) else []):
            if not isinstance(row, list) or len(row) < 3 or row[1] != "Fbv4je":
                continue
            try:
                inner = json.loads(row[2])
                if isinstance(inner, list) and len(inner) >= 2 and inner[0] == "garturlres":
                    urls.append(inner[1])
            except (ValueError, TypeError):
                failures.append("MALFORMED_GARTURLRES")
    return urls, ";".join(failures) or None


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def make_metadata():
    z = git_blob(SOURCE, PREFIX + ".zip")
    assert len(z) == 155162 and sha(z) == ZIP_SHA, "FROZEN_ZIP_SHA_MISMATCH"
    old_manifest = json.loads(git_blob(SOURCE, PREFIX + "/metadata/manifest.json"))
    with zipfile.ZipFile(io.BytesIO(z)) as archive:
        assert archive.testzip() is None, "FROZEN_ZIP_CRC_FAIL"
        members = set(archive.namelist())
        assert len(members) == 11, "FROZEN_ZIP_MEMBER_COUNT_FAIL"
        for member in sorted(members):
            blob = archive.read(member)
            assert blob == git_blob(SOURCE, PREFIX + "/" + member), "FROZEN_MEMBER_GIT_MISMATCH:" + member
            if member in old_manifest["files"]:
                spec = old_manifest["files"][member]
                assert len(blob) == spec["bytes"] and sha(blob) == spec["sha256"], "FROZEN_MANIFEST_MISMATCH:" + member
    code = git_blob(REFERENCE_CODE, "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py")
    assert sha(code) == REFERENCE_CODE_SHA256, "REFERENCE_RESOLVER_CODE_SHA_MISMATCH"
    assert all(x.encode("utf-8") in code for x in (
        "def google_news_resolution_params", "def google_news_batch_payload",
        "def parse_google_news_batch_resolution", "def resolve_google_news_publisher_url",
        "def validated_publisher_url",
    )), "REFERENCE_RESOLVER_FUNCTIONS_MISSING"
    reference = json.loads(git_blob(REFERENCE_PROOF, "research/google_news_publisher_resolution_repair_proof_2026-10-04.json"))
    assert reference["actions_run"] == 37228651148 and reference["repair_commit"] == REFERENCE_CODE
    rss = git_blob(SOURCE, PREFIX + "/raw/rss_response_body.bin")
    wrapper = git_blob(SOURCE, PREFIX + "/raw/article_attempt_body.bin")
    assert len(rss) == 23013 and sha(rss) == RSS_SHA
    assert len(wrapper) == 120766 and sha(wrapper) == HTML_SHA
    old_observation = json.loads(git_blob(SOURCE, PREFIX + "/metadata/observations.json"))
    assert old_observation["rss"]["status"] == old_observation["article_attempt"]["status"] == 200
    assert old_observation["rss"]["headers"].get("content-encoding") == "gzip"
    assert old_observation["article_attempt"]["headers"].get("content-encoding") == "gzip"
    for group, blob in (("rss", rss), ("article_attempt", wrapper)):
        assert old_observation[group]["body_bytes"] == len(blob)
        assert old_observation[group]["sha256"] == sha(blob)
    assert gzip.decompress(rss) and gzip.decompress(wrapper), "GZIP_FAIL"
    write_bytes("raw/frozen_rss_gzip.bin", rss)
    write_bytes("raw/frozen_google_html_gzip.bin", wrapper)
    selected = json.loads(git_blob(SOURCE, PREFIX + "/parsed/selected_rss_item.json"))["item"]
    actual = ET.fromstring(gzip.decompress(rss)).find("./channel/item")
    assert actual is not None, "FIRST_RSS_ITEM_MISSING"
    first = {
        "guid": (actual.findtext("guid") or "").strip(),
        "title": (actual.findtext("title") or "").strip(),
        "url": (actual.findtext("link") or "").strip(),
        "pubDate": (actual.findtext("pubDate") or "").strip(),
        "publisher": (actual.findtext("source") or "").strip(),
        "publisher_url": actual.find("source").get("url") if actual.find("source") is not None else None,
    }
    assert first == selected, "ORIGINAL_RSS_IDENTITY_MISMATCH"
    assert selected["publisher"] == "BBC" and selected["publisher_url"] == "https://www.bbc.com"
    url = parse.urlsplit(first["url"])
    assert url.scheme == "https" and url.hostname == "news.google.com"
    article_id = url.path.rsplit("/", 1)[-1]
    assert first["guid"] == article_id and re.fullmatch(r"[A-Za-z0-9_-]+", article_id)
    html_text = gzip.decompress(wrapper).decode("utf-8")
    tags = Nodes()
    tags.feed(html_text)
    signed = sorted({(x["ts"], x["sg"]) for x in tags.signed if x["ts"] and x["sg"]})
    signature = None
    if len(signed) == 1 and signed[0][0].isdigit():
        signature = {"article_id": article_id, "timestamp": int(signed[0][0]), "signature": signed[0][1]}
    bbc = offline_links(html_text)
    return {
        "source": {
            "accepted_commit": ACCEPTED, "source_commit": SOURCE,
            "source_zip_sha256": ZIP_SHA, "reference_proof_commit": REFERENCE_PROOF,
            "reference_run": 37228651148, "verified_reference_resolver_commit": REFERENCE_CODE,
            "verified_resolver_sha256": REFERENCE_CODE_SHA256,
            "rss_sha256": RSS_SHA, "html_sha256": HTML_SHA,
            "original_rss_utc": {"start": old_observation["rss"]["request_start_utc"],
                                 "complete": old_observation["rss"]["response_complete_utc"]},
            "original_wrapper_utc": {"start": old_observation["article_attempt"]["request_start_utc"],
                                     "complete": old_observation["article_attempt"]["response_complete_utc"]},
            "original_rss_http_status": 200, "original_google_wrapper_http_status": 200,
        },
        "item": first,
        "google_final_url": old_observation["article_attempt"]["final_url"],
        "offline": {
            "rss_gzip_verified": True, "wrapper_gzip_verified": True,
            "source_zip_and_members_verified": True,
            "google_signed_tags_found": len(tags.signed),
            "unique_signed_pair_count": len(signed),
            "signed_params": signature,
            "html_canonical_urls": tags.canonicals[:12],
            "explicit_html_bbc_href": sorted(set(u for u in tags.article_href if is_bbc(u)))[:20],
            "html_bbc_url_candidates": bbc,
            "original_publisher_article_url_proven": False,
            "offline_reason": "Saved RSS identifies BBC homepage and Google wrapper; no BBC article identity with uniquely attributable mapping from the wrapper alone.",
        },
    }


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def one_rpc(payload, referer):
    write_bytes("raw/google_rpc_request_form.bin", payload)
    metadata = {
        "endpoint": RPC,
        "method": "POST", "request_body_sha256": sha(payload),
        "request_body_bytes": len(payload), "request_content_type": "application/x-www-form-urlencoded;charset=utf-8",
        "cookies_sent": False, "redirect_following": False, "retries": 0,
        "source_referer": referer,
        "response_metadata_allowlist": ["content-type", "content-encoding", "date", "cache-control"],
        "attempts": 1,
    }
    hdrs = {
        "User-Agent": "Mozilla/5.0 (compatible; isolated-bbc-url-research/1.0)",
        "Accept-Language": "uk,en;q=0.7",
        "Accept-Encoding": "identity",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        "Referer": referer,
    }
    assert request.getproxies() == {} or True  # no use of predecessor cookies
    assert "Cookie" not in hdrs and "Authorization" not in hdrs
    req = request.Request(RPC, data=payload, headers=hdrs, method="POST")
    op = request.build_opener(NoRedirect)
    t0 = time.monotonic_ns()
    metadata["request_start_utc"] = now()
    raw = b""
    response = None
    try:
        response = op.open(req, timeout=18)
        raw = response.read(2_000_000)
        if len(raw) >= 2_000_000:
            metadata["error"] = "RESPONSE_SIZE_LIMIT"
        metadata["http_status"] = response.status
    except error.HTTPError as e:
        response = e
        metadata["http_status"] = e.code
        raw = e.read(2_000_000)
        metadata["error"] = "HTTP_ERROR"
    except Exception as e:
        metadata["http_status"] = None
        metadata["error"] = type(e).__name__ + ": " + str(e)[:250]
    finally:
        metadata["response_complete_utc"] = now()
        metadata["elapsed_monotonic_ns"] = time.monotonic_ns() - t0
    if response is not None:
        metadata["response_headers"] = {
            k: response.headers.get(k)
            for k in ("Content-Type", "Content-Encoding", "Date", "Cache-Control")
            if response.headers.get(k) is not None
        }
        metadata["final_response_url"] = response.geturl()
    metadata["response_entity_sha256"] = sha(raw)
    metadata["response_entity_bytes"] = len(raw)
    write_bytes("raw/google_rpc_response_entity.bin", raw)
    if metadata.get("http_status") == 200 and metadata.get("response_headers", {}).get("Content-Encoding", "").lower() == "gzip":
        try:
            decoded = gzip.decompress(raw)
        except Exception:
            decoded = b""
            metadata["error"] = "INVALID_RPC_GZIP"
    else:
        decoded = raw
    candidates, parse_error = parse_rpc_response(decoded) if metadata.get("http_status") == 200 else ([], "NON_200")
    metadata["parsed_garturlres_candidates"] = candidates
    metadata["parse_error"] = parse_error
    return metadata


def main():
    assert not ROOT.exists(), "FROZEN_OUTPUT_ALREADY_EXISTS"
    meta = make_metadata()  # Entire predecessor and offline phase precedes ANY RPC.
    write_json("metadata/source_and_offline.json", meta)
    signed = meta["offline"]["signed_params"]
    rpc = {
        "attempts": 0, "attempted": False,
        "reason": "No single valid signed pair in unchanged Google wrapper"
    }
    if signed is not None:
        payload = batch_request(signed["article_id"], signed["timestamp"], signed["signature"])
        rpc = one_rpc(payload, meta["google_final_url"])
        rpc["attempted"] = True
    write_json("metadata/google_rpc_observation.json", rpc)
    proposals = []
    for c in meta["offline"]["html_bbc_url_candidates"]:
        proposals.append({
            "url": c["url"], "origin": c["methods"],
            "validation_reject_reason": validate_bbc_article(c["url"]),
            "attribution": "NOT_PROVEN_FROM_HTML_ALONE",
        })
    resolved = [u for u in rpc.get("parsed_garturlres_candidates", []) if isinstance(u, str)]
    distinct = sorted(set(resolved))
    valid = [x for x in distinct if validate_bbc_article(x) is None]
    for u in distinct:
        proposals.append({
            "url": u, "origin": ["SIGNED_Fbv4je_garturlres"],
            "validation_reject_reason": validate_bbc_article(u),
            "attribution": "exact_original_google_article_identity",
        })
    result_url = valid[0] if len(distinct) == 1 and len(valid) == 1 and rpc.get("http_status") == 200 else None
    if result_url:
        verdict = "PROVEN"
        reason = "One Google Fbv4je garturlres URL for the exact signed frozen BBC Google article identity; validated unique HTTPS BBC article-shaped path."
    else:
        ambiguous = any(validate_bbc_article(p["url"]) is None for p in proposals)
        verdict = "PARTIAL" if ambiguous else "BLOCKED"
        reason = (
            "Candidate article URL exists but original-publisher attribution or uniqueness is not proven."
            if ambiguous else "Frozen offline sources and the sole permitted Google-only resolution path did not provide a suitable BBC article URL."
        )
    adjudication = {
        "schema": "google_news_bbc_original_publisher_url_resolution_v1",
        "item_guid": meta["item"]["guid"],
        "requested_scope": "one_exact_frozen_BBC_RSS_identity",
        "selected_item_kharkiv_filter_eligible": False,
        "original_bbc_article_url": result_url,
        "publisher_article_body_requested": False,
        "publisher_http_requests": 0, "rss_refresh_requests": 0,
        "google_rpc_requests": rpc["attempts"],
        "candidate_urls": proposals,
        "raw_derived_separation": True,
        "verdict": "GOOGLE NEWS BBC ARTICLE URL RESOLUTION = " + verdict,
        "reason": reason,
        "acceptance_pending_independent_review": True,
    }
    write_json("derived/adjudication.json", adjudication)
    write_bytes("README.md", (
        "# Targeted single-item BBC original URL resolution\n\n"
        "SOURCE = frozen 2026-10-12 Google News RSS first BBC item, immutable commit " + SOURCE + ".\n\n"
        "Only archived RSS and Google HTML gzip raw entities were copied byte-for-byte. "
        "No original Set-Cookie or identifier-bearing response headers were copied. "
        "If signed params exist, the only permitted source-side request is one POST "
        "to Google's Fbv4je endpoint, with no cookies, redirects or retries. "
        "No BBC HTTP connection, article-body fetch, fresh RSS, production or DB actions.\n\n"
        "This is a new independent research proof, NOT accepted production integration.\n"
        "Use the independent offline verifier with two clean copies before freezing.\n"
    ).encode("utf-8"))
    manifest = {}
    for f in sorted(ROOT.rglob("*")):
        if f.is_file() and f.name != "manifest.json":
            b = f.read_bytes()
            manifest[f.relative_to(ROOT).as_posix()] = {"bytes": len(b), "sha256": sha(b)}
    write_json("metadata/manifest.json", {
        "schema": 1, "scope": "all files present at capture time except manifest itself and subsequent independent verification reports",
        "source_zip_sha256": ZIP_SHA, "members": manifest,
    })
    print(json.dumps({
        "verdict": adjudication["verdict"],
        "google_rpc_requests": rpc["attempts"],
        "http_status": rpc.get("http_status"),
        "offline_signed_pairs": meta["offline"]["unique_signed_pair_count"],
        "url": result_url, "reason": reason,
        "manifest_members": len(manifest),
    }, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
