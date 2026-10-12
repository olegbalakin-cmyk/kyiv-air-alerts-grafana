#!/usr/bin/env python3
"""Offline validator B: independent streaming SHA, zlib gzip, regex markup audit."""
import hashlib
from html import unescape
import json
import os
from pathlib import Path
import re
import zlib

TARGET = "https://www.bbc.com/ukrainian/articles/ck9dzex1zp3qo"
PROOF = Path("research/bbc_publisher_http_2026_10_12/proof")
RAW = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "bbc-single-publisher-private-20261012" / "response.entity.bin"
MAX_DECODED = 32_000_000
ATTR = re.compile(r'''([\w:-]+)\s*=\s*(["'])(.*?)\2''', re.I | re.S)


def attributes(tag_text):
    return {key.lower(): unescape(value) for key, quote, value in ATTR.findall(tag_text)}


def text_only(markup):
    stripped = re.sub(r"<[^>]*>", " ", markup, flags=re.S)
    return " ".join(unescape(stripped).split())


def extract(html):
    title_match = re.search(r"<title(?:\s[^>]*)?>(.*?)</title\s*>", html, flags=re.I | re.S)
    title = text_only(title_match.group(1)) if title_match else ""
    canonical = None
    og = {}
    for link in re.findall(r"<link\b[^>]*>", html, flags=re.I | re.S):
        at = attributes(link)
        if "canonical" in at.get("rel", "").lower().split():
            canonical = at.get("href")
    for meta in re.findall(r"<meta\b[^>]*>", html, flags=re.I | re.S):
        at = attributes(meta)
        key = (at.get("property") or at.get("name") or "").lower()
        if key in ("og:url", "og:type", "article:published_time", "article:modified_time"):
            og[key] = at.get("content")
    structured = []
    for match in re.finditer(r"<script\b([^>]*)>(.*?)</script\s*>", html, flags=re.I | re.S):
        at = attributes(match.group(1))
        if "ld+json" not in at.get("type", "").lower():
            continue
        try:
            data = json.loads(match.group(2))
        except ValueError:
            continue
        stack = [data]
        while stack:
            x = stack.pop()
            if isinstance(x, list):
                stack.extend(x)
            elif isinstance(x, dict):
                type_text = str(x.get("@type", "")).lower()
                if "article" in type_text or "news" in type_text:
                    structured.append({
                        "type": x.get("@type") if isinstance(x.get("@type"), (str, list)) else None,
                        "date_published": x.get("datePublished"),
                        "date_modified": x.get("dateModified"),
                        "url": x.get("url") if isinstance(x.get("url"), str) else None,
                    })
                if "@graph" in x:
                    stack.append(x["@graph"])
    # Never publish paragraph text. Locate page article/main container, not generic footer or consent links.
    blocks = re.findall(r"<article\b[^>]*>(.*?)</article\s*>", html, flags=re.I | re.S)
    if not blocks:
        blocks = re.findall(r"<main\b[^>]*>(.*?)</main\s*>", html, flags=re.I | re.S)
    content_lengths = []
    for block in blocks:
        for paragraph in re.findall(r"<p\b[^>]*>(.*?)</p\s*>", block, flags=re.I | re.S):
            cleaned = text_only(paragraph)
            if len(cleaned) >= 20:
                content_lengths.append(len(cleaned))
    return {
        "document_title": title[:260],
        "canonical_url": canonical,
        "open_graph_url": og.get("og:url"),
        "open_graph_type": og.get("og:type"),
        "publication_meta": og.get("article:published_time"),
        "modification_meta": og.get("article:modified_time"),
        "structured_article_metadata": structured[:10],
        "article_paragraph_count": len(content_lengths),
        "article_paragraph_characters": sum(content_lengths),
    }


def main():
    observation = json.loads((PROOF / "observation.json").read_text(encoding="utf-8"))
    result = {"verifier": "B", "implementation": "Python streaming hash + zlib gzip + independent markup regex",
              "offline_no_network": True, "transport_hash_consistent": None,
              "decoded_html_sha256": None, "article_identity_proven": False,
              "body_substantive": False, "error_class": None}
    try:
        sha = hashlib.sha256()
        count = 0
        raw_chunks = []
        with RAW.open("rb") as f:
            while True:
                chunk = f.read(32768)
                if not chunk:
                    break
                count += len(chunk)
                sha.update(chunk)
                raw_chunks.append(chunk)
        digest = sha.hexdigest()
        raw = b"".join(raw_chunks)
        result["raw_entity_size_bytes"] = count
        result["raw_entity_sha256"] = digest
        result["transport_hash_consistent"] = (
            count == observation["raw_received_entity_size_bytes"]
            and digest == observation["raw_received_entity_sha256"])
        encoding = (observation["response_headers_selected"].get("content_encoding") or "identity").strip().lower()
        result["content_encoding"] = encoding
        if encoding == "gzip":
            # zlib's independent gzip framing/CRC check, not A's gzip.decompress API.
            inflater = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
            decoded = inflater.decompress(raw, MAX_DECODED + 1)
            if not inflater.eof or inflater.unused_data or inflater.unconsumed_tail:
                raise ValueError("IncompleteOrOverlongGzip")
            decoded += inflater.flush()
            result["gzip_crc_valid"] = True
        elif encoding in ("identity", ""):
            decoded = raw
            result["gzip_crc_valid"] = None
        else:
            raise ValueError("UnsupportedContentEncoding")
        if len(decoded) > MAX_DECODED:
            raise ValueError("DecodedSizeLimitExceeded")
        result["decoded_size_bytes"] = len(decoded)
        result["decoded_html_sha256"] = hashlib.sha256(memoryview(decoded)).hexdigest()
        result["html_content_type"] = (
            "text/html" in (observation["response_headers_selected"].get("content_type") or "").lower()
            or "application/xhtml+xml" in (observation["response_headers_selected"].get("content_type") or "").lower()
        )
        html = decoded.decode("utf-8", errors="replace")
        result["html_decode_replacements"] = html.count("\ufffd")
        data = extract(html)
        result.update(data)
        body = data["article_paragraph_count"] >= 3 and data["article_paragraph_characters"] >= 250
        url_match = TARGET in [data.get("canonical_url"), data.get("open_graph_url")] + [d.get("url") for d in data["structured_article_metadata"]]
        title = data["document_title"]
        blocked = any(x in title.lower() for x in ("access denied", "just a moment", "security check", "consent"))
        result["body_substantive"] = body
        result["identity_url_matches_exact_article"] = url_match
        result["article_identity_proven"] = bool(
            observation.get("http_status") == 200
            and observation.get("reading_finished_normally")
            and result["transport_hash_consistent"]
            and result["html_content_type"] and len(title) >= 10 and url_match and body and not blocked
        )
    except Exception as exc:
        result["error_class"] = type(exc).__name__
    (PROOF / "verify_B.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verifier": "B", "hash_consistent": result["transport_hash_consistent"],
                      "article_identity_proven": result["article_identity_proven"],
                      "error": result["error_class"]}, sort_keys=True))


if __name__ == "__main__":
    main()