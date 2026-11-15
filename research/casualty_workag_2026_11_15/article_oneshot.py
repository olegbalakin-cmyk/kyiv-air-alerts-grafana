"""Work AH designated article executor: no publisher traffic without single-use owner GO.

Work AC is the sole HTTP transport; Work J/AA/X parse and produce review-only cards.
The only supported live entry is the exact owner-dispatched research Actions job.
The grant and SHA-256 are supplied by the owner at dispatch, never read from a
mutable branch file or an untrusted source. No automatic casualties or writes.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana/scripts"))
import casualty_go_guard as guard
import casualty_workac_capture as capture

OWNER = "olegbalakin-cmyk"
RESEARCH_BRANCH = "research-casualty-workah-guarded-article-2026-11-15"
URLS = (
    "https://www.ukrinform.ua/amp/rubric-regions/4177207-armia-rf-zavdala-udaru-po-zaporizzu-zaginuli-dvoe-ludej.html",
    "https://mig.com.ua/vorozhyy-udar-po-pryvatnomu-budynku-v-zaporizhzhi-zahynuly-troye-lyudey/",
    "https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv",
)

class PilotBlocked(RuntimeError):
    pass

def validate_environment(environ):
    if environ.get("CASUALTY_ARTICLE_NETWORK") != "OWNER_APPROVED_ONE_SHOT":
        raise PilotBlocked("ARTICLE_NETWORK_OFF")
    if environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise PilotBlocked("MANUAL_DISPATCH_ONLY")
    if environ.get("GITHUB_ACTOR") != OWNER or environ.get("GITHUB_TRIGGERING_ACTOR") != OWNER:
        raise PilotBlocked("OWNER_DISPATCH_REQUIRED")
    if environ.get("GITHUB_REF") != "refs/heads/" + RESEARCH_BRANCH:
        raise PilotBlocked("WRONG_RESEARCH_BRANCH")
    if environ.get("GITHUB_RUN_ATTEMPT") != "1":
        raise PilotBlocked("RERUN_BLOCKED")
    sha = environ.get("GITHUB_SHA", "")
    if not re.fullmatch("[a-f0-9]{40}", sha):
        raise PilotBlocked("INVALID_HEAD")
    if environ.get("CASUALTY_APPROVED_HEAD") != sha:
        raise PilotBlocked("OWNER_HEAD_MISMATCH")
    if environ.get("GITHUB_REPOSITORY") != OWNER + "/kyiv-air-alerts-grafana":
        raise PilotBlocked("WRONG_REPOSITORY")
    if not environ.get("GITHUB_TOKEN"):
        raise PilotBlocked("GITHUB_ATOMIC_LEDGER_REQUIRED")
    return sha

def validate_scope(grant, *, approved_digest, environ, now=None):
    head = validate_environment(environ)
    guard.validate_grant(grant, approved_digest=approved_digest, head=head, now=now)
    if (grant["owner_go_id"] != environ.get("CASUALTY_OWNER_GO_ID") or
        grant["rss_get_budget"] != 0 or grant["allowed_urls"]["rss"] != [] or
        grant["article_get_budget"] != 3 or
        tuple(grant["allowed_urls"]["article"]) != URLS):
        raise PilotBlocked("EXACT_THREE_URL_SCOPE_REQUIRED")
    for url in URLS:
        capture.allowed_article_url(url)
    if (capture.MAX_BYTES != 2*1024*1024 or capture.CONNECT_TIMEOUT != 8 or
        capture.TOTAL_TIMEOUT != 20):
        raise PilotBlocked("TRANSPORT_BUDGET_DRIFT")
    return head

def execute(grant, *, approved_digest, environ, output,
            now=None, claim=None, fetch=None):
    """Dependency injection is for offline mocks only, never through Actions."""
    if (claim is not None or fetch is not None) and environ.get("CASUALTY_ARTICLE_NETWORK") != "OFFLINE_MOCK":
        raise PilotBlocked("INJECTED_NETWORK_FORBIDDEN")
    if environ.get("CASUALTY_ARTICLE_NETWORK") == "OFFLINE_MOCK":
        # Test transport is entirely injected. Still enforce exact grant shape.
        head = environ["GITHUB_SHA"]
        guard.validate_grant(grant, approved_digest=approved_digest, head=head, now=now)
        if grant["rss_get_budget"] or tuple(grant["allowed_urls"]["article"]) != URLS or grant["article_get_budget"] != 3:
            raise PilotBlocked("MOCK_SCOPE_MISMATCH")
        if claim is None or fetch is None:
            raise PilotBlocked("MOCK_ONLY_REQUIRES_INJECTIONS")
    else:
        head = validate_scope(grant, approved_digest=approved_digest, environ=environ, now=now)
    # Atomic create-ref occurs before any publisher fetch; uncertain failures fail closed.
    lease = (claim or guard.claim_grant)(
        grant, approved_digest=approved_digest, head=head,
        repo=environ["GITHUB_REPOSITORY"], token=environ["GITHUB_TOKEN"], now=now)
    rows = []
    previous = []
    for url in URLS:
        metadata = {}
        def transport(approved_url):
            if approved_url != url:
                raise PilotBlocked("TRANSPORT_URL_MISMATCH")
            raw, content_type, status, encoding = (fetch or capture.get_html)(approved_url)
            metadata.update({"http_status": status, "content_type": content_type,
                             "content_encoding": encoding,
                             "response_sha256": hashlib.sha256(raw).hexdigest(),
                             "wire_bytes": len(raw)})
            # Keep publisher HTML transient; title is bounded and never used as proof.
            parsed = capture.ArticleText()
            parsed.feed(capture._decode_limited(raw, encoding).decode("utf-8", "replace"))
            metadata["article_title"] = parsed.title()
            metadata["body_length"] = len(parsed.body())
            metadata["body_available"] = len(parsed.body()) >= 180
            return raw, content_type, status, encoding
        item = {"url": url, "url_sha256": hashlib.sha256(url.encode()).hexdigest(),
                "http_status": None, "html_extraction": "NOT_ATTEMPTED",
                "numeric_extraction": "NOT_ATTEMPTED",
                "evidence_status": "INSUFFICIENT_EVIDENCE"}
        try:
            parsed = capture.analyze_direct_article(
                url, owner_go=lease, fetch=transport, previous=previous,
                city_key="zaporizhzhia", now=now)
            fact, card = parsed["source_fact"], parsed["card"]
            if card["automatic_credits"] != 0 or card["publication_allowed"] or card["incident_id"] is not None:
                raise PilotBlocked("UNSAFE_EVIDENCE_CARD")
            previous.append(card)
            item.update({"http_status": metadata["http_status"],
                         "html_extraction": "BODY_EXTRACTED",
                         "numeric_extraction": "CLAIM_FOUND" if fact["claim_deaths"] is not None or fact["count_kind"] == "delta" else "UNKNOWN",
                         "evidence_status": "REVIEW_ONLY",
                         "article_title": metadata["article_title"],
                         "publication_date": fact["publication_date"],
                         "publication_date_origin": fact["publication_date_origin"],
                         "attack_date_claimed_not_verified": fact["attack_date_explicit"],
                         "place_status": fact["geographic_status"],
                         "fatal_total_claimed_not_credited": card["fatal_total_claimed_not_credited"],
                         "count_kind": card["count_kind_claimed"],
                         "source_excerpts": card["source_excerpts"],
                         "dedup_status": card["decision"],
                         "dedup_reasons": card["reasons"],
                         "incident_id": None})
        except (capture.CaptureBlocked, guard.GoBlocked, PilotBlocked, OSError, ValueError) as exc:
            # No retries, redirects or alternate URLs. No exception payload in logs.
            reason = str(exc) if isinstance(exc, (capture.CaptureBlocked, guard.GoBlocked, PilotBlocked)) else type(exc).__name__
            if not re.fullmatch("[A-Za-z0-9_:-]{1,100}", reason):
                reason = type(exc).__name__
            item.update({"error": reason, "html_extraction": "BLOCKED",
                         "numeric_extraction": "NOT_AVAILABLE"})
        item.update(metadata)
        rows.append(item)
    output_path = Path(output)
    if output_path.exists():
        raise PilotBlocked("OUTPUT_ALREADY_EXISTS")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"head": head, "owner_go_id": grant["owner_go_id"],
               "manifest_sha256": approved_digest,
               "article_get_budget": 3, "rss_get_budget": 0,
               "publisher_get_attempts_max": 3, "promote": "OFF",
               "automatic_credits": 0, "publication_allowed": False,
               "cross_source_incident_identity": "INSUFFICIENT_EVIDENCE",
               "rows": rows}
    data = (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if b"<html" in data.lower() or b"<!doctype" in data.lower():
        raise PilotBlocked("UNSAFE_HTML_IN_ARTIFACT")
    output_path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()

def main(environ):
    validate_environment(environ)
    raw, digest = environ.get("CASUALTY_OWNER_GO_JSON"), environ.get("CASUALTY_OWNER_GO_DIGEST")
    if not raw or not digest:
        raise PilotBlocked("OWNER_APPROVED_GRANT_REQUIRED")
    try:
        grant = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise PilotBlocked("BAD_OWNER_GRANT_JSON") from exc
    digest_result = execute(grant, approved_digest=digest, environ=environ,
                            output="/tmp/casualty_workah_article_proof.json")
    print("WORKAH_REVIEW_ONLY_PROOF_SHA256", digest_result)

if __name__ == "__main__":
    try:
        main(os.environ)
    except (PilotBlocked, guard.GoBlocked, capture.CaptureBlocked):
        # Fail closed without dumping grants, token or HTTP body into Actions logs.
        print("WORKAH_GUARD_BLOCKED", file=sys.stderr)
        sys.exit(1)
