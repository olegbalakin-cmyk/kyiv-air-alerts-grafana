#!/usr/bin/env python3
"""Offline validator A: gzip integrity and event-driven HTMLParser identity extraction."""
import gzip
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path

TARGET = "https://www.bbc.com/ukrainian/articles/ck9dzex1zp3qo"
PROOF = Path("research/bbc_publisher_http_2026_10_12/proof")
RAW = Path(os.environ.get("RUNNER_TEMP", "/tmp")) / "bbc-single-publisher-private-20261012" / "response.entity.bin"
MAX_DECODED = 32_000_000


class ArticleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title_parts = []
        self.title_on = False
        self.article_depth = 0
        self.main_depth = 0
        self.paragraph_on = False
        self.paragraph_parts = []
        self.paragraph_count = 0
        self.paragraph_characters = 0
        self.canonical = None
        self.metadata = {}
        self.script_on = False
        self.jsonld_parts = []
        self.jsonld_documents = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "title":
            self.title_on = True
        if tag == "article":
            self.article_depth += 1
        if tag == "main":
            self.main_depth += 1
        if tag == "p":
            self.paragraph_on = True
            self.paragraph_parts = []
        if tag == "link" and "canonical" in (d.get("rel") or "").lower().split():
            self.canonical = d.get("href")
        if tag == "meta":
            key = d.get("property") or d.get("name") or d.get("itemprop")
            if key and key.lower() in (
                "og:url", "og:type", "article:published_time", "article:modified_time",
                "datepublished", "datemodified", "citation_publication_date"
            ):
                self.metadata[key.lower()] = d.get("content")
        if tag == "script" and "ld+json" in (d.get("type") or "").lower():
            self.script_on = True
            self.jsonld_parts = []

    def handle_endtag(self, tag):
        if tag == "title":
            self.title_on = False
        if tag == "p" and self.paragraph_on:
            p = " ".join("".join(self.paragraph_parts).split())
            if self.article_depth or self.main_depth:
                if len(p) >= 20:
                    self.paragraph_count += 1
                    self.paragraph_characters += len(p)
            self.paragraph_on = False
            self.paragraph_parts = []
        if tag == "article" and self.article_depth:
            self.article_depth -= 1
        if tag == "main" and self.main_depth:
            self.main_depth -= 1
        if tag == "script" and self.script_on:
            try:
                self.jsonld_documents.append(json.loads("".join(self.jsonld_parts)))
            except (ValueError, TypeError):
                pass
            self.script_on = False
            self.jsonld_parts = []

    def handle_data(self, data):
        if self.title_on:
            self.title_parts.append(data)
        if self.paragraph_on:
            self.paragraph_parts.append(data)
        if self.script_on:
            self.jsonld_parts.append(data)


def schema_fields(doc):
    rows = []
    def visit(node):
        if isinstance(node, list):
            for entry in node:
                visit(entry)
        elif isinstance(node, dict):
            typ = node.get("@type")
            if typ and any(t in str(typ).lower() for t in ("article", "news")):
                rows.append({
                    "type": typ if isinstance(typ, (str, list)) else None,
                    "date_published": node.get("datePublished"),
                    "date_modified": node.get("dateModified"),
                    "url": node.get("url") if isinstance(node.get("url"), str) else None,
                })
            if "@graph" in node:
                visit(node["@graph"])
    visit(doc)
    return rows[:10]


def main():
    observation = json.loads((PROOF / "observation.json").read_text(encoding="utf-8"))
    result = {"verifier": "A", "implementation": "Python gzip + html.parser event-driven parse",
              "offline_no_network": True, "transport_hash_consistent": None,
              "decoded_html_sha256": None, "article_identity_proven": False,
              "body_substantive": False, "error_class": None}
    try:
        raw = RAW.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        result["raw_entity_size_bytes"] = len(raw)
        result["raw_entity_sha256"] = digest
        result["transport_hash_consistent"] = (
            len(raw) == observation["raw_received_entity_size_bytes"]
            and digest == observation["raw_received_entity_sha256"])
        encoding = (observation["response_headers_selected"].get("content_encoding") or "identity").strip().lower()
        result["content_encoding"] = encoding
        if encoding == "gzip":
            decoded = gzip.decompress(raw)  # verifies gzip CRC32 and declared ISIZE
            result["gzip_crc_valid"] = True
        elif encoding in ("identity", ""):
            decoded = raw
            result["gzip_crc_valid"] = None
        else:
            raise ValueError("UnsupportedContentEncoding")
        if len(decoded) > MAX_DECODED:
            raise ValueError("DecodedSizeLimitExceeded")
        result["decoded_size_bytes"] = len(decoded)
        result["decoded_html_sha256"] = hashlib.sha256(decoded).hexdigest()
        mime = (observation["response_headers_selected"].get("content_type") or "").lower()
        result["html_content_type"] = "text/html" in mime or "application/xhtml+xml" in mime
        html = decoded.decode("utf-8", errors="replace")
        result["html_decode_replacements"] = html.count("\ufffd")
        parser = ArticleHTML()
        parser.feed(html)
        parser.close()
        title = " ".join("".join(parser.title_parts).split())
        schema = [item for document in parser.jsonld_documents for item in schema_fields(document)]
        result.update({
            "document_title": title[:260],
            "canonical_url": parser.canonical,
            "open_graph_url": parser.metadata.get("og:url"),
            "open_graph_type": parser.metadata.get("og:type"),
            "publication_meta": parser.metadata.get("article:published_time") or parser.metadata.get("datepublished"),
            "modification_meta": parser.metadata.get("article:modified_time") or parser.metadata.get("datemodified"),
            "structured_article_metadata": schema,
            "article_paragraph_count": parser.paragraph_count,
            "article_paragraph_characters": parser.paragraph_characters,
        })
        body = parser.paragraph_count >= 3 and parser.paragraph_characters >= 250
        urls = [parser.canonical, parser.metadata.get("og:url")]
        urls += [item.get("url") for item in schema]
        url_match = TARGET in urls
        blocked = any(s in title.lower() for s in ("access denied", "just a moment", "security check", "consent"))
        result["body_substantive"] = body
        result["identity_url_matches_exact_article"] = url_match
        result["article_identity_proven"] = bool(
            observation.get("http_status") == 200
            and observation.get("reading_finished_normally")
            and result["html_content_type"]
            and result["transport_hash_consistent"]
            and len(title) >= 10 and url_match and body and not blocked
        )
    except Exception as exc:
        result["error_class"] = type(exc).__name__
    (PROOF / "verify_A.json").write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"verifier": "A", "hash_consistent": result["transport_hash_consistent"],
                      "article_identity_proven": result["article_identity_proven"],
                      "error": result["error_class"]}, sort_keys=True))


if __name__ == "__main__":
    main()