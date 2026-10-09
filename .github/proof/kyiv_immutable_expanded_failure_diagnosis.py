#!/usr/bin/env python3
"""Read-only frozen-artifact diagnosis; writes a JSON report, never fetches external evidence."""
from __future__ import annotations
import collections, datetime, hashlib, json, re, sys
from datetime import timedelta
from pathlib import Path

DIR=Path(sys.argv[1]) if len(sys.argv)>1 else Path("diagnosis-input")
OUT=Path(sys.argv[2]) if len(sys.argv)>2 else Path("diagnosis-output.json")
def load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
a=load(DIR/"acceptance"/"acceptance-proof.json")
d=load(DIR/"acquisition"/"kyiv_historical_runner_discovery_snapshot_2026-10-09.json")
n=load(DIR/"acquisition"/"kyiv_historical_runner_native_corpus_2026-10-09.json")
z=load(DIR/"acquisition"/"kyiv_historical_runner_normalized_evidence_2026-10-09.json")
r=load(DIR/"replay"/"runner-replay-1.json")
fr=load("research/kyiv_immutable_development_source_set_expanded_freeze_2026-10-09.json")
expected={"discovery":"fc1e184741c8409ce634015771a9484de8cfd8230037be56e3d8970d0178e5cc",
"native":"bcfdedba186b58671dab7c3c1bd33dc8ec0f2772c8b9f9c3bf053c7d64cff858",
"normalized":"e5790301a8d17b9997a3dbdfb71651e486de8ba6a4c39a552043754805e7ce2d"}
def canonical(doc): return (json.dumps(doc,sort_keys=True,ensure_ascii=False,separators=(",",":"))+"\n").encode("utf-8")
for name,obj in [("discovery",d),("native",n),("normalized",z)]:
 t=dict(obj);recorded=t.pop("payload_sha256")
 assert hashlib.sha256(canonical(t)).hexdigest()==recorded==expected[name], "IMMUTABLE_HASH_MISMATCH:"+name
freeze_sha="7fdcc2903205e8fc489b2eff588332a45cfaca09"
manifest_sha="58dbde111229d099413ad03e99be3839557431957c4ac72832b23be8a49bc08e"
classifier_sha="71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
classifier_blob="778469b74c2aa807d851cf2c2ee35cf4aa785589"
sources=["VA_Kyiv","KyivCityOfficial","vitaliy_klitschko","dsns_kyiv","kpszsu","suspilnenews","suspilne_kyiv","suspilne.media/kyiv","BBC_Ukrainian","Radio_Svoboda","Suspilne_National","war.telegraf.com.ua","5.ua","zaxid.net","kyiv.novyny.live"]
assert fr["expanded_development_manifest_sha256"]==a["expanded_development_manifest_sha256"]==manifest_sha
assert hashlib.sha256(canonical(a["expanded_development_manifest"])).hexdigest()==manifest_sha
assert fr["verdict"]=="KYIV IMMUTABLE EXPANDED DEVELOPMENT SOURCE SET = FROZEN"
assert a["source_families"]==sources==a["expanded_development_manifest"]["included_source_families"]
assert a["authoritative_classifier_commit"]==classifier_sha and a["authoritative_classifier_blob"]==classifier_blob
assert a["proof_run_id"]==37947654494 and a["result"]=="ALL_ACCEPTANCE_GATES_PASS"
assert a["proof_head_sha"]=="6f237628994c6d6ae1c6a1f50c73069473ce27e7"
assert len(d["development_episodes"])==67 and len(a["episode_classifier_traces_and_verdicts"])==67
cases_text="""a270a3c5ea1acc90815b3fa7|NO_RELEVANT_FROZEN_NATIVE_RESULT|Articles concern Oct 17, not Oct 15
6e4aada601d4b2bdd4e82796|RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET|Relevant Oct 19 Kyiv defence in bigkyiv.com.ua
ffdd8e7b96244ea6d8eff1ba|ADMISSION_PUBLICATION_WINDOW|Relevant Dec 31 BBC has midnight timestamp before gate
bc6a6d169ce879e22f52c163|NO_RELEVANT_FROZEN_NATIVE_RESULT|No frozen evidence of Apr 20-21 target
9fdcbb450cc23f35cffa44a5|NO_RELEVANT_FROZEN_NATIVE_RESULT|No relevant May 26 target evidence
0e8524c2751c7a424a68005f|RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET|June 6 Kyiv defence in outside nv.ua; no publication timestamp
4ccafc37528fe99ae73fab25|RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET|May 8 Glavcom documents incoming Kyiv missiles
0404dff72663daa6be63e53d|NO_RELEVANT_FROZEN_NATIVE_RESULT|Discovered attacks on Sept 12 and Sept 16, not Sept 14
d3bd74d1f16f20c03bea4c37|RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET|Sept 28 target title at nashkiev.ua, body low-quality and undated
bce8edfb6de8569f8f0cfb78|RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET|Oct 6-7 Kyiv attacks in tested Glavcom and Kyiv24
01ba82a909e539ff5cc3bd0b|RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET|Oct 19 night attack in tested Novynarnia
1e5a30f90ed7c3d37acfec09|RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET|Nov 4 debris in Kyiv in outside Interfax
ff853b73b65d1efa270a3c00|RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET|Nov 20 Kyiv UAV report in Focus includes retracted damage details
33b1cae83785426737f84083|RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET|Contemporaneous Jan 3 city explosions report in Censor
74f6abf659844954ad2e49d6|NO_RELEVANT_FROZEN_NATIVE_RESULT|Irpin reconstruction and unrelated Jan 16 news
f2225226e10802309d9e1f28|RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET|Jan 29 drone/debris in tested Kyiv24
d38211541ab9a1cb801d172e|RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET|Feb 4 Kyiv drone debris in tested Kyiv24 and Interfax
636a2ee8464e0041c402cef1|EVENT_TIME_PRESENT_BUT_TEMPORAL_PARSER_MISSES|Kyiv city drone attacks described from 02:00 local
9a2bf3c34a79636d8066c78d|EVENT_TIME_OUTSIDE_EPISODE|09:30 Kyiv blasts preceded target alert
8fbd6afd7256938d98a8604b|EXACT_CITY_CLASSIFIER_INSUFFICIENT|Kyiv-Chop highway by Busk is outside Kyiv city
147c36b91f2873dbdb60111b|ATTACK_EVENT_TRULY_INSUFFICIENT|Air-defence donation is no target attack
cbf5948f83b063e3f47d5f15|EVENT_TIME_TRULY_ABSENT|Night attack report has no episode-specific Kyiv event time
c475d1dca5c22956189e88e3|EVENT_TIME_PRESENT_BUT_TEMPORAL_PARSER_MISSES|Kyiv witness 05:00 then explosion within target
9af004368bc48e63928d7bfb|EVENT_TIME_OUTSIDE_EPISODE|Approved_sensitivity candidates instead describe May 30 night
88ca1c1ef79951ae26254a27|ATTACK_EVENT_TRULY_INSUFFICIENT|Planned quarry blasting, not military strike
8f30ec2c7271b6334f0e330e|EVENT_TIME_OUTSIDE_EPISODE|July 17 feature describes July 8 Ohmatdyt strike
9a7292036d131c5ba4aef348|EXACT_CITY_CLASSIFIER_INSUFFICIENT|Only Kyiv oblast homes/debris, not city
cfd8acaf2ae96fb3ab6508d6|EVENT_TIME_PRESENT_BUT_TEMPORAL_PARSER_MISSES|Actual 08:25 Kyiv explosions in target alert
168254a2ce25aaddeebac2ea|TEMPORAL_REPRESENTATION_LIMIT|Night and morning Aug 29 updates; 05:50 update not event clock
0cd3f3ba51803739eeff6e54|EXACT_CITY_CLASSIFIER_INSUFFICIENT|Glevakha in Kyiv oblast only
41d9805f11c0502bf96883ef|SAME_ATTACK_INSUFFICIENT|Oct 25 drone city hit but three distinct alerts during night
4a80aa1717ac46c27bdae139|EVENT_TIME_TRULY_ABSENT|Oct 30 overnight incident without target-specific clock
4049f3c4caa124ef85917591|EVENT_TIME_OUTSIDE_EPISODE|Nov 2 morning 05:02 and evening news do not bind 11:30 alert
88a0811097de29dc32d957dc|EVENT_TIME_TRULY_ABSENT|Evening crane strike has article timestamp only
c5f05a41bcd9e336afbb2362|EVENT_TIME_PRESENT_BUT_TEMPORAL_PARSER_MISSES|Blasts after 08:00 and drone at 08:17 during city target
1216abdb8a6d4cf8febfa361|TEMPORAL_REPRESENTATION_LIMIT|Correct Nov 24 city explosions only broad evening expression
16bc2bf84fc831300762775e|EVENT_TIME_TRULY_ABSENT|Nov 29 night news not specific to Nov 28 late-evening alarm
26c809a6df927f379fa024c2|EVENT_TIME_TRULY_ABSENT|Dec 1 overnight news has no target interval clock
b1a3ce8a8570afa5bef2aea9|ATTACK_EVENT_TRULY_INSUFFICIENT|Dec 13 morning attack and unrelated power schedules, not Dec 12 alarm
9655b05af7afaf32ec48589c|TEMPORAL_REPRESENTATION_LIMIT|06:45 alarm and soon-after explosions need interval model
5ccb7f44480bee98de8e01c4|TEMPORAL_REPRESENTATION_LIMIT|07:17 alarm, blasts less than one hour later
d3111283a5df66d38a665c20|EVENT_TIME_PRESENT_BUT_TEMPORAL_PARSER_MISSES|Kyiv PПО operating at 23:03 local with same-time blasts
880f46473f3bc2726147b82f|EXACT_CITY_CLASSIFIER_INSUFFICIENT|Unspecified drone debris found in Kyiv oblast"""
cases={}
for line in cases_text.splitlines():
 eid,cat,reason=line.split("|",2)
 assert eid not in cases
 cases[eid]=(cat,reason)
cats=["NO_RELEVANT_FROZEN_NATIVE_RESULT","RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET","NATIVE_ACQUISITION_FAILED","ADMISSION_PUBLICATION_WINDOW","ADMISSION_ATTACK_VOCABULARY","ADMISSION_EXACT_CITY","ADMISSION_OTHER","ATTACK_EVENT_PRESENT_BUT_PARSER_MISSES","ATTACK_EVENT_TRULY_INSUFFICIENT","EVENT_TIME_PRESENT_BUT_TEMPORAL_PARSER_MISSES","EVENT_TIME_TRULY_ABSENT","TEMPORAL_REPRESENTATION_LIMIT","EVENT_TIME_OUTSIDE_EPISODE","EXACT_CITY_CLASSIFIER_INSUFFICIENT","AIR_CONTEXT_INSUFFICIENT","SAME_ATTACK_INSUFFICIENT","OTHER_CLASSIFIER_FAILURE"]
quotes={
"636a2ee8464e0041c402cef1":("03bb94c6acdb8b765952c3a7","Починаючи з 2:00 після опівночі"),
"c475d1dca5c22956189e88e3":("bbb04ce34aba2a895fbc2ca3","О пʼятій ранку я завжди відкриваю ворота"),
"cfd8acaf2ae96fb3ab6508d6":("f0882d6580bb10476195589f","Близько 8:25 у Києві пролунали повторні вибухи"),
"c5f05a41bcd9e336afbb2362":("4f42246d7a7f7bdf08fc419d","Вибухи знову пролунали в Києві після 8 ранку"),
"d3111283a5df66d38a665c20":("6cbdf4909143c5622c726e0d","О 23:03 у КМВА зазначили, що в Києві працює ППО"),
"168254a2ce25aaddeebac2ea":("f80c7cec0bd7582e36458eb1","Мер столиці о 05:50 уточнив"),
"1216abdb8a6d4cf8febfa361":("9c87253c0bf69c8a4596f9e7","Ввечері 24 листопада у Києві пролунали вибухи"),
"9655b05af7afaf32ec48589c":("22aa010bef7f2012eaa4d169","У столиці повітряну тривогу оголосили о 6:45. Невдовзі пролунала серія вибухів"),
"5ccb7f44480bee98de8e01c4":("829903ed0656d90c152f4de1","Повітряну тривогу у столиці оголосили о 7.17. Менше ніж через годину пролунали вибухи")}
outside={
"6e4aada601d4b2bdd4e82796":["bigkyiv.com.ua"],
"0e8524c2751c7a424a68005f":["OUTSIDE:nv.ua"],
"4ccafc37528fe99ae73fab25":["Glavcom"],
"d3bd74d1f16f20c03bea4c37":["OUTSIDE:nashkiev.ua"],
"bce8edfb6de8569f8f0cfb78":["Glavcom","Kyiv24"],
"01ba82a909e539ff5cc3bd0b":["Novynarnia"],
"1e5a30f90ed7c3d37acfec09":["OUTSIDE:interfax.com.ua"],
"ff853b73b65d1efa270a3c00":["Focus"],
"33b1cae83785426737f84083":["OUTSIDE:censor.net"],
"f2225226e10802309d9e1f28":["Kyiv24"],
"d38211541ab9a1cb801d172e":["Kyiv24","OUTSIDE:interfax.com.ua"]}
pos={"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"}
traces=a["episode_classifier_traces_and_verdicts"]
ep={x["episode_id"]:x for x in d["development_episodes"]}
nmap={x["requested_native_url"]:x for x in n["records"]}
disco=collections.defaultdict(list)
for h in d["search_hits"]: disco[h["episode_id"]].append(h)
attack=re.compile("вибух|атак|обстріл|ппо|уламк|влуч|бпла|безпілот|дрон|шахед|ракет|баліст",re.I)
city=re.compile(r"\bКи(їв|єв)",re.I)
parse=lambda s:datetime.datetime.fromisoformat(s.replace("Z","+00:00"))
def admission(episode,record):
 native=record.get("native") or {}
 if not native.get("text"):return "NO_TEXT"
 if not native.get("published_at"):return "NO_PUBLICATION_TIMESTAMP"
 pub=parse(native["published_at"])
 if not parse(episode["alert_start"])-timedelta(hours=6)<=pub<=parse(episode["alert_end"])+timedelta(hours=24):return "OUTSIDE_PUBLICATION_WINDOW"
 text=(native.get("title") or "")+" "+native["text"]
 if not attack.search(text):return "NO_ATTACK_VOCABULARY"
 if not city.search(text):return "NO_EXACT_CITY"
 return "PASS"
good_families={f for f,x in r["quality_gates"].items() if x["verdict"]=="PASS"}
def previous(id,family):
 name="STAGE2 SINGLE "+family
 if name not in r["results"]:return []
 test=next(x for x in r["results"][name]["per_episode"] if x["episode_id"]==id)
 cc=[x for x in test["candidates"] if x.get("family")==family]
 return [{"configuration":name,"candidate_count":len(cc),"final_verdict":test["final"],"candidate_traces":cc}]
finals=[x for x in traces if x["truth_label"] in pos and x["final"] in pos]
failures=[x for x in traces if x["truth_label"] in pos and x["final"] not in pos]
assert len(finals)==5 and len(failures)==43 and set(cases)=={x["episode_id"] for x in failures}
assert sum(x["candidate_count"]==0 for x in failures)==17
assert sum(x["candidate_count"]>0 for x in failures)==26
assert sum(x["candidate_count"]>0 and x["truth_label"] in pos for x in traces)==31
assert sum(x["final"]=="STRICT_EVENT_POSITIVE" and x["truth_label"] in pos for x in traces)==3
assert sum(x["final"]=="SENSITIVITY_EVENT_POSITIVE" and x["truth_label"] in pos for x in traces)==2
assert sum(x["candidate_count"]>0 and x["truth_label"]=="HOLD_CONTROL" for x in traces)==13
assert sum(x["final"]=="STRICT_EVENT_POSITIVE" and x["truth_label"]=="HOLD_CONTROL" for x in traces)==2
assert sum(x["final"]=="SENSITIVITY_EVENT_POSITIVE" and x["truth_label"]=="HOLD_CONTROL" for x in traces)==0
bad=[];no_candidate=[]; counts=collections.Counter()
for row in sorted(failures,key=lambda x:ep[x["episode_id"]]["alert_start"]):
 id=row["episode_id"];category,reason=cases[id];e=ep[id]
 found={}
 for h in disco[id]:
  if h["native_url"] in nmap:
   nr=nmap[h["native_url"]];found[(nr["normalized_source_family"],nr["requested_native_url"])]=nr
 eligible=[x for x in found.values() if x["normalized_source_family"] in sources]
 admitted=[x for x in eligible if admission(e,x)=="PASS"]
 assert len(admitted)==row["candidate_count"],(id,len(admitted),row["candidate_count"])
 candidates=[]
 for c in row["candidates"]:
  native=nmap[c["url"]]["native"]
  assert hashlib.sha256(native["text"].encode("utf-8")).hexdigest()==c["text_sha256"]
  reasons=c["reason_codes"]
  candidates.append({"candidate_id":c["candidate_id"],"source_family":c["family"],
    "frozen_url":c["url"],"frozen_text_sha256":c["text_sha256"],
    "publication_timestamp":native.get("published_at"),"classifier_outcome":c["classifier_outcome"],
    "classifier_episode_binding":c["classifier_episode_id"],"reason_codes":reasons,
    "temporal_binding":c["temporal_binding"],
    "attack_event_representation":next((x.split(":",1)[1] for x in reasons if x.startswith("ATTACK_EVENT_TYPES:")),None),
    "exact_city_result":"EXACT_CITY_EVENT_TEXT" if "EXACT_CITY_EVENT_TEXT" in reasons else "NO_EXACT_CITY_EVENT_TEXT" if "NO_EXACT_CITY_EVENT_TEXT" in reasons else "NOT_PROVEN",
    "air_context_result":"AIR_MILITARY_CONTEXT" if "AIR_MILITARY_CONTEXT" in reasons else "NO_AIR_MILITARY_CONTEXT" if "NO_AIR_MILITARY_CONTEXT" in reasons else "NOT_PROVEN",
    "same_attack_result":"SAME_ATTACK_CONTEXT_SUPPORTED" if "SAME_ATTACK_CONTEXT_SUPPORTED" in reasons else "NOT_PROVEN",
    "classifier_error":c.get("classifier_error")})
 literal=None
 if id in quotes:
  candidate_id,quote=quotes[id];c=next(x for x in candidates if x["candidate_id"]==candidate_id)
  assert quote in nmap[c["frozen_url"]]["native"]["text"],"PARSER_LITERAL_NOT_FOUND:"+id
  literal={"candidate_id":candidate_id,"frozen_text_sha256":c["frozen_text_sha256"],"url":c["frozen_url"],
    "exact_frozen_quote":quote,"literal_verified":True}
 assert category not in {"EVENT_TIME_PRESENT_BUT_TEMPORAL_PARSER_MISSES","TEMPORAL_REPRESENTATION_LIMIT"} or literal
 audit=None
 if row["candidate_count"]==0:
  audit={"episode_id":id,"frozen_discovery_hits":len(disco[id]),"frozen_native_results":len(found),
    "selected_source_rejected_records":[{"source_family":x["normalized_source_family"],
       "url":x["requested_native_url"],"frozen_text_sha256":x.get("extracted_text_sha256"),
       "admission_failure":admission(e,x),"publication_timestamp":(x.get("native") or {}).get("published_at")}
       for x in eligible if admission(e,x)!="PASS"],
    "outside_source_material_evidence":[],"failed_native_acquisitions":[]}
  for nr in found.values():
   fam=nr["normalized_source_family"]
   if fam in outside.get(id,[]):
    prior=previous(id,fam)
    audit["outside_source_material_evidence"].append({"source_family":fam,"url":nr["requested_native_url"],
      "frozen_title":(nr.get("native") or {}).get("title"),
      "frozen_text_sha256":nr.get("extracted_text_sha256"),
      "publication_timestamp":(nr.get("native") or {}).get("published_at"),
      "current_admission_outcome":admission(e,nr),
      "prior_quality_gate":r["quality_gates"].get(fam),
      "prior_tested":fam in good_families,"prior_test_outcomes":prior,
      "prior_gained_candidate":any(x["candidate_count"]>0 for x in prior),
      "prior_final_positive":any(x["final_verdict"] in pos for x in prior)})
   if nr.get("error") and not nr.get("native"):
    audit["failed_native_acquisitions"].append({"source_family":fam,"url":nr["requested_native_url"],
     "error":nr["error"],"target_relevance":"not proven from frozen body"})
  assert category!="RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET" or audit["outside_source_material_evidence"]
  no_candidate.append(audit)
 secondary=[]
 if category=="RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET" and any(
    x["current_admission_outcome"]!="PASS" for x in audit["outside_source_material_evidence"]):
  secondary.append("SECONDARY_PUBLICATION_OR_NATIVE_BODY_ADMISSION_LIMIT")
 if row["candidate_count"] and category not in {"EVENT_TIME_TRULY_ABSENT","EVENT_TIME_PRESENT_BUT_TEMPORAL_PARSER_MISSES","TEMPORAL_REPRESENTATION_LIMIT"} and any(
     "NO_STRICT_TEMPORAL_BINDING" in c["reason_codes"] for c in candidates):
  secondary.append("NO_STRICT_TEMPORAL_BINDING_NOT_FIRST_MATERIAL_FAILURE")
 bad.append({"episode_id":id,"alert_start":e["alert_start"],"alert_end":e["alert_end"],
  "selected_source_eligible_evidence_count":len(eligible),"selected_source_admitted_evidence_count":len(admitted),
  "candidate_count":row["candidate_count"],"candidate_ids":[c["candidate_id"] for c in candidates],
  "candidate_source_families":sorted({c["source_family"] for c in candidates}),
  "candidate_classifier_verdicts":{c["candidate_id"]:c["classifier_outcome"] for c in candidates},
  "candidate_level_traces":candidates,"final_alert_level_verdict":row["final"],
  "primary_first_material_failure":category,"explanation":reason,
  "literal_frozen_evidence":literal,"secondary_failures":secondary,"no_candidate_corpus_audit":audit})
 counts[category]+=1
assert sum(counts.values())==43
out_ids={x["episode_id"] for x in bad if x["primary_first_material_failure"]=="RELEVANT_FROZEN_RESULT_OUTSIDE_FROZEN_SOURCE_SET"}
prior_ids={x["episode_id"] for x in no_candidate if x["episode_id"] in out_ids and any(t["prior_gained_candidate"] for t in x["outside_source_material_evidence"])}
prior_final={x["episode_id"] for x in no_candidate if x["episode_id"] in out_ids and any(t["prior_final_positive"] for t in x["outside_source_material_evidence"])}
source_eligible={x["episode_id"] for x in no_candidate if x["episode_id"] in out_ids and any(
 t["prior_tested"] and t["prior_gained_candidate"] and t["current_admission_outcome"]=="PASS"
 for t in x["outside_source_material_evidence"])}
# Also an excluded-quality-tested source demonstrably admits the Dec 31 positive,
# while the currently eligible BBC evidence fails the publication-time gate.
dec="ffdd8e7b96244ea6d8eff1ba"
assert cases[dec][0]=="ADMISSION_PUBLICATION_WINDOW"
for h in disco[dec]:
 rec=nmap.get(h["native_url"])
 if rec and rec["normalized_source_family"] in good_families and admission(ep[dec],rec)=="PASS":
  if any(x["candidate_count"]>0 for x in previous(dec,rec["normalized_source_family"])):
   source_eligible.add(dec)
def ids(cat):return sorted(x["episode_id"] for x in bad if x["primary_first_material_failure"]==cat)
lever_ids={"residual_source_eligibility":sorted(source_eligible),
 "candidate_admission":[dec],
 "attack_event_parser":ids("ATTACK_EVENT_PRESENT_BUT_PARSER_MISSES"),
 "temporal_parser":ids("EVENT_TIME_PRESENT_BUT_TEMPORAL_PARSER_MISSES"),
 "temporal_representation":ids("TEMPORAL_REPRESENTATION_LIMIT"),
 "exact_city":[],"air_context":[],"same_attack":[]}
assert len(source_eligible)==8,(len(source_eligible),sorted(source_eligible))
assert len(out_ids)==11 and len(prior_ids)==7 and not prior_final
assert max(map(len,lever_ids.values()))==len(source_eligible)
genuine_names=["NO_RELEVANT_FROZEN_NATIVE_RESULT","ATTACK_EVENT_TRULY_INSUFFICIENT",
 "EVENT_TIME_TRULY_ABSENT","EVENT_TIME_OUTSIDE_EPISODE","EXACT_CITY_CLASSIFIER_INSUFFICIENT",
 "AIR_CONTEXT_INSUFFICIENT","SAME_ATTACK_INSUFFICIENT"]
genuine={cat:{"count":len(ids(cat)),"episode_ids":ids(cat)} for cat in genuine_names}
allrank=sorted(cats,key=lambda cat:(-counts[cat],cats.index(cat)))
proof={"schema":"kyiv-immutable-expanded-baseline-remaining-failure-diagnosis-v1",
 "diagnosis_date":"2026-10-09",
 "expanded_freeze_identity":{"base_commit":freeze_sha,"expanded_manifest_sha256":manifest_sha,"source_families":sources,
  "classifier_commit":classifier_sha,"classifier_blob":classifier_blob,**{x+"_sha256":y for x,y in expected.items()}},
 "acceptance_proof_identity":{"run_id":37947654494,"head_sha":a["proof_head_sha"],
  "artifact_id":11624138372,"conclusion":a["result"],
  "candidate_sets_equal":67,"classifier_outcomes_equal":67,"episode_verdicts_equal":67,"evidence_network_fetches":0},
 "cohort":{"total":67,"known_positives":48,"historical_holds":19,"final_positives":5,
  "strict_positives":3,"sensitivity_positives":2,"candidate_covered_positives":31,
  "remaining_failures":43,"no_candidate_failures":17,"candidate_covered_nonfinal_failures":26,
  "holds_with_candidate":13,"hold_strict":2,"hold_sensitivity":0,"new_uncleared_hold_promotions":0},
 "five_final_positive_known_episode_ids_and_verdicts":[{"episode_id":t["episode_id"],"verdict":t["final"]} for t in finals],
 "exact_43_remaining_failures":bad,"no_candidate_frozen_corpus_audit":no_candidate,
 "first_failure_counts":{cat:counts[cat] for cat in cats},"first_failure_total":43,
 "residual_source_ceiling":{"no_candidate_positives_with_relevant_outside_frozen_evidence":len(out_ids),
  "outside_episode_ids":sorted(out_ids),"of_these_previously_gained_candidates":len(prior_ids),
  "prior_candidate_episode_ids":sorted(prior_ids),"of_these_previously_final_positives":len(prior_final),
  "prior_final_ids":sorted(prior_final),
  "unique_recoverable_from_previously_tested_source_eligibility_alone":len(source_eligible),
  "candidate_gain_episode_ids":sorted(source_eligible),"demonstrated_final_positive_gain":0,
  "scope_warning":"These are candidate-entry ceilings, not proven safe final-positive gains."},
 "admission_ceiling":{"publication_window":{"count":1,"ids":[dec]},"attack_vocabulary":{"count":0,"ids":[]},
  "exact_city":{"count":0,"ids":[]},"other":{"count":0,"ids":[]}},
 "parser_representation_ceilings":{key:{"unique_episode_count":len(v),"ids":v} for key,v in lever_ids.items() if key not in ("residual_source_eligibility","candidate_admission")},
 "genuinely_evidence_insufficient":{"unique_episode_count":sum(x["count"] for x in genuine.values()),
   "split":genuine,"scope_warning":"Only currently frozen evidence, with absent clocks and incompatible episode evidence, even under perfect parsing."},
 "same_corpus_predecessor_comparison":{"prior_source_families":12,"expanded_source_families":15,
   "prior_final_positives":3,"expanded_final_positives":5,"final_positive_gain":2,
   "prior_candidate_covered":26,"expanded_candidate_covered":31,"candidate_gain":5,
   "prior_remaining_failures":45,"expanded_remaining_failures":43,
   "prior_source_eligibility_ceiling":11,"residual_safe_tested_candidate_ceiling":len(source_eligible),
   "mechanism":"Source-only changes exposed additional downstream classifier failures; no external corpus change."},
 "bottleneck_rankings":{"first_failure_count_ranking":[{"category":x,"count":counts[x]} for x in allrank],
   "demonstrated_recoverable_ranking":[{"lever":k,"unique_episode_ceiling":len(v),
      "promotion_level":"admitted candidate" if k=="residual_source_eligibility" else "potential repair not final-positive proof"}
      for k,v in sorted(lever_ids.items(),key=lambda item:-len(item[1]))],
   "dominant_primary_first_failure":allrank[0],
   "largest_demonstrated_recoverable_lever":"residual_source_eligibility",
   "largest_demonstrated_unique_positive_ceiling":len(source_eligible)},
 "exactly_one_recommendation":"PILOT NEXT SAFE SOURCE-ELIGIBILITY EXPANSION",
 "independent_validation":"INDEPENDENT VALIDATION = NOT READY",
 "diagnosis_verdict":"KYIV IMMUTABLE EXPANDED BASELINE FAILURE DIAGNOSIS = MIXED",
 "safety":{"blind_per_episode_inspected":False,"historical_backfill_started":False,
   "neon_writes":0,"production_mutations":0,"source_set_mutations":0,"classifier_mutations":0,
   "fresh_discovery":False,"publisher_or_telegram_fetches":0,
   "new_native_acquisition":0,"hold_forensics_reopened":False,
   "mutation_confirmation":"Only a research diagnosis JSON on the isolated diagnosis branch; proof-only files remain on a separate branch."}}
assert proof["genuinely_evidence_insufficient"]["unique_episode_count"]==22
assert len(proof["five_final_positive_known_episode_ids_and_verdicts"])==5
OUT.parent.mkdir(parents=True,exist_ok=True)
raw=json.dumps(proof,ensure_ascii=False,sort_keys=True,indent=2)+"\n"
OUT.write_text(raw,encoding="utf-8")
print(json.dumps({"verdict":proof["diagnosis_verdict"],"counts":proof["first_failure_counts"],
 "source_ceiling":len(source_eligible),"temporal_parser_ceiling":len(lever_ids["temporal_parser"]),
 "temporal_representation_ceiling":len(lever_ids["temporal_representation"]),
 "genuine_insufficient":22,"sha256":hashlib.sha256(raw.encode("utf-8")).hexdigest(),
 "bytes":len(raw.encode("utf-8"))},ensure_ascii=False,sort_keys=True))
