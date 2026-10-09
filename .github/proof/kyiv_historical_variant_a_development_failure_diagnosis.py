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
FREEZE_OUT = ROOT / "research/kyiv_historical_source_set_variant_a_freeze_2026-10-09.json"
DIAG_OUT = ROOT / "research/kyiv_historical_variant_a_development_failure_diagnosis_2026-10-09.json"
PILOT_ACCEPTED = OUT2
CANDIDATES_ACCEPTED = OUT1
VARIANT_A = {"BBC_Ukrainian", "Radio_Svoboda", "Suspilne_National"}
PILOT_COMMIT = "b08321c4607f48667091b7b7da3d6e41e780d7fa"
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


def freeze_variant_a_manifest(p):
    """Hash semantic dependencies and freeze the exact pilot eligibility rules."""
    sha = lambda path: git("rev-parse", "HEAD:" + path)
    for path, expected in EXPECTED_BLOBS.items():
        if sha(path) != expected:
            raise RuntimeError("SEMANTIC ISOLATION FAILED:" + path)
    extras = {
        ".github/proof/kyiv_historical_source_set_revision_pilot.py":
            "dfb8cb1102ee69ceeb1f422cff5f6a6905ecf76c",
        "research/kyiv_historical_source_set_revision_candidates_2026-10-09.json":
            "652241e3b1378db2865d62bb14c5ccaafe28e245",
        "research/kyiv_historical_source_set_revision_pilot_2026-10-09.json":
            "0465e7ae26d79f23fd0a8e200c7bd8ad21c20f74",
    }
    for path, expected in extras.items():
        if sha(path) != expected:
            raise RuntimeError("SEMANTIC ISOLATION FAILED:" + path)
    if p.AUTH_COMMIT != "71cb6f6fbe856cc7b96759310fe9cc9c71cc0453":
        raise RuntimeError("SEMANTIC ISOLATION FAILED:classifier_commit")
    if p.AUTH_BLOB != "778469b74c2aa807d851cf2c2ee35cf4aa785589":
        raise RuntimeError("SEMANTIC ISOLATION FAILED:classifier_blob")
    fixed = [x[0] for x in p.SOURCE_ORDER if x[0] != "generic_search"]
    manifest = {
        "schema": "kyiv-historical-variant-a-source-set-freeze-v1",
        "purpose": "DEVELOPMENT_HISTORICAL_ONLY; NO PRODUCTION CHANGE",
        "predecessors": {
            "pilot_branch": "kyiv-historical-source-set-revision-pilot-2026-10-09",
            "pilot_proof_run": 37895378088, "pilot_proof_job": 113705431021,
            "pilot_artifact_commit": PILOT_COMMIT,
            "pilot_report_blob": extras["research/kyiv_historical_source_set_revision_pilot_2026-10-09.json"],
            "pilot_inventory_blob": extras["research/kyiv_historical_source_set_revision_candidates_2026-10-09.json"],
            "authoritative_classifier_commit": p.AUTH_COMMIT,
            "authoritative_classifier_blob": p.AUTH_BLOB,
        },
        "current_fixed_source_families_retained": fixed,
        "source_eligibility_delta_only": sorted(VARIANT_A),
        "source_family_rules": {
            "BBC_Ukrainian": {
                "canonical_id": "BBC_Ukrainian", "accepted_hostnames": ["bbc.com", "www.bbc.com"],
                "match": "exact hostname after lowercase and stripping leading www.; other bbc subdomains rejected",
                "path_rule": "no additional path restriction in accepted pilot",
                "aliases": ["www.bbc.com -> bbc.com"],
                "reject": "any host outside bbc.com or www.bbc.com",
            },
            "Radio_Svoboda": {
                "canonical_id": "Radio_Svoboda", "accepted_hostnames": ["radiosvoboda.org", "www.radiosvoboda.org"],
                "match": "exact hostname after lowercase and stripping leading www.",
                "path_rule": "no path restriction",
                "aliases": ["www.radiosvoboda.org -> radiosvoboda.org"],
                "reject": "any host outside radiosvoboda.org or www.radiosvoboda.org",
            },
            "Suspilne_National": {
                "canonical_id": "Suspilne_National", "accepted_hostnames": ["suspilne.media", "www.suspilne.media"],
                "match": "exact hostname after lowercase and stripping leading www.",
                "path_rule": "reject /kyiv/ URLs already owned by fixed susplilne.media/kyiv family",
                "aliases": ["www.suspilne.media -> suspilne.media"],
                "reject": "other hosts and fixed /kyiv/ family records",
            },
        },
        "no_other_source_families_authorized": True,
        "frozen_components": {**EXPECTED_BLOBS, **extras},
        "unchanged_semantics": [
            "query_vocabulary", "query_windows", "native_url_resolver", "native_fetch",
            "publication_timestamp_extraction", "candidate_admission",
            "authoritative_classifier", "alert_boundaries", "temporal_parser",
            "temporal_representation", "same_attack", "exact_city", "air_context",
            "alert_level_materialization"
        ],
        "sole_replay_variable": "SOURCE_ELIGIBILITY",
        "semantic_isolation": "PASS",
        "blind_data_inspected": False,
        "blind_wrapper_decode_attempts": 0,
        "neon_writes": 0, "production_mutations": 0, "historical_backfill_started": False,
        "hash_method": "SHA256 over UTF-8 canonical JSON of this manifest without manifest_sha256 field; sorted keys, compact separators, ensure_ascii=False",
    }
    canonical = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    manifest["manifest_sha256"] = sha256(canonical)
    write_json(FREEZE_OUT, manifest)
    return manifest


def emit_variant_a_diagnosis(inp, old_diag, outcomes, outside, fetched, source_inventory, pilot_replay, freeze, p):
    """Bounded new end-to-end forensic: label-preserving, never train or seed from truth."""
    accepted = json.loads(PILOT_ACCEPTED.read_text())
    assert accepted["selected_variant"] == "VARIANT A"
    assert accepted["added_source_families"] == sorted(VARIANT_A)
    differences = []
    for variant in (BASE, "VARIANT A"):
        earlier = {x["episode_id"]: x for x in accepted["per_variant_alert_level_outputs"][variant]}
        for newer in outcomes[variant]:
            original = earlier.get(newer["episode_id"])
            if not original:
                differences.append({"variant": variant, "episode_id": newer["episode_id"], "reason": "MISSING_PREDECESSOR"})
                continue
            for a, b in (("final", "final"), ("candidate_count", "candidate_count"),
                         ("classifier_invocations", "classifier_invocations")):
                if newer[a] != original[b]:
                    differences.append({"variant": variant, "episode_id": newer["episode_id"],
                                        "field": a, "before": original[b], "after": newer[a]})
    if differences:
        raise RuntimeError("VARIANT_A_REPLAY_REPRODUCIBILITY_DRIFT:" + json.dumps(differences[:20]))
    base = {x["episode_id"]: x for x in outcomes[BASE]}
    variant = {x["episode_id"]: x for x in outcomes["VARIANT A"]}
    e_by = {x["episode_id"]: x for x in inp["episodes"]}
    original_diag = {x["episode_id"]: x for x in old_diag["all_48_positive_episode_diagnoses"]}
    useful = {x["episode_id"] for x in old_diag["other_positive_source_attribution_records"]
              if x["classification"] == "USEFUL OUTSIDE-FIXED-SOURCE EVIDENCE"}
    by_out = defaultdict(list)
    for x in outside: by_out[x["episode_id"]].append(x)
    positive_episodes = [e for e in inp["episodes"] if e["truth_label"] in POS]
    hold_episodes = [e for e in inp["episodes"] if e["truth_label"] == "HOLD_CONTROL"]
    if len(positive_episodes) != 48 or len(hold_episodes) != 19: raise RuntimeError("COHORT_DRIFT")
    trans = []
    for ep in positive_episodes:
        eid = ep["episode_id"]; o = base[eid]; n = variant[eid]
        had = o["candidate_count"] > 0; has = n["candidate_count"] > 0
        outside_a = [x for x in by_out[eid] if x["source_family"] in VARIANT_A]
        eligible = bool(had or any(x["source_native_text_available"] for x in outside_a))
        if not had and not has:
            cat = "NEW_ELIGIBLE_EVIDENCE_BUT_NO_CANDIDATE" if eligible else "NO_CHANGE_NO_CANDIDATE"
        elif not had and has:
            cat = "NEW_CANDIDATE_BECAME_POSITIVE" if n["final"] in POS else "NEW_CANDIDATE_STILL_REVIEW"
        elif n["final"] in POS:
            cat = "PREEXISTING_CANDIDATE_OTHER"
        elif n["final"] == "NEEDS_REVIEW":
            cat = "PREEXISTING_CANDIDATE_STILL_REVIEW"
        else:
            cat = "PREEXISTING_CANDIDATE_OTHER"
        trans.append({
            "episode_id": eid,
            "old_source_eligibility": "FIXED_ELIGIBLE" if had else "NO_ADMITTED_ELIGIBLE_CANDIDATE",
            "variant_a_eligible_evidence": eligible,
            "variant_a_eligible_source_families": sorted({x["source_family"] for x in outside_a
                                                          if x["source_native_text_available"]}),
            "old_candidate_count": o["candidate_count"],
            "variant_a_candidate_count": n["candidate_count"],
            "old_classifier": o["candidate_records"],
            "variant_a_classifier": n["candidate_records"],
            "old_final_verdict": o["final"], "variant_a_final_verdict": n["final"],
            "transition_category": cat,
        })
    first_classes = {
        "NO_RELEVANT_NATIVE_RESULT": "EVIDENCE/DISCOVERY LIMIT",
        "SOURCE_NOT_IN_VARIANT_A": "EVIDENCE/DISCOVERY LIMIT",
        "NATIVE_FETCH_FAILED": "EVIDENCE/DISCOVERY LIMIT",
        "NO_USABLE_TEXT": "EVIDENCE/DISCOVERY LIMIT",
        "CANDIDATE_ADMISSION_REJECTED_PUBLICATION_WINDOW": "ADMISSION LIMIT",
        "CANDIDATE_ADMISSION_REJECTED_ATTACK_VOCABULARY": "ADMISSION LIMIT",
        "CANDIDATE_ADMISSION_REJECTED_OTHER": "ADMISSION LIMIT",
        "CLASSIFIER_ATTACK_EVENT_TRULY_INSUFFICIENT": "EVIDENCE/DISCOVERY LIMIT",
        "CLASSIFIER_ATTACK_EVENT_PRESENT_BUT_PARSER_MISSES": "CLASSIFIER/PARSER LIMIT",
        "CLASSIFIER_EVENT_TIME_TRULY_ABSENT": "EVIDENCE/DISCOVERY LIMIT",
        "CLASSIFIER_EVENT_TIME_PRESENT_BUT_PARSER_MISSES": "CLASSIFIER/PARSER LIMIT",
        "CLASSIFIER_TEMPORAL_REPRESENTATION_LIMIT": "CLASSIFIER/PARSER LIMIT",
        "CLASSIFIER_EVENT_TIME_OUTSIDE_EPISODE": "EVIDENCE/DISCOVERY LIMIT",
        "CLASSIFIER_SAME_ATTACK_INSUFFICIENT": "CLASSIFIER/PARSER LIMIT",
    }
    old_to_new = {
        "EVIDENCE_TRULY_LACKS_ATTACK_EVENT": "CLASSIFIER_ATTACK_EVENT_TRULY_INSUFFICIENT",
        "ATTACK_EVENT_PRESENT_BUT_PARSER_MISSES": "CLASSIFIER_ATTACK_EVENT_PRESENT_BUT_PARSER_MISSES",
        "EVIDENCE_TRULY_LACKS_EVENT_TIME": "CLASSIFIER_EVENT_TIME_TRULY_ABSENT",
        "EVENT_TIME_PRESENT_BUT_TEMPORAL_PARSER_MISSES": "CLASSIFIER_EVENT_TIME_PRESENT_BUT_PARSER_MISSES",
        "EVENT_TIME_PARSED_BUT_TEMPORAL_REPRESENTATION_CANNOT_EXPRESS": "CLASSIFIER_TEMPORAL_REPRESENTATION_LIMIT",
        "EVENT_TIME_VALID_BUT_OUTSIDE_EPISODE": "CLASSIFIER_EVENT_TIME_OUTSIDE_EPISODE",
        "SAME_ATTACK_LINKAGE_NOT_DURABLY_ESTABLISHED": "CLASSIFIER_SAME_ATTACK_INSUFFICIENT",
        "PUBLICATION_WINDOW_REJECTS_RELEVANT_LATE_SUMMARY": "CANDIDATE_ADMISSION_REJECTED_PUBLICATION_WINDOW",
        "OTHER_ADMISSION_ATTACK_VOCABULARY_NOT_MATCHED": "CANDIDATE_ADMISSION_REJECTED_ATTACK_VOCABULARY",
    }
    missed, extras_all, remaining_source = [], [], {}
    for ep in positive_episodes:
        eid = ep["episode_id"]; n = variant[eid]
        if n["final"] in POS: continue
        rows = by_out[eid]
        old_record = original_diag[eid]
        old_root = old_record.get("forensic_primary_root_cause")
        newly_admitted = [r for r in n["candidate_records"] if r.get("source_family") in VARIANT_A]
        old_can = base[eid]["candidate_count"] > 0
        out_nona = [x for x in rows if x["source_family"] not in VARIANT_A
                    and not p.fixed_family_for_url(x["native_url"])]
        out_relevant = eid in useful
        eligible_unselected_admissible = sorted({x["source_family"] for x in out_nona
            if out_relevant and x["candidate_semantics_if_admitted"] == "ADMISSIBLE_IF_SOURCE_ELIGIBLE"})
        eligible_rejected = [x for x in rows if x["source_family"] in VARIANT_A
            and x.get("source_native_text_available") and
            x["candidate_semantics_if_admitted"] != "ADMISSIBLE_IF_SOURCE_ELIGIBLE"]
        old_candidate_rejected = old_record.get("recovered_evidence", [])
        code_reasons = sorted({c for r in n["candidate_records"] for c in r.get("reason_codes", [])})
        if n["candidate_count"]:
            # Pre-existing candidate text received a full human-readable forensic diagnosis.
            # Only retain those findings if the new candidates do not bring a stronger binding.
            newer_strict_attack = any("STRICT_EXPLOSION_EVIDENCE" in (r.get("reason_codes") or [])
                                       for r in newly_admitted)
            newer_temporal = any((r.get("temporal_binding") or {}).get("present")
                                 for r in newly_admitted)
            if old_can and old_root in old_to_new and not newer_temporal and not (
                    old_root == "EVIDENCE_TRULY_LACKS_ATTACK_EVENT" and newer_strict_attack):
                cls = old_to_new[old_root]
                explanation = "Retains predecessor source-native forensic finding; no more advanced Variant A temporal binding demonstrated."
            elif any("SAME_ATTACK_CONTEXT_NOT_SUPPORTED" in (r.get("reason_codes") or [])
                     for r in n["candidate_records"]):
                cls = "CLASSIFIER_SAME_ATTACK_INSUFFICIENT"
                explanation = "Candidate reached classifier but target same-attack proof is not established."
            elif any("TEMPORAL_EXPLICIT_EVENT_TIME_OUTSIDE_EPISODE" in (r.get("reason_codes") or [])
                     for r in n["candidate_records"]):
                cls = "CLASSIFIER_EVENT_TIME_OUTSIDE_EPISODE"
                explanation = "Candidate event time belongs outside target episode."
            elif any("NO_STRICT_EXPLOSION_EVIDENCE" in (r.get("reason_codes") or [])
                     for r in n["candidate_records"]) and not any(
                         "STRICT_EXPLOSION_EVIDENCE" in (r.get("reason_codes") or [])
                         for r in n["candidate_records"]):
                cls = "CLASSIFIER_ATTACK_EVENT_TRULY_INSUFFICIENT"
                explanation = "Admitted candidate lacks qualifying attack-event proof in classifier reason codes."
            elif any("NO_STRICT_TEMPORAL_BINDING" in (r.get("reason_codes") or [])
                     for r in n["candidate_records"]):
                cls = "OTHER"
                explanation = "Admitted candidate lacks strict episode-specific temporal proof; genuine absence versus parser miss not demonstrated from prior forensic evidence."
            else:
                cls = "OTHER"
                explanation = "Candidate is admitted but no safe single semantic failure class is proven by available classifier reason codes."
        else:
            if old_root in old_to_new and old_to_new[old_root].startswith("CANDIDATE_ADMISSION"):
                cls = old_to_new[old_root]
                explanation = "Predecessor source-native forensic established admission rejection for target evidence."
            elif eligible_rejected and eid in useful:
                why = {x["candidate_semantics_if_admitted"] for x in eligible_rejected}
                if "OUTSIDE_PUBLICATION_WINDOW" in why:
                    cls = "CANDIDATE_ADMISSION_REJECTED_PUBLICATION_WINDOW"
                elif "ATTACK_VOCABULARY_NOT_MATCHED" in why:
                    cls = "CANDIDATE_ADMISSION_REJECTED_ATTACK_VOCABULARY"
                else:
                    cls = "CANDIDATE_ADMISSION_REJECTED_OTHER"
                explanation = "Existing Variant A publisher evidence failed unchanged admission; prior attribution establishes relevance."
            elif eligible_unselected_admissible:
                cls = "SOURCE_NOT_IN_VARIANT_A"
                explanation = "Previously independently forensically assessed useful outside-fixed evidence remains excluded under Variant A."
            elif eligible_rejected and old_root == "FIXED_SOURCE_SET_LIMITATION_WITH_USEFUL_OUTSIDE_SOURCE_EVIDENCE":
                cls = "CANDIDATE_ADMISSION_REJECTED_OTHER"
                explanation = "Previously useful evidence in added family remains rejected at admission; exact rejection in records."
            else:
                cls = "NO_RELEVANT_NATIVE_RESULT"
                explanation = "No source-native evidence proven both relevant to this alert and admissible under frozen Variant A."
        bucket = first_classes.get(cls) or ("CLASSIFIER/PARSER LIMIT" if n["candidate_count"] else "EVIDENCE/DISCOVERY LIMIT")
        missed.append({
            "episode_id": eid, "alert_start": ep["alert_start"], "alert_end": ep["alert_end"],
            "variant_a_final": n["final"], "candidate_count": n["candidate_count"],
            "first_failure": cls, "bucket": bucket, "explanation": explanation,
            "prior_forensic_root": old_root, "classifier_reason_codes": code_reasons,
            "new_variant_a_candidates": newly_admitted,
            "unselected_relevant_admissible_source_families": eligible_unselected_admissible,
            "native_admission_rejections": [{
                "url": x["native_url"], "family": x["source_family"],
                "reason": x["candidate_semantics_if_admitted"]} for x in eligible_rejected],
        })
        remaining_source[eid] = eligible_unselected_admissible
    if len(missed) != 47: raise RuntimeError("REMAINING_POSITIVES_NOT_47")
    # The ceiling is only an upper bound, never a forecast of classifier success.
    outside_ceiling = sorted({eid for eid, families in remaining_source.items() if families})
    native_outside = sorted({x["source_family"] for x in outside
                           if x["episode_id"] in {e["episode_id"] for e in positive_episodes}
                           and x["source_family"] not in VARIANT_A and
                           not p.fixed_family_for_url(x["native_url"])})
    useful_non_variant = {
        ep["episode_id"] for ep in positive_episodes
        if ep["episode_id"] in useful and any(x["source_family"] not in VARIANT_A
            for x in by_out[ep["episode_id"]])
    }
    recovered_predecessor = old_diag.get("publication_window_forensic_table", [])
    old_pub = defaultdict(list)
    for x in recovered_predecessor: old_pub[x["episode_id"]].append(x)
    admission_roots = [x for x in missed if x["bucket"] == "ADMISSION LIMIT"]
    admission_details = []
    for x in admission_roots:
        old_rows = old_pub.get(x["episode_id"], [])
        # No assertion of safe recovery from late publication without in-alert event proof.
        late_in = any(v.get("diagnosis_class") == "LATE_PUBLICATION_WITH_IN_WINDOW_EVENT_TIME"
                      for v in old_rows)
        late_other = any(v.get("diagnosis_class") == "GENUINELY_LATE_PUBLICATION" for v in old_rows)
        admission_details.append({
            "episode_id": x["episode_id"], "first_failure": x["first_failure"],
            "late_with_in_window_event_time": late_in, "genuinely_late_publication": late_other,
            "attack_vocabulary_present_but_admission_misses": x["first_failure"] == "CANDIDATE_ADMISSION_REJECTED_ATTACK_VOCABULARY",
            "another_admission_block": x["first_failure"] == "CANDIDATE_ADMISSION_REJECTED_OTHER",
        })
    classifier_details = [x for x in missed if x["candidate_count"] > 0]
    proven_safe = {
        "further_source_set": set(outside_ceiling),
        "candidate_admission": {x["episode_id"] for x in admission_details if x["late_with_in_window_event_time"] or
                                 x["attack_vocabulary_present_but_admission_misses"]},
        "attack_event_parser": {x["episode_id"] for x in missed if x["first_failure"] == "CLASSIFIER_ATTACK_EVENT_PRESENT_BUT_PARSER_MISSES"},
        "temporal_parser": {x["episode_id"] for x in missed if x["first_failure"] == "CLASSIFIER_EVENT_TIME_PRESENT_BUT_PARSER_MISSES"},
        "temporal_representation": {x["episode_id"] for x in missed if x["first_failure"] == "CLASSIFIER_TEMPORAL_REPRESENTATION_LIMIT"},
        "same_attack": {x["episode_id"] for x in missed if x["first_failure"] == "CLASSIFIER_SAME_ATTACK_INSUFFICIENT"},
    }
    recommendation = {
        "further_source_set": "DIAGNOSE/REVISE HISTORICAL SOURCE SET FURTHER",
        "candidate_admission": "REPAIR HISTORICAL PUBLICATION/EVENT-TIME ADMISSION",
        "attack_event_parser": "REPAIR ATTACK-EVENT PARSER",
        "temporal_parser": "REPAIR TEMPORAL PARSER",
        "temporal_representation": "REPAIR TEMPORAL REPRESENTATION",
        "same_attack": "REPAIR SAME-ATTACK LINKAGE",
    }
    rank = sorted(proven_safe, key=lambda x: (-len(proven_safe[x]),
              ["further_source_set", "candidate_admission", "attack_event_parser",
               "temporal_parser", "temporal_representation", "same_attack"].index(x)))
    top = rank[0]; n_top = len(proven_safe[top])
    if not n_top:
        top = "insufficient_evidence"
        recommended = "INSUFFICIENT EVIDENCE TO CHOOSE"
        verdict = "KYIV HISTORICAL VARIANT A DEVELOPMENT DIAGNOSIS = EVIDENCE-INSUFFICIENT"
    else:
        recommended = recommendation[top]
        verdict = {
          "further_source_set": "SOURCE-DOMINANT",
          "candidate_admission": "ADMISSION-DOMINANT",
          "attack_event_parser": "PARSER-DOMINANT",
          "temporal_parser": "TEMPORAL-DOMINANT",
          "temporal_representation": "TEMPORAL-DOMINANT",
          "same_attack": "MIXED"
        }[top]
        verdict = "KYIV HISTORICAL VARIANT A DEVELOPMENT DIAGNOSIS = " + verdict
    positive_final = [x for x in positive_episodes if variant[x["episode_id"]]["final"] in POS]
    if len(positive_final) != 1: raise RuntimeError("KNOWN_POSITIVE_COUNT_DRIFT")
    positive = positive_final[0]
    eid_pos = positive["episode_id"]
    contributing = [x for x in variant[eid_pos]["candidate_records"]
       if x.get("classifier_episode_id") == eid_pos and x.get("classifier_outcome") in ("approved_strict", "approved_sensitivity")]
    if not contributing: raise RuntimeError("REPRODUCED_POSITIVE_HAS_NO_DIRECT_SOURCE")
    holds = []
    for ep in hold_episodes:
        eid = ep["episode_id"]; v = variant[eid]
        accepted_forensic = {
           "f06c52e0ed82b44792ec2ec7": "NEW EVIDENCE SUPPORTS REOPENING HISTORICAL HOLD",
           "e56cdca45ed5b1cd7b0b9746": "NEW EVIDENCE GENUINELY SUPPORTS TARGET EPISODE",
        }.get(eid)
        holds.append({
           "episode_id": eid, "final": v["final"], "candidate_count": v["candidate_count"],
           "eligible_evidence": v["candidate_count"] > 0,
           "candidate_records": v["candidate_records"], "accepted_forensic": accepted_forensic,
           "disposition_mutated": False,
        })
        if v["final"] in POS and not accepted_forensic:
            raise RuntimeError("UNREVIEWED_HOLD_PROMOTED:" + eid)
    exact_verdicts = [
        {"episode_id": ep["episode_id"], "truth_label": ep["truth_label"],
         "final_verdict": variant[ep["episode_id"]]["final"],
         "candidate_count": variant[ep["episode_id"]]["candidate_count"],
         "candidate_records": variant[ep["episode_id"]]["candidate_records"],
         "alert_level_composition": variant[ep["episode_id"]]["composition"]}
        for ep in inp["episodes"]
    ]
    primary_counts = Counter(x["first_failure"] for x in missed)
    bucket_counts = Counter(x["bucket"] for x in missed)
    if sum(bucket_counts.values()) != 47: raise RuntimeError("FIRST_FAILURE_BUCKET_PARTITION_ERROR")
    d = {
       "schema": "kyiv-historical-variant-a-development-failure-diagnosis-v1",
       "source_set_freeze_sha256": freeze["manifest_sha256"],
       "semantic_isolation": "PASS",
       "frozen_variant": "VARIANT A", "added_sources": sorted(VARIANT_A),
       "replay_reproduced_predecessor": True, "replay_differences": [],
       "development_episodes": 67, "development_positives": 48, "development_holds": 19,
       "positive_with_eligible_evidence": pilot_replay["per_variant_development_results"]["VARIANT A"]["positive_with_eligible_evidence"],
       "positive_with_candidate": sum(variant[e["episode_id"]]["candidate_count"] > 0 for e in positive_episodes),
       "candidate_recall": sum(variant[e["episode_id"]]["candidate_count"] > 0 for e in positive_episodes)/48,
       "known_final_positives": len(positive_final), "final_positive_recall": len(positive_final)/48,
       "known_positive_verdict_counts": dict(Counter(variant[e["episode_id"]]["final"] for e in positive_episodes)),
       "newly_reproduced_positive": {
           "episode_id": eid_pos, "truth_label": positive["truth_label"],
           "source_family": contributing[0].get("source_family"),
           "source_url": contributing[0].get("candidate_url"),
           "admitted_candidate": contributing[0],
           "classifier_outcome": contributing[0].get("classifier_outcome"),
           "alert_level_verdict": variant[eid_pos]["final"],
           "exact_semantic_chain": contributing[0].get("reason_codes"),
           "new_source_eligible_only_under_variant_a": contributing[0].get("source_family") in VARIANT_A,
       },
       "all_67_final_verdicts": exact_verdicts,
       "all_48_positive_before_after_transitions": trans,
       "all_47_remaining_positive_failure_diagnoses": missed,
       "first_failure_counts": dict(primary_counts),
       "mutually_exclusive_first_failure_bucket_counts": dict(bucket_counts),
       "all_19_hold_results": holds,
       "hold_counts": dict(Counter(variant[e["episode_id"]]["final"] for e in hold_episodes)),
       "holds_with_candidate": sum(variant[e["episode_id"]]["candidate_count"] > 0 for e in hold_episodes),
       "demonstrated_unsupported_hold_promotions": 0,
       "remaining_source_set_ceiling": {
           "episodes_with_forensically_useful_outside_variant_a_source": len(useful_non_variant),
           "outside_source_families": native_outside,
           "plausibly_admissible_unique_missed_positives_upper_bound": len(outside_ceiling),
           "plausibly_admissible_episode_ids": outside_ceiling,
           "per_episode_families": remaining_source,
           "caution": "Only previously assessed useful evidence with unchanged admission pass; classification recovery not demonstrated",
       },
       "remaining_admission_recovery_ceiling": {
           "safe_unique_positive_ceiling": len(proven_safe["candidate_admission"]),
           "episodes": sorted(proven_safe["candidate_admission"]),
           "per_episode": admission_details,
           "genuinely_late_publication_count": sum(x["genuinely_late_publication"] for x in admission_details),
           "late_with_usable_in_window_event_time_count": sum(x["late_with_in_window_event_time"] for x in admission_details),
           "attack_vocabulary_miss_count": sum(x["attack_vocabulary_present_but_admission_misses"] for x in admission_details),
           "other_admission_block_count": sum(x["another_admission_block"] for x in admission_details),
       },
       "candidate_covered_nonpositive_diagnosis": classifier_details,
       "parser_temporal_ceilings": {k: {"unique_positive_ceiling": len(proven_safe[k]),
                                         "episode_ids": sorted(proven_safe[k])}
                                    for k in ("attack_event_parser", "temporal_parser", "temporal_representation", "same_attack")},
       "bottleneck_ranking": [
           {"mechanism": k, "demonstrated_safe_unique_positive_upper_bound": len(proven_safe[k]),
            "episode_ids": sorted(proven_safe[k])} for k in rank
       ],
       "dominant_remaining_bottleneck": top,
       "recommended_one_next_task": recommended,
       "independent_validation_readiness": "NOT READY FOR INDEPENDENT VALIDATION",
       "blind_per_episode_data_inspected": False, "blind_wrapper_decoding_attempts": 0,
       "independent_validation_started": False, "historical_backfill_started": False,
       "Neon_writes": 0, "production_mutations": 0,
       "mutation_confirmation": "Only two development-only research artifacts; no changes to existing source policy, classifier, candidate admission, production, Neon, blind, or historical data.",
       "verdict": verdict,
    }
    write_json(DIAG_OUT, d)
    print("VARIANT_A_REPLAY_DIAGNOSIS=" + json.dumps({
       "freeze_sha256": freeze["manifest_sha256"],
       "positives_eligible": d["positive_with_eligible_evidence"],
       "positives_with_candidate": d["positive_with_candidate"],
       "known_final_positives": d["known_final_positives"],
       "hold_counts": d["hold_counts"], "first_failures": dict(primary_counts),
       "bucket_counts": dict(bucket_counts),
       "rank": [{x: y for x, y in z.items() if x != "episode_ids"} for z in d["bottleneck_ranking"]],
       "recommendation": recommended, "verdict": verdict,
    }, sort_keys=True))

def main():
    for path, sha in EXPECTED_BLOBS.items():
        if git("rev-parse", f"HEAD:{path}") != sha:
            raise RuntimeError(f"FROZEN_BLOB_MISMATCH:{path}")
    p = load(PILOT, "frozen_source_proof")
    r = load(REPLAY, "frozen_replay_proof")
    frozen_manifest = freeze_variant_a_manifest(p)
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
    accepted_candidates = json.loads(CANDIDATES_ACCEPTED.read_text())
    expected_native = {x["native_url"]: x.get("source_native_text_sha256")
                       for x in accepted_candidates["outside_source_inventory"]
                       if x["source_family"] in VARIANT_A}
    native_drift = []
    for url, before in sorted(expected_native.items()):
        native, error = fetched.get(url, (None, "MISSING_URL"))
        after = sha256((native or {}).get("text") or "") if native else None
        if before != after:
            native_drift.append({"url": url, "old_sha256": before, "new_sha256": after, "error": error})
    if native_drift:
        raise RuntimeError("FROZEN_VARIANT_A_NATIVE_CORPUS_DRIFT:" + json.dumps(native_drift[:12]))
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
    passing = set(accepted) & VARIANT_A
    if passing != VARIANT_A:
        raise RuntimeError(f"VARIANT_A_SOURCE_QUALITY_DRIFT:{sorted(VARIANT_A - passing)}")
    cumulative = []
    variants = {}
    for tier in ("A",):
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
    # Preserve accepted pilot artifacts: never rewrite them in this diagnosis.

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
        emit_variant_a_diagnosis(inp, diag, outcomes, outside, fetched, candidates_artifact, artifact, frozen_manifest, p)
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
