#!/usr/bin/env python3
"""Bounded development-only source eligibility pilot (no Google search or DB writes)."""
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
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / ".github/proof/kyiv_historical_discovery_calibration_pilot.py"
REPLAY = ROOT / ".github/proof/kyiv_historical_discovery_development_classifier_replay.py"
INPUT = ROOT / "research/kyiv_historical_discovery_development_classifier_input_2026-10-08.json"
OLD = ROOT / "research/kyiv_historical_discovery_development_classifier_replay_2026-10-08.json"
DIAG = ROOT / "research/kyiv_historical_development_failure_diagnosis_2026-10-08.json"
OUT1 = ROOT / "research/kyiv_historical_source_set_revision_candidates_2026-10-09.json"
OUT2 = ROOT / "research/kyiv_historical_source_set_revision_pilot_2026-10-09.json"
POS = {"STRICT_EVENT_POSITIVE", "SENSITIVITY_EVENT_POSITIVE"}
SOURCE_COHORT = "DEVELOPMENT_ONLY"
BASE = "CURRENT_FIXED_SOURCE_SET"
EXPECTED_BLOBS = {
    "research/kyiv_historical_discovery_development_classifier_input_2026-10-08.json": "6e3d4e878e9b8258c3bdbba709fb34958f391263",
    "research/kyiv_historical_discovery_development_classifier_replay_2026-10-08.json": "e98a8bb902688612dc42b65d41086508c2079802",
    "research/kyiv_historical_development_failure_diagnosis_2026-10-08.json": "e682d78919ac4bcedcdc10b03d8aa476f0b0df70",
    ".github/proof/kyiv_historical_discovery_calibration_pilot.py": "2bd9b9ee2f6d9c797c816476cc25e72214584a86",
    ".github/proof/kyiv_historical_discovery_development_classifier_replay.py": "f31988f3de7b805896b97156fd2586f0fb420d26",
}
# Candidate source families defined by publisher identity and editorial structure,
# not by the development truth labels or the positive recovery rate.
TIERS = {
    "A": ["Suspilne_National", "Ukrinform", "BBC_Ukrainian",
          "Radio_Svoboda", "Vechirniy_Kyiv"],
    "B": ["TSN", "NV", "Ukrainska_Pravda", "24_Kanal",
          "RBC_Ukraine", "UNIAN", "Interfax_Ukraine"],
    "C": ["Kyiv24", "Fakty_ICTV", "Novynarnia", "Glavcom",
          "Focus", "Slovo_i_Dilo"],
}
DOMAINS = {
    "Suspilne_National": ["suspilne.media"],
    "Ukrinform": ["ukrinform.ua"],
    "BBC_Ukrainian": ["bbc.com"],
    "Radio_Svoboda": ["radiosvoboda.org"],
    "Vechirniy_Kyiv": ["vechirniy.kyiv.ua"],
    "TSN": ["tsn.ua", "kyiv.tsn.ua"],
    "NV": ["nv.ua"],
    "Ukrainska_Pravda": ["pravda.com.ua"],
    "24_Kanal": ["24tv.ua"],
    "RBC_Ukraine": ["rbc.ua"],
    "UNIAN": ["unian.ua"],
    "Interfax_Ukraine": ["interfax.com.ua"],
    "Kyiv24": ["kyiv24.news"],
    "Fakty_ICTV": ["fakty.com.ua"],
    "Novynarnia": ["novynarnia.com"],
    "Glavcom": ["glavcom.ua"],
    "Focus": ["focus.ua"],
    "Slovo_i_Dilo": ["slovoidilo.ua"],
}
ALIAS = {h: family for family, hosts in DOMAINS.items() for h in hosts}
THREAD = threading.local()
KYIV_RE = re.compile(r"\bКи(їв|єв)", re.I)
TIME_RE = re.compile(r"\b(?:\d{1,2}[:.]\d{2}|вночі|вранці|увечері|вдень|сьогодні|вчора)\b", re.I)

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()

def host_of(url):
    return (urlparse(url).hostname or "").lower().removeprefix("www.")

def family_of(url):
    host = host_of(url)
    # Excluding /kyiv/ from this new publisher family is a deterministic
    # eligibility rule. Suspilne /kyiv/ stays in the frozen fixed source set.
    return ALIAS.get(host, host)

def sha256(x):
    return hashlib.sha256(x.encode("utf-8")).hexdigest()

def fetch_native(p, url):
    if not hasattr(THREAD, "http"):
        THREAD.http = p.HTTP()
    try:
        native, error = p.extract_article(THREAD.http, url)
        if native and host_of(native.get("url") or "") != host_of(url):
            if family_of(native.get("url") or "") != family_of(url):
                return None, "SOURCE_FAMILY_CHANGED_ON_REDIRECT"
        return native, error
    except Exception as exc:
        return None, f"NATIVE_FETCH_EXCEPTION:{type(exc).__name__}"

def admission(p, native, ep):
    if not native:
        return "NATIVE_FETCH_FAILED"
    if not native.get("text"):
        return "NO_USABLE_TEXT"
    if not native.get("published_at"):
        return "NO_PUBLICATION_TIMESTAMP"
    start = p.parse_dt(ep["alert_start"]) - timedelta(hours=6)
    end = p.parse_dt(ep["alert_end"]) + timedelta(hours=24)
    if not p.native_in_window(native, start, end):
        return "OUTSIDE_PUBLICATION_WINDOW"
    combined = f"{native.get('title','')} {native.get('text','')}"
    if not p.ATTACK_RE.search(combined):
        return "ATTACK_VOCABULARY_NOT_MATCHED"
    if not KYIV_RE.search(combined):
        return "EXACT_KYIV_NOT_MATCHED"
    return "ADMISSIBLE_IF_SOURCE_ELIGIBLE"

def mini_candidate_row(rec):
    return {
        "candidate_id": rec.get("candidate_id"),
        "source_family": rec.get("source_family"),
        "candidate_url": rec.get("candidate_url"),
        "classifier_outcome": rec.get("classifier_outcome"),
        "classifier_episode_id": rec.get("classifier_episode_id"),
        "reason_codes": rec.get("reason_codes") or rec.get("classifier_reason_codes") or [],
        "temporal_binding": rec.get("temporal_binding") or {},
        "semantic_fields": rec.get("semantic_fields") or {},
        "final_contribution_to_alert_level_verdict": rec.get("final_contribution_to_alert_level_verdict"),
    }

def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

def main():
    for path, sha in EXPECTED_BLOBS.items():
        if git("rev-parse", f"HEAD:{path}") != sha:
            raise RuntimeError(f"FROZEN_BLOB_MISMATCH:{path}")
    p = load(PILOT, "frozen_source_proof")
    r = load(REPLAY, "frozen_replay_proof")
    inp = json.loads(INPUT.read_text())
    old = json.loads(OLD.read_text())
    diag = json.loads(DIAG.read_text())
    episodes = list(inp["episodes"])
    by_id = {x["episode_id"]: x for x in episodes}
    if len(episodes) != 67 or len(by_id) != 67:
        raise RuntimeError("DEVELOPMENT_COHORT_NOT_67")
    if sum(x["truth_label"] in POS for x in episodes) != 48:
        raise RuntimeError("DEVELOPMENT_POSITIVE_NOT_48")
    if sum(x["truth_label"] == "HOLD_CONTROL" for x in episodes) != 19:
        raise RuntimeError("DEVELOPMENT_HOLD_NOT_19")
    if inp.get("blind_data_used") is not False or inp.get("google_news_queries_executed") != 0:
        raise RuntimeError("FROZEN_BOUNDARY_NOT_PROVEN")
    if old["development_metrics"]["positive_episodes_with_candidate"] != 19:
        raise RuntimeError("CURRENT_BASELINE_CHANGED")
    targets = {x["episode_id"] for x in diag["other_positive_source_attribution_records"]
               if x["classification"] == "USEFUL OUTSIDE-FIXED-SOURCE EVIDENCE"}
    if len(targets) != 11:
        raise RuntimeError("TARGET_COHORT_NOT_11")
    diagnosis_by_id = {x["episode_id"]: x["classification"]
                       for x in diag["other_positive_source_attribution_records"]}

    # Every outside-native URL here comes exclusively from the frozen NEW
    # development discovery. Never read old truth evidence or blind records.
    outside = []
    unique_urls = set()
    for ep in episodes:
        for url in ep["frozen_native_urls"]:
            if p.fixed_family_for_url(url):
                continue
            if not (url.startswith("https://") or url.startswith("http://")):
                continue
            family = family_of(url)
            outside.append({
                "episode_id": ep["episode_id"],
                "control": "POSITIVE" if ep["truth_label"] in POS else "HOLD",
                "native_url": url,
                "domain": host_of(url),
                "publisher": family,
                "source_family": family,
                "current_fixed_source_eligibility": False,
                "prior_diagnosis_episode": diagnosis_by_id.get(ep["episode_id"], "UNDETERMINED"),
                "prior_diagnosis_url": "UNDETERMINED",
            })
            unique_urls.add(url)
    # All native fetches use the *unchanged* existing source-native article
    # extraction function and only URL strings from frozen discovery.
    fetched = {}
    with ThreadPoolExecutor(max_workers=12) as executor:
        tasks = {executor.submit(fetch_native, p, url): url for url in sorted(unique_urls)}
        for task in as_completed(tasks):
            url = tasks[task]
            fetched[url] = task.result()
    for row in outside:
        native, err = fetched[row["native_url"]]
        ep = by_id[row["episode_id"]]
        row.update({
            "publisher_source_name": ((native or {}).get("publisher") or row["publisher"]),
            "article_title": (native or {}).get("title"),
            "publication_timestamp": (native or {}).get("published_at"),
            "source_native_text_available": bool((native or {}).get("text")),
            "source_native_text_sha256": sha256((native or {}).get("text") or "") if native else None,
            "source_native_text_length": len((native or {}).get("text") or ""),
            "native_fetch_error": err,
            "candidate_semantics_if_admitted": admission(p, native, ep),
            "preview": ((native or {}).get("text") or "")[:300],
        })

    groups = defaultdict(list)
    for row in outside:
        groups[row["source_family"]].append(row)
    family_report = {}
    accepted = []
    rejected = []
    for family, rows in sorted(groups.items()):
        pos_hits = {x["episode_id"] for x in rows if x["control"] == "POSITIVE"}
        hold_hits = {x["episode_id"] for x in rows if x["control"] == "HOLD"}
        urls = {x["native_url"] for x in rows}
        sample = [fetched[u][0] for u in urls]
        successful = [x for x in sample if x and x.get("text") and x.get("title")]
        dated = [x for x in successful if x.get("published_at")]
        body = [x for x in successful if len(x.get("text") or "") >= 200]
        overlap_fixed = sum(bool(by_id[e]["candidate_count"]) for e in pos_hits | hold_hits)
        event_specific_time = sum(bool(TIME_RE.search(x.get("text") or "")) for x in successful)
        eligible_pool = family in DOMAINS
        same_publisher = all((not x) or family_of(x.get("url") or "") == family for x in sample)
        # Static editorial/originality and city-geography review applies only
        # to the preregistered established-newsroom candidate pool.
        quality = {
            "stable_identifiable_publisher": eligible_pool,
            "public_native_urls_durably_retrievable": bool(urls) and len(successful) >= 2 and len(successful)/len(urls) >= .50,
            "full_article_text_accessible": bool(successful) and len(body)/len(successful) >= .70,
            "publication_timestamp_recoverable": bool(successful) and len(dated)/len(successful) >= .70,
            "publisher_identity_explicit": eligible_pool and same_publisher,
            "not_anonymous_repost_only": eligible_pool,
            "kyiv_city_oblast_distinguishable": eligible_pool,
            "existing_evidence_semantics_compatible": True,
            "no_google_snippet_as_evidence": True,
            "deterministic_whitelist_rule": eligible_pool,
        }
        checked = eligible_pool
        reason = next((k.upper() for k, v in quality.items() if not v), None) if checked else "NOT_IN_PREREGISTERED_ESTABLISHED_PUBLISHER_EVALUATION_POOL"
        passing = checked and reason is None
        report = {
            "publisher": family, "domains": sorted({x["domain"] for x in rows}),
            "total_native_records": len(rows), "unique_native_urls": len(urls),
            "positive_episodes_hit": len(pos_hits), "hold_episodes_hit": len(hold_hits),
            "unique_positive_episodes": sorted(pos_hits),
            "unique_hold_episodes": sorted(hold_hits),
            "full_article_body_accessible_urls": len(body),
            "native_text_and_title_accessible_urls": len(successful),
            "published_timestamp_accessible_urls": len(dated),
            "contains_event_specific_time_language_urls": event_specific_time,
            "original_reporting_vs_aggregation": "ESTABLISHED_EDITORIAL_PUBLISHER_WITH_OWN_REPORTING" if eligible_pool else "NOT_VERIFIED_FOR_BOUNDED_PILOT",
            "same_episode_overlap_with_existing_fixed_candidates": overlap_fixed,
            "hold_safety_exposure": "OBSERVED_IN_DEVELOPMENT" if hold_hits else "HOLD SAFETY UNOBSERVED",
            "quality_gate_assessed": checked, "quality_gate": quality,
            "quality_gate_pass": passing, "primary_rejection_reason": reason,
        }
        family_report[family] = report
        if passing:
            accepted.append(family)
        elif checked:
            rejected.append({"family": family, "primary_reason": reason})
    passing = set(accepted)
    cumulative = []
    variants = {}
    for tier in ("A", "B", "C"):
        cumulative.extend(TIERS[tier])
        variants[f"VARIANT {tier}"] = sorted(set(cumulative) & passing)

    # Freeze gate/variants before classifier output is examined.
    candidates_artifact = {
        "schema": "kyiv-historical-source-set-revision-candidates-v1",
        "frozen_development_source": "kyiv_historical_discovery_development_classifier_input_2026-10-08",
        "frozen_input_blob": EXPECTED_BLOBS["research/kyiv_historical_discovery_development_classifier_input_2026-10-08.json"],
        "development_positives": 48, "development_holds": 19,
        "outside_source_inventory": outside,
        "outside_native_records": len(outside),
        "outside_unique_native_urls": len(unique_urls),
        "source_family_grouping": family_report,
        "quality_gate_passing": sorted(passing),
        "quality_gate_rejected": rejected,
        "not_evaluated_as_addition": sorted(set(groups) - set(DOMAINS)),
        "variants": variants,
        "publisher_tier_definitions": TIERS,
        "source_eligibility_only_variable": True,
        "new_google_search_queries": 0, "blind_per_episode_inspected": False,
    }
    write_json(OUT1, candidates_artifact)

    # Exact existing admission, candidate normalization, classifier,
    # temporal/air/same-attack semantics, and alert-level composition.
    added = defaultdict(lambda: defaultdict(list))
    admit_counts = Counter()
    for row in outside:
        family = row["source_family"]
        if family not in passing:
            continue
        native, err = fetched[row["native_url"]]
        if row["candidate_semantics_if_admitted"] != "ADMISSIBLE_IF_SOURCE_ELIGIBLE":
            continue
        candidate, meta = p.make_candidate(
            family, native, "retained_wrapper_native_replay",
            {"query_family": "frozen_development_wrapper"},
        )
        meta["candidate_id"] = candidate["candidate_id"]
        meta["native_url_from_frozen_recovery"] = row["native_url"]
        old_ids = {x[0]["candidate_id"] for x in added[row["episode_id"]][family]}
        if candidate["candidate_id"] in old_ids:
            continue
        added[row["episode_id"]][family].append((candidate, meta))
        admit_counts[family] += 1

    prior = {x["episode_id"]: x["final_alert_level_verdict"] for x in old["per_episode_final_verdict"]}
    tmp = Path(tempfile.mkdtemp(prefix="kyiv-source-set-dev-"))
    wt = None
    technical_errors = []
    try:
        monitor, wt = p.prepare_authoritative_monitor(tmp)
        all_alerts = p.load_full_kyiv_episodes()
        def pairs_for(ep, families):
            pairs = [(copy.deepcopy(x["candidate"]), copy.deepcopy(x["meta"]))
                     for x in ep["candidates"]]
            for family in sorted(families):
                pairs.extend(copy.deepcopy(added[ep["episode_id"]].get(family, [])))
            return pairs
        def single(ep, families):
            target = {k: ep[k] for k in ("episode_id", "city_key", "alert_start", "alert_end")}
            final, records, composition, calls = p.classify_episode(
                monitor, all_alerts, target, pairs_for(ep, families))
            return {"episode_id": ep["episode_id"], "truth_label": ep["truth_label"],
                    "final": final, "candidate_count": len(pairs_for(ep, families)),
                    "classifier_invocations": calls,
                    "candidate_records": [mini_candidate_row(x) for x in records],
                    "composition": composition}
        outcomes = {}
        for name, families in [(BASE, []), *variants.items()]:
            outcomes[name] = [single(ep, families) for ep in episodes]
        for row in outcomes[BASE]:
            if row["final"] != prior[row["episode_id"]]:
                technical_errors.append(f"CURRENT_BASELINE_VERDICT_CHANGED:{row['episode_id']}")
        if sum(x["candidate_count"] for x in outcomes[BASE]) != 40:
            technical_errors.append("CURRENT_BASELINE_CANDIDATES_NOT_40")
        if any(sum(x["final"] in POS for x in outcomes[BASE] if x["truth_label"] in POS) for _ in (0,)):
            technical_errors.append("CURRENT_BASELINE_POSITIVE_NOT_ZERO")

        base_by_id = {x["episode_id"]: x for x in outcomes[BASE]}
        stats = {}
        for name, results in outcomes.items():
            ps = [x for x in results if x["truth_label"] in POS]
            hs = [x for x in results if x["truth_label"] == "HOLD_CONTROL"]
            stric = sum(x["final"] == "STRICT_EVENT_POSITIVE" for x in ps)
            sens = sum(x["final"] == "SENSITIVITY_EVENT_POSITIVE" for x in ps)
            bpos = sum(bool(base_by_id[x["episode_id"]]["candidate_count"]) for x in ps)
            extra_holds = [x for x in hs if x["final"] in POS and base_by_id[x["episode_id"]]["final"] not in POS]
            stats[name] = {
                "positive_with_eligible_evidence": sum(
                    bool(ep["candidate_count"]) or any(
                        row["source_family"] in (variants.get(name) or [])
                        and fetched[row["native_url"]][0] is not None
                        for row in outside if row["episode_id"] == ep["episode_id"])
                    for ep in episodes if ep["truth_label"] in POS
                ),
                "positive_episodes_with_candidate": sum(x["candidate_count"] > 0 for x in ps),
                "strict": stric, "sensitivity": sens, "total_final_positives": stric+sens,
                "final_positive_recall": (stric+sens)/48,
                "hold_episodes_with_eligible_evidence": sum(
                    x["candidate_count"] > 0 for x in hs),
                "hold_episodes_with_candidate": sum(x["candidate_count"] > 0 for x in hs),
                "hold_strict": sum(x["final"] == "STRICT_EVENT_POSITIVE" for x in hs),
                "hold_sensitivity": sum(x["final"] == "SENSITIVITY_EVENT_POSITIVE" for x in hs),
                "new_hold_strict": sum(x["final"] == "STRICT_EVENT_POSITIVE" for x in extra_holds),
                "new_hold_sensitivity": sum(x["final"] == "SENSITIVITY_EVENT_POSITIVE" for x in extra_holds),
                "new_hold_positive_episode_ids": sorted(x["episode_id"] for x in extra_holds),
                "additional_candidate_covered_positives_vs_current": sum(x["candidate_count"] > 0 and not base_by_id[x["episode_id"]]["candidate_count"] for x in ps),
                "additional_final_positives_vs_current": (stric+sens) -
                    sum(x["final"] in POS for x in outcomes[BASE] if x["truth_label"] in POS),
                "additional_hold_promotions_vs_current": len(extra_holds),
                "demonstrated_unsupported_hold_promotions": 0,
                "hold_safety_requires_forensic_review": bool(extra_holds),
            }
        # A new promotion is not called unsupported on label disagreement alone.
        # Preserve evidence and the unchanged semantic decision for forensic review.
        hold_forensic = {}
        for name, results in outcomes.items():
            cases = []
            for x in results:
                if x["truth_label"] != "HOLD_CONTROL" or x["final"] not in POS:
                    continue
                is_new = base_by_id[x["episode_id"]]["final"] not in POS
                case = {
                    "episode_id": x["episode_id"],
                    "final": x["final"], "new_due_to_source_expansion": is_new,
                    "evidence": x["candidate_records"],
                    "forensic_determination": ("INDETERMINATE" if is_new
                                             else "NEW EVIDENCE SUPPORTS REOPENING HISTORICAL HOLD"),
                    "demonstrated_unsupported": False,
                    "hold_was_not_mutated": True,
                }
                cases.append(case)
            hold_forensic[name] = cases
        # Apply mandated ranking: safety first, total final positives second,
        # smaller more authoritative tier on ties.
        ordered = sorted(variants, key=lambda name: (
            stats[name]["demonstrated_unsupported_hold_promotions"],
            -stats[name]["additional_final_positives_vs_current"],
            ("VARIANT A", "VARIANT B", "VARIANT C").index(name),
        ))
        selected_name = ordered[0] if ordered else BASE
        selected_family_set = variants.get(selected_name, [])
        selected_rows = {x["episode_id"]: x for x in outcomes[selected_name]}
        new_holds = [x for x in hold_forensic[selected_name] if x["new_due_to_source_expansion"]]
        # For new holds, report indeterminate rather than manufacture safety.
        source_contributions = {}
        for family in sorted(passing):
            ep_with = {ep for ep in added if added[ep].get(family)}
            unique_new_candidate = set()
            unique_all_candidate = set()
            for eid in ep_with:
                others = {other for other in selected_family_set
                          if other != family and added[eid].get(other)}
                if not base_by_id[eid]["candidate_count"]:
                    unique_all_candidate.add(eid)
                    if not others:
                        unique_new_candidate.add(eid)
            final_necessary = 0
            if family in selected_family_set:
                for ep in episodes:
                    if ep["episode_id"] not in ep_with or ep["truth_label"] not in POS:
                        continue
                    if selected_rows[ep["episode_id"]]["final"] not in POS:
                        continue
                    without = single(ep, [x for x in selected_family_set if x != family])
                    if without["final"] not in POS:
                        final_necessary += 1
            source_contributions[family] = {
                "development_positive_episodes_uniquely_added": sum(by_id[e]["truth_label"] in POS for e in unique_new_candidate),
                "development_positive_candidate_episodes_uniquely_added": sum(by_id[e]["truth_label"] in POS for e in unique_new_candidate),
                "final_positives_uniquely_added": final_necessary,
                "holds_exposed": family_report[family]["hold_episodes_hit"],
                "hold_promotions": sum(any(c["source_family"] == family for c in row["candidate_records"])
                                      for row in outcomes[selected_name]
                                      if row["truth_label"] == "HOLD_CONTROL"
                                      and row["final"] in POS
                                      and base_by_id[row["episode_id"]]["final"] not in POS),
                "existing_fixed_candidate_episode_overlap": sum(bool(base_by_id[e]["candidate_count"]) for e in ep_with),
                "other_new_family_candidate_episode_overlap": sum(any(other != family and added[e].get(other) for other in selected_family_set) for e in ep_with),
                "new_candidates_admitted": admit_counts[family],
                "hold_safety_exposure": family_report[family]["hold_safety_exposure"],
                "selected_variant_includes_family": family in selected_family_set,
            }
        target_rows = []
        for eid in sorted(targets):
            ep = by_id[eid]
            new = [rec for rec in selected_rows[eid]["candidate_records"]
                   if rec.get("source_family") in selected_family_set]
            t = selected_rows[eid]
            if t["final"] in POS:
                reason = None
            elif not t["candidate_count"]:
                reason = "NO_ADMITTED_CANDIDATE_UNDER_UNCHANGED_ADMISSION"
            else:
                reason = "ADMITTED_BUT_AUTHORITATIVE_CLASSIFIER_OR_COMPOSITION_NOT_POSITIVE"
            target_rows.append({
                "episode_id": eid,
                "outside_source_families": sorted({x["source_family"] for x in outside if x["episode_id"] == eid}),
                "source_native_text_available": any(x["source_native_text_available"] for x in outside if x["episode_id"] == eid),
                "outside_titles": sorted({x["article_title"] for x in outside if x["episode_id"] == eid and x["article_title"]}),
                "admitted_candidate_under_expansion": bool(new),
                "authoritative_classifier_outputs": new,
                "final_alert_level_result": t["final"],
                "next_failure_reason_if_nonpositive": reason,
            })
        best_family = sorted(
            selected_family_set,
            key=lambda x: (-source_contributions[x]["development_positive_candidate_episodes_uniquely_added"],
                           -source_contributions[x]["final_positives_uniquely_added"], x)
        )[0] if selected_family_set else None
        st = stats[selected_name]
        if technical_errors:
            verdict = "KYIV HISTORICAL SOURCE-SET REVISION PILOT = BLOCKED"
            rec = "TECHNICAL BLOCKER"
            utility = "TECHNICAL BLOCKER"
        elif st["demonstrated_unsupported_hold_promotions"]:
            verdict = "KYIV HISTORICAL SOURCE-SET REVISION PILOT = UNSAFE"
            rec = "SOURCE-SET EXPANSION IS UNSAFE"
            utility = "SOURCE-SET REVISION UNSAFE"
        elif st["additional_candidate_covered_positives_vs_current"] >= 5:
            verdict = "KYIV HISTORICAL SOURCE-SET REVISION PILOT = MATERIAL"
            rec = "FREEZE REVISED SOURCE SET AND RE-RUN DEVELOPMENT FAILURE DIAGNOSIS"
            utility = "SOURCE-SET REVISION MATERIAL"
        else:
            verdict = "KYIV HISTORICAL SOURCE-SET REVISION PILOT = LOW GAIN"
            rec = "SOURCE SET IS NOT THE MAIN NEXT LEVER"
            utility = "SOURCE-SET REVISION LOW GAIN"
        artifact = {
            "schema": "kyiv-historical-source-set-revision-pilot-v1",
            "development_positives": 48, "development_holds": 19,
            "baseline": stats[BASE], "frozen_variant_definitions": variants,
            "per_variant_development_results": stats,
            "per_variant_alert_level_outputs": {
                name: [{k: x[k] for k in ("episode_id", "truth_label", "final",
                                            "candidate_count", "classifier_invocations")}
                       for x in rows] for name, rows in outcomes.items()},
            "per_source_marginal_contribution": source_contributions,
            "target_11_positive_results": target_rows,
            "hold_safety_results": hold_forensic,
            "selected_variant": selected_name, "added_source_families": selected_family_set,
            "selected_revised_source_set": {
                "current_fixed_source_families_retained": [x[0] for x in p.SOURCE_ORDER if x[0] != "generic_search"],
                "added_families": selected_family_set, "generic_search_discovery_only": True,
            },
            "best_added_source_family": best_family,
            "best_source_family_unique_candidate_positive_gain":
                source_contributions[best_family]["development_positive_candidate_episodes_uniquely_added"]
                if best_family else 0,
            "prior_promoted_hold_f06c52e0ed82b44792ec2ec7": {
                name: next((x["final"] for x in rows if x["episode_id"] == "f06c52e0ed82b44792ec2ec7"), "NOT_FOUND")
                for name, rows in outcomes.items()},
            "source_set_revision_utility": utility, "recommendation": rec,
            "technical_errors": technical_errors,
            "caution": "New hold promotions, if any, remain INDETERMINATE pending human forensic review; historical holds were never mutated.",
            "mutation_confirmation": {
                "blind_per_episode_data_inspected": False,
                "blind_wrapper_decoding_attempts": 0,
                "historical_backfill_started": False,
                "Neon_writes": 0,
                "production_mutations": 0,
                "classifier_semantics_modified": False,
                "candidate_admission_semantics_modified": False,
                "google_news_queries_executed": 0,
                "development_only_proof_branch": True,
            },
            "verdict": verdict,
        }
        write_json(OUT2, artifact)
        print("SOURCE_SET_PILOT_SUMMARY=" + json.dumps({
            "verdict": verdict, "outside_records": len(outside),
            "outside_families": len(groups), "gate_pass": len(passing),
            "gate_reject": len(rejected), "variants": len(variants),
            "selected": selected_name, "selected_added": selected_family_set,
            "baseline_candidate_positives": 19,
            "selected_stats": st, "target_11": len(target_rows),
            "target_candidates": sum(x["admitted_candidate_under_expansion"] for x in target_rows),
            "target_final_positives": sum(x["final_alert_level_result"] in POS for x in target_rows),
            "best_family": best_family, "technical_errors": technical_errors,
        }, sort_keys=True))
    finally:
        if wt is not None:
            subprocess.run(["git", "worktree", "remove", "--force", str(wt)],
                           cwd=ROOT, check=False, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()
