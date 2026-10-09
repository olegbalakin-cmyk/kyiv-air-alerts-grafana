#!/usr/bin/env python3
"""One offline authoritative EXPANSION-3 acceptance replay; no evidence acquisition."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SEMANTIC_BASE = "b749e0195c4ec1b2262c998e381a92277a89a5e9"
PILOT_COMMIT = SEMANTIC_BASE
PILOT_RUN = 37937223379
PILOT_ARTIFACT = 11618274220
PILOT_SHA256 = "8886cfef985b39e190c8d9b137d6e787e52c6b70372572b9f1381b580c9b7efe"
AUTH_COMMIT = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
AUTH_PATH = "kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
AUTH_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
PREDECESSOR_MANIFEST_SHA = "bc77629b7936e02488cd611da1515dc9f9b52db945d5cf334aaa60245ca295ee"
PREDECESSOR_FREEZE_BLOB = "b959a6e0c98c3349a3525ae2f3a7040feef14701"
PREDECESSOR_FREEZE_PATH = "research/kyiv_immutable_development_source_set_freeze_2026-10-09.json"
PILOT_PATH = "research/kyiv_immutable_source_eligibility_expansion_pilot_2026-10-09.json"
PROOF_SCRIPT = ".github/proof/kyiv_expanded_development_acceptance_freeze_proof.py"
PROOF_WORKFLOW = ".github/workflows/kyiv-expanded-development-acceptance-freeze-proof.yml"
PROOF_BRANCH = "kyiv-expanded-development-freeze-acceptance-proof-2026-10-09"
ARTIFACT_NAME = "kyiv-expansion3-authoritative-acceptance-proof"
SOURCES = [
    "VA_Kyiv", "KyivCityOfficial", "vitaliy_klitschko", "dsns_kyiv",
    "kpszsu", "suspilnenews", "suspilne_kyiv", "suspilne.media/kyiv",
    "BBC_Ukrainian", "Radio_Svoboda", "Suspilne_National",
    "war.telegraf.com.ua", "5.ua", "zaxid.net", "kyiv.novyny.live",
]
ADDITIONS = ("5.ua", "zaxid.net", "kyiv.novyny.live")
CORPUS_HASHES = {
    "discovery": "fc1e184741c8409ce634015771a9484de8cfd8230037be56e3d8970d0178e5cc",
    "native": "bcfdedba186b58671dab7c3c1bd33dc8ec0f2772c8b9f9c3bf053c7d64cff858",
    "normalized": "e5790301a8d17b9997a3dbdfb71651e486de8ba6a4c39a552043754805e7ce2d",
}
COHORT_IDENTITY_SHA = "a785fec6b40ff4732a12762015bccaf8d2d8dfc0ddb1ff5f6397d3c387b38bee"
POS = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}
EXPECTED_HOLDS = {"e56cdca45ed5b1cd7b0b9746", "f06c52e0ed82b44792ec2ec7"}
PILOT_MODULE = ROOT / ".github/proof/kyiv_immutable_source_eligibility_expansion_pilot.py"


def require(ok, why):
    if not ok:
        raise RuntimeError(why)


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def canonical(o):
    return (json.dumps(o, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


def git(*a):
    return subprocess.check_output(["git", *a], cwd=ROOT, text=True).strip()


def verify_identity():
    require(os.environ.get("GITHUB_REF_NAME") == PROOF_BRANCH, "WRONG_PROOF_BRANCH")
    require(git("rev-parse", SEMANTIC_BASE) == SEMANTIC_BASE, "SEMANTIC_BASE_MISSING")
    require(git("merge-base", SEMANTIC_BASE, "HEAD") == SEMANTIC_BASE, "WRONG_PROOF_BASE")
    require(
        set(git("diff", "--name-only", SEMANTIC_BASE, "HEAD").splitlines()) == {PROOF_SCRIPT, PROOF_WORKFLOW},
        "PROOF_BRANCH_MUTATION_BOUNDARY_VIOLATED",
    )
    require(git("rev-parse", "HEAD:" + PREDECESSOR_FREEZE_PATH) == PREDECESSOR_FREEZE_BLOB,
            "PREDECESSOR_FREEZE_CHANGED")
    require(git("rev-parse", SEMANTIC_BASE + ":" + PILOT_PATH) ==
            git("rev-parse", "HEAD:" + PILOT_PATH), "PILOT_ARTIFACT_CHANGED")
    require(sha256((ROOT / PILOT_PATH).read_bytes()) == PILOT_SHA256, "PILOT_JSON_SHA_MISMATCH")
    subprocess.run(["git", "fetch", "--no-tags", "origin", AUTH_COMMIT],
                   cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    require(git("rev-parse", AUTH_COMMIT + ":" + AUTH_PATH) == AUTH_BLOB,
            "AUTHORITATIVE CLASSIFIER IDENTITY MISMATCH")
    denied = [k for k, v in os.environ.items() if v and
              (k in {"DATABASE_URL", "DIRECT_URL", "PGHOST", "PGUSER",
                     "PGPASSWORD", "PGDATABASE"} or
               k.startswith(("NEON_", "POSTGRES_", "SUPABASE_DB_")))]
    require(not denied, "DB_CREDENTIAL_PRESENT:" + ",".join(denied))


def load_pilot():
    spec = importlib.util.spec_from_file_location("unchanged_expansion_pilot_for_acceptance", PILOT_MODULE)
    p = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(p)

    def verified_predecessor():
        doc = json.loads((ROOT / PREDECESSOR_FREEZE_PATH).read_text(encoding="utf-8"))
        m = doc["selected_source_set_manifest"]
        encodings = (
            canonical(m),
            json.dumps(m, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"),
            (json.dumps(m, sort_keys=True, ensure_ascii=False, indent=2) + "\n").encode("utf-8"),
        )
        require(PREDECESSOR_MANIFEST_SHA in {sha256(x) for x in encodings},
                "PREDECESSOR_MANIFEST_SHA_MISMATCH")
        require(doc["selected_source_set_manifest_sha256"] == PREDECESSOR_MANIFEST_SHA,
                "PREDECESSOR_MANIFEST_REFERENCE_CHANGED")
        require(m["included_source_families"] == SOURCES[:12], "PREDECESSOR_SOURCES_CHANGED")
        require(m["classifier_commit"] == AUTH_COMMIT and m["classifier_blob_sha"] == AUTH_BLOB,
                "PREDECESSOR_CLASSIFIER_CHANGED")
        require(m["corpus_hashes_sha256"] == CORPUS_HASHES, "PREDECESSOR_CORPUS_CHANGED")
        require(m["cohort_manifest"]["episodes"] == 67 and
                m["cohort_manifest"]["known_positives"] == 48 and
                m["cohort_manifest"]["holds"] == 19 and
                m["cohort_manifest"]["sha256_of_canonical_sorted_67_episode_ids"] == COHORT_IDENTITY_SHA,
                "PREDECESSOR_COHORT_CHANGED")
        return m

    # Only override the pilot's branch-diff check. Original admission,
    # candidate construction, offline replay and classifier are untouched.
    p.verification = verified_predecessor
    return p


def compare_fingerprints(current, previous):
    for fp in (current, previous):
        require(len(fp["candidate_rows"]) == 67 and len(fp["episode_verdicts"]) == 67,
                "EXPANSION-3 ACCEPTANCE REPLAY MISMATCH:COHORT_SIZE")
    c = {e["episode_id"]: e for e in current["candidate_rows"]}
    p = {e["episode_id"]: e for e in previous["candidate_rows"]}
    cv = dict(current["episode_verdicts"])
    pv = dict(previous["episode_verdicts"])
    ids = sorted(set(c) | set(p) | set(cv) | set(pv))
    require(len(c) == len(p) == len(cv) == len(pv) == len(ids) == 67,
            "EXPANSION-3 ACCEPTANCE REPLAY MISMATCH:EPISODE_IDS")
    candidate_ok = classifier_ok = verdict_ok = 0
    changed = []
    for eid in ids:
        fields = []
        if c[eid]["candidate_ids"] == p[eid]["candidate_ids"] and c[eid]["candidate_count"] == p[eid]["candidate_count"]:
            candidate_ok += 1
        else:
            fields.extend(("candidate_ids", "candidate_count"))
        if c[eid]["candidate_outcomes"] == p[eid]["candidate_outcomes"]:
            classifier_ok += 1
        else:
            fields.extend(("candidate_classifier_outcome", "classifier_episode_binding"))
        if cv[eid] == pv[eid]:
            verdict_ok += 1
        else:
            fields.append("final_episode_verdict")
        if fields:
            changed.append({"episode_id": eid, "fields": sorted(set(fields))})
    if changed:
        raise RuntimeError("EXPANSION-3 ACCEPTANCE REPLAY MISMATCH:" +
                           json.dumps(changed, sort_keys=True))
    return {
        "candidate_set_equality": candidate_ok,
        "classifier_outcome_equality": classifier_ok,
        "episode_verdict_equality": verdict_ok,
        "denominator": 67,
        "differing_episodes": changed,
    }


def metric_gate(rows, p, baseline):
    positive = [r for r in rows if r["truth_label"] in POS]
    holds = [r for r in rows if r["truth_label"] == "HOLD_CONTROL"]
    require(len(positive) == 48 and len(holds) == 19, "COHORT_LABEL_GATE_FAILED")
    summary = p.summarize(rows, ADDITIONS, baseline)
    metrics = {
        "eligible_positive_episodes": sum(x["candidate_count"] > 0 for x in positive),
        "candidate_covered_positives": sum(x["candidate_count"] > 0 for x in positive),
        "candidate_recall_pct": round(100 * sum(x["candidate_count"] > 0 for x in positive) / 48, 3),
        "strict_positive_episodes": sum(x["final"] == "STRICT_EVENT_POSITIVE" for x in positive),
        "sensitivity_positive_episodes": sum(x["final"] == "SENSITIVITY_EVENT_POSITIVE" for x in positive),
        "final_positive_episodes": sum(x["final"] in POS for x in positive),
        "final_positive_recall_pct": round(100 * sum(x["final"] in POS for x in positive) / 48, 3),
        "holds_with_candidate": sum(x["candidate_count"] > 0 for x in holds),
        "hold_strict": sum(x["final"] == "STRICT_EVENT_POSITIVE" for x in holds),
        "hold_sensitivity": sum(x["final"] == "SENSITIVITY_EVENT_POSITIVE" for x in holds),
    }
    expected = {
        "eligible_positive_episodes": 31,
        "candidate_covered_positives": 31,
        "candidate_recall_pct": 64.583,
        "strict_positive_episodes": 3,
        "sensitivity_positive_episodes": 2,
        "final_positive_episodes": 5,
        "final_positive_recall_pct": 10.417,
        "holds_with_candidate": 13,
        "hold_strict": 2,
        "hold_sensitivity": 0,
    }
    require(metrics == expected, "EXPANSION-3 ACCEPTANCE REPLAY MISMATCH:METRIC_GATE:" +
            json.dumps(metrics, sort_keys=True))
    positive_holds = {r["episode_id"] for r in holds if r["final"] in POS}
    require(positive_holds == EXPECTED_HOLDS and
            not summary["new_uncleared_hold_promotions"] and
            summary["unique_positive_hold_episode_ids"] == sorted(EXPECTED_HOLDS),
            "HOLD SAFETY ACCEPTANCE FAILED:UNEXPECTED_POSITIVE_HOLD")
    clearance = {h["episode_id"]: h["clearance"] for h in summary["hold_safety_accounting"]}
    require(clearance == {
        "e56cdca45ed5b1cd7b0b9746": "EXACT_PRECLEARED_SUSPILNE_IDENTITY",
        "f06c52e0ed82b44792ec2ec7": "PREEXISTING_BASELINE_HOLD",
    }, "HOLD SAFETY ACCEPTANCE FAILED:CLEARANCE_IDENTITY")
    by = {e["episode_id"]: e for e in rows}
    e56 = by["e56cdca45ed5b1cd7b0b9746"]
    require(any(all(c.get(k) == value for k, value in p.CLEARANCE.items()) for c in e56["candidates"]),
            "HOLD SAFETY ACCEPTANCE FAILED:E56_FROZEN_EVIDENCE")
    f06 = by["f06c52e0ed82b44792ec2ec7"]
    ref = next(b for b in baseline if b["episode_id"] == f06["episode_id"])
    require(ref["final"] == "STRICT_EVENT_POSITIVE" and
            any(c["candidate_id"] == "7e17816122c34aed4440a768" and
                c["classifier_outcome"] == "approved_strict" and
                c["classifier_episode_id"] == f06["episode_id"] for c in f06["candidates"]),
            "HOLD SAFETY ACCEPTANCE FAILED:F06_PREEXISTING_BASELINE")
    return metrics, summary["hold_safety_accounting"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-dir", type=Path, required=True)
    parser.add_argument("--prior-replay", type=Path, required=True)
    parser.add_argument("--fingerprint-a", type=Path, required=True)
    parser.add_argument("--fingerprint-b", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    verify_identity()
    p = load_pilot()
    pilot_bytes = (ROOT / PILOT_PATH).read_bytes()
    pilot = json.loads(pilot_bytes)
    require(pilot["provisional_best_name"] == "EXPANSION-3" and
            pilot["provisional_best_added_families"] == list(ADDITIONS) and
            pilot["cumulative_results"]["EXPANSION-3"]["included_source_families"] == SOURCES and
            pilot["classifier_commit"] == AUTH_COMMIT and pilot["classifier_blob"] == AUTH_BLOB and
            pilot["immutable_corpus_hashes"] == CORPUS_HASHES and
            pilot["repeated_replay_proof"]["episode_verdicts_equal_count"] == 67,
            "PILOT_PROVENANCE_NOT_ACCEPTED")
    prior_fingerprint = json.loads(args.fingerprint_a.read_text(encoding="utf-8"))
    second_fingerprint = json.loads(args.fingerprint_b.read_text(encoding="utf-8"))
    require(prior_fingerprint == second_fingerprint, "PILOT_FINGERPRINTS_DISAGREE")
    require(sha256(canonical(prior_fingerprint)) ==
            pilot["repeated_replay_proof"]["replay_fingerprint_sha256"],
            "PILOT_FINGERPRINT_SHA_MISMATCH")

    offline = p.Offline(args.corpus_dir, args.prior_replay)
    try:
        require(offline.manifest["included_source_families"] == SOURCES[:12],
                "PREDECESSOR_SOURCE_SET_CHANGED")
        require(all(x in offline.passing for x in ADDITIONS),
                "EXPANSION3_QUALITY_GATE_FAILED")
        actual_sources = ({x[0] for x in offline.p.SOURCE_ORDER if x[0] != "generic_search"}
                          | set(p.BASE_SOURCES) | set(ADDITIONS))
        require(actual_sources == set(SOURCES) and len(SOURCES) == len(set(SOURCES)) == 15,
                "SOURCE_SET_SCOPE_INVALID")
        # EXACTLY ONE NEW authoritative pass over the 67 development episodes.
        # Offline.replay constructs fresh candidates and invokes classify_episode.
        rows = offline.replay(ADDITIONS)
        require(len(rows) == 67 and len({r["episode_id"] for r in rows}) == 67,
                "ACCEPTANCE_REPLAY_NOT_67")
        require({c["family"] for r in rows for c in r["candidates"]} <= set(SOURCES),
                "EXTRANEOUS_SOURCE_FAMILY")
        fingerprint = json.loads(canonical(p.fingerprint(rows)))
        comparisons = compare_fingerprints(fingerprint, prior_fingerprint)
        baseline_rows = offline.prior["results"]["STAGE2 SINGLE war.telegraf.com.ua"]["per_episode"]
        metrics, hold_safety = metric_gate(rows, p, baseline_rows)
        old_manifest = offline.manifest
    finally:
        offline.close()

    run_id = os.environ.get("GITHUB_RUN_ID", "")
    head_sha = os.environ.get("GITHUB_SHA", "")
    require(run_id.isdigit() and len(head_sha) == 40, "ACCEPTANCE_PROOF_RUN_IDENTITY_MISSING")
    network = {"publisher": 0, "google_search": 0, "telegram": 0,
               "new_wrapper_resolutions": 0, "new_native_acquisitions": 0}
    acceptance_identity = {
        "proof_branch": PROOF_BRANCH,
        "proof_run_id": int(run_id),
        "proof_head_sha": head_sha,
        "proof_artifact_name": ARTIFACT_NAME,
        "candidate_equality": 67,
        "classifier_outcome_equality": 67,
        "episode_verdict_equality": 67,
        "evidence_network_fetches": network,
    }
    expanded_manifest = {
        "schema": "kyiv-immutable-expanded-development-source-set-manifest-v1",
        "configuration_id": "EXPANSION-3",
        "semantic_predecessor_commit": SEMANTIC_BASE,
        "predecessor_manifest_sha256": PREDECESSOR_MANIFEST_SHA,
        "pilot_provenance": {
            "pilot_run_id": PILOT_RUN, "pilot_proof_commit": PILOT_COMMIT,
            "pilot_json_sha256": PILOT_SHA256, "pilot_actions_artifact_id": PILOT_ARTIFACT,
        },
        "acceptance_replay_provenance": acceptance_identity,
        "classifier_commit": AUTH_COMMIT,
        "classifier_path": AUTH_PATH,
        "classifier_blob_sha": AUTH_BLOB,
        "immutable_corpus": {
            "acquisition_run_id": 37916038826, "acquisition_artifact_id": 11608819645,
            "original_replay_artifact_id": 11609004684, "payload_hashes_sha256": CORPUS_HASHES,
            "native_to_normalized_exact_text_identity_verified": True,
        },
        "cohort_manifest": old_manifest["cohort_manifest"],
        "source_family_count": 15,
        "included_source_families": SOURCES,
        "newly_added_families": list(ADDITIONS),
        "source_domain_eligibility_rules": {
            "unchanged_predecessor_rules": old_manifest["source_domain_eligibility_rules"],
            "new_exact_source_hostnames": {
                "5.ua": "5.ua", "zaxid.net": "zaxid.net",
                "kyiv.novyny.live": "kyiv.novyny.live",
            },
            "family_from_frozen_normalized_source_family": True,
            "hostname_normalization": "lowercase, remove initial www. only",
            "alias_expansion": False, "domain_broadening": False,
            "new_quality_gate": "unchanged prior stage2 family-quality predicate",
            "candidate_admission": "unchanged original runner: native text, published_at, window [-6h,+24h], attack regex, exact city",
            "candidate_deduplication": "source family plus deterministic native candidate_id",
        },
        "accepted_performance": metrics,
        "hold_safety_provenance": {
            "positive_hold_episode_ids": sorted(EXPECTED_HOLDS),
            "e56_exact_precleared_evidence": {
                "episode_id": "e56cdca45ed5b1cd7b0b9746",
                **p.CLEARANCE,
                "forensic_verdict": "FROZEN EVIDENCE CONFIRMS TARGET EPISODE",
                "clearance_only_this_frozen_evidence": True,
            },
            "f06_preexisting_baseline_hold": {
                "episode_id": "f06c52e0ed82b44792ec2ec7",
                "status": "PREEXISTING_BASELINE_HOLD",
                "new_forensic_adjudication": False,
            },
            "new_uncleared_hold_promotions": 0,
        },
        "safety": {
            "blind_per_episode_inspected": False,
            "historical_backfill_started": False,
            "neon_writes": 0, "production_mutations": 0,
            "production_source_strategy_changed": False,
            "independent_validation_readiness": "NOT READY",
        },
    }
    expanded_sha = sha256(canonical(expanded_manifest))
    proof = {
        "schema": "kyiv-expansion3-authoritative-offline-acceptance-v1",
        "result": "ALL_ACCEPTANCE_GATES_PASS",
        "acceptance_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "semantic_predecessor_commit": SEMANTIC_BASE,
        "predecessor_manifest_sha256": PREDECESSOR_MANIFEST_SHA,
        "pilot_proof_commit": PILOT_COMMIT,
        "pilot_run_id": PILOT_RUN, "pilot_json_sha256": PILOT_SHA256,
        "proof_branch": PROOF_BRANCH, "proof_run_id": int(run_id),
        "proof_head_sha": head_sha, "proof_artifact_name": ARTIFACT_NAME,
        "authoritative_classifier_commit": AUTH_COMMIT,
        "authoritative_classifier_blob": AUTH_BLOB,
        "immutable_corpus_hashes": CORPUS_HASHES,
        "cohort_manifest": old_manifest["cohort_manifest"],
        "source_families": SOURCES,
        "episode_classifier_traces_and_verdicts": rows,
        "candidate_sets": [{
            "episode_id": r["episode_id"], "candidate_count": r["candidate_count"],
            "candidates": [{"candidate_id": c["candidate_id"], "source_family": c["family"],
                            "frozen_url": c["url"], "frozen_text_sha256": c["text_sha256"]}
                           for c in r["candidates"]]
        } for r in rows],
        "pilot_expansion3_comparison": comparisons,
        "accepted_performance": metrics,
        "hold_safety_provenance": hold_safety,
        "new_uncleared_hold_promotions": 0,
        "evidence_network_fetches": network,
        "evidence_network_hard_disabled": True,
        "no_new_discovery_or_native_acquisition": True,
        "blind_per_episode_inspected": False,
        "historical_backfill_started": False,
        "neon_writes": 0,
        "production_mutations": 0,
        "expanded_development_manifest": expanded_manifest,
        "expanded_development_manifest_canonicalization": "UTF-8 JSON sort_keys=True ensure_ascii=False separators=(',', ':') plus one LF",
        "expanded_development_manifest_sha256": expanded_sha,
    }
    args.output.write_bytes(canonical(proof))
    print("ACCEPTANCE_PROOF_RESULT=ALL_ACCEPTANCE_GATES_PASS", flush=True)
    print("ACCEPTANCE_METRICS_JSON=" + json.dumps(metrics, sort_keys=True), flush=True)
    print("ACCEPTANCE_EQUALITY_JSON=" + json.dumps(comparisons, sort_keys=True), flush=True)
    print("EXPANDED_MANIFEST_SHA256=" + expanded_sha, flush=True)
    print("EXPANDED_MANIFEST_JSON=" +
          json.dumps(expanded_manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")),
          flush=True)
    print("ACCEPTANCE_PROOF_JSON_SHA256=" + sha256(args.output.read_bytes()), flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("ACCEPTANCE_PROOF_FAILURE=" + type(exc).__name__ + ":" + str(exc),
              file=sys.stderr, flush=True)
        raise
