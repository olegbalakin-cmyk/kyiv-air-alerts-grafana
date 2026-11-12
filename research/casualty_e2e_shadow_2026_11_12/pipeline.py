#!/usr/bin/env python3
"""Read-only casualty shadow bridge: saved WIP -> verified excerpts -> generator.

Never fetch publishers, write review queues/revisions, or authorize publication.
The only positive input here is independently pinned source text from an earlier
approved GitHub Actions artifact. A HTTP receipt without text is never evidence
for a casualty count.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "kyiv-air-alerts-grafana" / "scripts"))
from casualty_auto_review import extract_cached_reports, fingerprint, prepare
from review_casualty_candidates import load_queue, load_revision_rows

RETAINED_EVIDENCE_SHA256 = "84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df"
RETAINED_ZAP_TEXT_SHA256 = "011894b7c4bd906dcfd0c5d2f7cef07a932976ca313220fa9089999264feb259"
RECEIPTS_102_SHA256 = "4c21321b8a75d57f60efc97f581e89604eaa03289bb64bfba26e491ac83a203b"
CONFIRMED_ZAP_CANDIDATE = "e0fba98b19473874e9a1d8f1"
CONTRACT_FIELDS = ("incident_id", "count_kind", "baseline_credited",
                   "identity_proof", "credited_proof")
OUTPUT_FILES = ("candidate_decisions.json", "attack_decisions.json", "blocked_cases.json",
                "proposals.json", "generator_probe.json", "summary.json", "manifest.json")
SOURCE_MISSING = "BLOCKED_SOURCE_CONTENT"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable_sha(obj) -> str:
    return sha(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":")).encode("utf-8"))


def read_pinned(path: Path, expected: str | None = None):
    body = path.read_bytes()
    actual = sha(body)
    if expected and actual != expected:
        raise RuntimeError(f"PIN_MISMATCH: {path.name}: {actual}")
    return json.loads(body), actual


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def ensure_output_isolated(out: Path, inputs: list[Path]):
    out = out.resolve()
    if not out.is_absolute():
        raise RuntimeError("Absolute shadow output path required")
    if ROOT.resolve() == out or ROOT.resolve() in out.parents:
        raise RuntimeError("Shadow output must not be inside repository")
    if any(out == p.resolve() or out in p.resolve().parents for p in inputs):
        raise RuntimeError("Output path conflicts with an input")
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("Shadow output directory must be empty")
    out.mkdir(parents=True, exist_ok=True)


def anchored_articles(queue: list[dict], original: dict):
    by_id = {c["candidate_id"]: c for c in queue}
    if len(by_id) != len(queue):
        raise RuntimeError("Duplicate WIP candidate_id")
    receipts = {r["candidate_id"]: r for r in original["receipts"]}
    retained, issues = [], {}
    for article in original["articles"]:
        cid = article["candidate_id"]
        receipt, candidate = receipts.get(cid), by_id.get(cid)
        if not candidate or not receipt:
            issues[cid] = "CANDIDATE_NOT_IN_CURRENT_WIP_OR_RECEIPT_MISSING"
            continue
        if receipt.get("candidate_fingerprint") != fingerprint(candidate):
            issues[cid] = "WIP_CANDIDATE_FINGERPRINT_CHANGED"
            continue
        if receipt.get("resolved_url") != article["url"] or receipt.get("http_status") != 200:
            issues[cid] = "ORIGINAL_SOURCE_RECEIPT_MISMATCH"
            continue
        if not article.get("text") or article["url"].startswith("https://news.google.com"):
            issues[cid] = SOURCE_MISSING
            continue
        if cid == CONFIRMED_ZAP_CANDIDATE and sha(article["text"].encode("utf-8")) != RETAINED_ZAP_TEXT_SHA256:
            raise RuntimeError("ZAP_TEXT_SHA256_MISMATCH")
        retained.append(article)
    return retained, issues


def source_index(matrix: dict, receipts: dict):
    if receipts.get("raw_article_text_stored") is not False:
        raise RuntimeError("PR102 receipt scope changed; review required")
    rows, groups = {}, []
    for group in matrix["groups"]:
        ids = [c["candidate_id"] for c in group["candidates"]]
        materials = []
        for cid in ids:
            index = receipts["candidate_receipt_index"].get(cid)
            if type(index) is not int or not 0 <= index < len(receipts["source_receipts"]):
                raise RuntimeError(f"PR102 missing receipt for {cid}")
            r = receipts["source_receipts"][index]
            if r.get("http_status") != 200 or not re.fullmatch(r"[0-9a-f]{64}", r.get("response_sha256", "")):
                raise RuntimeError(f"PR102 invalid transport receipt for {cid}")
            if not str(r.get("resolved_url") or "").startswith("https://"):
                raise RuntimeError(f"PR102 missing original URL for {cid}")
            rows[cid] = {"original_url": r["resolved_url"],
                         "http_sha256": r["response_sha256"],
                         "receipt_status": "TRANSPORT_ONLY_NO_BODY",
                         "official_body_available": False}
            materials.append(r["resolved_url"])
        groups.append({"cluster_id": group["cluster_id"], "candidate_ids": ids,
                       "publisher_urls": sorted(set(materials)),
                       "evidence_status": SOURCE_MISSING})
    return rows, groups


def get_event(rows: list[dict], cid: str):
    found = [e for e in rows if cid in {m["candidate_id"] for m in e["messages"]}]
    if len(found) != 1:
        raise RuntimeError(f"Expected exactly one event for {cid}, found {len(found)}")
    return found[0]


def make_proposal(event: dict, proofs: dict, manifest: dict, monthly: list[dict],
                  revisions: list[dict]) -> dict:
    """Adapt a parsed VERIFIED total to production cumulative contract.

    Intentionally fail closed for any previously credited event or October month
    containing legacy records: there is no safe generic transition from old
    per-event deltas to new cumulative snapshots without provenance.
    """
    incident = event["incident"]
    city, attack_day = incident.get("city_key"), date.fromisoformat(incident["attack_date"])
    if event["category"] != "AUTO_READY" or city != "zaporizhzhia":
        raise ValueError("Only the pinned source-backed Zaporizhzhia incident is eligible")
    if {m["candidate_id"] for m in event["messages"]} != {CONFIRMED_ZAP_CANDIDATE}:
        raise ValueError("Multiple candidate/event identities need review")
    through = date.fromisoformat(manifest["validated_through"])
    if attack_day <= through:
        raise ValueError("BASELINE_EVENT_ALLOCATION_UNKNOWN")
    if attack_day.strftime("%Y-%m") in {m["month"] for m in monthly}:
        raise ValueError("MONTHLY_BASELINE_CREDIT_UNKNOWN")
    if any(r["city_key"] == city and r["status"] == "confirmed" and
           str(r["attack_date"])[:7] == attack_day.strftime("%Y-%m") for r in revisions):
        raise ValueError("EXISTING_SAME_MONTH_REVISION_REQUIRES_LEDGER_BINDING")
    if event.get("already_accounted") != 0 or event.get("reserved_in_previous_proposals") != 0:
        raise ValueError("EXISTING_EVENT_CREDIT_OR_RESERVATION")
    if len(event["reports"]) != 1 or event["reports"][0]["provenance"].get("article_sha256") != RETAINED_ZAP_TEXT_SHA256:
        raise ValueError("SOURCE_HASH_NOT_PINNED")
    total = event.get("confirmed_total_claim")
    if type(total) is not int or total <= 0 or event.get("proposed_delta") != total:
        raise ValueError("UNSAFE_CUMULATIVE_TOTAL")
    source = event["reports"][0]["sources"][0]
    if source["url"] != proofs["source_url"] or source.get("origin_id") != "dsns":
        raise ValueError("OFFICIAL_SOURCE_PROVENANCE_MISMATCH")
    ident = {"event_id": event["event_id"], "incident": incident,
             "source_sha256": RETAINED_ZAP_TEXT_SHA256,
             "candidate_ids": [CONFIRMED_ZAP_CANDIDATE]}
    evidence_digest = stable_sha(ident)
    credited_digest = stable_sha({
        "baseline_manifest_sha256": proofs["city_manifest_sha256"],
        "baseline_monthly_sha256": proofs["city_csv_sha256"],
        "revisions_sha256": proofs["revisions_sha256"],
        "validated_through": manifest["validated_through"],
        "attack_date": attack_day.isoformat(), "confirmed_existing_for_month": 0,
    })
    observation = event["reports"][0]["observed_at"]
    dt = datetime.fromisoformat(observation.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    row = {
        "record_id": "shadow:" + evidence_digest[:32],
        "city_key": city, "observed_at": dt.astimezone(timezone.utc).isoformat(),
        "attack_date": attack_day.isoformat(), "deaths_delta": str(total),
        "status": "confirmed", "source_name": "ДСНС (атрибуція Суспільне)",
        "source_url": source["url"], "candidate_ids": CONFIRMED_ZAP_CANDIDATE,
        "note": "SHADOW_ONLY; provenance in generator_probe.json; no publication",
        "incident_id": "incident:" + evidence_digest[:32],
        "count_kind": "cumulative", "baseline_credited": "0",
        "identity_proof": "sha256:" + evidence_digest,
        "credited_proof": "sha256:" + credited_digest,
    }
    return row


def generator_probe(generator: Path, ledger: Path, proposal: dict, monthly: list[dict],
                    city_manifest: dict, dashboard: Path, out: Path):
    """Run the EXACT production dedup + city overlay on a private temporary copy."""
    with tempfile.TemporaryDirectory(prefix="casualty-generator-shadow-", dir=out) as td:
        root = Path(td) / "kyiv-air-alerts-grafana"
        scripts, casualties = root / "scripts", root / "data" / "casualties"
        scripts.mkdir(parents=True)
        casualties.mkdir(parents=True)
        shutil.copyfile(generator, scripts / "update_casualties.py")
        ledger_rows = read_csv(ledger)
        columns = list(dict.fromkeys(list(ledger_rows[0]) if ledger_rows else
                                     ["record_id", "city_key", "observed_at", "attack_date",
                                      "deaths_delta", "status", "source_name", "source_url",
                                      "note", "candidate_ids"]))
        columns += [key for key in CONTRACT_FIELDS if key not in columns]
        with (casualties / "revisions.csv").open("w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=columns)
            wr.writeheader()
            for r in ledger_rows + [proposal]:
                wr.writerow({k: r.get(k, "") for k in columns})
        spec = importlib.util.spec_from_file_location("casualty_generator_shadow", scripts / "update_casualties.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        revisions = module.load_revisions()
        effective = module.reconcile_confirmed_revisions(revisions)
        assert len([r for r in effective if r["city_key"] == "zaporizhzhia"]) == 1
        series = {"meta": city_manifest,
                  "monthly": [{"month": r["month"], "time": module.month_timestamp(r["month"]),
                               "deaths": int(r["deaths_confirmed"])} for r in monthly]}
        after = module.apply_city_revision_overlay(series, effective, "zaporizhzhia")
        month = proposal["attack_date"][:7]
        before_count = sum(int(r["deaths"]) for r in series["monthly"] if r["month"] == month)
        after_count = sum(int(r["deaths"]) for r in after["monthly"] if r["month"] == month)
        if before_count != 0 or after_count != int(proposal["deaths_delta"]):
            raise RuntimeError("GENERATOR_SHADOW_DELTA_MISMATCH")
        loaded = json.loads(dashboard.read_text(encoding="utf-8"))
        existing = loaded["casualties_by_city"]["zaporizhzhia"]["monthly"]
        if {(str(r["month"]), int(r["deaths"])) for r in existing} != {
                (r["month"], int(r["deaths"])) for r in series["monthly"]}:
            raise RuntimeError("DASHBOARD_BASELINE_NOT_IDENTICAL_TO_CSV")
        before_other = stable_sha({k: v for k, v in loaded["casualties_by_city"].items()
                                   if k != "zaporizhzhia"})
        simulated = copy.deepcopy(loaded)
        simulated["casualties_by_city"]["zaporizhzhia"] = after
        if stable_sha({k: v for k, v in simulated["casualties_by_city"].items()
                       if k != "zaporizhzhia"}) != before_other:
            raise RuntimeError("UNRELATED_CITY_CHANGED")
        # Retain a small JSON patch/probe, not an entire production dashboard.
        return {"status": "PASS", "month": month, "before_month": before_count,
                "shadow_month": after_count, "new_delta": after_count - before_count,
                "production_generator_sha256": sha(generator.read_bytes()),
                "production_revisions_sha256": sha(ledger.read_bytes()),
                "unchanged_22_other_cities_sha256": before_other,
                "isolated_dashboard_patch": {"casualties_by_city": {"zaporizhzhia": after}},
                "publication_allowed": False}


def run(args):
    paths = [Path(getattr(args, name)).resolve() for name in
             ("queue", "evidence", "receipts", "matrix", "revisions", "baseline",
              "city_manifest", "city_csv", "generator", "dashboard")]
    if not all(p.is_file() for p in paths):
        raise RuntimeError("BLOCKED_INPUT_NOT_PRESENT")
    previous_path = Path(args.previous_proposals).resolve() if args.previous_proposals else None
    if previous_path:
        if not previous_path.is_file():
            raise RuntimeError("PREVIOUS_SHADOW_PROPOSALS_NOT_FOUND")
        paths.append(previous_path)
    out = Path(args.output).resolve()
    ensure_output_isolated(out, paths)
    queue_path, evidence_path, receipt_path, matrix_path, revision_path, baseline_path, \
        manifest_path, csv_path, generator_path, dashboard_path = paths[:10]
    before = {p.name + ":" + str(i): sha(p.read_bytes()) for i, p in enumerate(paths)}
    queue = load_queue(queue_path)
    if not queue or len({c["city_key"] for c in queue}) > 23:
        raise RuntimeError("Invalid 23-city WIP queue snapshot")
    original, _ = read_pinned(evidence_path, RETAINED_EVIDENCE_SHA256)
    receipts, _ = read_pinned(receipt_path, RECEIPTS_102_SHA256)
    matrix, _ = read_pinned(matrix_path)
    baseline, _ = read_pinned(baseline_path)
    if len(baseline) != 23 or not {c["city_key"] for c in queue}.issubset(set(baseline)):
        raise RuntimeError("WIP candidates contain unknown monitored city")
    manifest, _ = read_pinned(manifest_path)
    city_rows = read_csv(csv_path)
    ledger = load_revision_rows(revision_path)
    original_articles, source_errors = anchored_articles(queue, original)
    reports = extract_cached_reports(queue, original_articles)
    previous_proposals = []
    if previous_path:
        previous_proposals, _ = read_pinned(previous_path)
        if not isinstance(previous_proposals, list) or any(not isinstance(r, dict) for r in previous_proposals):
            raise RuntimeError("PREVIOUS_PROPOSAL_FORMAT_INVALID")
    prepared = prepare(queue, ledger, reports, baseline, previous_proposals)
    sources, clusters = source_index(matrix, receipts)
    candidate_to_event = {}
    for event in prepared["events"]:
        for msg in event["messages"]:
            if msg["candidate_id"] in candidate_to_event:
                raise RuntimeError("Candidate assigned to multiple events")
            candidate_to_event[msg["candidate_id"]] = event
    if len(candidate_to_event) != len(queue):
        raise RuntimeError("Prepared candidate coverage is incomplete")
    proofs = {
        "source_url": next(a["url"] for a in original_articles if a["candidate_id"] == CONFIRMED_ZAP_CANDIDATE)
           if any(a["candidate_id"] == CONFIRMED_ZAP_CANDIDATE for a in original_articles) else None,
        "city_manifest_sha256": sha(manifest_path.read_bytes()),
        "city_csv_sha256": sha(csv_path.read_bytes()),
        "revisions_sha256": sha(revision_path.read_bytes()),
    }
    proposals = []
    generator_result = {"status": "SKIPPED_NO_SAFE_PROPOSAL"}
    candidate_decisions = []
    positive_id = CONFIRMED_ZAP_CANDIDATE
    bridge_error = None
    positive = candidate_to_event.get(positive_id)
    if positive is not None and positive.get("action") == "PROPOSAL_ALREADY_PREPARED":
        generator_result = {"status": "SKIPPED_ALREADY_RESERVED", "new_proposals": 0}
    elif positive is not None and positive["category"] == "AUTO_READY":
        try:
            row = make_proposal(positive, proofs, manifest, city_rows, ledger)
            generator_result = generator_probe(generator_path, revision_path, row, city_rows,
                                               manifest, dashboard_path, out)
            proposals.append(row)
        except (ValueError, RuntimeError, KeyError, AssertionError) as exc:
            bridge_error = f"{type(exc).__name__}: {exc}"
            generator_result = {"status": "BLOCKED_GENERATOR_COMPATIBILITY", "reason": bridge_error}
    for item in queue:
        cid = item["candidate_id"]
        event = candidate_to_event[cid]
        explicit = sources.get(cid)
        reasons = list(event.get("reasons", []))
        has_report = bool(event["reports"])
        if not has_report:
            reasons.append(SOURCE_MISSING)
        if cid in source_errors:
            reasons.append(source_errors[cid])
        if explicit:
            reasons.append("TRANSPORT_RECEIPT_NOT_FACT_EVIDENCE")
        if cid == positive_id and bridge_error:
            reasons.append("BLOCKED_GENERATOR_COMPATIBILITY")
        if cid == positive_id and (proposals or positive.get("action") == "PROPOSAL_ALREADY_PREPARED"):
            status = "AUTO_READY"
            reasons = []
        elif event.get("category") == "AUTO_READY" and event.get("action") == "ALREADY_ACCOUNTED" and has_report:
            status = "REJECTED"
            reasons.append("EXISTING_VERIFIED_CREDIT_NO_NEW_RECORD")
        else:
            status = "NEEDS_REVIEW"
        candidate_decisions.append({
            "candidate_id": cid, "city_key": item["city_key"], "status": status,
            "event_id": event["event_id"], "facts_from_retained_text": has_report,
            "source": explicit or ({"original_url": event["reports"][0]["sources"][0]["url"],
                                   "source_text_sha256": event["reports"][0]["provenance"]["article_sha256"]}
                                  if has_report else None),
            "reasons": sorted(set(reasons)), "proposed_record_id":
                proposals[0]["record_id"] if cid == positive_id and proposals else None,
            "publication_allowed": False,
        })
    by_id = {c["candidate_id"]: c for c in candidate_decisions}
    attack_decisions = []
    if positive_id in by_id:
        positive_event = candidate_to_event[positive_id]
        attack_decisions.append({
            "cluster_id": "oct_10_guided_bomb", "incident": positive_event.get("incident"),
            "candidate_ids": [positive_id], "status": by_id[positive_id]["status"],
            "proposed_total": positive_event.get("confirmed_total_claim") if by_id[positive_id]["status"] == "AUTO_READY" else None,
            "new_increment": int(proposals[0]["deaths_delta"]) if proposals else 0 if positive_event.get("action") == "PROPOSAL_ALREADY_PREPARED" else None,
            "source_text_sha256": RETAINED_ZAP_TEXT_SHA256 if by_id[positive_id]["status"] == "AUTO_READY" else None,
            "reasons": by_id[positive_id]["reasons"], "publication_allowed": False})
    for group in clusters:
        ids = group["candidate_ids"]
        if not all(cid in by_id for cid in ids):
            raise RuntimeError("Frozen PR102 candidate missing from WIP")
        attack_decisions.append({**group, "status": "NEEDS_REVIEW",
                                 "reasons": [SOURCE_MISSING, "OFFICIAL_FULL_TEXT_NOT_RETAINED",
                                             "INCIDENT_AND_PRIOR_CREDIT_NOT_PROVEN"],
                                 "attack_date": None, "confirmed_total": None,
                                 "new_increment": None, "publication_allowed": False})
    counters = Counter(c["status"] for c in candidate_decisions)
    issue_counts = Counter(r for c in candidate_decisions for r in c["reasons"])
    summary = {
        "mode": "SHADOW_ONLY", "publication_allowed": False,
        "city_count": len(baseline),
        "candidate_city_count": len({c["city_key"] for c in queue}),
        "candidates_seen": len(queue), "auto_ready_candidates": counters["AUTO_READY"],
        "needs_review_candidates": counters["NEEDS_REVIEW"],
        "rejected_candidates": counters["REJECTED"],
        "attack_clusters_targeted": len(attack_decisions),
        "attack_clusters_auto_ready": sum(x["status"] == "AUTO_READY" for x in attack_decisions),
        "attack_clusters_blocked": sum(x["status"] == "NEEDS_REVIEW" for x in attack_decisions),
        "shadow_proposals": len(proposals), "reason_counts": dict(sorted(issue_counts.items())),
        "generator_probe": generator_result["status"], "source_content_blocker":
            [g["cluster_id"] for g in clusters],
        "decision": "PARTIAL_SOURCE_BACKED_SHADOW_PROOF_NOT_END_TO_END_PASS",
        "scope": "Stored WIP snapshot, retained source excerpts and PR102 transport metadata only",
    }
    outputs = {
        "candidate_decisions.json": candidate_decisions, "attack_decisions.json": attack_decisions,
        "blocked_cases.json": [c for c in candidate_decisions if c["status"] != "AUTO_READY"],
        "proposals.json": proposals, "generator_probe.json": generator_result,
        "summary.json": summary}
    for name, value in outputs.items():
        (out / name).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
                                encoding="utf-8")
    after = {p.name + ":" + str(i): sha(p.read_bytes()) for i, p in enumerate(paths)}
    if before != after:
        raise RuntimeError("INPUT_CHANGED_DURING_SHADOW")
    manifest_out = {"input_sha256": before, "input_unchanged": True,
                    "outputs_sha256": {name: sha((out / name).read_bytes()) for name in outputs},
                    "public_data_mutated": False, "external_publisher_http": False,
                    "publication_allowed": False}
    (out / "manifest.json").write_text(json.dumps(manifest_out, indent=2) + "\n")
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--previous-proposals", help="JSON proposals from an earlier shadow-only execution")
    for f in ("queue", "evidence", "receipts", "matrix", "revisions", "baseline",
              "city_manifest", "city_csv", "generator", "dashboard", "output"):
        p.add_argument("--" + f.replace("_", "-"), required=True)
    result = run(p.parse_args())
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
