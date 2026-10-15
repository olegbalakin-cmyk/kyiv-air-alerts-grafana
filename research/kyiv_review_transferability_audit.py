#!/usr/bin/env python3
import json, os, re, sys, importlib.util
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

BASE_PATH = Path("research/kyiv_positive_success_cutoff_audit.py")
FROZEN_PATH = "research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json"
FROZEN_COMMIT = "efefa399e69eadd3d7fc8393ac1553cfde35f138"
FROZEN_BLOB = "8a2f6bd33f879be9db978da59c12c34e61f6f843"
OUT = "research/kyiv_review_transferability_audit_2026-10-06.json"
CUTOFF = "2025-02-12"

spec = importlib.util.spec_from_file_location("baseaudit", BASE_PATH)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

def sempath(p):
    return re.sub(r"\[\d+\]", "[]", p)

def truth(v):
    return base.has_truthy(v)

def uniq(vals):
    out=[]
    seen=set()
    for v in vals:
        s=base.norm(v)
        if s and s not in seen:
            seen.add(s); out.append(s)
    return out

def pair_values(pairs, path_contains=(), value_re=None):
    out=[]
    for p,v in pairs:
        pl=p.lower()
        if path_contains and not any(t in pl for t in path_contains):
            continue
        sv=base.norm(v)
        if not sv:
            continue
        if value_re and not re.search(value_re, sv, re.I):
            continue
        out.append((p,sv))
    return out

def boolish(v):
    return base.low(v) in ("true","1","yes")

def parse_any_dt(v):
    return base.parse_dt(v)

def get_alert_end(pairs):
    c=[]
    for p,v in pairs:
        pl=p.lower()
        if parse_any_dt(v) and "alert" in pl and any(t in pl for t in ("end","ended","finish")):
            score=(10 if "alert_end" in pl else 0)+(5 if "ended_at" in pl else 0)
            c.append((score,p,v))
    c.sort(reverse=True)
    return c[0][2] if c else None

def extract_text_fields(pairs):
    terms=("segment","excerpt","evidence_text","source_text","fulltext","snippet","title","text")
    vals=[]
    for p,v in pairs:
        if not isinstance(v,str): continue
        pl=p.lower()
        if any(t in pl for t in terms):
            s=base.norm(v)
            if len(s)>=12 and not s.startswith("http"):
                vals.append(s)
    return uniq(vals)

def extract_source_urls(pairs):
    vals=[]
    for p,v in pairs:
        if not isinstance(v,str): continue
        s=v.strip()
        if s.startswith("http://") or s.startswith("https://"):
            pl=p.lower()
            if any(t in pl for t in ("source","url","link","publisher","article","telegram","rss")):
                vals.append(s)
    return uniq(vals)

def extract_source_identities(pairs):
    vals=[]
    for p,v in pairs:
        if not isinstance(v,str): continue
        pl=p.lower()
        if any(t in pl for t in ("source_name","publisher_name","publisher","channel_name","source_title")):
            s=base.norm(v)
            if s and not s.startswith("http") and len(s)<160:
                vals.append(s)
    return uniq(vals)

def source_hosts(urls):
    hs=[]
    for u in urls:
        try:
            h=urlparse(u).netloc.lower().split(":")[0]
        except Exception:
            h=""
        if h.startswith("www."): h=h[4:]
        if h: hs.append(h)
    return uniq(hs)

def extract_source_timestamps(pairs):
    vals=[]
    for p,v in pairs:
        dt=parse_any_dt(v)
        if not dt: continue
        pl=p.lower()
        if "alert" in pl: continue
        if any(t in pl for t in ("published","publication","message_time","message_timestamp","post_time","post_timestamp","created_at","source_time","source_timestamp","timestamp")):
            vals.append({"path":p,"value":v})
    # de-duplicate path/value
    seen=set(); out=[]
    for x in vals:
        k=(x["path"],str(x["value"]))
        if k not in seen: seen.add(k); out.append(x)
    return out

def accepted_observation_ids(pairs):
    vals=[]
    member_slots=set()
    for p,v in pairs:
        pl=p.lower()
        if "observation_id" in pl and truth(v):
            vals.append(base.norm(v))
        m=re.search(r"accepted_evidence_membership\[(\d+)\]\[0\]$",p)
        if m and truth(v):
            member_slots.add(m.group(1)); vals.append(base.norm(v))
    return uniq(vals), len(member_slots)

def extract_codes(pairs, token):
    return uniq(v for p,v in pairs if token in p.lower() and truth(v))

def review_provenance_fields(pairs):
    out=[]
    for p,v in pairs:
        pl=p.lower()
        if any(t in pl for t in ("review_provenance","reviewer","human_review","manual_review","review_decision","review_rationale")) and truth(v):
            s=base.norm(v)
            if len(s)>1000:s=s[:1000]+"…"
            out.append({"path":p,"value":s})
    return out

def temporal_fields(pairs):
    out=[]
    for p,v in pairs:
        pl=p.lower()
        if any(t in pl for t in ("temporal","event_time","event_clock","event_interval","binding","publication","message_time","post_time")) and truth(v):
            s=base.norm(v)
            if len(s)>1000:s=s[:1000]+"…"
            out.append({"path":p,"value":s})
    return out

def relevant_evidence_fields(pairs, limit=300):
    out=[]
    terms=("classifier_reason","attack_event","air_military_context","air_context","same_attack",
           "temporal","binding","review","accepted_evidence","observation","source_url","source_link",
           "evidence_payload","evidence_excerpt","evidence_text","segment","publication","message","event_type",
           "logical_alert","episode")
    for p,v in pairs:
        if any(t in p.lower() for t in terms) and truth(v):
            s=base.norm(v)
            if len(s)>1200:s=s[:1200]+"…"
            out.append({"path":p,"value":s})
            if len(out)>=limit: break
    return out

def text_blob(texts):
    return "\n".join(texts).lower()

def feature_extract(pairs, verdict, alert_start):
    reason_codes=extract_codes(pairs,"classifier_reason_codes")
    temporal_codes=uniq(v for p,v in pairs if "temporal" in p.lower() and ("code" in p.lower() or "reason" in p.lower()) and truth(v))
    binding_methods=uniq(v for p,v in pairs if "binding_metadata" in p.lower() and p.lower().endswith(".method") and truth(v))
    event_types=uniq(v for p,v in pairs if "event_type" in p.lower() and truth(v))
    texts=extract_text_fields(pairs)
    blob=text_blob(texts)
    urls=extract_source_urls(pairs)
    identities=extract_source_identities(pairs)
    hosts=source_hosts(urls)
    source_ts=extract_source_timestamps(pairs)
    obs_ids, member_slots=accepted_observation_ids(pairs)

    explicit_event_time = any(
        any(t in p.lower() for t in ("event_time","event_clock","event_interval","explicit_event_time","explicit_clock","absolute_time"))
        and truth(v)
        for p,v in pairs
    ) or any(re.search(r"(EXPLICIT.*(CLOCK|TIME|INTERVAL)|EVENT_(CLOCK|TIME|INTERVAL))",c,re.I) for c in temporal_codes)

    explicit_alert_relation = (
        any("TEMPORAL_EXPLICIT_ALERT_RELATION" in c for c in temporal_codes)
        or bool(re.search(r"(під час|після початку|у момент|during|after (the )?start).{0,40}(тривог|alert)",blob,re.I))
    )
    during_alert_wording = (
        any("EXPLICIT_ALERT_RELATION" in c for c in temporal_codes)
        or bool(re.search(r"(під час (повітряної )?тривог|після початку (повітряної )?тривог|during (the )?(air )?alert|after (the )?alert (began|started))",blob,re.I))
    )
    contemporaneous_wording = bool(re.search(
        r"(зараз|наразі|нині|у ці хвилини|чути (?:вибух|роботу)|працює ппо|повідомляють про вибух|explosions? (?:are )?heard|air defen[cs]e (?:is )?(?:working|operating)|currently|now)",
        blob,re.I
    ))
    completed_wording = bool(re.search(
        r"(пролунал|сталися вибух|було чути|збил|знищил|влуч|ударив|атакувал|відбулася атак|explosions? (?:were )?heard|struck|hit|was shot down|were shot down|attacked)",
        blob,re.I
    )) and not explicit_event_time

    ambiguous_multi = (
        any(re.search(r"(MULTIPLE|AMBIG|OVERLAP).*(ALERT|EPISODE)|(ALERT|EPISODE).*(MULTIPLE|AMBIG|OVERLAP)",x,re.I) for x in reason_codes+temporal_codes)
        or any(re.search(r"multiple_or_no_tracked_episodes|multiple.*episodes|ambiguous.*episode",base.norm(v),re.I) for p,v in pairs if truth(v))
    )
    unique_match = (
        "MATCH_UNIQUE" in reason_codes
        or any(re.search(r"(MATCH_UNIQUE|UNIQUE.*EPISODE|EPISODE.*UNIQUE)",x,re.I) for x in reason_codes+temporal_codes)
    )

    publication_or_message_time = len(source_ts)>0 or any(re.search(r"(PUBLICATION|MESSAGE|POST).*TIME|TIME.*(PUBLICATION|MESSAGE|POST)",x,re.I) for x in temporal_codes)
    only_publication_or_message_time = publication_or_message_time and not explicit_event_time and not explicit_alert_relation

    broad_retrospective = (
        any(re.search(r"(BROAD|RETROSPECT|DAY_LEVEL|DATE_ONLY|MORNING|EVENING|NIGHT|EARLIER|LATER)",x,re.I) for x in temporal_codes+reason_codes)
        or bool(re.search(r"(сьогодні|вранці|зранку|увечері|ввечері|вночі|цієї ночі|напередодні|раніше|пізніше|today|this morning|this evening|overnight|earlier|later)",blob,re.I))
    )

    attack_supported = (
        "STRICT_EXPLOSION_EVIDENCE" in reason_codes
        or any(boolish(v) for p,v in pairs if ("strict_explosion.present" in p.lower() or "attack_event.present" in p.lower()))
        or bool(set(event_types) & {"explosion","air_defense_action","impact","strike","hit","fire"})
    )
    air_supported = (
        "AIR_MILITARY_CONTEXT" in reason_codes
        or any(boolish(v) for p,v in pairs if ("air_military_context.present" in p.lower() or "air_defense_context" in p.lower()))
    )
    same_attack_supported = (
        "SAME_ATTACK_CONTEXT_SUPPORTED" in reason_codes
        or any(boolish(v) for p,v in pairs if "same_attack_context.present" in p.lower())
    )
    exact_city = (
        "EXACT_CITY_EVENT_TEXT" in reason_codes
        or any(boolish(v) for p,v in pairs if "exact_city.present" in p.lower())
    )

    reviewed_temporal = any("TEMPORAL_REVIEWED_VALIDATED_BINDING" in x for x in reason_codes+temporal_codes)
    reviewed_sensitivity = (
        "REVIEW_PROVENANCE_SENSITIVITY_BINDING_USED" in reason_codes
        or any("reviewed_episode_specific_sensitivity_binding" in base.low(v) for p,v in pairs if truth(v))
    )
    review_present = bool(review_provenance_fields(pairs))
    review_target = uniq(v for p,v in pairs if "review_provenance" in p.lower() and ("target_episode_id" in p.lower() or p.lower().endswith(".episode_id")) and truth(v))

    logical_rep = any(re.search(r"(LOGICAL.*(ALERT|EPISODE).*(AMBIG|REPRESENT|GROUP)|REPRESENTATION|GROUPING)",base.norm(v),re.I) for p,v in pairs if truth(v))
    parser_context_fail = any(re.search(r"(PARSER|SYNTAX|CONTEXT_SELECTION|CONTEXT-SELECTION|STALE.*ALERT|NORMALIZATION.*FAIL)",base.norm(v),re.I) for p,v in pairs if truth(v))

    payload_text_present = bool(texts)
    evidence_payload_present = any("evidence_payload" in p.lower() and truth(v) for p,v in pairs) or payload_text_present

    # Timing relative to alert, only where actual source/message/publication timestamps are durably retained.
    timing=[]
    a0=parse_any_dt(alert_start)
    a1=parse_any_dt(get_alert_end(pairs))
    if a0 and a0.tzinfo is None: a0=a0.replace(tzinfo=timezone.utc)
    if a1 and a1.tzinfo is None: a1=a1.replace(tzinfo=timezone.utc)
    for x in source_ts:
        dt=parse_any_dt(x["value"])
        if not dt or not a0: continue
        if dt.tzinfo is None: dt=dt.replace(tzinfo=timezone.utc)
        try:
            delta=(dt-a0).total_seconds()/60.0
            if a1:
                if a1.tzinfo is None: a1=a1.replace(tzinfo=timezone.utc)
                if a0 <= dt <= a1: rel="WITHIN_ALERT"
                elif dt < a0: rel="BEFORE_ALERT"
                else: rel="AFTER_ALERT"
            else:
                rel="AFTER_START" if dt>=a0 else "BEFORE_ALERT"
            timing.append({"path":x["path"],"timestamp":x["value"],"minutes_from_alert_start":round(delta,3),"relation":rel})
        except Exception:
            pass

    return {
        "reason_codes":reason_codes,
        "temporal_codes_or_reasons":temporal_codes,
        "binding_methods":binding_methods,
        "event_types":event_types,
        "observation_ids":obs_ids,
        "evidence_observation_count": max(len(obs_ids), member_slots),
        "accepted_evidence_membership_count": member_slots,
        "source_urls":urls,
        "source_identities":identities,
        "source_hosts":hosts,
        "source_count": len(urls) if urls else None,
        "independent_corroboration_count": len(identities) if identities else (len(hosts) if hosts else None),
        "source_timestamps":source_ts,
        "source_timing_relative_to_alert":timing,
        "explicit_event_time":explicit_event_time,
        "explicit_alert_relation":explicit_alert_relation,
        "during_alert_wording":during_alert_wording,
        "contemporaneous_wording":contemporaneous_wording,
        "completed_event_wording_without_explicit_time":completed_wording,
        "event_time_ambiguous_across_alerts":ambiguous_multi,
        "event_time_inside_one_alert_or_unique_match":unique_match,
        "only_publication_or_message_time":only_publication_or_message_time,
        "broad_or_retrospective_time":broad_retrospective,
        "attack_event_strength":"SUPPORTED" if attack_supported else "INSUFFICIENT_OR_NOT_STORED",
        "air_context_strength":"SUPPORTED" if air_supported else "INSUFFICIENT_OR_NOT_STORED",
        "same_attack_confidence":"SUPPORTED" if same_attack_supported else "UNCLEAR_OR_NOT_STORED",
        "exact_city_event_text":exact_city,
        "logical_alert_ambiguity":logical_rep,
        "parser_or_context_selection_failure":parser_context_fail,
        "evidence_payload_present":evidence_payload_present,
        "review_provenance_present":review_present,
        "reviewed_temporal_binding":reviewed_temporal,
        "reviewed_sensitivity_binding":reviewed_sensitivity,
        "review_target_episode_ids":review_target,
        "retained_source_text_or_excerpt":texts[:30],
    }

def build_context(data):
    arrays=base.discover_arrays(data)
    dict_arrays=[(p,a) for p,a in arrays if a and isinstance(a[0],dict)]
    best=None
    for p,a in dict_arrays:
        per_path={}
        for row in a:
            rowvals=defaultdict(set)
            for fp,v in base.flatten(row):
                sv=base.norm(v)
                if sv in base.KNOWN_VERDICTS:
                    sem=re.sub(r"\[\d+\]","[]",fp)
                    rowvals[sem].add(sv)
            for sem,vals in rowvals.items():
                if len(vals)==1:
                    vv=next(iter(vals))
                    per_path.setdefault(sem,Counter())[vv]+=1
        for sem,counts in per_path.items():
            score=sum(min(counts[k],base.EXPECTED_ALL[k]) for k in base.EXPECTED_ALL)
            cand=(score,p,a,counts,sem)
            if best is None or score>best[0]: best=cand
            if counts==base.EXPECTED_ALL:
                best=(10**9,p,a,counts,sem); break
        if best and best[0]==10**9: break
    if best is None or best[3]!=base.EXPECTED_ALL:
        raise RuntimeError("classification table not found")
    _,class_path,class_rows,all_counts,verdict_sem=best

    id_index=defaultdict(list); table_records={}
    for tp,arr in dict_arrays:
        table_records[tp]=arr
        for i,r in enumerate(arr):
            for k,v in base.id_pairs(r,tp):
                id_index[(k,v)].append((tp,i))

    def context_for(class_i):
        row=class_rows[class_i]
        seen={(class_path,class_i)}
        q=deque(base.id_pairs(row,class_path)); known=set(q); rounds=0
        while q and rounds<2000 and len(seen)<300:
            k,v=q.popleft(); rounds+=1
            for tp,i in id_index.get((k,v),[]):
                key=(tp,i)
                if key in seen or tp==class_path: continue
                seen.add(key)
                for kv in base.id_pairs(table_records[tp][i],tp):
                    if kv not in known: known.add(kv); q.append(kv)
        pairs=[(f"classification.{p}",v) for p,v in base.flatten(row)]
        for tp,i in sorted(seen):
            if tp==class_path and i==class_i: continue
            pairs.extend((f"related.{tp}[{i}].{p}",v) for p,v in base.flatten(table_records[tp][i]))
        return pairs,seen

    context_cache={}
    city_path_counts=Counter()
    for i in range(len(class_rows)):
        pairs,seen=context_for(i); context_cache[i]=(pairs,seen)
        for p,v in base.city_exact_pairs(pairs):
            city_path_counts[sempath(p)]+=1
    exact=[p for p,c in city_path_counts.items() if c==2456]
    if exact:
        exact.sort(key=lambda p:(0 if "city" in p.lower() else 1,len(p))); chosen=exact[0]
    else:
        chosen=city_path_counts.most_common(1)[0][0]

    kyiv=[]
    for i,(pairs,_) in context_cache.items():
        if any(sempath(p)==chosen for p,v in base.city_exact_pairs(pairs)):
            kyiv.append(i)
    if len(kyiv)!=2456:
        raise RuntimeError(f"Kyiv baseline mismatch {len(kyiv)}")

    start_candidates=Counter()
    for i in kyiv:
        for p,v in context_cache[i][0]:
            pl=p.lower()
            if base.parse_dt(v) and "alert" in pl and any(t in pl for t in ("start","started","begin")):
                start_candidates[sempath(p)]+=1
    start_sem=start_candidates.most_common(1)[0][0]
    def get_start(pairs):
        for p,v in pairs:
            if sempath(p)==start_sem and base.parse_dt(v): return v
        for p,v in pairs:
            if base.parse_dt(v) and "alert" in p.lower() and any(t in p.lower() for t in ("start","started","begin")): return v
        return None
    return class_path,class_rows,context_cache,kyiv,get_start,all_counts

def episode_id_candidates(pairs):
    vals=[]
    for p,v in pairs:
        pl=p.lower()
        if truth(v) and (
            pl.endswith(".alert_episode_id") or
            pl.endswith(".classification_episode_id") or
            pl.endswith(".target_episode_id") or
            ("binding_metadata" in pl and pl.endswith(".episode_id"))
        ):
            vals.append(base.norm(v))
    return uniq(vals)

def episode_record(i, class_rows, class_path, context_cache, get_start):
    pairs,seen=context_cache[i]
    verdict=base.verdict_from_pairs(pairs)
    start=get_start(pairs)
    f=feature_extract(pairs,verdict,start)
    return {
        "classification_row_index":i,
        "alert_episode_id_candidates":episode_id_candidates(pairs),
        "alert_start":start,
        "alert_end":get_alert_end(pairs),
        "verdict":verdict,
        **f,
        "review_provenance":review_provenance_fields(pairs)[:120],
        "temporal_binding_fields":temporal_fields(pairs)[:160],
        "evidence_provenance_excerpt":relevant_evidence_fields(pairs,300),
        "joined_record_count":len(seen),
    }

def dist_bool(records,key):
    return {"true":sum(bool(r.get(key)) for r in records),"false":sum(not bool(r.get(key)) for r in records)}

def dist_value(records,key):
    c=Counter()
    for r in records:
        v=r.get(key)
        if isinstance(v,list):
            if not v:c["<NONE>"]+=1
            else:
                for x in set(map(str,v)): c[x]+=1
        else:c[str(v)]+=1
    return dict(c.most_common())

def metric_summary(records):
    keys=[
      "explicit_event_time","event_time_inside_one_alert_or_unique_match","event_time_ambiguous_across_alerts",
      "only_publication_or_message_time","completed_event_wording_without_explicit_time","contemporaneous_wording",
      "during_alert_wording","logical_alert_ambiguity","parser_or_context_selection_failure","evidence_payload_present",
      "review_provenance_present"
    ]
    return {
      "n":len(records),
      "boolean_features":{k:dist_bool(records,k) for k in keys},
      "source_count":{"known":sum(r["source_count"] is not None for r in records),"mean":round(sum(r["source_count"] or 0 for r in records)/max(1,sum(r["source_count"] is not None for r in records)),3) if any(r["source_count"] is not None for r in records) else None,"distribution":dict(Counter(r["source_count"] for r in records if r["source_count"] is not None).most_common())},
      "independent_corroboration_count":{"known":sum(r["independent_corroboration_count"] is not None for r in records),"distribution":dict(Counter(r["independent_corroboration_count"] for r in records if r["independent_corroboration_count"] is not None).most_common())},
      "attack_event_strength":dist_value(records,"attack_event_strength"),
      "air_context_strength":dist_value(records,"air_context_strength"),
      "same_attack_confidence":dist_value(records,"same_attack_confidence"),
      "reason_codes":dist_value(records,"reason_codes"),
      "temporal_codes_or_reasons":dist_value(records,"temporal_codes_or_reasons"),
      "binding_methods":dist_value(records,"binding_methods"),
      "event_types":dist_value(records,"event_types"),
      "source_timing_relations":dict(Counter(x["relation"] for r in records for x in r["source_timing_relative_to_alert"]).most_common()),
    }

def blocker_for(r):
    rc=" | ".join(r["reason_codes"]+r["temporal_codes_or_reasons"]).upper()
    if not r["evidence_payload_present"]:
        return "EVIDENCE_PAYLOAD_INCOMPLETE"
    if r["attack_event_strength"]!="SUPPORTED" or r["air_context_strength"]!="SUPPORTED" or not r["exact_city_event_text"]:
        return "EVENT_OR_AIR_CONTEXT_INSUFFICIENT"
    if r["logical_alert_ambiguity"]:
        return "LOGICAL_ALERT_REPRESENTATION_PROBLEM"
    if r["same_attack_confidence"]!="SUPPORTED":
        return "SAME_ATTACK_RELATION_UNCLEAR"
    if r["explicit_event_time"] and r["event_time_ambiguous_across_alerts"]:
        return "EXPLICIT_TIME_BUT_ALERT_BINDING_AMBIGUOUS"
    if r["event_time_ambiguous_across_alerts"]:
        return "MULTIPLE_ALERT_EPISODES_PLAUSIBLE"
    if r["only_publication_or_message_time"]:
        return "ONLY_PUBLICATION_OR_MESSAGE_TIME"
    if r["broad_or_retrospective_time"]:
        return "BROAD_OR_RETROSPECTIVE_TIME"
    if not r["explicit_event_time"] and not r["explicit_alert_relation"] and not r["during_alert_wording"]:
        return "NO_EXPLICIT_EVENT_TIME"
    if (
        r["attack_event_strength"]=="SUPPORTED" and r["air_context_strength"]=="SUPPORTED"
        and r["same_attack_confidence"]=="SUPPORTED" and r["exact_city_event_text"]
        and (r["explicit_event_time"] or r["explicit_alert_relation"] or r["during_alert_wording"] or r["contemporaneous_wording"])
        and not r["review_provenance_present"]
    ):
        return "REVIEW_DECISION_NOT_EXECUTED"
    if r["parser_or_context_selection_failure"]:
        return "OTHER"
    return "INDETERMINATE"

def main():
    actual=os.environ.get("FROZEN_BLOB_ACTUAL","")
    result={
      "frozen_artifact_identity":{"path":FROZEN_PATH,"commit":FROZEN_COMMIT,"expected_blob":FROZEN_BLOB,"actual_blob":actual,"blob_verified":actual==FROZEN_BLOB},
      "mutation_confirmation":{
        "classifier_mutations":0,"parser_mutations":0,"temporal_representation_mutations":0,"alert_grouping_mutations":0,
        "source_mutations":0,"historical_state_mutations":0,"queue_mutations":0,"persistence_mutations":0,
        "neon_db_queries":0,"neon_db_writes":0,"deployments":0
      },
      "verdict":"KYIV REVIEW TRANSFERABILITY = INDETERMINATE"
    }
    if actual!=FROZEN_BLOB:
        result["diagnostic"]="FROZEN_BLOB_MISMATCH"; Path(OUT).write_text(json.dumps(result,ensure_ascii=False,indent=2)); return 2
    data=json.load(open(os.environ.get("SNAPSHOT_PATH",FROZEN_PATH),encoding="utf-8"))
    class_path,class_rows,context_cache,kyiv,get_start,all_counts=build_context(data)
    counts=Counter(base.verdict_from_pairs(context_cache[i][0]) for i in kyiv)
    if counts!=base.EXPECTED_KYIV:
        result["diagnostic"]={"KYIV_COUNTS_MISMATCH":dict(counts)}; Path(OUT).write_text(json.dumps(result,ensure_ascii=False,indent=2)); return 3

    A=[];B=[];C=[]
    for i in kyiv:
        pairs,_=context_cache[i]
        v=base.verdict_from_pairs(pairs); st=get_start(pairs); d=base.date_only(st)
        a,l,e=base.evidence_flags(pairs)
        if v in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"):
            A.append(episode_record(i,class_rows,class_path,context_cache,get_start))
        elif v=="NEEDS_REVIEW" and e and d and d<=CUTOFF:
            B.append(episode_record(i,class_rows,class_path,context_cache,get_start))
        elif v=="NEEDS_REVIEW" and e and d and d>CUTOFF:
            C.append(episode_record(i,class_rows,class_path,context_cache,get_start))

    result["cohort_counts"]={"ACCEPTED_POSITIVE":len(A),"PRE_CUTOFF_REVIEW":len(B),"POST_CUTOFF_REVIEW":len(C)}
    if (len(A),len(B),len(C))!=(145,57,209):
        result["diagnostic"]={"COHORT_COUNT_MISMATCH":result["cohort_counts"]}
        Path(OUT).write_text(json.dumps(result,ensure_ascii=False,indent=2)); return 4

    for r in C:r["primary_blocker"]=blocker_for(r)
    for r in B:r["primary_blocker"]=blocker_for(r)
    result["cohort_feature_summary"]={
      "ACCEPTED_POSITIVE":metric_summary(A),
      "PRE_CUTOFF_REVIEW":metric_summary(B),
      "POST_CUTOFF_REVIEW":metric_summary(C)
    }
    result["post_cutoff_blocker_distribution"]=dict(Counter(r["primary_blocker"] for r in C).most_common())
    result["pre_cutoff_hold_distribution"]=dict(Counter(r["primary_blocker"] for r in B).most_common())
    result["episode_ledger"]={"ACCEPTED_POSITIVE":A,"PRE_CUTOFF_REVIEW":B,"POST_CUTOFF_REVIEW":C}
    Path(OUT).write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps({
      "cohort_counts":result["cohort_counts"],
      "blockers_post":result["post_cutoff_blocker_distribution"],
      "holds_pre":result["pre_cutoff_hold_distribution"],
      "features":result["cohort_feature_summary"]
    },ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    sys.exit(main())
