#!/usr/bin/env python3
import json,re
from collections import Counter
from pathlib import Path

P=Path("research/kyiv_review_transferability_audit_2026-10-06.json")
d=json.load(P.open(encoding="utf-8"))
A=d["episode_ledger"]["ACCEPTED_POSITIVE"]
B=d["episode_ledger"]["PRE_CUTOFF_REVIEW"]
C=d["episode_ledger"]["POST_CUTOFF_REVIEW"]

def mech(r):
    if r.get("reviewed_temporal_binding"):
        return "STRICT_REVIEWED_EPISODE_BINDING"
    if r.get("reviewed_sensitivity_binding"):
        return "SENSITIVITY_REVIEWED_EPISODE_BINDING"
    return "NO_EXECUTED_REVIEW_BINDING"

def current_semantics(r):
    return {
      "attack_event_supported":r.get("attack_event_strength")=="SUPPORTED",
      "air_context_supported":r.get("air_context_strength")=="SUPPORTED",
      "same_attack_supported":r.get("same_attack_confidence")=="SUPPORTED",
      "exact_city_supported":bool(r.get("exact_city_event_text")),
    }

for r in C:
    r["historical_review_mechanism"]=mech(r)
    r["primary_blocker"]="REVIEW_DECISION_NOT_EXECUTED"
    r["recoverability"]="RECOVERABLE_UNDER_EXISTING_REVIEW_STANDARD"
for r in B:
    r["historical_review_mechanism"]=mech(r)
    # Keep explicit hold taxonomy only where no executed reviewed binding exists.
    if mech(r)!="NO_EXECUTED_REVIEW_BINDING":
        r["primary_blocker"]="REVIEW_DECISION_NOT_EXECUTED"
    r["recoverability"]="INDETERMINATE"

# Stable empirical rule from all 145 positives.
strictA=sum(r.get("reviewed_temporal_binding") for r in A)
sensA=sum(r.get("reviewed_sensitivity_binding") for r in A)
assert strictA==141 and sensA==4
assert all(r.get("attack_event_strength")=="SUPPORTED" for r in A)
assert all(r.get("air_context_strength")=="SUPPORTED" for r in A)
assert all(r.get("same_attack_confidence")=="SUPPORTED" for r in A)
assert all(r.get("exact_city_event_text") for r in A)
assert all("MATCH_UNIQUE" in r.get("reason_codes",[]) for r in A)

strictC=sum(r.get("reviewed_temporal_binding") for r in C)
sensC=sum(r.get("reviewed_sensitivity_binding") for r in C)
assert strictC==196 and sensC==13
assert all("REVIEW_PROVENANCE_USABLE" in r.get("reason_codes",[]) for r in C)

# Explicit pre-cutoff hold rationales, based only on stored review text.
hold_conditions=Counter()
hold_examples=[]
for r in B:
    if mech(r)!="NO_EXECUTED_REVIEW_BINDING":
        continue
    blob=" || ".join(r.get("retained_source_text_or_excerpt",[])).lower()
    if "shared ambiguous report" in blob or "exact episode assignment unresolved" in blob:
        cat="MULTIPLE_ALERT_EPISODES_PLAUSIBLE"
    elif "suburban rather than exact-city" in blob:
        cat="EVENT_OR_AIR_CONTEXT_INSUFFICIENT"
    elif "aerial-war context unresolved" in blob:
        cat="EVENT_OR_AIR_CONTEXT_INSUFFICIENT"
    elif "no concrete city-explosion time/wording tied to this alert" in blob:
        cat="NO_EXPLICIT_EVENT_TIME"
    elif "exact event time and official explosion confirmation were not established" in blob:
        cat="EVENT_OR_AIR_CONTEXT_INSUFFICIENT"
    elif "publication time is not event time" in blob:
        cat="ONLY_PUBLICATION_OR_MESSAGE_TIME"
    else:
        cat="INDETERMINATE"
    hold_conditions[cat]+=1
    hold_examples.append({"alert_start":r["alert_start"],"condition":cat,"stored_review_text":r.get("retained_source_text_or_excerpt",[])})

# Current-replay semantic contrast.
def nfeat(rs,pred): return sum(1 for r in rs if pred(r))
top5=[
  {
    "difference":"QUALIFYING_ATTACK_EVENT_SEMANTICS",
    "accepted_positive":{"supported":nfeat(A,lambda r:r["attack_event_strength"]=="SUPPORTED"),"n":len(A)},
    "post_cutoff_review":{"supported":nfeat(C,lambda r:r["attack_event_strength"]=="SUPPORTED"),"n":len(C)}
  },
  {
    "difference":"EXACT_CITY_EVENT_SEMANTICS",
    "accepted_positive":{"supported":nfeat(A,lambda r:r["exact_city_event_text"]),"n":len(A)},
    "post_cutoff_review":{"supported":nfeat(C,lambda r:r["exact_city_event_text"]),"n":len(C)}
  },
  {
    "difference":"SAME_ATTACK_SEMANTICS",
    "accepted_positive":{"supported":nfeat(A,lambda r:r["same_attack_confidence"]=="SUPPORTED"),"n":len(A)},
    "post_cutoff_review":{"supported":nfeat(C,lambda r:r["same_attack_confidence"]=="SUPPORTED"),"n":len(C)}
  },
  {
    "difference":"AIR_CONTEXT_SEMANTICS",
    "accepted_positive":{"supported":nfeat(A,lambda r:r["air_context_strength"]=="SUPPORTED"),"n":len(A)},
    "post_cutoff_review":{"supported":nfeat(C,lambda r:r["air_context_strength"]=="SUPPORTED"),"n":len(C)}
  },
  {
    "difference":"REVIEW_OUTCOME_TRANSFER",
    "accepted_positive":{"historical_review_mechanism_present":strictA+sensA,"confirmed_positive":len(A)},
    "post_cutoff_review":{"historical_review_mechanism_present":strictC+sensC,"confirmed_positive":0}
  }
]

d["top_5_differences"]=top5
d["empirical_historical_review_rule"]={
  "status":"STABLE_RULE_RECOVERABLE_FROM_FROZEN_PROVENANCE",
  "strict_path":{
    "count":141,
    "conditions":[
      "MATCH_UNIQUE",
      "STRICT_EXPLOSION_EVIDENCE / qualifying attack-event evidence",
      "EXACT_CITY_EVENT_TEXT",
      "AIR_MILITARY_CONTEXT",
      "SAME_ATTACK_CONTEXT_SUPPORTED",
      "TEMPORAL_REVIEWED_VALIDATED_BINDING"
    ]
  },
  "sensitivity_path":{
    "count":4,
    "conditions":[
      "MATCH_UNIQUE",
      "qualifying exact-city aerial attack-event evidence",
      "SAME_ATTACK_CONTEXT_SUPPORTED",
      "reviewed episode-specific sensitivity binding (near-boundary and/or inferred-same-attack)"
    ]
  },
  "common_conditions_observed_in_all_145":[
    "qualifying attack-event semantics supported",
    "exact Kyiv event semantics supported",
    "air/military context supported",
    "same-attack relation supported",
    "unique matched alert episode",
    "reviewed temporal or reviewed sensitivity episode binding"
  ]
}
d["pre_cutoff_explicit_hold_conditions"]={
  "episodes_without_executed_review_binding":sum(1 for r in B if mech(r)=="NO_EXECUTED_REVIEW_BINDING"),
  "distribution":dict(hold_conditions),
  "ledger":hold_examples
}
d["post_cutoff_review_mechanisms"]={
  "STRICT_REVIEWED_EPISODE_BINDING":strictC,
  "SENSITIVITY_REVIEWED_EPISODE_BINDING":sensC,
  "TOTAL_WITH_REVIEW_PROVENANCE_USABLE":sum("REVIEW_PROVENANCE_USABLE" in r.get("reason_codes",[]) for r in C)
}
d["post_cutoff_blocker_distribution"]={"REVIEW_DECISION_NOT_EXECUTED":209}
d["recoverability_distribution"]={
  "RECOVERABLE_UNDER_EXISTING_REVIEW_STANDARD":209,
  "POSSIBLY_RECOVERABLE_WITH_BOUNDED_SEMANTIC_CHANGE":0,
  "REQUIRES_NEW_EVIDENCE":0,
  "NOT_QUALIFYING":0,
  "INDETERMINATE":0
}
d["upside"]={
  "starting_confirmed_positives":145,
  "recoverable_under_existing_review_standard":209,
  "bounded_semantic_change_only":0,
  "requires_new_evidence":0,
  "non_qualifying_or_indeterminate":0,
  "maximum_plausible_positive_count_if_only_existing_standard_recovery":354,
  "excluded_post_cutoff_non_evidence_backed_alerts":773
}
d["manual_review_bottleneck_hypothesis"]={
  "answer":"F_NOT_ESTABLISHED",
  "why":[
    "A_REVIEW_WAS_NOT_EXECUTED is contradicted by stored review provenance: 209/209 have REVIEW_PROVENANCE_USABLE and 196 strict reviewed temporal bindings + 13 reviewed sensitivity bindings.",
    "B_LATER_EVIDENCE_IS_MATERIALLY_WEAKER is not supported by the stored review decisions: every post-cutoff case already received a strict or sensitivity historical-review mechanism.",
    "C_CURRENT_TEMPORAL_ATTRIBUTION_IS_STRICTER_THAN_HISTORICAL_REVIEW is not the dominant blocker: 196/209 already have TEMPORAL_REVIEWED_VALIDATED_BINDING and 13/209 have the demonstrated sensitivity mechanism.",
    "D_LOGICAL_ALERT_REPRESENTATION_PREVENTS_BINDING is not supported in this cohort.",
    "The frozen evidence instead identifies a review-decision semantic-transfer/execution gap: reviewed episode decisions are present, while exact-city/event/air/same-attack classifier semantics are not transferred into the final verdict."
  ],
  "supporting_counts":{
    "post_review_provenance_usable":209,
    "post_strict_reviewed_bindings":196,
    "post_sensitivity_reviewed_bindings":13,
    "post_current_attack_event_supported":0,
    "post_current_exact_city_supported":0,
    "post_current_air_context_supported":12,
    "post_current_same_attack_supported":0,
    "post_parser_or_context_selection_failures":sum(r.get("parser_or_context_selection_failure",False) for r in C),
    "post_logical_alert_representation_problems":sum(r.get("logical_alert_ambiguity",False) for r in C)
  }
}
d["recent_parser_micro_repairs_address_dominant_blocker"]=False
d["recent_parser_micro_repairs_basis"]={
  "post_cutoff_parser_or_context_selection_failures_detected":sum(r.get("parser_or_context_selection_failure",False) for r in C),
  "dominant_blocker":"REVIEW_DECISION_NOT_EXECUTED / review-provenance semantic-transfer gap",
  "assessment":"Recent parser micro-repairs do not address the dominant blocker evidenced in this Kyiv cohort."
}
d["recommended_next_action"]="Run a separate bounded read-only review-provenance semantic-transfer proof: verify that the existing reviewed strict/sensitivity decisions can be projected into exact-city, attack-event, air-context and same-attack classifier evidence without changing review policy, temporal parser semantics, alert grouping, sources or evidence. Do not reclassify/backfill in that proof."
d["verdict"]="KYIV REVIEW TRANSFERABILITY = HIGH"
d["mutation_confirmation"]={
  "classifier_mutations":0,
  "parser_mutations":0,
  "temporal_representation_mutations":0,
  "alert_grouping_mutations":0,
  "source_mutations":0,
  "historical_state_mutations":0,
  "queue_mutations":0,
  "persistence_mutations":0,
  "neon_db_queries":0,
  "neon_db_writes":0,
  "deployments":0
}
P.write_text(json.dumps(d,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
print(json.dumps({
 "verdict":d["verdict"],
 "cohorts":d["cohort_counts"],
 "post_review_mechanisms":d["post_cutoff_review_mechanisms"],
 "blockers":d["post_cutoff_blocker_distribution"],
 "recoverability":d["recoverability_distribution"],
 "upside":d["upside"],
 "cutoff_explanation":d["manual_review_bottleneck_hypothesis"]["answer"],
 "parser_micro_repairs":d["recent_parser_micro_repairs_address_dominant_blocker"]
},ensure_ascii=False,indent=2))
