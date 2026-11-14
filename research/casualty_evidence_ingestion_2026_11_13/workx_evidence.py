"""Work X: evidence index over existing Work J / Work R retained fact cards.

No HTML retrieval, article storage, incident inference, credit, or publication.
An index row is a review aid. Only the existing reviewer/operator may approve
an event, with an independently established attack identity and prior credits.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from urllib.parse import urlsplit, urlunsplit

SCHEMA = "casualty-workx-retained-evidence-v1"
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PRIVATE = re.compile(
    r"https?://|[<>№]|\b(?:вул\.?|вулиц\w*|провул\w*|проспект\w*|"
    r"адрес\w*|квартир\w*|паспорт\w*)\b|[\w.+-]+@[\w.-]+\.[a-z]{2,}",
    re.I,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _valid_sha(value) -> bool:
    return isinstance(value, str) and bool(HEX64.fullmatch(value))


def _source_url(raw) -> str | None:
    """For local evidence identity only; deliberately no redirects or HTTP."""
    try:
        p = urlsplit(str(raw or ""))
        if p.scheme != "https" or not p.hostname or p.username or p.password:
            return None
        if p.port not in (None, 443):
            return None
        path = p.path.rstrip("/") or "/"
        return urlunsplit(("https", p.hostname.casefold(), path, p.query, ""))
    except ValueError:
        return None


def source_type(url: str | None) -> str:
    p = urlsplit(url or "")
    h = (p.hostname or "").casefold()
    if h == "npu.gov.ua" or h.endswith(".npu.gov.ua"):
        return "POLICE"
    if h == "dsns.gov.ua" or h.endswith(".dsns.gov.ua"):
        return "EMERGENCY_SERVICE"
    if h.endswith(".gov.ua"):
        return "GOVERNMENT_OR_LOCAL_AUTHORITY"
    if h in {"news.google.com", "google.com"}:
        return "AGGREGATOR_NOT_PRIMARY"
    if h:
        return "EDITORIAL_OR_OTHER_UNVERIFIED"
    return "SOURCE_UNRESOLVED"


def _bounded_excerpts(card: dict, reasons: set[str]) -> list[dict]:
    """Never forward raw article text, partial sentences or unverified hashes."""
    output = []
    for x in (card.get("excerpts") or [])[:3]:
        if not isinstance(x, dict):
            reasons.add("MALFORMED_EVIDENCE_EXCERPT")
            continue
        t = x.get("text")
        if (not isinstance(t, str) or not 1 <= len(t) <= 170
                or PRIVATE.search(t) or _sha(t) != x.get("excerpt_sha256")):
            reasons.add("EVIDENCE_EXCERPT_UNSAFE_OR_HASH_MISMATCH")
            continue
        output.append({"text": t, "excerpt_sha256": x["excerpt_sha256"],
                       "claim_number": x.get("claim_number")
                       if type(x.get("claim_number")) is int else None})
    return output


def _bounded_context(card: dict, reasons: set[str]) -> list[dict]:
    """Work R mentions are UNVERIFIED clues; do not copy their text twice."""
    review = card.get("incident_review") or {}
    result = []
    for x in (review.get("evidence_mentions") or [])[:8]:
        if not isinstance(x, dict):
            continue
        if not _valid_sha(x.get("excerpt_sha256")):
            reasons.add("CONTEXT_HASH_MISSING")
            continue
        result.append({
            "sentence_order_not_event_time": x.get("article_sentence_order"),
            "unverified_tags": [str(t)[:50] for t in (x.get("tags") or [])[:5]],
            "excerpt_sha256": x["excerpt_sha256"],
        })
    return result


def build_review_index(facts: dict, queue: list[dict] | None = None,
                       previous: list[dict] | None = None) -> dict:
    """Enrich *retained* Work J/R cards. Never manufacture a link or total.

    Exact same URL+body SHA is a repeated publication, not a new fatality.
    Same URL with changed body is a possible update, not a proven new event.
    Different URLs, matching dates, numbers or victim ages NEVER establish
    incident identity or cross-source linkage in this function.
    """
    if facts.get("publication_allowed") is not False or facts.get("automatic_credits") != 0:
        raise ValueError("UNSAFE_UPSTREAM_EVIDENCE_CONTRACT")
    cards = facts.get("facts")
    if not isinstance(cards, list):
        raise ValueError("MISSING_RETAINED_FACT_CARDS")
    queue = queue or []
    by_id = {}
    for candidate in queue:
        if not isinstance(candidate, dict):
            continue
        cid = candidate.get("candidate_id")
        if cid in by_id:
            raise ValueError("DUPLICATE_CANDIDATE_ID")
        if cid:
            by_id[cid] = candidate

    prior = {}
    for row in previous or []:
        url = _source_url(row.get("original_source_url"))
        if url:
            prior.setdefault(url, row)
    rows = []
    included = set()

    for card in cards:
        if not isinstance(card, dict):
            raise ValueError("MALFORMED_RETAINED_CARD")
        if card.get("publication_allowed") is not False or card.get("decision") != "NEEDS_REVIEW":
            raise ValueError("UPSTREAM_FACT_NOT_FAIL_CLOSED")
        cid = card.get("candidate_id")
        candidate = by_id.get(cid, {})
        if cid:
            included.add(cid)
        reasons = set(str(r) for r in card.get("reasons") or [])
        source = _source_url(card.get("source_url"))
        if not source:
            reasons.add("PRIMARY_URL_NOT_VERIFIED")
        if source_type(source) == "AGGREGATOR_NOT_PRIMARY":
            reasons.add("ORIGINAL_SOURCE_NOT_RECOVERED")
        response_sha = card.get("document_sha256")
        if not _valid_sha(response_sha):
            response_sha = None
            reasons.add("RESPONSE_SHA256_NOT_RETAINED")
        body_sha = card.get("extracted_text_sha256")
        if not _valid_sha(body_sha):
            body_sha = None
            reasons.add("EXTRACTED_TEXT_SHA256_NOT_RETAINED")
        excerpts = _bounded_excerpts(card, reasons)
        if not excerpts:
            reasons.add("VERIFIABLE_SOURCE_EXCERPT_MISSING")
        review = card.get("incident_review") or {}
        context = _bounded_context(card, reasons)
        claimed_attack_date = card.get("attack_date_explicit")
        if not claimed_attack_date:
            reasons.add("ATTACK_DATE_NOT_ESTABLISHED")
        if not review.get("locality_verified"):
            reasons.add("EXACT_LOCALITY_NOT_ESTABLISHED")
        # Source date is not the attack date. No proxy from publication time.
        publication = card.get("publication_date") or candidate.get("published_at")
        count = card.get("claim_deaths")
        if type(count) is not int or not 0 < count <= 100000:
            count = None
            reasons.add("FATAL_TOTAL_NOT_PROVEN")
        kind = card.get("claim_type") or card.get("count_kind") or "unknown"
        if kind == "ADDITIONAL_DEATH_REPORTED":
            count = None
            reasons.add("LATE_DEATH_REQUIRES_INCIDENT_LINK_AND_BASELINE")
        if "MULTIPLE_POSSIBLE_INCIDENTS" in reasons:
            count = None
            reasons.add("CANNOT_ATTRIBUTE_TOTAL_TO_ONE_ATTACK")
        if "CONFLICTING_FATAL_TOTALS" in reasons:
            count = None
        reasons.add("CROSS_SOURCE_INCIDENT_IDENTITY_NOT_VERIFIED")
        reasons.add("PRIOR_DEATH_CREDIT_NOT_RECONCILED")

        prev = prior.get(source)
        linked = None
        decision = "NEEDS_REVIEW"
        if prev:
            linked = prev.get("candidate_id")  # Source reference, never event ID.
            if response_sha and response_sha == prev.get("response_sha256"):
                decision = "DUPLICATE_SOURCE_REPLAY"
                reasons.add("REPEATED_PUBLICATION_ZERO_NEW_CREDIT")
            else:
                reasons.add("SAME_URL_POSSIBLE_UPDATED_REPORT_NOT_EVENT_PROOF")
        row = {
            "candidate_id": cid,
            "source_role": card.get("source_role"),
            "original_source_url": source,
            "source_type": source_type(source),
            "feed_url": _source_url(candidate.get("url")),
            "publication_date_claimed": publication,
            "attack_date_claimed_not_verified": claimed_attack_date,
            "city_key_candidate_not_verified": candidate.get("city_key") or card.get("city_key_candidate_not_verified"),
            "attack_time_verified": review.get("attack_time_verified"),
            "locality_verified": review.get("locality_verified"),
            "struck_object_verified": review.get("struck_object_verified"),
            "unverified_context": context,
            "count_kind_claimed": kind,
            "fatal_total_claimed_not_credited": count,
            "prior_message_candidate_id_same_url_only": linked,
            "incident_id": None,
            "incident_identity_proof": None,
            "baseline_credited": None,
            "source_excerpts": excerpts,
            "response_sha256": response_sha,
            "extracted_text_sha256": body_sha,
            "decision": decision,
            "reasons": sorted(reasons),
            "automatic_credits": 0,
            "publication_allowed": False,
        }
        row["card_sha256"] = _sha(json.dumps(row, ensure_ascii=False, sort_keys=True))
        rows.append(row)
        if source:
            prior[source] = row

    # Retain an explicit blocked record even when the original page text was
    # never captured; news titles, RSS snippets and HTTP200 are not death facts.
    for cid, candidate in by_id.items():
        if cid in included:
            continue
        rows.append({
            "candidate_id": cid, "source_role": "publisher",
            "original_source_url": None, "source_type": "SOURCE_UNRESOLVED",
            "feed_url": _source_url(candidate.get("url")),
            "publication_date_claimed": candidate.get("published_at"),
            "attack_date_claimed_not_verified": None,
            "city_key_candidate_not_verified": candidate.get("city_key"),
            "fatal_total_claimed_not_credited": None, "count_kind_claimed": "unknown",
            "prior_message_candidate_id_same_url_only": None, "incident_id": None,
            "source_excerpts": [], "response_sha256": None,
            "extracted_text_sha256": None,
            "decision": "NEEDS_REVIEW",
            "reasons": ["SOURCE_TEXT_NOT_RETAINED", "ATTACK_IDENTITY_UNVERIFIED",
                        "NO_AUTOMATIC_CREDIT"], "automatic_credits": 0,
            "publication_allowed": False,
        })

    statuses = Counter(x["decision"] for x in rows)
    return {
        "schema": SCHEMA, "cards": rows,
        "summary": {
            "total": len(rows),
            "needs_review": statuses["NEEDS_REVIEW"],
            "duplicate_source_replay": statuses["DUPLICATE_SOURCE_REPLAY"],
            "source_evidence_cards_with_excerpts": sum(bool(x["source_excerpts"]) for x in rows),
            "automatically_linked_incidents": 0, "automatic_credits": 0,
            "external_http": 0, "publication_allowed": False,
        },
        "publication_allowed": False,
    }
