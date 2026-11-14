#!/usr/bin/env python3
"""Three-source Work K guarded research runner (Work E/I + Work J).

Never writes source article bodies, casualty ledgers, WIP, or production data.
Capture is disabled unless a separate launch.json exists and GitHub's first
push is from the one specified reviewed predecessor commit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
import subprocess
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
EXPECTED_BASE = "657fd70564bf5393d3fcd209e47d95fa986f3010"
EXPECTED_BRANCH = "research-casualty-workr-identity-2026-11-14"
WORKZ_BRANCH = "research-casualty-workz-source-evidence-2026-11-14"
WORKX_HEAD = "b07a5957cb57ab8cf008d14373b15fa1db47b3af"
PLAN_PATH = HERE / "capture_plan.json"
TEMPLATE_PATH = HERE / "authorization_template.json"
BLOBS = {
    "research/casualty_evidence_ingestion_2026_11_13/ingest.py": "ef2bf3b83bcab8d579105865659c58b4ee009b44",
    "kyiv-air-alerts-grafana/scripts/casualty_auto_review.py": "4d4a8a5ce4b206f6735680b5644826a2cb7318fb",
    "research/casualty_controlled_capture_preflight_2026_11_13/capture_plan.json": "2f45d15b0e79cb11bf8ab605e314436dc0d3ed7c",
}
import research.casualty_evidence_ingestion_2026_11_13.ingest as e
from review_casualty_candidates import load_queue


def write_json(path: Path, value: object):
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def sha_data(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()



SCOPE = "EXACT_PR111_T03_T04_T05_SINGLE_EXECUTION"
TARGET_IDS = ("T03", "T04", "T05")
LIMITS = {"max_initial_urls": 3, "max_requests_total": 6,
          "min_delay_seconds": 1, "max_response_bytes": 1000000,
          "timeout_seconds": 15, "max_redirects_per_url": 3,
          "retries": 0, "authorization_max_hours": 24}


def _pilot_branch(launch: dict) -> str:
    """Work Z needs an explicit new grant pinned to the reviewed Work X tree."""
    if launch.get("workz_evidence_pilot") is True:
        if launch.get("workx_head_sha") != WORKX_HEAD:
            raise RuntimeError("WORKZ_WORKX_HEAD_MISMATCH")
        return WORKZ_BRANCH
    if "workz_evidence_pilot" in launch or "workx_head_sha" in launch:
        raise RuntimeError("WORKZ_NOT_EXPLICITLY_AUTHORIZED")
    return EXPECTED_BRANCH


def check_scope(queue):
    for name, expected in BLOBS.items():
        if (git("rev-parse", "HEAD:" + name) != expected
                or git("hash-object", name) != expected):
            raise RuntimeError("PINNED_SOURCE_BLOB_DRIFT:" + name)
    # The checked tree and working files must also be the modules imported by
    # this runner (rather than a different copy earlier on sys.path).
    for module, name in ((e, "research/casualty_evidence_ingestion_2026_11_13/ingest.py"),
                         (sys.modules.get("casualty_auto_review"),
                          "kyiv-air-alerts-grafana/scripts/casualty_auto_review.py")):
        if module is None or Path(getattr(module, "__file__", "")).resolve() != ROOT / name:
            raise RuntimeError("PINNED_SOURCE_BLOB_DRIFT:" + name)
    upstream = json.loads((ROOT / "research/casualty_controlled_capture_preflight_2026_11_13/capture_plan.json").read_text())
    plan = json.loads(PLAN_PATH.read_text())
    template = json.loads(TEMPLATE_PATH.read_text())
    selected = [t for t in upstream["targets"] if t["target_id"] in TARGET_IDS]
    if tuple(t["target_id"] for t in selected) != TARGET_IDS:
        raise RuntimeError("SOURCE_SELECTION_DRIFT")
    if (tuple(t.get("target_id") for t in plan.get("targets", [])) != TARGET_IDS
            or plan.get("limits") != LIMITS
            or plan.get("publication_allowed") is not False
            or plan.get("automatic_promote_allowed") is not False
            or plan.get("automatic_workflow_enabled") is not False):
        raise RuntimeError("WORKK_PLAN_DRIFT")
    for target, original in zip(plan["targets"], selected):
        for name in ("target_id", "case_id", "role", "url", "domain", "candidate_ids", "source_type"):
            if target.get(name) != original.get(name):
                raise RuntimeError("WORKK_TARGET_DRIFT:" + name)
    hosts = sorted({t["domain"] for t in selected})
    expected_targets = [{"url": t["url"], "role": t["role"],
                         "candidate_ids": t["candidate_ids"], "approved_redirect_urls": []}
                        for t in selected]
    if (template.get("status") != "NOT_AUTHORIZED"
            or template.get("authorization_id") is not None
            or template.get("approved_at_utc") is not None
            or template.get("expires_at_utc") is not None
            or template.get("owner_approval_record") is not None
            or template.get("targets") != expected_targets
            or template.get("allowed_hosts") != hosts
            or plan.get("allowed_hosts") != hosts
            or template.get("approval_scope") != SCOPE
            or template.get("enable_controlled_capture") is not False
            or template.get("publication_allowed") is not False
            or template.get("schedule_enabled") is not False
            or template.get("automatic_promote_allowed") is not False
            or template.get("repeat_allowed") is not False):
        raise RuntimeError("WORKK_NOT_DEFAULT_OFF")
    for key in ("max_initial_urls", "max_requests_total", "max_response_bytes",
                "min_delay_seconds", "timeout_seconds", "max_redirects_per_url", "retries"):
        if template.get(key) != LIMITS[key]:
            raise RuntimeError("WORKK_RESOURCE_BUDGET_DRIFT:" + key)
    if template.get("expires_after_hours_max") != 24:
        raise RuntimeError("WORKK_AUTH_DURATION_DRIFT")
    ids = {c["candidate_id"] for c in queue}
    if any(not set(t["candidate_ids"]).issubset(ids) for t in selected):
        raise RuntimeError("FROZEN_CANDIDATE_DRIFT")
    return plan, template


def validate_launch(launch, template, queue, *, environ=None, now=None):
    environ = os.environ if environ is None else environ
    now = datetime.now(timezone.utc) if now is None else now
    consumed_authorizations = {
        "CASUALTY-T01-T10-OWNER-20261113-ONE-SHOT-01",
        "CASUALTY-T03-T05-OWNER-20261113-2021Z-ONE-SHOT-01",
    }
    auth = launch.get("authorization_id")
    previous = launch.get("expected_previous_commit_sha")
    if (launch.get("scope") != SCOPE
            or launch.get("expected_source_base_sha") != EXPECTED_BASE
            or launch.get("publication_allowed") is not False
            or launch.get("automatic_promote_allowed") is not False
            or launch.get("repeat_allowed") is not False
            or not isinstance(auth, str) or not auth.startswith("CASUALTY-T03-T05-")
            or auth in consumed_authorizations
            or not isinstance(launch.get("owner_approval_record"), str)
            or not launch["owner_approval_record"].strip()
            or not isinstance(previous, str) or len(previous) != 40
            or not all(c in "0123456789abcdef" for c in previous)):
        raise RuntimeError("NEW_OWNER_GRANT_SCOPE_INVALID")
    if (environ.get("GITHUB_REF") != "refs/heads/" + _pilot_branch(launch)
            or environ.get("GITHUB_RUN_ATTEMPT") != "1"
            or environ.get("GITHUB_EVENT_NAME") != "push"
            or environ.get("GITHUB_EVENT_BEFORE") != previous):
        raise RuntimeError("FRESH_SINGLE_PUSH_OWNER_GRANT_REQUIRED")
    try:
        approved = datetime.fromisoformat(launch["approved_at_utc"].replace("Z", "+00:00"))
        expires = datetime.fromisoformat(launch["expires_at_utc"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise RuntimeError("INVALID_APPROVAL_WINDOW") from exc
    if (approved.tzinfo is None or expires.tzinfo is None
            or not approved <= now < expires
            or not timedelta(0) < expires - approved <= timedelta(hours=24)):
        raise RuntimeError("SINGLE_USE_AUTHORIZATION_EXPIRED_OR_INVALID")
    if _pilot_branch(launch) == WORKZ_BRANCH and expires - approved > timedelta(hours=1):
        raise RuntimeError("WORKZ_GRANT_MUST_EXPIRE_WITHIN_ONE_HOUR")
    policy = dict(template)
    policy.update(authorization_id=auth, approved_at_utc=launch["approved_at_utc"],
                  expires_at_utc=launch["expires_at_utc"],
                  owner_approval_record=launch["owner_approval_record"],
                  status="OWNER_APPROVED_SOURCE_CAPTURE_ONCE",
                  enable_controlled_capture=True)
    e.validate_capture_approval(policy, True, queue, now=now)
    return policy



# Work L adds a one-commit gate to the unchanged Work K capture engine.
# A special launch.json-only push is the sole permitted live trigger. All
# other pushes/PRs remain strictly offline; no grant is in this repository.
WORKK_HEAD = "69e7d023b4104c3583943eaf59f38b1d05ee32e5"
LAUNCH_REL = "research/casualty_one_time_capture_2026_11_13/launch.json"


def validate_one_launch_commit(launch, plan, *, environ=None, git_call=None):
    """Fail before first GET unless this is the first exact approved launch commit."""
    environ = os.environ if environ is None else environ
    git_call = git if git_call is None else git_call
    if not isinstance(launch, dict):
        raise RuntimeError("WORKL_GRANT_INVALID")
    previous = launch.get("expected_previous_commit_sha")
    if (launch.get("expected_preflight_head_sha") != previous
            or launch.get("workk_head_sha") != WORKK_HEAD
            or launch.get("exact_urls") != [t["url"] for t in plan["targets"]]
            or launch.get("allowed_hosts") != plan["allowed_hosts"]
            or launch.get("limits") != LIMITS
            or launch.get("approved_redirect_urls") != {t["target_id"]: [] for t in plan["targets"]}
            or launch.get("production_write_allowed") is not False
            or launch.get("source_fulltext_persistence_allowed") is not False
            or launch.get("status") != "OWNER_APPROVED_SINGLE_LAUNCH"):
        raise RuntimeError("WORKL_EXACT_OWNER_GRANT_NOT_MATCHED")
    auth = launch.get("authorization_id", "")
    if not isinstance(auth, str) or any(t in auth.upper() for t in ("SYNTHETIC", "EXAMPLE", "TEST")):
        raise RuntimeError("WORKL_NOT_A_REAL_FRESH_GRANT")
    if (environ.get("GITHUB_ACTOR") != "olegbalakin-cmyk"
            or environ.get("GITHUB_REF") != "refs/heads/" + _pilot_branch(launch)
            or environ.get("GITHUB_EVENT_NAME") != "push"
            or environ.get("GITHUB_RUN_ATTEMPT") != "1"
            or environ.get("GITHUB_EVENT_BEFORE") != previous
            or not environ.get("GITHUB_SHA")):
        raise RuntimeError("WORKL_LAUNCH_IDENTITY_OR_ATTEMPT_REJECTED")
    if (git_call("rev-parse", "HEAD") != environ["GITHUB_SHA"]
            or git_call("rev-parse", "HEAD^") != previous):
        raise RuntimeError("WORKL_EXACT_PARENT_OR_HEAD_REJECTED")
    if git_call("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD") != LAUNCH_REL:
        raise RuntimeError("WORKL_LAUNCH_ONLY_COMMIT_REQUIRED")
    if git_call("log", "--format=%H", "HEAD^", "--", LAUNCH_REL):
        raise RuntimeError("WORKL_AUTHORIZATION_ALREADY_USED_IN_BRANCH_HISTORY")
    try:
        git_call("merge-base", "--is-ancestor", WORKK_HEAD, previous)
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        raise RuntimeError("WORKL_WORKK_ANCESTRY_NOT_VERIFIED") from exc
    try:
        git_call("merge-base", "--is-ancestor", EXPECTED_BASE, previous)
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        raise RuntimeError("WORKN_WORKM_ANCESTRY_NOT_VERIFIED") from exc
    if _pilot_branch(launch) == WORKZ_BRANCH:
        try:
            git_call("merge-base", "--is-ancestor", WORKX_HEAD, previous)
        except (subprocess.CalledProcessError, RuntimeError) as exc:
            raise RuntimeError("WORKZ_WORKX_ANCESTRY_NOT_VERIFIED") from exc


def withhold_unsafe_excerpts(card):
    """Conservative evidence-output filter; Work J remains the only extractor."""
    original = list(card.get("excerpts", []))
    safe = []
    for excerpt in original:
        snippet = excerpt.get("text", "") if isinstance(excerpt, dict) else ""
        if not isinstance(snippet, str) or not snippet or len(snippet) > 170:
            continue
        # Work J already redacts email/phone. Drop entire quote when other
        # personal details or unreviewed proper names could remain.
        tail = " ".join(snippet.split()[1:])
        if (re.search(r"[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}", snippet)
                or re.search(r"\+?\d[\d ()-]{9,}\d", snippet)
                or re.search(r"\b(?:вулиця|вул\.?|будинок|буд\.?|квартира|кв\.?|"
                             r"паспорт|адреса|телефон|прізвище|ім'я|по батькові)\b", snippet, re.I)
                or re.search(r"\b[А-ЯЄІЇҐ][а-яєіїґ'’-]{2,}\b", tail)):
            continue
        safe.append(excerpt)
    card["excerpts"] = safe
    if len(safe) != len(original):
        card["reasons"] = sorted(set(card.get("reasons", []) + [
            "PRIVACY_REVIEW_EXCERPT_WITHHELD"]))
    return card



def retain_incident_review_clues(text: str) -> dict:
    """Retain bounded evidence mentions for a human, never infer attack identity.

    This is a Work R output adapter for the existing in-memory capture, not
    an incident parser or a cross-source matching decision.
    """
    result = {
        "status": "INSUFFICIENT_EVIDENCE",
        "attack_identity_verified": False,
        "attack_date_verified": None,
        "attack_time_verified": None,
        "locality_verified": None,
        "struck_object_verified": None,
        "direct_two_to_three_update_proven": False,
        "independent_police_link_proven": False,
        "chronology_is_source_sentence_order_only": True,
        "evidence_mentions": [],
    }
    if not isinstance(text, str) or not text.strip():
        return result
    patterns = (
        ("DATE_MENTION_NOT_ATTACK_DATE", r"\b(?:[12]?\d|3[01])\s+(?:січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\b|\b\d{1,2}[./]\d{1,2}[./]\d{2,4}\b"),
        ("PLACE_MENTION_NOT_LOCALITY_PROOF", r"\b(?:у|в|на)\s+запоріжжі\b|\bзапоріжжя\b|\bзапорізьк\w*\s+област\w*\b"),
        ("TIME_MENTION_NOT_ATTACK_TIME", r"\b(?:о|близько|приблизно)\s+\d{1,2}[:.]\d{2}\b|\b(?:вночі|вранці|вдень|увечері|надвечір|під ранок)\b"),
        ("ATTACK_METHOD_OR_IMPACT_MENTION", r"\b(?:ракет\w*|дрон\w*|безпілот\w*|бпла|авіаудар\w*|авіабомб\w*|артилер\w*|обстріл\w*|удар\w*|влучан\w*)\b"),
        ("STRUCK_OBJECT_MENTION", r"\b(?:приватн\w*|житлов\w*)\s+будин\w*|\b(?:багатоповерхів\w*|підприємств\w*|інфраструктур\w*|автомобіл\w*|школ\w*|лікарн\w*)\b"),
        ("FATALITY_MENTION_NOT_A_CONFIRMED_TOTAL", r"\b(?:загин\w*|загиб\w*|помер\w*|смерт\w*)\b"),
        ("REPORT_SEQUENCE_MENTION_NOT_LINK", r"\b(?:пізніше|згодом|спочатку|раніше|перед тим|додатково|уточнил\w*|також|ще\s+одн\w*|зросл\w*)\b"),
        ("OFFICIAL_REFERENCE_MENTION", r"\b(?:поліці\w*|дснс|ова|військов\w*\s+адміністраці\w*)\b"),
    )
    # The full extracted body exists only in memory. Each output is a short,
    # stand-alone sentence; do not retain article paragraphs or full source.
    sentences = re.split(r"(?<=[.!?])\s+", " ".join(text.split()))
    budget = min(650, len(text) // 4)
    # Work R previously stopped after the first eight mentions. That can
    # discard later corrections and official-source context in a long article.
    # Select diverse types of redacted source evidence first, without claiming
    # that any mention establishes an incident or chronological update.
    candidates = []
    for index, sentence in enumerate(sentences):
        if not 24 <= len(sentence) <= 170:
            continue
        kinds = [name for name, pattern in patterns
                 if re.search(pattern, sentence.casefold())]
        if not kinds:
            continue
        excerpt = re.sub(r"\bзапоріж(?:жя|жі|жю)\b|\bзапорізьк\w*\b",
                         "[ГЕО]", sentence, flags=re.I)
        excerpt = re.sub(r"\bбудин\w*\b", "[ОБ'ЄКТ]", excerpt, flags=re.I)
        if re.search(r"[<>№]|https?://|\b(?:вулиц\w*|вул\.?|провул\w*|проспект\w*|"
                     r"квартир\w*|паспорт\w*|адрес\w*|будинок\s*\d+)\b", excerpt, re.I):
            continue
        holder = {"excerpts": [{"text": excerpt}], "reasons": []}
        withhold_unsafe_excerpts(holder)
        if not holder["excerpts"]:
            continue
        candidates.append((index, excerpt, kinds))
    selected, used, counts, covered = [], 0, {}, set()
    while len(selected) < 8:
        eligible = []
        for ix, quote, tags in candidates:
            if used + len(quote) > budget:
                continue
            usable = [tag for tag in tags if counts.get(tag, 0) < 2]
            if usable:
                eligible.append((ix, quote, usable))
        if not eligible:
            break
        index, excerpt, kinds = min(
            eligible, key=lambda v: (-len(set(v[2]) - covered), v[0]))
        selected.append({
            "article_sentence_order": index + 1,
            "tags": kinds,
            "excerpt": excerpt,
            "excerpt_sha256": sha_data(excerpt.encode("utf-8")),
            "decision": "NEEDS_REVIEW",
        })
        candidates = [v for v in candidates if v[0] != index]
        used += len(excerpt)
        covered.update(kinds)
        for tag in kinds:
            counts[tag] = counts.get(tag, 0) + 1
    result["evidence_mentions"] = sorted(
        selected, key=lambda v: v["article_sentence_order"])
    return result

def retain_results(queue, plan, volatile, audit, output, *, authorization_id):
    """Adapt PR #118 output writer, preserving Work J audit facts and reviewer gates."""
    if (len(plan["targets"]) != 3 or len(audit.get("targets", [])) > 3
            or not 0 <= audit.get("requests_used", -1) <= 6):
        raise RuntimeError("CAPTURE_SCOPE_OR_BUDGET_OVERFLOW")
    output.mkdir(parents=True, exist_ok=True)
    receipts = [{"target_id": t["target_id"], "case_id": t["case_id"],
                 "role": t["role"], "candidate_ids": t["candidate_ids"],
                 "receipt": {k: v for k, v in record.items()
                             if k not in ("page_title", "blocked_redirect_url")},
                 "publication_allowed": False}
                for t, record in zip(plan["targets"], audit["targets"])]
    # Required Work K integration: do NOT persist volatile original source bodies.
    facts = e.minimal_capture_facts(volatile, queue)
    if (facts.get("publication_allowed") is not False
            or facts.get("automatic_credits") != 0
            or facts.get("official_incidents_automatically_matched") != 0):
        raise RuntimeError("WORKJ_PUBLICATION_GUARD_VIOLATED")
    roles = {x["receipt"].get("resolved_url"): x["role"] for x in receipts}
    volatile_texts = {(item.get("url"), role): str(item.get("text") or "")
                      for role, key in (("publisher", "articles"), ("official", "official_articles"))
                      for item in volatile.get(key, [])}
    for card in facts["facts"]:
        withhold_unsafe_excerpts(card)
        card["incident_review"] = retain_incident_review_clues(
            volatile_texts.get((card.get("source_url"), card.get("source_role")), ""))
        url = card.get("source_url")
        if not url or roles.get(url) != card.get("source_role"):
            raise RuntimeError("FACT_WITHOUT_MATCHING_SOURCE_RECEIPT")
        if card.get("decision") != "NEEDS_REVIEW" or card.get("publication_allowed") is not False:
            raise RuntimeError("FACT_NOT_FAIL_CLOSED")
        if not isinstance(card.get("document_sha256"), str) or len(card["document_sha256"]) != 64:
            card["reasons"] = sorted(set(card["reasons"] + ["DOCUMENT_SHA256_MISSING"]))
        if not card.get("excerpts"):
            privacy = "PRIVACY_REVIEW_EXCERPT_WITHHELD" in card.get("reasons", [])
            reason = ("SHORT_EVIDENCE_PRIVACY_WITHHELD" if privacy else
                      "SHORT_EVIDENCE_NOT_EXTRACTED")
            card["reasons"] = sorted(set(card["reasons"] + [reason]))
        if any(len(x.get("text", "")) > 170 for x in card.get("excerpts", [])):
            raise RuntimeError("EXCERPT_OVER_170")
        if "text" in card or "body" in card:
            raise RuntimeError("FULL_SOURCE_BODY_IN_FACT_CARD")
    extracted, parser_errors = [], {}
    try:
        retained, rejected = e.work_a.anchored_articles(queue, volatile)
        diagnostics = {}
        reports = e.extract_cached_reports(queue, retained, diagnostics=diagnostics)
        parser_errors = {"candidate_binding_issue_count": len(rejected),
                         "workj_reason_counts": diagnostics.get("reason_counts", {}),
                         "workj_stage_counts": diagnostics.get("stage_counts", {})}
        for report in reports:
            extracted.append({"candidate_ids": report.get("candidate_ids", []),
                              "incident": report.get("incident"),
                              "count": report.get("count"),
                              "report_sha256": e.stable_digest(report),
                              "decision": "NEEDS_REVIEW",
                              "independent_official_event_link_proven": False,
                              "prior_credit_reconciled": False, "publication_allowed": False})
    except Exception as exc:
        parser_errors = {"reason": "NEEDS_REVIEW_PARSER_EXCEPTION",
                         "work_a_error_type": type(exc).__name__}
    # Work X consumes only already-redacted Work J/R fact cards. It never
    # opens sources, grants incident identity, links police claims, or credits.
    from research.casualty_evidence_ingestion_2026_11_13 import workx_evidence
    facts["workx_review_index"] = workx_evidence.build_review_index(facts, queue)
    if (facts["workx_review_index"]["summary"]["automatic_credits"] != 0
            or facts["workx_review_index"]["publication_allowed"] is not False):
        raise RuntimeError("WORKX_AUTO_CREDIT_GUARD")
    source_decisions = []
    retained_urls = {x.get("source_url") for x in facts["facts"]}
    for item in receipts:
        url = item["receipt"].get("resolved_url") or item["receipt"].get("requested_url")
        source_decisions.append({"target_id": item["target_id"], "source_url": url,
                                 "source_role": item["role"], "decision": "NEEDS_REVIEW",
                                 "reason": ("SOURCE_FACTS_RETAINED_UNVERIFIED"
                                            if url in retained_urls
                                            else item["receipt"].get("reason") or "SOURCE_TEXT_NOT_RETAINED"),
                                 "publication_allowed": False})
    summary = {"decision": "CONTROLLED_THREE_SOURCE_RESEARCH_ONLY",
               "authorization_id": authorization_id, "source_base_commit": EXPECTED_BASE,
               "run_once": True, "requested_urls": 3, "allowed_hosts": 3,
               "max_requests_total": 6, "requests_used": audit["requests_used"],
               "targets_attempted": len(receipts), "targets_not_attempted": 3-len(receipts),
               "stopped_early": audit.get("stopped_early", False),
               "stop_reason": audit.get("stop_reason"),
               "retained_minimal_fact_cards": len(facts["facts"]),
               "unverified_parser_reports": len(extracted),
               "oct22_attack_identity": "NOT_INDEPENDENTLY_VERIFIED",
               "oct22_cumulative_2_to_3": "NEEDS_REVIEW_NOT_ADDITIVE",
               "oct22_prior_credit_reconciled": False,
               "proposed_new_credits": None, "automatic_death_credits": 0,
               "official_links_verified": False, "publication_allowed": False,
               "production_changed": False, "wip_changed": False, "neon_changed": False,
               "full_article_bodies_saved": False}
    write_json(output / "capture_receipts.json", {"summary": summary, "targets": receipts})
    write_json(output / "minimal_capture_facts.json", facts)
    write_json(output / "fact_preview_unverified.json", {
        "reports": extracted, "parser_errors": parser_errors,
        "source_decisions": source_decisions,
        "no_full_publisher_text": True, "human_review_required": True,
        "publication_allowed": False})
    write_json(output / "summary.json", summary)
    hashes = {p.name: sha_data(p.read_bytes()) for p in sorted(output.glob("*.json"))
              if p.name != "manifest.json"}
    write_json(output / "manifest.json", {
        "files_sha256": hashes, "owner_grant_scope": SCOPE,
        "captured_raw_bodies_persisted": False, "publication_allowed": False})
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--queue", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--launch", type=Path)
    ap.add_argument("--preflight-only", action="store_true")
    args = ap.parse_args()
    output = args.output.resolve()
    if not args.output.is_absolute() or output == ROOT or ROOT in output.parents:
        raise RuntimeError("OUTPUT_MUST_BE_EPHEMERAL_OUTSIDE_REPO")
    queue = load_queue(args.queue)
    plan, template = check_scope(queue)
    if args.preflight_only:
        if args.launch:
            raise RuntimeError("NO_LAUNCH_DURING_PREFLIGHT")
        output.mkdir(parents=True, exist_ok=True)
        write_json(output / "preflight.json", {
            "decision": "THREE_SOURCE_RUNNER_OFFLINE_PREPARED_NOT_AUTHORIZED",
            "targets": 3, "allowed_hosts": 3, "max_requests_total": 6,
            "external_get_requests": 0, "authorization_status": "NOT_AUTHORIZED",
            "publisher_text_persisted": False, "publication_allowed": False})
        print("WORKK_OFFLINE_PREFLIGHT_PASS; external GET=0; owner grant absent")
        return
    if not args.launch:
        raise RuntimeError("MISSING_SEPARATE_OWNER_GRANT")
    launch = json.loads(args.launch.read_text())
    if not args.launch.is_file() or args.launch.resolve() != HERE / "launch.json":
        raise RuntimeError("WORKL_LAUNCH_FILE_MUST_BE_EXACT_REPO_PATH")
    policy = validate_launch(launch, template, queue)
    validate_one_launch_commit(launch, plan)
    output.mkdir(parents=True, exist_ok=True)
    try:
        volatile, audit = e.controlled_capture(policy, queue, enabled=True)
    except Exception as exc:
        write_json(output / "capture_failure.json", {
            "decision": "CAPTURE_ABORTED_NO_PUBLICATION",
            "reason_type": type(exc).__name__,
            "request_count_after_exception": "UNKNOWN_STOP_NO_RETRY",
            "publication_allowed": False, "no_source_body_stored": True})
        raise
    summary = retain_results(queue, plan, volatile, audit, output,
                             authorization_id=launch["authorization_id"])
    print("WORKK_SHADOW_CAPTURE_ONLY", summary["targets_attempted"],
          "GET", summary["requests_used"],
          "facts", summary["retained_minimal_fact_cards"], "publication FORBIDDEN")


if __name__ == "__main__":
    main()
