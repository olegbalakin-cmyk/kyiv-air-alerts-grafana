#!/usr/bin/env python3
"""Independent, strictly offline verification of one prospective capture."""
import argparse
import base64
import gzip
import hashlib
import ipaddress
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, message):
    if not ok:
        raise AssertionError(message)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_feed(body, encoding):
    if encoding == "gzip":
        body = gzip.decompress(body)
    elif encoding not in ("", "identity"):
        raise ValueError("Unsupported feed content encoding: " + encoding)
    return ET.fromstring(body)


def item_fields(item):
    src = item.find("source")
    return {
        "title": item.findtext("title") or "",
        "url": (item.findtext("link") or "").strip(),
        "publisher": src.text or "" if src is not None else "",
        "publisher_url": src.attrib.get("url", "") if src is not None else "",
        "pubDate": item.findtext("pubDate") or "",
        "guid": item.findtext("guid") or "",
    }


def host(url):
    return (urlsplit(url).hostname or "").lower().removeprefix("www.")


def public_url(url):
    parsed = urlsplit(url)
    name = parsed.hostname or ""
    if parsed.scheme != "https" or not name or parsed.username or parsed.password:
        return False
    if name.lower() == "localhost" or name.lower().endswith((".local", ".internal")):
        return False
    try:
        return ipaddress.ip_address(name).is_global
    except ValueError:
        return True


def same_publisher(target, source):
    a, b = host(target), host(source)
    return bool(a and b and (a == b or a.endswith("." + b) or b.endswith("." + a)))


def legacy_url(article_link, publisher_home):
    # Only reads the opaque base64 bytes embedded in an RSS item; no HTTP is used.
    token = urlsplit(article_link).path.rstrip("/").split("/")[-1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{15,}", token):
        return None
    try:
        blob = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4))
    except Exception:
        return None
    candidates = re.findall(rb'https?://[^\x00-\x20\x7f-\xff<>"\']+', blob)
    decoded = []
    for match in candidates:
        try:
            url = match.decode("ascii")
            if public_url(url) and same_publisher(url, publisher_home):
                decoded.append(url)
        except (UnicodeError, ValueError):
            pass
    return decoded[0] if len(set(decoded)) == 1 else None


def parse_utc(value):
    require(isinstance(value, str) and value.endswith("Z"), "timestamp is not UTC Z")
    require(re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z", value) is not None,
            "UTC clock lacks the declared microsecond text resolution")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate(root):
    checks = {}
    manifest = read_json(root / "metadata/manifest.json")
    observations = read_json(root / "metadata/observations.json")
    selected = read_json(root / "parsed/selected_rss_item.json")
    linkage = read_json(root / "derived/source_article_linkage.json")
    require(manifest.get("schema") == 1, "manifest schema")
    for name, expected in manifest["files"].items():
        path = root / name
        require(not Path(name).is_absolute() and ".." not in Path(name).parts,
                "manifest unsafe path")
        require(path.is_file(), "missing " + name)
        payload = path.read_bytes()
        require(len(payload) == expected["bytes"], "length mismatch " + name)
        require(sha256(payload) == expected["sha256"], "SHA-256 mismatch " + name)
    checks["sha256_manifest_all_frozen_members"] = True

    for stage in ("rss", "article_attempt"):
        obs = observations.get(stage)
        if obs is None:
            continue
        for field in ("request_start_utc", "response_complete_utc"):
            parse_utc(obs[field])
        require(parse_utc(obs["response_complete_utc"]) >=
                parse_utc(obs["request_start_utc"]), "negative UTC interval " + stage)
        require(obs["clock_contract"]["timestamp_format"] == "UTC ISO-8601 microsecond text",
                "undeclared clock format")
        require(obs["clock_contract"]["meaning"] == "client-side request-start and full-body-read completion observations",
                "undeclared timestamp meaning")
        require(obs["clock_contract"]["accuracy"] == "not independently calibrated",
                "clock accuracy overclaim")
        require(obs["elapsed_monotonic_ns"] >= 0, "negative monotonic time")
        require(public_url(obs["requested_url"]), "unsafe requested URL")
        for hop in obs["redirects"]:
            require(public_url(hop["from_url"]) and public_url(hop["to_url"]),
                    "unsafe redirect")
        if obs["body_path"] is not None:
            body = (root / obs["body_path"]).read_bytes()
            require(obs["body_complete"] is True, "partial body represented as complete")
            require(len(body) == obs["body_bytes"], "observed body byte size mismatch")
            require(sha256(body) == obs["sha256"], "observed body hash mismatch")
        else:
            require(obs["body_bytes"] is None and obs["sha256"] is None,
                    "fabricated missing body")
    checks["transport_clocks_headers_and_raw_bytes"] = True

    rss = observations["rss"]
    require(rss["requested_url"] == observations["source_contract"]["exact_requested_url"],
            "requested URL differs from contract")
    if rss["body_path"] and rss["body_complete"] and rss["status"] == 200:
        root_xml = parse_feed((root / rss["body_path"]).read_bytes(),
                              (rss["headers"].get("content-encoding") or "").lower())
        items = root_xml.findall(".//item")
        if selected.get("present"):
            i = selected["item_index_zero_based"]
            require(type(i) is int and 0 <= i < len(items), "RSS index missing")
            require(item_fields(items[i]) == selected["item"], "selected RSS item not in feed")
            require(selected["item"]["url"] != "" and selected["item"]["title"] != "",
                    "selected RSS item has no identity")
        else:
            require(not any(item_fields(x)["url"] and item_fields(x)["title"]
                            for x in items), "RSS has selectable items but selected none")
        checks["selected_item_in_unchanged_rss"] = True
    else:
        require(not selected.get("present"), "selected item without usable RSS body")
        checks["selected_item_in_unchanged_rss"] = "NOT_OBSERVABLE"

    attempt = observations.get("article_attempt")
    if selected.get("present"):
        require(attempt is not None or linkage["state"] == "NOT_ATTEMPTED",
                "missing article attempt metadata")
        if attempt is not None:
            base = selected["item"]["url"]
            source_home = selected["item"]["publisher_url"]
            embedded = legacy_url(base, source_home)
            expected_url = embedded if embedded else base
            require(linkage["resolution_method"] ==
                    ("embedded_legacy_rss_url" if embedded else "rss_item_link_redirect_follow"),
                    "incorrect linkage derivation method")
            require(linkage["attempt_url"] == expected_url and
                    attempt["requested_url"] == expected_url,
                    "attempt URL not reproducible from RSS")
            observed = bool(attempt["body_path"] and attempt["body_complete"] and
                            attempt["status"] == 200 and source_home and
                            same_publisher(attempt["final_url"], source_home))
            require(linkage["publisher_http_observed"] == observed,
                    "publisher attribution inconsistent with observed response")
            if linkage["publisher_http_observed"]:
                require(attempt["body_path"] == "raw/publisher_body.bin",
                        "publisher payload must have separate raw path")
            else:
                require(attempt["body_path"] in ("raw/article_attempt_body.bin", None),
                        "unverified Google wrapper incorrectly called publisher")
            checks["source_to_article_relationship"] = (
                "REPRODUCIBLE_PUBLISHER_HTTP" if observed else "REPRODUCIBLE_ATTEMPT_ONLY")
        else:
            checks["source_to_article_relationship"] = "NOT_ATTEMPTED"
    else:
        require(attempt is None and not linkage["publisher_http_observed"],
                "publisher asserted without RSS item")
        checks["source_to_article_relationship"] = "NOT_OBSERVABLE"

    require(all(name.startswith(("raw/", "metadata/", "parsed/", "derived/"))
                or name in ("README.md", "validate_offline.py")
                for name in manifest["files"]), "nonseparated source paths")
    require((root / "metadata/observations.json").is_file() and
            (root / "parsed/selected_rss_item.json").is_file() and
            (root / "derived/source_article_linkage.json").is_file(),
            "source and derived data mixed")
    checks["original_payloads_separate_from_parsed_derived_data"] = True
    checks["offline_only_no_network_git_db"] = True

    result = {
        "result": "PASS",
        "checks": checks,
        "manifest_sha256": sha256((root / "metadata/manifest.json").read_bytes()),
        "rss_sha256": rss.get("sha256"),
        "article_attempt_sha256": attempt.get("sha256") if attempt else None,
        "checks_fingerprint_sha256": sha256(json.dumps(checks, sort_keys=True,
                                                      separators=(",", ":")).encode()),
    }
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True)
    args = p.parse_args()
    try:
        print(json.dumps(validate(args.root), sort_keys=True, ensure_ascii=False))
    except Exception as exc:
        print(json.dumps({"result": "FAIL", "error": type(exc).__name__ + ": " + str(exc)},
                         sort_keys=True, ensure_ascii=False))
        sys.exit(1)
