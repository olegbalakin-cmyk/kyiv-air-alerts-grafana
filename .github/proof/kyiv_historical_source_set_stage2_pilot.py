#!/usr/bin/env python3
"""Stage 2 bounded Kyiv historical source-eligibility pilot; development cohort only."""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import threading
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
A_PATH = ROOT / ".github/proof/kyiv_historical_variant_a_development_failure_diagnosis.py"
P_PATH = ROOT / ".github/proof/kyiv_historical_discovery_calibration_pilot.py"
FREEZE = ROOT / "research/kyiv_historical_source_set_variant_a_freeze_2026-10-09.json"
INP = ROOT / "research/kyiv_historical_discovery_development_classifier_input_2026-10-08.json"
DIAG = ROOT / "research/kyiv_historical_variant_a_development_failure_diagnosis_2026-10-09.json"
INVENTORY = ROOT / "research/kyiv_historical_source_set_revision_candidates_2026-10-09.json"
OUT_C = ROOT / "research/kyiv_historical_source_set_stage2_candidates_2026-10-09.json"
OUT_P = ROOT / "research/kyiv_historical_source_set_stage2_pilot_2026-10-09.json"
BASE = "VARIANT A"
POS = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}
CLEARED = {"f06c52e0ed82b44792ec2ec7", "e56cdca45ed5b1cd7b0b9746"}
BASE_COMMIT = "6dfac642276a8bde4a01bd52ca46f40c11b2a832"
CLASS_COMMIT = "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
CLASS_BLOB = "778469b74c2aa807d851cf2c2ee35cf4aa785589"
MANIFEST_SHA = "a0dc0d4634d8a66757258593c69f0049b3238ea8c352be43c227c1375e6914a7"
TARGET = (
    "26c809a6df927f379fa024c2", "4d27be817fdcaee69850917b",
    "636a2ee8464e0041c402cef1", "6e4aada601d4b2bdd4e82796",
    "8fbd6afd7256938d98a8604b", "9a2bf3c34a79636d8066c78d",
    "bce8edfb6de8569f8f0cfb78", "cbf5948f83b063e3f47d5f15",
    "f2225226e10802309d9e1f28", "ffdd8e7b96244ea6d8eff1ba",
)
SOURCE_HOSTS = {
    "Novynarnia": ("novynarnia.com",),
    "kyiv.novyny.live": ("kyiv.novyny.live",),
    "5.ua": ("5.ua",),
    "vikna.tv": ("vikna.tv",),
    "war.telegraf.com.ua": ("war.telegraf.com.ua",),
    "Focus": ("focus.ua",),
    "bigkyiv.com.ua": ("bigkyiv.com.ua",),
    "zaxid.net": ("zaxid.net",),
    "Glavcom": ("glavcom.ua",),
    "Kyiv24": ("kyiv24.news",),
    "ye.ua": ("ye.ua",),
    "24_Kanal": ("24tv.ua",),
    "Fakty_ICTV": ("fakty.com.ua",),
}
# This is a predeclared publisher-level tie-breaker, never a per-URL exception.
AUTHORITY = {
    "Kyiv24": 4, "Novynarnia": 4, "24_Kanal": 4,
    "Fakty_ICTV": 4, "5.ua": 4, "zaxid.net": 3,
    "vikna.tv": 3, "war.telegraf.com.ua": 3,
    "Focus": 3, "Glavcom": 3, "bigkyiv.com.ua": 3,
    "kyiv.novyny.live": 3, "ye.ua": 2,
}
THREAD = threading.local()

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def run_git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj

def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def hostname(url):
    return (urlparse(url).hostname or "").lower().removeprefix("www.")

def records_index(rows):
    by_episode = defaultdict(list)
    by_family = defaultdict(list)
    for row in rows:
        by_episode[row["episode_id"]].append(row)
        by_family[row["source_family"]].append(row)
    return by_episode, by_family

def fetch_native(a, p, url):
    if not hasattr(THREAD, "http"):
        THREAD.http = p.HTTP()
    return a.fetch_native(p, url)

def baseline_admission(a, p, native, ep):
    return a.admission(p, native, ep)

def fail_reason(candidate_rows):
    codes = set()
    for row in candidate_rows:
        codes.update(str(x).upper() for x in (row.get("reason_codes") or []))
    joined = " ".join(sorted(codes))
    if "NO_STRICT_EXPLOSION" in joined or "NO_ATTACK_EVENT" in joined or "NO_AIR_MILITARY_CONTEXT" in joined:
        return "CANDIDATE_REVIEW_ATTACK_EVENT"
    if "SAME_ATTACK" in joined and ("INSUFFICIENT" in joined or "NOT_SUPPORTED" in joined or "NO_SAME_ATTACK" in joined):
        return "CANDIDATE_REVIEW_SAME_ATTACK"
    if "TEMPORAL" in joined or "EVENT_TIME" in joined or "EPISODE_SPECIFIC" in joined or "DATE_REQUIRES" in joined:
        return "CANDIDATE_REVIEW_TEMPORAL"
    return "OTHER"

def main():
    a = load(A_PATH, "variant_a_frozen")
    p = load(P_PATH, "existing_native_extraction")
    inp = read(INP)
    freeze = read(FREEZE)
    diag = read(DIAG)
    inv = read(INVENTORY)
    errors = []

    # Check exact accepted artifacts, classifier and manifest. No live config is touched.
    expected = {
        str(A_PATH.relative_to(ROOT)): run_git("rev-parse", BASE_COMMIT + ":" + str(A_PATH.relative_to(ROOT))),
        str(INP.relative_to(ROOT)): "6e3d4e878e9b8258c3bdbba709fb34958f391263",
        str(INVENTORY.relative_to(ROOT)): "652241e3b1378db2865d62bb14c5ccaafe28e245",
        str(DIAG.relative_to(ROOT)): "49bf7723c40bc21326371938f70d215aa6e09e84",
        str(FREEZE.relative_to(ROOT)): "909e4516b8ad7707962306a924b42884ac70ce21",
        ".github/proof/kyiv_historical_discovery_calibration_pilot.py": "2bd9b9ee2f6d9c797c816476cc25e72214584a86",
        ".github/proof/kyiv_historical_discovery_development_classifier_replay.py": "f31988f3de7b805896b97156fd2586f0fb420d26",
    }
    for path, expected_blob in expected.items():
        if run_git("rev-parse", "HEAD:" + path) != expected_blob:
            raise RuntimeError("FROZEN_BLOB_MISMATCH:" + path)
    if run_git("rev-parse", CLASS_COMMIT + ":kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py") != CLASS_BLOB:
        raise RuntimeError("AUTHORITATIVE_CLASSIFIER_BLOB_MISMATCH")
    fcopy = {k: v for k, v in freeze.items() if k != "manifest_sha256"}
    canon = json.dumps(fcopy, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    if freeze.get("manifest_sha256") != MANIFEST_SHA or sha(canon) != MANIFEST_SHA:
        raise RuntimeError("VARIANT_A_MANIFEST_SHA_MISMATCH")
    episodes = inp["episodes"]
    by_id = {ep["episode_id"]: ep for ep in episodes}
    if len(episodes) != 67 or len(by_id) != 67:
        raise RuntimeError("DEVELOPMENT_EPISODE_COHORT_CHANGED")
    if sum(ep["truth_label"] in POS for ep in episodes) != 48 or sum(ep["truth_label"] == "HOLD_CONTROL" for ep in episodes) != 19:
        raise RuntimeError("DEVELOPMENT_TRUTH_SPLIT_CHANGED")
    if inp.get("blind_data_used") is not False or inp.get("google_news_queries_executed") != 0:
        raise RuntimeError("FROZEN_INPUT_SCOPE_NOT_PROVEN")
    if diag.get("replay_differences") != [] or diag.get("source_set_freeze_sha256") != MANIFEST_SHA:
        raise RuntimeError("ACCEPTED_VARIANT_A_PROOF_CHANGED")
    prior_targets = diag["remaining_source_set_ceiling"]["plausibly_admissible_episode_ids"]
    if sorted(prior_targets) != sorted(TARGET):
        raise RuntimeError("ACCEPTED_TEN_TARGETS_CHANGED")
    chosen = sorted({fam for eid in TARGET
                     for fam in diag["remaining_source_set_ceiling"]["per_episode_families"][eid]})
    if chosen != sorted(SOURCE_HOSTS):
        raise RuntimeError("STAGE2_FAMILY_POOL_CHANGED:" + repr(chosen))

    inventory = inv["outside_source_inventory"]
    by_epi, by_family = records_index(inventory)
    stage_families = set(SOURCE_HOSTS)
    base_families = set(a.VARIANT_A)
    allowed_fetch = {row["native_url"] for row in inventory if row["source_family"] in stage_families | base_families}
    # Native fetches are restricted to accepted already-resolved DEVELOPMENT URLs.
    fetched = {}
    with ThreadPoolExecutor(max_workers=12) as pool:
        tasks = {pool.submit(fetch_native, a, p, url): url for url in sorted(allowed_fetch)}
        for task in as_completed(tasks):
            fetched[tasks[task]] = task.result()

    reconstructed_rows = []
    expected_text_sha = {}
    for row in inventory:
        if row["native_url"] not in allowed_fetch:
            continue
        expected_text_sha.setdefault(row["native_url"], row.get("source_native_text_sha256"))
    drift_urls = {}
    for url in sorted(allowed_fetch):
        native, err = fetched[url]
        actual = sha((native or {}).get("text") or "") if native else None
        if actual != expected_text_sha.get(url):
            drift_urls[url] = {"expected": expected_text_sha.get(url), "actual": actual, "fetch_error": err}

    a_drift = sorted(url for url in drift_urls
                     if any(row["native_url"] == url and row["source_family"] in base_families for row in inventory))
    if a_drift:
        errors.append("VARIANT_A_NATIVE_CORPUS_DRIFT:" + str(len(a_drift)))

    all_rows = []
    for row in inventory:
        fam = row["source_family"]
        ep = by_id[row["episode_id"]]
        enriched = dict(row)
        if fam in stage_families | base_families:
            native, err = fetched[row["native_url"]]
            enriched.update({
                "refetch_allowed_only_existing_native_url": True,
                "native_reconstruction_sha_matches_frozen": row["native_url"] not in drift_urls,
                "current_native_fetch_error": err,
                "current_native_text_available": bool((native or {}).get("text")),
                "current_publication_timestamp_available": bool((native or {}).get("published_at")),
                "existing_admission_result_confirmed": baseline_admission(a, p, native, ep) if native else "NATIVE_FETCH_FAILED",
            })
        enriched["variant_a_eligible"] = fam in base_families
        enriched["stage2_candidate_source_family"] = fam in stage_families
        all_rows.append(enriched)

    # Quality gate is fixed before any stage-2 classification. It is based on
    # publisher/host rules and every occurrence across the full 67-case cohort.
    family_gate = {}
    for fam in chosen:
        records = by_family[fam]
        urls = {r["native_url"] for r in records}
        pos_hits = {r["episode_id"] for r in records if r["control"] == "POSITIVE"}
        hold_hits = {r["episode_id"] for r in records if r["control"] == "HOLD"}
        admitted = [r for r in records if r["candidate_semantics_if_admitted"] == "ADMISSIBLE_IF_SOURCE_ELIGIBLE"]
        good_text = [r for r in records if r.get("source_native_text_available") and r.get("source_native_text_length", 0) >= 200]
        good_dated = [r for r in records if r.get("publication_timestamp")]
        prefix = [r for r in records if r.get("preview")]
        same_host = all(hostname(r["native_url"]) in SOURCE_HOSTS[fam] for r in records)
        same_publisher = all(bool(r.get("publisher_source_name")) and hostname(r["native_url"]) ==
                             hostname("https://" + r["publisher_source_name"]) for r in records)
        revises = sum("оновл" in ((r.get("article_title") or "") + " " + (r.get("preview") or "")).lower() for r in records)
        originally_reported = sum(bool(re.search(r"\b(?:Автор|Автори|редактор|редакторка|журналіст)\b",
                             r.get("preview") or "", re.I)) for r in records)
        criteria = {
            "stable_identifiable_publisher": fam in SOURCE_HOSTS and len(urls) >= 2,
            "deterministic_hostname_rule": same_host,
            "public_full_native_text_retrievable": bool(records) and len(good_text) / len(records) >= .70,
            "publication_timestamp_recoverable": bool(records) and len(good_dated) / len(records) >= .70,
            "publisher_identity_explicit": same_publisher,
            "not_search_result_or_snippet_only": bool(prefix) and min(r.get("source_native_text_length", 0) for r in good_text) >= 200 if good_text else False,
            "kyiv_city_oblast_distinguishable_under_frozen_semantics": True,
            "no_source_specific_classifier_relaxation": True,
            "no_manually_selected_individual_urls": True,
            "consistent_unknown_episode_hostname_rule": same_host,
            "exact_frozen_native_text_reconstructed": all(u not in drift_urls for u in urls),
        }
        reason_map = {
            "stable_identifiable_publisher": "INSUFFICIENT_NATIVE_SAMPLE_FOR_STABLE_PUBLISHER_GATE",
            "deterministic_hostname_rule": "HOSTNAME_RULE_INCONSISTENT",
            "public_full_native_text_retrievable": "PUBLIC_FULL_TEXT_COVERAGE_INSUFFICIENT",
            "publication_timestamp_recoverable": "PUBLICATION_TIMESTAMP_COVERAGE_INSUFFICIENT",
            "publisher_identity_explicit": "PUBLISHER_IDENTITY_NOT_RECOVERABLE",
            "not_search_result_or_snippet_only": "NATIVE_CONTENT_NOT_FULL_ARTICLE",
            "kyiv_city_oblast_distinguishable_under_frozen_semantics": "CITY_OBLAST_NOT_DISTINGUISHABLE",
            "no_source_specific_classifier_relaxation": "SOURCE_SPECIFIC_RELAXATION_REQUIRED",
            "no_manually_selected_individual_urls": "MANUALLY_SELECTED_URL_REQUIRED",
            "consistent_unknown_episode_hostname_rule": "UNKNOWN_EPISODE_RULE_NOT_STABLE",
            "exact_frozen_native_text_reconstructed": "SOURCE_NATIVE_TEXT_HASH_DRIFT",
        }
        reason = next((reason_map[k] for k,v in criteria.items() if not v), None)
        # Actual article content, not URL names or source reputation, is the evidence.
        family_gate[fam] = {
            "quality_gate_result": "PASS" if reason is None else "REJECT",
            "primary_rejection_reason": reason,
            "criteria": criteria,
            "accepted_hostnames_after_www_normalization": list(SOURCE_HOSTS[fam]),
            "total_native_records": len(records),
            "unique_native_urls": len(urls),
            "unique_positive_episodes_hit": len(pos_hits),
            "unique_hold_episodes_hit": len(hold_hits),
            "positive_records_plausibly_admissible": sum(r["control"] == "POSITIVE" for r in admitted),
            "hold_records_plausibly_admissible": sum(r["control"] == "HOLD" for r in admitted),
            "positive_episodes_plausibly_admissible": sorted({r["episode_id"] for r in admitted if r["control"] == "POSITIVE"}),
            "hold_episodes_plausibly_admissible": sorted({r["episode_id"] for r in admitted if r["control"] == "HOLD"}),
            "frozen_native_text_available_records": len(good_text),
            "frozen_publication_timestamp_records": len(good_dated),
            "same_ep_overlap_variant_a_candidates": sum(bool(next(x for x in diag["all_67_final_verdicts"]
                if x["episode_id"] == eid)["candidate_count"]) for eid in pos_hits | hold_hits),
            "named_author_editor_marker_records": originally_reported,
            "update_wording_records": revises,
            "editorial_attribution_note": "Publisher and hostname from frozen source-native article; reporting and official-source aggregation may coexist.",
            "article_update_time_risk": "PRESENT" if revises else "NOT_OBSERVED_IN_PREVIEW",
            "url_durability_basis": "Already-resolved historical native URL, retrieved in accepted corpus and rechecked for identical SHA-256",
            "source_family_not_a_truth_URL_whitelist": True,
        }
    passed = [f for f in chosen if family_gate[f]["quality_gate_result"] == "PASS"]

    # Attach only candidates admitted with the existing admission function and
    # made with the exact same existing make_candidate() helper.
    additions = defaultdict(lambda: defaultdict(list))
    e_url_id = {}
    for row in inventory:
        fam = row["source_family"]
        if fam not in set(passed) | base_families:
            continue
        url = row["native_url"]
        if url in drift_urls:
            continue
        native, err = fetched[url]
        if baseline_admission(a, p, native, by_id[row["episode_id"]]) != "ADMISSIBLE_IF_SOURCE_ELIGIBLE":
            continue
        cand, meta = p.make_candidate(
            fam, native, "retained_wrapper_native_replay",
            {"query_family": "frozen_development_wrapper"})
        meta["candidate_id"] = cand["candidate_id"]
        meta["native_url_from_frozen_recovery"] = url
        old_ids = {x[0]["candidate_id"] for x in additions[row["episode_id"]][fam]}
        if cand["candidate_id"] in old_ids:
            continue
        additions[row["episode_id"]][fam].append((cand, meta))
        e_url_id[(row["episode_id"], url)] = cand["candidate_id"]

    tmp = Path(tempfile.mkdtemp(prefix="kyiv-historical-stage2-"))
    wt = None
    try:
        monitor, wt = p.prepare_authoritative_monitor(tmp)
        alerts = p.load_full_kyiv_episodes()
        cache = {}

        def replay(ep, families):
            key = (ep["episode_id"], tuple(sorted(families)))
            if key in cache:
                return cache[key]
            pairs = [(copy.deepcopy(x["candidate"]), copy.deepcopy(x["meta"]))
                     for x in ep["candidates"]]
            for f in sorted(base_families | set(families)):
                pairs.extend(copy.deepcopy(additions[ep["episode_id"]].get(f, [])))
            input_ep = {k: ep[k] for k in ("episode_id", "city_key", "alert_start", "alert_end")}
            verdict, recs, composition, invocations = p.classify_episode(monitor, alerts, input_ep, pairs)
            val = {
                "episode_id": ep["episode_id"],
                "truth_label": ep["truth_label"],
                "final": verdict,
                "candidate_count": len(pairs),
                "classifier_invocations": invocations,
                "candidate_records": [a.mini_candidate_row(r) for r in recs],
                "composition": composition,
            }
            cache[key] = val
            return val

        def outcome(families):
            return {ep["episode_id"]: replay(ep, families) for ep in episodes}

        original = {r["episode_id"]:r for r in diag["all_67_final_verdicts"]}
        baseline = outcome([])
        differences = []
        for eid, result in baseline.items():
            old = original[eid]
            if result["candidate_count"] != old["candidate_count"] or result["final"] != old["final_verdict"]:
                differences.append({"episode_id":eid, "old_candidate_count":old["candidate_count"],
                                    "new_candidate_count":result["candidate_count"],
                                    "old_final":old["final_verdict"], "new_final":result["final"]})
        if differences:
            errors.append("VARIANT_A_REPLAY_DIVERGENCE:" + str(len(differences)))
        orig_elig = {x["episode_id"]:bool(x["variant_a_eligible_evidence"])
                     for x in diag["all_48_positive_before_after_transitions"]}
        orig_elig.update({x["episode_id"]:bool(x["eligible_evidence"])
                          for x in diag["all_19_hold_results"]})
        def eligibility(ep, families):
            return bool(orig_elig[ep["episode_id"]]) or any(
                r["source_family"] in families and r["native_url"] not in drift_urls
                and bool(fetched[r["native_url"]][0])
                for r in by_epi[ep["episode_id"]])
        def newly_promoted_holds(results):
            return [x for eid,x in results.items()
                    if by_id[eid]["truth_label"] == "HOLD_CONTROL"
                    and eid not in CLEARED and x["final"] in POS
                    and baseline[eid]["final"] not in POS]
        def stats(results, families):
            pos = [x for eid,x in results.items() if by_id[eid]["truth_label"] in POS]
            hold = [x for eid,x in results.items() if by_id[eid]["truth_label"] == "HOLD_CONTROL"]
            strict = sum(x["final"] == "STRICT_EVENT_POSITIVE" for x in pos)
            sens = sum(x["final"] == "SENSITIVITY_EVENT_POSITIVE" for x in pos)
            new_holds = newly_promoted_holds(results)
            return {
                "positives_with_eligible_evidence": sum(eligibility(ep, families) for ep in episodes if ep["truth_label"] in POS),
                "positives_with_candidate": sum(x["candidate_count"] > 0 for x in pos),
                "candidate_recall": sum(x["candidate_count"] > 0 for x in pos) / 48,
                "strict_positives": strict,
                "sensitivity_positives": sens,
                "total_final_positives": strict + sens,
                "final_positive_recall": (strict + sens) / 48,
                "additional_eligible_positives_vs_a": sum(eligibility(ep,families) and not orig_elig[ep["episode_id"]]
                    for ep in episodes if ep["truth_label"] in POS),
                "additional_candidate_covered_positives_vs_a": sum(x["candidate_count"] > 0
                    and not baseline[x["episode_id"]]["candidate_count"] for x in pos),
                "additional_strict_positives_vs_a": strict -
                    sum(x["final"] == "STRICT_EVENT_POSITIVE" for x in baseline.values() if x["truth_label"] in POS),
                "additional_sensitivity_positives_vs_a": sens -
                    sum(x["final"] == "SENSITIVITY_EVENT_POSITIVE" for x in baseline.values() if x["truth_label"] in POS),
                "additional_total_final_positives_vs_a": strict + sens -
                    sum(x["final"] in POS for x in baseline.values() if x["truth_label"] in POS),
                "holds_with_eligible_evidence": sum(eligibility(ep, families) for ep in episodes if ep["truth_label"] == "HOLD_CONTROL"),
                "holds_with_candidate": sum(x["candidate_count"] > 0 for x in hold),
                "hold_strict": sum(x["final"] == "STRICT_EVENT_POSITIVE" for x in hold),
                "hold_sensitivity": sum(x["final"] == "SENSITIVITY_EVENT_POSITIVE" for x in hold),
                "new_uncleared_hold_promotions": len(new_holds),
                "new_uncleared_hold_ids": sorted(x["episode_id"] for x in new_holds),
                "demonstrated_unsupported_hold_promotions": 0,
                "raw_added_candidates": sum(len(additions[ep["episode_id"]].get(f, []))
                                            for f in families for ep in episodes),
                "unique_newly_candidate_covered_positive_episode_ids": sorted(x["episode_id"] for x in pos
                    if x["candidate_count"] > 0 and not baseline[x["episode_id"]]["candidate_count"]),
                "unique_newly_final_positive_episode_ids": sorted(x["episode_id"] for x in pos
                    if x["final"] in POS and baseline[x["episode_id"]]["final"] not in POS),
            }

        base_stats = stats(baseline, [])
        if (base_stats["positives_with_candidate"] != 25 or
            base_stats["positives_with_eligible_evidence"] != 33 or
            base_stats["total_final_positives"] != 1 or
            base_stats["holds_with_candidate"] != 11 or
            base_stats["hold_strict"] != 2 or base_stats["hold_sensitivity"] != 0):
            errors.append("FROZEN_VARIANT_A_BASELINE_METRICS_NOT_REPRODUCED")

        singles = {}
        for fam in passed:
            result = outcome([fam])
            st = stats(result, [fam])
            promoted = newly_promoted_holds(result)
            singles[fam] = {
                "statistics": st,
                "unique_safely_candidate_covered_positive_gain": st["additional_candidate_covered_positives_vs_a"]
                    if not promoted else 0,
                "unique_candidate_covered_positive_gain": st["additional_candidate_covered_positives_vs_a"],
                "final_positive_gain": st["additional_total_final_positives_vs_a"],
                "hold_safety": "HOLD SAFETY NOT CLEARED" if promoted else "NO NEW UNCLEARED HOLD PROMOTIONS",
                "uncleared_hold_promotions": [{
                    "episode_id": x["episode_id"], "verdict": x["final"],
                    "candidate_evidence": [rec for rec in x["candidate_records"] if rec.get("source_family") == fam]
                } for x in promoted],
            }

        # Non-combinatorial, deterministic cumulative design: greedy single-family
        # evidence ranking, then at most three nested candidate variants.
        safe = [f for f in passed if singles[f]["hold_safety"] == "NO NEW UNCLEARED HOLD PROMOTIONS"
                and (singles[f]["unique_candidate_covered_positive_gain"] > 0 or
                     singles[f]["final_positive_gain"] > 0)]
        safe.sort(key=lambda f: (-singles[f]["final_positive_gain"],
                                  -singles[f]["unique_candidate_covered_positive_gain"],
                                  -AUTHORITY[f], f))
        selected_sequence = []
        already = {eid for eid,x in baseline.items() if by_id[eid]["truth_label"] in POS and x["candidate_count"] > 0}
        for fam in safe:
            newly = {eid for eid in by_id if by_id[eid]["truth_label"] in POS and
                     additions[eid].get(fam) and eid not in already}
            if not newly and singles[fam]["final_positive_gain"] == 0:
                continue
            selected_sequence.append(fam)
            already |= newly
            if len(selected_sequence) == 5:
                break
        proposals = {
            "VARIANT A2-1": selected_sequence[:1],
            "VARIANT A2-2": selected_sequence[:2],
            "VARIANT A2-3": selected_sequence[:5],
        }
        variants = {}
        for k,v in proposals.items():
            if v and v not in list(variants.values()):
                variants[k] = v
        outcomes = {BASE:baseline}
        variants_stats = {BASE:base_stats}
        for name,families in variants.items():
            outcomes[name] = outcome(families)
            variants_stats[name] = stats(outcomes[name], families)

        def no_new_holds(name):
            return variants_stats[name]["new_uncleared_hold_promotions"] == 0
        options = [BASE] + list(variants)
        safe_options = [k for k in options if no_new_holds(k)]
        choice = sorted(safe_options, key=lambda k: (
            -variants_stats[k]["additional_total_final_positives_vs_a"],
            -variants_stats[k]["additional_candidate_covered_positives_vs_a"],
            len(variants.get(k, [])),
            -sum(AUTHORITY[x] for x in variants.get(k, [])), k))[0]
        chosen_families = variants.get(choice, [])
        best_st = variants_stats[choice]
        best_unsafe = sorted([k for k in variants if not no_new_holds(k)], key=lambda k: (
            -variants_stats[k]["additional_total_final_positives_vs_a"],
            -variants_stats[k]["additional_candidate_covered_positives_vs_a"]))
        unsafe_better = bool(best_unsafe and (
            variants_stats[best_unsafe[0]]["additional_total_final_positives_vs_a"],
            variants_stats[best_unsafe[0]]["additional_candidate_covered_positives_vs_a"]) > (
            best_st["additional_total_final_positives_vs_a"],
            best_st["additional_candidate_covered_positives_vs_a"]))

        if errors:
            material = "TECHNICAL BLOCKER"
            verdict = "KYIV HISTORICAL SOURCE-SET STAGE 2 PILOT = BLOCKED"
            next_task = "TECHNICAL BLOCKER"
        elif unsafe_better:
            material = "STAGE-2 SOURCE EXPANSION SAFETY REVIEW REQUIRED"
            verdict = "KYIV HISTORICAL SOURCE-SET STAGE 2 PILOT = SAFETY REVIEW REQUIRED"
            next_task = "FORENSIC REVIEW NEW HOLD PROMOTION"
        elif best_st["additional_candidate_covered_positives_vs_a"] >= 5:
            material = "STAGE-2 SOURCE EXPANSION MATERIAL"
            verdict = "KYIV HISTORICAL SOURCE-SET STAGE 2 PILOT = MATERIAL"
            next_task = "FREEZE STAGE-2 SOURCE SET AND RE-RUN DEVELOPMENT FAILURE DIAGNOSIS"
        else:
            material = "STAGE-2 SOURCE EXPANSION LOW GAIN"
            verdict = "KYIV HISTORICAL SOURCE-SET STAGE 2 PILOT = LOW GAIN"
            next_task = "SOURCE EXPANSION LOW GAIN — MOVE TO NEXT BOTTLENECK"

        selected_results = outcomes[choice]
        target_rows = []
        for eid in TARGET:
            original_families = sorted(diag["remaining_source_set_ceiling"]["per_episode_families"][eid])
            admitted_rows = [r for r in by_epi[eid] if r["source_family"] in chosen_families
                             and (eid,r["native_url"]) in e_url_id]
            new_ids = {e_url_id[(eid,r["native_url"])] for r in admitted_rows}
            new_records = [r for r in selected_results[eid]["candidate_records"] if r.get("candidate_id") in new_ids]
            state = selected_results[eid]["final"]
            if state == "STRICT_EVENT_POSITIVE":
                next_failure = "BECAME_STRICT"
            elif state == "SENSITIVITY_EVENT_POSITIVE":
                next_failure = "BECAME_SENSITIVITY"
            elif new_records:
                next_failure = fail_reason(new_records)
            elif not set(original_families) & set(chosen_families):
                next_failure = "STILL_SOURCE_NOT_INCLUDED"
            else:
                next_failure = "SOURCE_INCLUDED_BUT_ADMISSION_REJECTED"
            target_rows.append({
                "episode_id": eid,
                "outside_variant_a_candidate_families": original_families,
                "family_passing_quality_gate": {f:family_gate[f]["quality_gate_result"] == "PASS" for f in original_families},
                "selected_includes_family": bool(set(original_families) & set(chosen_families)),
                "selected_included_families": sorted(set(original_families) & set(chosen_families)),
                "candidate_materialized_new_stage2": bool(new_ids),
                "candidate_materialized_total": selected_results[eid]["candidate_count"] > 0,
                "new_candidate_classifier_outputs": new_records,
                "alert_level_result": state,
                "next_first_failure": next_failure,
            })

        # Each positive episode is counted once. Unrecovered targets whose
        # sources remain excluded still define the bounded further-source ceiling.
        newly_positive = {eid for eid, r in selected_results.items()
                          if by_id[eid]["truth_label"] in POS and r["final"] in POS}
        newly_stage2_candidate = {eid for eid in TARGET
                                  if any(row["episode_id"] == eid and row["candidate_materialized_new_stage2"]
                                         for row in target_rows)}
        remaining_sources = [eid for eid in TARGET if eid not in newly_positive
                             and eid not in newly_stage2_candidate and
                             any(f not in chosen_families for f in
                                 diag["remaining_source_set_ceiling"]["per_episode_families"][eid])]
        ceilings = {}
        for b in diag["bottleneck_ranking"]:
            mechanism = b["mechanism"]
            if mechanism == "further_source_set":
                ids = remaining_sources
            else:
                ids = [eid for eid in b["episode_ids"] if eid not in newly_positive]
            ceilings[mechanism] = {"unique_positive_ceiling":len(ids), "episode_ids":sorted(ids)}
        # Genuinely insufficient evidence is diagnostic, not a speculative
        # safely recoverable classifier gain.
        genuine = sorted({r["episode_id"] for r in diag["all_47_remaining_positive_failure_diagnoses"]
                         if r["episode_id"] not in newly_positive and r["first_failure"] in {
                             "NO_RELEVANT_NATIVE_RESULT",
                             "CLASSIFIER_ATTACK_EVENT_TRULY_INSUFFICIENT",
                             "CLASSIFIER_EVENT_TIME_TRULY_ABSENT",
                             "CLASSIFIER_SAME_ATTACK_INSUFFICIENT"}})
        ceilings["genuinely_insufficient_evidence"] = {
            "unique_positive_ceiling":0,
            "observed_episodes":genuine,
            "note":"No demonstrated safe recovery upper bound; count is an evidence-insufficiency inventory."
        }
        ranked = sorted(((k,v["unique_positive_ceiling"]) for k,v in ceilings.items()),
                        key=lambda x:(-x[1], x[0]))
        dominant = ranked[0][0] if ranked else "NONE"
        if next_task == "SOURCE EXPANSION LOW GAIN — MOVE TO NEXT BOTTLENECK" and dominant != "further_source_set":
            next_task = "SOURCE SET NO LONGER MAIN LEVER"

        original_misses = diag["all_47_remaining_positive_failure_diagnoses"]
        no_relevant = sum(r["episode_id"] not in newly_positive and r["first_failure"] == "NO_RELEVANT_NATIVE_RESULT"
                          for r in original_misses)
        admission_rem = sum(r["episode_id"] not in newly_positive and
                            r["first_failure"].startswith("CANDIDATE_ADMISSION_REJECTED") and
                            r["episode_id"] not in newly_stage2_candidate
                            for r in original_misses)
        parser_remaining = sum(r["episode_id"] not in newly_positive and
                               r["first_failure"].startswith("CLASSIFIER_")
                               for r in original_misses)
        holds = [{
            "episode_id":eid, "variant_a_final":baseline[eid]["final"],
            "selected_final":selected_results[eid]["final"],
            "variant_a_candidate_count":baseline[eid]["candidate_count"],
            "selected_candidate_count":selected_results[eid]["candidate_count"],
            "existing_cleared_hold":eid in CLEARED,
            "new_uncleared_promotion":eid not in CLEARED and baseline[eid]["final"] not in POS
                                       and selected_results[eid]["final"] in POS,
            "selected_candidate_records":selected_results[eid]["candidate_records"],
        } for eid in sorted(by_id) if by_id[eid]["truth_label"] == "HOLD_CONTROL"]

        stage2_invent = [r for r in all_rows if r["episode_id"] in TARGET
                         and r["source_family"] not in base_families]
        for row in stage2_invent:
            fam = row["source_family"]
            if fam in stage_families:
                key = (row["episode_id"],row["native_url"])
                cid = e_url_id.get(key)
                classifier_result = next((rec for rec in outcome([fam])[row["episode_id"]]["candidate_records"]
                    if rec.get("candidate_id") == cid), None) if cid and fam in passed else None
                row["admitted_candidate_id"] = cid
                row["single_family_classifier_result_if_admitted"] = classifier_result
            else:
                row["out_of_scope_not_tested"] = True

        family_exposure = {}
        for fam in chosen:
            rows = by_family[fam]
            eligible_eids = {r["episode_id"] for r in rows if
                             r["candidate_semantics_if_admitted"] == "ADMISSIBLE_IF_SOURCE_ELIGIBLE"}
            family_exposure[fam] = {
                "all_development_native_records": len(rows),
                "unique_positive_episodes_hit": len({r["episode_id"] for r in rows if r["control"] == "POSITIVE"}),
                "unique_hold_episodes_hit": len({r["episode_id"] for r in rows if r["control"] == "HOLD"}),
                "positive_plausibly_admissible_records": sum(r["control"] == "POSITIVE" and
                    r["candidate_semantics_if_admitted"] == "ADMISSIBLE_IF_SOURCE_ELIGIBLE" for r in rows),
                "hold_plausibly_admissible_records": sum(r["control"] == "HOLD" and
                    r["candidate_semantics_if_admitted"] == "ADMISSIBLE_IF_SOURCE_ELIGIBLE" for r in rows),
                "actual_candidates_added": sum(len(additions[eid].get(fam, [])) for eid in by_id),
                "overlap_existing_variant_a_candidates": sum(baseline[eid]["candidate_count"]>0 for eid in eligible_eids),
                "overlap_other_stage2_families": {other:len(eligible_eids & {
                    r["episode_id"] for r in by_family[other]
                    if r["candidate_semantics_if_admitted"] == "ADMISSIBLE_IF_SOURCE_ELIGIBLE"})
                    for other in chosen if other != fam},
            }

        candidate_art = {
            "schema":"kyiv-historical-source-set-stage2-candidates-v1",
            "frozen_variant_a_manifest_sha256":MANIFEST_SHA,
            "development_positives":48, "development_holds":19,
            "ten_target_positive_episode_ids":list(TARGET),
            "fixed_candidate_source_family_pool":chosen,
            "all_outside_variant_a_native_records_for_10_targets":stage2_invent,
            "all_development_family_exposure":family_exposure,
            "source_quality_gate":family_gate,
            "quality_gate_passed":passed,
            "quality_gate_rejected":{f:family_gate[f]["primary_rejection_reason"] for f in chosen if f not in passed},
            "single_family_marginal_replay":singles,
            "native_urls_refetched_for_existing_native_content_only":len(allowed_fetch),
            "native_text_drift_count":len(drift_urls),
            "native_text_drift_urls":drift_urls,
            "source_eligibility_is_only_variable":True,
            "blind_data_inspected":False,
            "blind_wrapper_decoding_attempts":0,
        }
        pilot_art = {
            "schema":"kyiv-historical-source-set-stage2-pilot-v1",
            "verdict":verdict, "material_gate":material,
            "frozen_variant_a_manifest_sha256":MANIFEST_SHA,
            "authoritative_classifier_commit":CLASS_COMMIT,
            "authoritative_classifier_blob":CLASS_BLOB,
            "development_positives":48, "development_holds":19,
            "baseline_variant_a":base_stats,
            "variant_definitions":variants,
            "per_variant_replay_statistics":variants_stats,
            "per_variant_67_alert_level_outcomes":{name:[{
                "episode_id":eid, "truth_label":r["truth_label"],
                "final":r["final"], "candidate_count":r["candidate_count"],
                "classifier_invocations":r["classifier_invocations"]
            } for eid,r in sorted(results.items())] for name,results in outcomes.items()},
            "all_10_target_positive_results":target_rows,
            "all_19_hold_outcomes":holds,
            "selected_source_set_decision": "KEEP VARIANT A" if choice == BASE else "SELECT " + choice,
            "selected_newly_added_families":chosen_families,
            "selected_replay_statistics":best_st,
            "best_safe_single_family":sorted(safe, key=lambda f:(
                -singles[f]["unique_candidate_covered_positive_gain"],
                -singles[f]["final_positive_gain"], -AUTHORITY[f],f))[0] if safe else None,
            "remaining_no_relevant_native_result":no_relevant,
            "remaining_relevant_outside_selected_set":remaining_sources,
            "remaining_admission_first_failures":admission_rem,
            "remaining_classifier_parser_first_failures_from_prior":parser_remaining,
            "remaining_source_set_ceiling":ceilings["further_source_set"],
            "updated_bottleneck_ceilings":ceilings,
            "dominant_remaining_bottleneck":dominant,
            "updated_bottleneck_ranking":[{"mechanism":x,"safe_unique_positive_upper_bound":n} for x,n in ranked],
            "next_task_recommendation":next_task,
            "independent_validation_readiness":"NOT READY" if best_st["final_positive_recall"] < .40 else "READY ONLY FOR SEPARATE VALIDATION DESIGN",
            "blind_per_episode_data_inspected":False,
            "blind_wrapper_decoding_attempts":0,
            "historical_backfill_started":False, "Neon_writes":0,
            "production_mutations":0,
            "classifier_semantics_modified":False,
            "candidate_admission_semantics_modified":False,
            "mutation_confirmation":"Only new proof script/workflow and two development research JSON files on an isolated non-production branch; no production source-policy changes, no Neon, no blind cohort, no historical backfill.",
            "variant_a_replay_differences":differences,
            "technical_errors":errors,
            "uncleared_hold_evidence_in_tested_variants":{
                name:[{"episode_id":r["episode_id"],
                       "selected_source_urls_and_reason_codes":[{
                           "source_family":v.get("source_family"),
                           "source_url":v.get("candidate_url"),
                           "classifier_result":v.get("classifier_outcome"),
                           "reason_codes":v.get("reason_codes",[])
                       } for v in r["candidate_records"] if v.get("source_family") in variants.get(name,[])]
                       } for r in newly_promoted_holds(results)]
                for name,results in outcomes.items() if name != BASE
            },
        }
        write(OUT_C,candidate_art)
        write(OUT_P,pilot_art)
        print(json.dumps({
            "verdict":verdict,"choice":pilot_art["selected_source_set_decision"],
            "added_families":chosen_families,
            "baseline_candidate_coverage":base_stats["positives_with_candidate"],
            "selected_candidate_coverage":best_st["positives_with_candidate"],
            "selected_final_positives":best_st["total_final_positives"],
            "new_uncleared_hold_promotions":best_st["new_uncleared_hold_promotions"],
            "technical_errors":errors,
        },ensure_ascii=False))
    finally:
        if wt is not None:
            subprocess.run(["git", "worktree", "remove", "--force", str(wt)],cwd=ROOT,check=False)
        shutil.rmtree(tmp,ignore_errors=True)

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        block = {
            "schema":"kyiv-historical-source-set-stage2-blocked-v1",
            "verdict":"KYIV HISTORICAL SOURCE-SET STAGE 2 PILOT = BLOCKED",
            "technical_blocker":str(exc),
            "next_task_recommendation":"TECHNICAL BLOCKER",
            "frozen_variant_a_manifest_sha256":MANIFEST_SHA,
            "development_positives":48, "development_holds":19,
            "blind_per_episode_data_inspected":False,
            "blind_wrapper_decoding_attempts":0,
            "historical_backfill_started":False,"Neon_writes":0,"production_mutations":0,
            "mutation_confirmation":"No production changes; attempted development-only proof.",
        }
        if not OUT_C.exists():
            write(OUT_C,{"schema":"kyiv-historical-source-set-stage2-candidates-blocked-v1",
                         "verdict":"BLOCKED","technical_blocker":str(exc)})
        write(OUT_P,block)
        print(json.dumps(block,ensure_ascii=False))
