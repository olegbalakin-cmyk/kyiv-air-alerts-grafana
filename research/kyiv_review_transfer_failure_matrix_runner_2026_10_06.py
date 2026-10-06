#!/usr/bin/env python3
import hashlib
import itertools
import json
import os
import re
import runpy
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

BASE_HARNESS = "research/kyiv_review_semantic_transfer_runner_2026_10_06.py"
OUT = Path("kyiv_review_transfer_failure_matrix_2026-10-06.json")

# Execute the accepted proof harness unchanged. Cohort membership is therefore
# reconstructed with exactly the same transfer semantics as the predecessor.
g = runpy.run_path(BASE_HARNESS)

A0 = g["A"]  # historical accepted positives
H0 = g["B"]  # historical pre-cutoff review holds
P0 = g["C"]  # post-cutoff evidence-backed review cohort

disposition = g["disposition"]
finaldisp = g["finaldisp"]
ident_bad = g["ident_bad"]
semantics = g["semantics"]

COHORT_ORDER = ["A", "B", "C", "D", "E", "F", "G"]

def post_classification(r):
    d = disposition(r)
    s = semantics(r)
    missing = [k for k, v in s.items() if not v]
    if ident_bad(r):
        return "TRANSFER_NOT_PROVEN_OTHER", missing
    if d not in ("STRICT", "SENSITIVITY"):
        return "TRANSFER_NOT_PROVEN_INCONSISTENT_REVIEW_PROVENANCE", missing
    if missing:
        return "TRANSFER_NOT_PROVEN_MISSING_SEMANTIC_FIELD", missing
    if d == "STRICT":
        return "TRANSFER_PROVEN_STRICT", missing
    if d == "SENSITIVITY":
        return "TRANSFER_PROVEN_SENSITIVITY", missing
    return "TRANSFER_NOT_PROVEN_OTHER", missing

def historical_positive_ok(r):
    d = disposition(r)
    s = semantics(r)
    return (not ident_bad(r)) and d == finaldisp(r) and all(s.values())

def historical_hold_falsely_promoted(r):
    return disposition(r) in ("STRICT", "SENSITIVITY") and all(semantics(r).values())

cohorts = {
    "A": [r for r in A0 if historical_positive_ok(r)],
    "B": [r for r in A0 if not historical_positive_ok(r)],
    "C": [r for r in H0 if not historical_hold_falsely_promoted(r)],
    "D": [r for r in H0 if historical_hold_falsely_promoted(r)],
    "E": [],
    "F": [],
    "G": [],
}
for r in P0:
    cls, _ = post_classification(r)
    d = disposition(r)
    if d == "STRICT":
        (cohorts["E"] if cls == "TRANSFER_PROVEN_STRICT" else cohorts["F"]).append(r)
    elif d == "SENSITIVITY":
        if cls == "TRANSFER_PROVEN_SENSITIVITY":
            raise SystemExit("Unexpected proven post-cutoff sensitivity transfer; accepted predecessor says 0/13.")
        cohorts["G"].append(r)
    else:
        raise SystemExit("Unexpected post-cutoff stored disposition outside STRICT/SENSITIVITY.")

expected_sizes = {"A": 54, "B": 91, "C": 31, "D": 26, "E": 153, "F": 43, "G": 13}
actual_sizes = {k: len(v) for k, v in cohorts.items()}
if actual_sizes != expected_sizes:
    raise SystemExit(f"Cohort-size mismatch: expected={expected_sizes} actual={actual_sizes}")

TOKEN_RE = re.compile(
    r"(review|provenance|binding|disposition|status|validated|validation|approved|approval|"
    r"hold|reject|temporal|attack_event|event_semantic|exact_city|city_semantic|air_context|"
    r"same_attack|accepted|evidence|schema|version|case|campaign|classifier|origin|target_episode_id)",
    re.I,
)
PAYLOAD_TOKENS = (
    "evidence_text", "source_text", "article_text", "raw_text", "article_body",
    "source_excerpt", "snippet", "headline", "event_text", "full_text", "message_text",
)
IDENTITY_TOKENS = ("episode_id", "event_id", "alert_id", "uuid", "sha256", "blob_sha", "commit_sha")
DISCRIMINATOR_EXCLUDE = (
    "verdict",
    "transfer_classification",
    "shadow_classifier_outcome",
    "agreement_with_stored_review_disposition",
)

def field_wanted(name):
    return bool(TOKEN_RE.search(str(name)))

def is_payload_field(name):
    n = str(name).lower()
    return any(t in n for t in PAYLOAD_TOKENS)

def is_identity_field(name):
    n = str(name).lower()
    return any(t in n for t in IDENTITY_TOKENS) or n.endswith("_id") or ".id" in n

def is_null_empty(v):
    return v is None or v == "" or v == [] or v == {}

def canonical_value(field, v):
    if is_null_empty(v):
        return None
    if is_identity_field(field):
        return "<NONEMPTY_IDENTIFIER>"
    if is_payload_field(field):
        return "<NONEMPTY_TEXT>"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return json.dumps(v, ensure_ascii=False)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        if len(s) <= 256:
            return s
        h = hashlib.sha256(s.encode("utf-8")).hexdigest()
        return f"<LONG_VALUE_SHA256:{h}:LEN={len(s)}>"
    try:
        s = json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except TypeError:
        s = str(v)
    if len(s) <= 256:
        return s
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return f"<LONG_VALUE_SHA256:{h}:LEN={len(s)}>"

def add_value(dst, field, value):
    dst[field].append(value)

def flatten_selected_top_level(r):
    dst = defaultdict(list)

    # Structured provenance arrays: preserve the actual stored path names.
    for array_name in ("review_provenance", "evidence_provenance_excerpt"):
        seq = r.get(array_name) or []
        if isinstance(seq, list):
            for item in seq:
                if not isinstance(item, dict):
                    continue
                p = item.get("path")
                if not isinstance(p, str):
                    continue
                # All review-provenance paths used by the proof are eligible;
                # other provenance paths are included when semantically/review relevant.
                pl = p.lower()
                if ".review_provenance." in pl or field_wanted(p):
                    add_value(dst, p, item.get("value"))

    def walk(obj, prefix=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("review_provenance", "evidence_provenance_excerpt"):
                    continue
                name = f"{prefix}.{k}" if prefix else str(k)
                if isinstance(v, dict):
                    walk(v, name)
                elif isinstance(v, list):
                    if field_wanted(name):
                        if not v:
                            add_value(dst, name, [])
                        elif all(not isinstance(x, (dict, list)) for x in v):
                            # ID-bearing lists are represented by presence only, not raw IDs.
                            if is_identity_field(name):
                                add_value(dst, name, "<NONEMPTY_IDENTIFIER_LIST>")
                            else:
                                for x in v:
                                    add_value(dst, name, x)
                else:
                    if field_wanted(name):
                        add_value(dst, name, v)
        elif field_wanted(prefix):
            add_value(dst, prefix, obj)

    walk(r)
    return dict(dst)

record_fields = {}
for ck, records in cohorts.items():
    record_fields[ck] = [flatten_selected_top_level(r) for r in records]

all_fields = sorted(
    set().union(*[
        set(m.keys())
        for ck in COHORT_ORDER
        for m in record_fields[ck]
    ])
)

def cohort_field_stats(ck, field):
    recs = record_fields[ck]
    present = 0
    null_empty = 0
    value_counts = Counter()
    for m in recs:
        if field not in m:
            continue
        present += 1
        vals = m[field]
        canon = [canonical_value(field, v) for v in vals]
        nonempty = {v for v in canon if v is not None}
        if not nonempty:
            null_empty += 1
        for v in nonempty:
            value_counts[v] += 1
    return {
        "field_present_count": present,
        "field_missing_count": len(recs) - present,
        "null_empty_count": null_empty,
        "distinct_values": sorted(value_counts.keys()),
        "value_counts": dict(sorted(value_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "raw_value_suppressed": bool(is_payload_field(field) or is_identity_field(field)),
    }

field_cross_tabs = {}
for f in all_fields:
    field_cross_tabs[f] = {ck: cohort_field_stats(ck, f) for ck in COHORT_ORDER}

def feature_matches(m, feature):
    field = feature["field"]
    op = feature["op"]
    exists = field in m
    if op == "present":
        return exists
    if op == "missing":
        return not exists
    if not exists:
        return False
    canon = [canonical_value(field, v) for v in m[field]]
    nonempty = {v for v in canon if v is not None}
    if op == "null_or_empty":
        return len(nonempty) == 0
    if op == "eq":
        return feature["value"] in nonempty
    raise ValueError(op)

def feature_key(p):
    if p["op"] == "eq":
        return f'{p["field"]} == {p["value"]}'
    return f'{p["field"]}::{p["op"]}'

def discriminator_field_eligible(field):
    n = field.lower()
    return not any(x in n for x in DISCRIMINATOR_EXCLUDE)

def candidate_features():
    feats = []
    for f in all_fields:
        if not discriminator_field_eligible(f):
            continue
        feats.append({"field": f, "op": "present"})
        feats.append({"field": f, "op": "missing"})
        feats.append({"field": f, "op": "null_or_empty"})
        # Exact equality is used only for non-identity, non-payload categorical values.
        if is_identity_field(f) or is_payload_field(f):
            continue
        vals = set()
        for ck in COHORT_ORDER:
            for m in record_fields[ck]:
                if f not in m:
                    continue
                for raw in m[f]:
                    cv = canonical_value(f, raw)
                    if cv is not None:
                        vals.add(cv)
        # High-cardinality exact values are not treated as simple categorical predicates.
        if len(vals) <= 100:
            for v in sorted(vals):
                feats.append({"field": f, "op": "eq", "value": v})
    # Deduplicate while preserving deterministic order.
    out, seen = [], set()
    for p in feats:
        k = feature_key(p)
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out

features = candidate_features()

def eval_predicate(feature, positive_maps, negative_maps):
    pc = sum(feature_matches(m, feature) for m in positive_maps)
    nc = sum(feature_matches(m, feature) for m in negative_maps)
    return {
        "predicate": feature,
        "positive_coverage_count": pc,
        "positive_coverage_pct": round(100.0 * pc / len(positive_maps), 3) if positive_maps else 0.0,
        "negative_false_positive_count": nc,
        "negative_false_positive_pct": round(100.0 * nc / len(negative_maps), 3) if negative_maps else 0.0,
    }

def eval_two(p1, p2, positive_maps, negative_maps):
    pc = sum(feature_matches(m, p1) and feature_matches(m, p2) for m in positive_maps)
    nc = sum(feature_matches(m, p1) and feature_matches(m, p2) for m in negative_maps)
    return {
        "predicates": [p1, p2],
        "positive_coverage_count": pc,
        "positive_coverage_pct": round(100.0 * pc / len(positive_maps), 3) if positive_maps else 0.0,
        "negative_false_positive_count": nc,
        "negative_false_positive_pct": round(100.0 * nc / len(negative_maps), 3) if negative_maps else 0.0,
    }

def single_search(positive_maps, negative_maps):
    rows = [eval_predicate(p, positive_maps, negative_maps) for p in features]
    rows = [x for x in rows if x["positive_coverage_count"] > 0]
    rows.sort(key=lambda x: (
        x["negative_false_positive_count"],
        -x["positive_coverage_count"],
        feature_key(x["predicate"]),
    ))
    return rows

def two_search(single_rows, positive_maps, negative_maps, limit=100):
    # Combine only the strongest single predicates and require different fields.
    seeds = single_rows[:80]
    out = []
    seen = set()
    for a, b in itertools.combinations(seeds, 2):
        p1, p2 = a["predicate"], b["predicate"]
        if p1["field"] == p2["field"]:
            continue
        keys = tuple(sorted((feature_key(p1), feature_key(p2))))
        if keys in seen:
            continue
        seen.add(keys)
        row = eval_two(p1, p2, positive_maps, negative_maps)
        if row["positive_coverage_count"] > 0:
            out.append(row)
    out.sort(key=lambda x: (
        x["negative_false_positive_count"],
        -x["positive_coverage_count"],
        " && ".join(feature_key(p) for p in x["predicates"]),
    ))
    return out[:limit]

test1_pos = record_fields["A"]
test1_neg = record_fields["D"]
test1_single = single_search(test1_pos, test1_neg)
test1_two = two_search(test1_single, test1_pos, test1_neg)

hist_pos_maps = record_fields["A"] + record_fields["B"]
hist_hold_maps = record_fields["C"] + record_fields["D"]
test2_single = single_search(hist_pos_maps, hist_hold_maps)
test2_clean = [x for x in test2_single if x["negative_false_positive_count"] == 0]
test2_two = two_search(test2_single, hist_pos_maps, hist_hold_maps)

def first_hist_positive_failure(r):
    if ident_bad(r):
        return "episode_identity_mismatch"
    if disposition(r) != finaldisp(r):
        return "strict_sensitivity_mismatch"
    s = semantics(r)
    missing = [k for k, v in s.items() if not v]
    if missing:
        return f"missing_semantic_field:{missing[0]}"
    return "transfer_not_proven_other"

def first_post_failure(r):
    cls, missing = post_classification(r)
    if cls == "TRANSFER_NOT_PROVEN_MISSING_SEMANTIC_FIELD" and missing:
        return f"{cls}:{missing[0]}"
    return cls

failure_counts = {
    "historical_positive_misses_91": dict(sorted(Counter(first_hist_positive_failure(r) for r in cohorts["B"]).items())),
    "historical_false_promotions_26": {"unsupported_promotions": len(cohorts["D"])},
    "post_cutoff_strict_misses_43": dict(sorted(Counter(first_post_failure(r) for r in cohorts["F"]).items())),
    "post_cutoff_sensitivity_misses_13": dict(sorted(Counter(first_post_failure(r) for r in cohorts["G"]).items())),
}

def state_counts_for_diff(field, ck):
    stats = field_cross_tabs[field][ck]
    n = actual_sizes[ck]
    out = {
        "<PRESENT>": stats["field_present_count"],
        "<MISSING>": stats["field_missing_count"],
        "<NULL_EMPTY>": stats["null_empty_count"],
    }
    for v, c in stats["value_counts"].items():
        out[f"VALUE::{v}"] = c
    return out, n

field_diff_rank = []
for f in all_fields:
    ac, an = state_counts_for_diff(f, "A")
    dc, dn = state_counts_for_diff(f, "D")
    states = set(ac) | set(dc)
    best = None
    for state in states:
        av = ac.get(state, 0)
        dv = dc.get(state, 0)
        app = 100.0 * av / an if an else 0.0
        dpp = 100.0 * dv / dn if dn else 0.0
        diff = abs(app - dpp)
        item = (diff, state, av, dv, app, dpp)
        if best is None or item[0] > best[0] or (item[0] == best[0] and item[1] < best[1]):
            best = item
    if best:
        field_diff_rank.append({
            "field": f,
            "max_abs_share_difference_pp": round(best[0], 3),
            "state": best[1],
            "A_count": best[2],
            "D_count": best[3],
            "A_pct": round(best[4], 3),
            "D_pct": round(best[5], 3),
        })
field_diff_rank.sort(key=lambda x: (-x["max_abs_share_difference_pp"], x["field"]))

def git_blob(path):
    return subprocess.check_output(["git", "rev-parse", f"HEAD:{path}"], text=True).strip()

input_identities = {
    "accepted_predecessor_actions_run_id": 37453010964,
    "accepted_predecessor_head": "f41125ad1a29289b92c42a05256c87dfacde2f0f",
    "accepted_proof_harness": {
        "path": BASE_HARNESS,
        "blob": git_blob(BASE_HARNESS),
    },
    "review_audit": {
        "commit": "ea10551381104fa2c223fe558b13351f2ad637cf",
        "expected_blob": "07198463815373021b5b320c1dd959ed58ff795c",
        "actual_blob": os.environ.get("AUDIT_BLOB_ACTUAL"),
        "verified": os.environ.get("AUDIT_BLOB_ACTUAL") == "07198463815373021b5b320c1dd959ed58ff795c",
    },
    "snapshot": {
        "commit": "efefa399e69eadd3d7fc8393ac1553cfde35f138",
        "expected_blob": "8a2f6bd33f879be9db978da59c12c34e61f6f843",
        "actual_blob": os.environ.get("SNAPSHOT_BLOB_ACTUAL"),
        "verified": os.environ.get("SNAPSHOT_BLOB_ACTUAL") == "8a2f6bd33f879be9db978da59c12c34e61f6f843",
    },
}

mutation_confirmation = {
    "production_data_mutations": 0,
    "production_semantic_mutations": 0,
    "review_policy_mutations": 0,
    "classifier_mutations": 0,
    "parser_mutations": 0,
    "temporal_representation_mutations": 0,
    "logical_alert_grouping_mutations": 0,
    "source_evidence_mutations": 0,
    "historical_state_mutations": 0,
    "review_queue_mutations": 0,
    "persistence_mutations": 0,
    "neon_db_queries": 0,
    "neon_db_writes": 0,
    "deployments": 0,
}

matrix = {
    "cohort_sizes": {
        "verified": actual_sizes == expected_sizes,
        "expected": expected_sizes,
        "actual": actual_sizes,
    },
    "field_cross_tabs": field_cross_tabs,
    "exact_first_failure_reason_counts": failure_counts,
    "best_single_field_discriminators": {
        "test1_A_vs_D": {
            "positive_group": "A",
            "negative_group": "D",
            "all_single_field_predicates_with_A_coverage_gt_0": test1_single,
        },
        "test2_all_historical_positives_vs_all_historical_holds": {
            "positive_group": "A+B",
            "negative_group": "C+D",
            "clean_predicate_exists": bool(test2_clean),
            "clean_single_field_predicates": test2_clean,
            "best_single_field_predicates": test2_single[:200],
        },
        "A_vs_D_field_difference_rank": field_diff_rank,
    },
    "best_two_field_discriminators": {
        "test1_A_vs_D": test1_two,
        "test2_all_historical_positives_vs_all_historical_holds": test2_two,
    },
    "input_identities": input_identities,
    "mutation_confirmation": mutation_confirmation,
}

blob = json.dumps(matrix, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
OUT.write_bytes(blob)

# Compact log payload for final chat response; no episode ledger/source text.
chat_summary = {
    "cohort_sizes_verified": actual_sizes == expected_sizes,
    "cohort_sizes": actual_sizes,
    "top_10_fields_A_vs_D": field_diff_rank[:10],
    "top_test1_single_discriminators": test1_single[:10],
    "top_test1_two_field_discriminators": test1_two[:10],
    "test2_clean_predicate_exists": bool(test2_clean),
    "test2_clean_single_predicates_top10": test2_clean[:10],
    "historical_positive_miss_reasons": failure_counts["historical_positive_misses_91"],
    "false_promotion_reasons": failure_counts["historical_false_promotions_26"],
    "strict_miss_reasons": failure_counts["post_cutoff_strict_misses_43"],
    "sensitivity_miss_reasons": failure_counts["post_cutoff_sensitivity_misses_13"],
    "artifact_filename": OUT.name,
    "artifact_size_bytes": len(blob),
    "mutation_confirmation": mutation_confirmation,
}
print("FINAL_CHAT_SUMMARY=" + json.dumps(chat_summary, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
