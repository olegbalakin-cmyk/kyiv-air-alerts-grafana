#!/usr/bin/env python3
"""Small WIP -> retained source -> existing casualty_auto_review evidence adapter.

OFFLINE_REPLAY is the default and never opens a socket. CONTROLLED_CAPTURE requires
a new, exact-target written authorization and an explicit runtime opt-in.
Neither mode can promote reviews, write casualties, or publish anything.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "research" / "casualty_e2e_shadow_2026_11_12"))
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana" / "scripts"))
import pipeline as work_a
from casualty_auto_review import canonical_url, extract_cached_reports, fingerprint, incident_id
from review_casualty_candidates import load_queue

MODE_DEFAULT = "OFFLINE_REPLAY"
REASON_MISSING = "BLOCKED_SOURCE_CONTENT"
CAPTURE_HOSTS = frozenset({
    "suspilne.media", "zprz.city", "ukrinform.ua", "mig.com.ua",
    "zabor.zp.ua", "shelter.in.ua", "radiosvoboda.org", "interfax.com.ua",
    "1news.zp.ua", "spravzhne.media", "zp.npu.gov.ua",
})
AGGREGATORS = frozenset({"news.google.com", "ukr.net", "www.ukr.net"})
OFFICIAL_HOSTS = frozenset({"zp.npu.gov.ua"})
SCHEMA = "casualty-evidence-ingestion-v1"
ALLOWED_OUTPUTS = ("work_a_reports.json", "fact_cards.json",
                   "source_decisions.json", "blocked_clusters.json",
                   "summary.json", "manifest.json")
USER_AGENT = "CasualtyEvidenceResearch/1.0 (source-only, owner-authorized)"

def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def stable_digest(value) -> str:
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":")).encode("utf-8"))

def host(url: str) -> str:
    try:
        parsed = urlsplit(str(url or ""))
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            return ""
        if parsed.username or parsed.password or parsed.port not in (None, 443):
            return ""
        return parsed.hostname.lower().removeprefix("www.")
    except ValueError:
        return ""

def source_class(url: str) -> str:
    rawhost = (urlsplit(str(url or "")).hostname or "").lower()
    if rawhost in AGGREGATORS:
        return "AGGREGATOR_NOT_ORIGINAL"
    if host(url) in OFFICIAL_HOSTS:
        return "OFFICIAL_PRIMARY"
    if host(url):
        return "PUBLISHER_OR_REPRINT"
    return "UNRESOLVED"

def _short_excerpts(text: str, totals: list[int]) -> list[dict]:
    """Tiny, de-identified audit snippets; not a replacement for source bodies."""
    pieces = re.split(r"(?<=[.!?])\s+|\n+", text)
    excerpts = []
    for n in totals[:3]:
        for sentence in pieces:
            if not re.search(r"(?<!\d)" + re.escape(str(n)) + r"(?!\d)", sentence):
                continue
            if not re.search(r"загиб|загин|помер|смерт|дснс", sentence, re.I):
                continue
            short = re.sub(r"\s+", " ", sentence).strip()
            short = re.sub(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", "[redacted]", short)
            short = re.sub(r"\+?\d[\d ()-]{9,}\d", "[redacted]", short)
            words = short.split()[:23]
            short = " ".join(words)[:170]
            if short and all(e["text"] != short for e in excerpts):
                excerpts.append({"text": short, "excerpt_sha256": digest(short.encode("utf-8")),
                                 "claim_number": n})
            break
    return excerpts[:3]

def _article_receipts(original: dict) -> dict:
    records = original.get("receipts", [])
    if not isinstance(records, list):
        raise RuntimeError("INVALID_RETAINED_RECEIPTS")
    result = {}
    for r in records:
        cid = r.get("candidate_id")
        if not cid or cid in result:
            raise RuntimeError("DUPLICATE_OR_MISSING_RETAINED_RECEIPT")
        result[cid] = r
    return result

def build(queue: list[dict], original: dict, receipts102: dict, matrix: dict,
          *, queue_sha: str, original_sha: str, receipts_sha: str) -> dict:
    """Use Work A's parsing semantics verbatim, without adding candidate title facts."""
    by_id = {str(c.get("candidate_id")): c for c in queue}
    if len(by_id) != len(queue):
        raise RuntimeError("DUPLICATE_WIP_CANDIDATE")
    articles, article_errors = work_a.anchored_articles(queue, original)
    reports = extract_cached_reports(queue, articles)
    article_by_id = {a["candidate_id"]: a for a in articles}
    retained_receipts = _article_receipts(original)
    receipts_index, groups = work_a.source_index(matrix, receipts102)
    cards = []
    reported_ids = set()
    for report in reports:
        ids = report["candidate_ids"]
        if len(ids) != 1 or ids[0] not in article_by_id or ids[0] in reported_ids:
            raise RuntimeError("REPORT_TO_ARTICLE_NOT_UNIQUE")
        cid = ids[0]
        article = article_by_id[cid]
        text = str(article["text"])
        text_sha = digest(text.encode("utf-8"))
        if text_sha != report.get("provenance", {}).get("article_sha256"):
            raise RuntimeError("REPORT_SOURCE_SHA_MISMATCH")
        if report.get("candidate_fingerprints", {}).get(cid) != fingerprint(by_id[cid]):
            raise RuntimeError("WIP_FINGERPRINT_MISMATCH")
        if report.get("count", {}).get("kind") != "total":
            raise RuntimeError("NON_TOTAL_COUNT_NOT_SAFE")
        update = report.get("provenance", {}).get("cumulative_update")
        totals = (update.get("reported_totals") if isinstance(update, dict) else None) or [
            report["count"]["value"]]
        if not all(type(x) is int and x > 0 for x in totals):
            raise RuntimeError("INVALID_REPORTED_TOTALS")
        reported_ids.add(cid)
        r = retained_receipts[cid]
        if r.get("http_status") != 200 or r.get("resolved_url") != article["url"]:
            raise RuntimeError("RETAINED_TRANSPORT_MISMATCH")
        official_id = report["sources"][0].get("origin_id", "unattributed")
        cards.append({
            "candidate_id": cid,
            "incident_id": incident_id(report["incident"]),
            "incident": report["incident"],
            "death_count_kind": "cumulative" if update else "total",
            "reported_totals": totals,
            "confirmed_total": report["count"]["value"],
            "source_url": article["url"],
            "feed_or_aggregator_url": by_id[cid].get("url"),
            "source_class": source_class(article["url"]),
            "attributed_official_origin_id": official_id,
            "official_body_independently_retained": False,
            "original_text_sha256": text_sha,
            "receipt_candidate_fingerprint": r["candidate_fingerprint"],
            "fetched_at_or_observed_at": article.get("observed_at"),
            "retained_receipt_status": r.get("http_status"),
            "attack_date_basis": report["provenance"].get("date_basis"),
            "official_update_sentence_sha256": (update or {}).get("official_sentence_sha256"),
            "small_excerpts": _short_excerpts(text, totals),
            "work_a_report_sha256": stable_digest(report),
            "candidate_title_used_as_fact": False,
            "publication_allowed": False,
        })
    if any(source_class(c["source_url"]) == "AGGREGATOR_NOT_ORIGINAL" for c in cards):
        raise RuntimeError("AGGREGATOR_AS_FACT_SOURCE")
    candidate_decisions = []
    for item in queue:
        cid = item["candidate_id"]
        if cid in reported_ids:
            reason = "FACTS_EXTRACTED_FOR_EXISTING_REVIEWER"
            status = "EXTRACTED_NOT_PUBLISHED"
        elif cid in article_by_id:
            reason = "RETAINED_TEXT_NOT_SUFFICIENT_TO_ESTABLISH_ATTACK_AND_TOTAL"
            status = "NEEDS_REVIEW"
        else:
            reason = article_errors.get(cid, REASON_MISSING)
            status = "NEEDS_REVIEW"
        receipt = receipts_index.get(cid)
        candidate_decisions.append({
            "candidate_id": cid, "status": status, "reason": reason,
            "original_url": (receipt or {}).get("original_url"),
            "source_text_present": cid in article_by_id,
            "http_200_is_not_confirmation": bool(receipt),
            "publication_allowed": False,
        })
    blocked = []
    for group in groups:
        ids = group["candidate_ids"]
        if any(cid in reported_ids for cid in ids):
            raise RuntimeError("PR102_CLUSTER_HAS_UNEXPECTED_FACT_REPORT")
        canonical = {canonical_url(receipts_index[cid]["original_url"]) for cid in ids}
        reasons = [REASON_MISSING, "TRANSPORT_ONLY_NOT_FACT_EVIDENCE",
                   "NO_RETAINED_OFFICIAL_CONFIRMATION_BODY"]
        if group["cluster_id"].startswith("sep_"):
            reasons.append("BASELINE_EVENT_ALLOCATION_UNKNOWN")
        if group["cluster_id"] == "oct_26_apartment":
            reasons.append("LATE_DEATH_NEEDS_INDEPENDENT_OFFICIAL_CONFIRMATION")
        if len(canonical) < len(ids):
            reasons.append("SAME_ORIGINAL_URL_NOT_INDEPENDENT_SOURCE")
        blocked.append({
            "cluster_id": group["cluster_id"],
            "candidate_ids": ids,
            "status": "NEEDS_REVIEW",
            "reasons": reasons,
            "original_url_count": len(canonical),
            "retained_original_body_count": 0,
            "independently_retained_official_body_count": 0,
            "attack_date": None, "confirmed_deaths": None, "proposed_delta": None,
            "publication_allowed": False,
        })
    handoff = {
        "schema": SCHEMA,
        "queue_sha256": queue_sha,
        "source_evidence_sha256": original_sha,
        "pr102_receipts_sha256": receipts_sha,
        "reports": reports,
        "publication_allowed": False,
    }
    summary = {
        "schema": SCHEMA, "mode": MODE_DEFAULT,
        "candidate_count": len(queue),
        "parsed_fact_reports": len(reports),
        "source_text_available_candidates": len(article_by_id),
        "source_text_missing_or_unusable_candidates": len(queue) - len(reported_ids),
        "blocked_pr102_clusters": len(blocked),
        "blocked_pr102_candidate_ids": sum(len(g["candidate_ids"]) for g in blocked),
        "HTTP_200_is_never_death_confirmation": True,
        "independent_official_bodies_captured_by_this_run": 0,
        "external_publisher_http_requests": 0,
        "wip_edited": False, "casualty_json_edited": False,
        "publication_allowed": False,
        "regular_workflow_enabled": False,
        "decision": "EVIDENCE_INGESTION_OFFLINE_PARTIAL_PENDING_WORK_A_PROOF",
    }
    return {
        "work_a_reports.json": handoff,
        "fact_cards.json": cards,
        "source_decisions.json": candidate_decisions,
        "blocked_clusters.json": blocked,
        "summary.json": summary,
    }

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class _TextExtractor(HTMLParser):
    """No scripts, CSS, nav, footer, aside. Prefer article/main when present."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.article, self.main = [], [], []
        self.skip_depth = 0
        self.in_article, self.in_main = 0, 0
        self.title_depth, self.title_parts = 0, []
    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "footer", "aside", "form"}:
            self.skip_depth += 1
        if tag == "article":
            self.in_article += 1
        if tag == "main":
            self.in_main += 1
        if tag == "title":
            self.title_depth += 1
    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer", "aside", "form"}:
            self.skip_depth = max(0, self.skip_depth - 1)
        if tag == "article":
            self.in_article = max(0, self.in_article - 1)
        if tag == "main":
            self.in_main = max(0, self.in_main - 1)
        if tag == "title":
            self.title_depth = max(0, self.title_depth - 1)
    def handle_data(self, data):
        s = " ".join(data.split())
        if not s:
            return
        if self.title_depth:
            self.title_parts.append(s)
        if self.skip_depth:
            return
        self.parts.append(s)
        if self.in_article:
            self.article.append(s)
        if self.in_main:
            self.main.append(s)
    def body(self):
        return " ".join(self.article or self.main or self.parts)

def validate_capture_approval(approval: dict, enabled: bool, queue: list[dict],
                              now: datetime | None = None) -> dict:
    if not enabled:
        raise RuntimeError("CONTROLLED_CAPTURE_DEFAULT_OFF")
    if not isinstance(approval, dict) or not approval.get("authorization_id"):
        raise RuntimeError("WRITTEN_OWNER_AUTHORIZATION_REQUIRED")
    now = now or datetime.now(timezone.utc)
    try:
        start = datetime.fromisoformat(approval["approved_at_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(approval["expires_at_utc"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise RuntimeError("INVALID_AUTHORIZATION_WINDOW") from exc
    if start.tzinfo is None or end.tzinfo is None or not start <= now <= end or end - start > timedelta(hours=48):
        raise RuntimeError("EXPIRED_OR_EXCESSIVE_AUTHORIZATION_WINDOW")
    targets = approval.get("targets")
    if not isinstance(targets, list) or not 1 <= len(targets) <= 14:
        raise RuntimeError("INVALID_APPROVED_TARGET_COUNT")
    if not 1 <= approval.get("max_requests_total", 0) <= 30:
        raise RuntimeError("INVALID_REQUEST_BUDGET")
    if approval["max_requests_total"] < len(targets):
        raise RuntimeError("INSUFFICIENT_REQUEST_BUDGET")
    if not 1 <= approval.get("max_response_bytes", 0) <= 1_000_000:
        raise RuntimeError("INVALID_BODY_LIMIT")
    if approval.get("min_delay_seconds", 0) < 1.0:
        raise RuntimeError("CAPTURE_RATE_LIMIT_TOO_HIGH")
    allowed_hosts = approval.get("allowed_hosts")
    if not isinstance(allowed_hosts, list) or not allowed_hosts or not set(allowed_hosts).issubset(CAPTURE_HOSTS):
        raise RuntimeError("UNAPPROVED_HOST")
    valid_ids = {c["candidate_id"] for c in queue}
    seen_urls = set()
    for target in targets:
        url = target.get("url", "")
        if not isinstance(url, str) or host(url) not in allowed_hosts or not urlsplit(url).path:
            raise RuntimeError("TARGET_NOT_EXACT_ALLOWLISTED")
        if url in seen_urls:
            raise RuntimeError("DUPLICATE_HTTP_TARGET")
        seen_urls.add(url)
        role = target.get("role")
        ids = target.get("candidate_ids", [])
        if role not in ("publisher", "official") or not isinstance(ids, list):
            raise RuntimeError("INVALID_TARGET_ROLE")
        if role == "publisher" and (not ids or any(cid not in valid_ids for cid in ids)):
            raise RuntimeError("UNPINNED_WIP_CANDIDATE")
        if role == "official" and ids:
            raise RuntimeError("OFFICIAL_NEEDS_SEPARATE_LINKING_NOT_CANDIDATE_BINDING")
    return approval

def _capture_once(url: str, approval: dict, budget: dict, opener=None) -> tuple[dict, str]:
    """Allowed only after validate_capture_approval; no JS, login, proxy or bypass."""
    opener = opener or build_opener(_NoRedirect, ProxyHandler({}))
    receipt = {
        "requested_url": url, "capture_time_utc": datetime.now(timezone.utc).isoformat(),
        "redirect_chain": [], "http_status": None, "resolved_url": None,
        "response_sha256": None, "response_bytes": None, "page_title": None,
        "status": "NEEDS_REVIEW", "reason": "TRANSPORT_UNAVAILABLE",
    }
    current = url
    for redirect in range(4):
        if host(current) not in approval["allowed_hosts"]:
            receipt["reason"] = "REDIRECT_NOT_ALLOWLISTED"
            return receipt, ""
        if budget["used"] >= approval["max_requests_total"]:
            receipt["reason"] = "REQUEST_BUDGET_EXCEEDED"
            return receipt, ""
        if budget["used"]:
            time.sleep(approval["min_delay_seconds"])
        budget["used"] += 1
        try:
            response = opener.open(Request(current, headers={"User-Agent": USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml", "Accept-Language": "uk,en;q=0.8"},
                    method="GET"), timeout=15)
        except HTTPError as exc:
            response = exc
        except (OSError, URLError, ValueError) as exc:
            receipt["reason"] = "TRANSPORT_" + type(exc).__name__
            return receipt, ""
        with response:
            status = int(response.status or response.code)
            location = response.headers.get("Location")
            receipt["redirect_chain"].append({"request_url": current,
                       "http_status": status, "location": location if status in (301, 302, 303, 307, 308) else None})
            if status in (301, 302, 303, 307, 308):
                if not location or redirect == 3:
                    receipt["reason"] = "REDIRECT_LIMIT"
                    return receipt, ""
                current = urljoin(current, location)
                continue
            receipt["http_status"] = status
            receipt["resolved_url"] = current
            receipt["content_type"] = response.headers.get("Content-Type", "")
            if status != 200:
                receipt["reason"] = "HTTP_" + str(status)
                return receipt, ""
            if "html" not in receipt["content_type"].lower():
                receipt["reason"] = "NON_HTML"
                return receipt, ""
            raw = response.read(approval["max_response_bytes"] + 1)
            if len(raw) > approval["max_response_bytes"]:
                receipt["reason"] = "BODY_LIMIT_EXCEEDED"
                return receipt, ""
            receipt["response_bytes"] = len(raw)
            receipt["response_sha256"] = digest(raw)
            parser = _TextExtractor()
            parser.feed(raw.decode("utf-8", "replace"))
            text = parser.body()
            receipt["page_title"] = " ".join(parser.title_parts)[:180]
            if len(text) < 180 or re.search(r"captcha|access denied|enable javascript|sign in to read",
                                            text, flags=re.I):
                receipt["reason"] = "CONTENT_INACCESSIBLE_OR_NOT_ARTICLE"
                return receipt, ""
            receipt["status"] = "BODY_EXTRACTED_NOT_VERIFIED"
            receipt["reason"] = "PENDING_REVIEWER_FACT_VALIDATION"
            return receipt, text
    return receipt, ""

def controlled_capture(approval: dict, queue: list[dict], *, enabled: bool) -> tuple[dict, dict]:
    policy = validate_capture_approval(approval, enabled, queue)
    by_id = {c["candidate_id"]: c for c in queue}
    ephemeral = {"articles": [], "receipts": [], "official_articles": []}
    audit = {"authorization_id": policy["authorization_id"],
             "requests_used": 0, "targets": [], "publication_allowed": False}
    budget = {"used": 0}
    for target in policy["targets"]:
        receipt, text = _capture_once(target["url"], policy, budget)
        audit["targets"].append(receipt)
        if not text:
            continue
        if target["role"] == "official":
            ephemeral["official_articles"].append({
                "url": receipt["resolved_url"], "text": text,
                "observed_at": receipt["capture_time_utc"],
                "response_sha256": receipt["response_sha256"]})
            continue
        for cid in target["candidate_ids"]:
            ephemeral["articles"].append({
                "candidate_id": cid, "url": receipt["resolved_url"],
                "text": text, "observed_at": receipt["capture_time_utc"]})
            ephemeral["receipts"].append({
                "candidate_id": cid, "candidate_fingerprint": fingerprint(by_id[cid]),
                "resolved_url": receipt["resolved_url"], "http_status": receipt["http_status"],
                "response_sha256": receipt["response_sha256"],
                "redirect_chain": receipt["redirect_chain"],
                "capture_time_utc": receipt["capture_time_utc"]})
    audit["requests_used"] = budget["used"]
    return ephemeral, audit

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mode", choices=("OFFLINE_REPLAY", "CONTROLLED_CAPTURE"),
                   default=MODE_DEFAULT)
    p.add_argument("--queue", type=Path, required=True)
    p.add_argument("--evidence", type=Path, help="existing retained approved source JSON")
    p.add_argument("--receipts", type=Path, required=True)
    p.add_argument("--matrix", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--approval", type=Path, help="new separate exact-target written consent")
    p.add_argument("--enable-controlled-capture", action="store_true")
    args = p.parse_args()
    inputs = [args.queue, args.receipts, args.matrix]
    if args.evidence:
        inputs.append(args.evidence)
    if args.approval:
        inputs.append(args.approval)
    work_a.ensure_output_isolated(args.output.resolve(), [i.resolve() for i in inputs])
    queue_bytes = args.queue.read_bytes()
    queue = load_queue(args.queue)
    receipts102, rsha = work_a.read_pinned(args.receipts, work_a.RECEIPTS_102_SHA256)
    matrix, _ = work_a.read_pinned(args.matrix)
    if args.mode == MODE_DEFAULT:
        if args.enable_controlled_capture or args.approval:
            raise RuntimeError("UNEXPECTED_CAPTURE_OPT_IN_DURING_OFFLINE_REPLAY")
        if not args.evidence:
            raise RuntimeError("MISSING_APPROVED_RETAINED_EVIDENCE")
        original, osha = work_a.read_pinned(args.evidence, work_a.RETAINED_EVIDENCE_SHA256)
        capture_audit = None
    else:
        if not args.approval:
            raise RuntimeError("CONTROLLED_CAPTURE_DEFAULT_OFF")
        approval = json.loads(args.approval.read_text(encoding="utf-8"))
        original, capture_audit = controlled_capture(approval, queue, enabled=args.enable_controlled_capture)
        osha = stable_digest(original)
    result = build(queue, original, receipts102, matrix, queue_sha=digest(queue_bytes),
                   original_sha=osha, receipts_sha=rsha)
    if capture_audit:
        # Audit metadata only. No raw publisher/official article bodies written.
        result["summary.json"]["mode"] = "CONTROLLED_CAPTURE"
        result["summary.json"]["external_publisher_http_requests"] = capture_audit["requests_used"]
        result["summary.json"]["decision"] = "CAPTURED_UNVALIDATED_RESEARCH_ONLY"
        result["capture_receipts.json"] = capture_audit
    out = args.output
    for name, value in result.items():
        (out / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                          indent=2) + "\n", encoding="utf-8")
    manifest = {"input_sha256": {str(x.name): digest(x.read_bytes()) for x in inputs},
                "output_sha256": {name: digest((out / name).read_bytes()) for name in result},
                "publication_allowed": False, "default_off": True,
                "full_copyright_articles_saved": False,
                "owner_authorization_required_for_capture": True}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False,
                                                  indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary.json"], ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
