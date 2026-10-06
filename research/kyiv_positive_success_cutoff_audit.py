#!/usr/bin/env python3
import json, os, re, sys, hashlib
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

FROZEN_COMMIT="efefa399e69eadd3d7fc8393ac1553cfde35f138"
FROZEN_BLOB="8a2f6bd33f879be9db978da59c12c34e61f6f843"
FROZEN_PATH="research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json"
OUT="attack_event_kyiv_positive_success_cutoff_audit_2026-10-06.json"
CUTOFF="2025-02-12"
KNOWN_VERDICTS={"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE","NO_CONFIRMED_EVENT","NEEDS_REVIEW"}
EXPECTED_ALL=Counter({
    "STRICT_EVENT_POSITIVE":1017,
    "SENSITIVITY_EVENT_POSITIVE":63,
    "NO_CONFIRMED_EVENT":23530,
    "NEEDS_REVIEW":1795,
})
EXPECTED_KYIV=Counter({
    "STRICT_EVENT_POSITIVE":141,
    "SENSITIVITY_EVENT_POSITIVE":4,
    "NO_CONFIRMED_EVENT":2045,
    "NEEDS_REVIEW":266,
})
KYIV_VALUES={"kyiv","київ","киев","м. київ","м. киев","city of kyiv","kyiv city"}

def norm(v):
    if v is None: return ""
    return re.sub(r"\s+"," ",str(v)).strip()

def low(v): return norm(v).lower()

def scalar(v):
    return isinstance(v,(str,int,float,bool)) or v is None

def flatten(obj, prefix=""):
    out=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}" if prefix else str(k)
            if scalar(v):
                out.append((p,v))
            elif isinstance(v,dict):
                out.extend(flatten(v,p))
            elif isinstance(v,list):
                if not v:
                    out.append((p,[]))
                else:
                    for i,x in enumerate(v):
                        q=f"{p}[{i}]"
                        if scalar(x): out.append((q,x))
                        elif isinstance(x,(dict,list)): out.extend(flatten(x,q))
    elif isinstance(obj,list):
        for i,x in enumerate(obj):
            q=f"{prefix}[{i}]"
            if scalar(x): out.append((q,x))
            else: out.extend(flatten(x,q))
    return out

def discover_arrays(obj,prefix=""):
    found=[]
    if isinstance(obj,dict):
        for k,v in obj.items():
            p=f"{prefix}.{k}" if prefix else str(k)
            if isinstance(v,list):
                found.append((p,v))
            elif isinstance(v,dict):
                found.extend(discover_arrays(v,p))
    elif isinstance(obj,list):
        found.append((prefix,obj))
    return found

def path_leaf(p):
    x=re.sub(r"\[\d+\]","",p)
    return x.split(".")[-1].lower()

def table_hint(path):
    b=path.lower().split(".")[-1]
    b=re.sub(r"\[\d+\]","",b)
    if "classification" in b: return "classification"
    if "alert_episode" in b or b in ("alerts","alert_episodes"): return "alert_episode"
    if "observation" in b: return "observation"
    if "source_link" in b: return "source_link"
    if "source" in b: return "source"
    if "review" in b: return "review"
    if "provenance" in b: return "provenance"
    if "event" in b: return "event"
    return re.sub(r"s$","",b)

def id_pairs(record, table_path):
    ans=[]
    hint=table_hint(table_path)
    for p,v in flatten(record):
        if v is None or isinstance(v,bool): continue
        leaf=path_leaf(p)
        canon=None
        if leaf.endswith("_id"):
            canon=leaf
        elif leaf=="id":
            # Nested parent semantic if present; otherwise table semantic.
            parts=re.sub(r"\[\d+\]","",p).lower().split(".")
            parent=parts[-2] if len(parts)>=2 else hint
            if "classification" in parent: canon="classification_id"
            elif "alert_episode" in parent or parent=="alert": canon="alert_episode_id"
            elif "observation" in parent: canon="observation_id"
            elif "source_link" in parent: canon="source_link_id"
            elif "source" in parent: canon="source_id"
            elif "review" in parent: canon="review_id"
            elif "event" in parent: canon="event_id"
            else: canon=f"{hint}_id"
        if canon:
            sv=norm(v)
            if sv:
                ans.append((canon,sv))
    return ans

def has_truthy(v):
    if v is None: return False
    if v is False: return False
    if isinstance(v,(list,dict)): return len(v)>0
    s=low(v)
    return s not in ("","none","null","false","0","[]","{}","n/a","na")

def parse_dt(v):
    if not isinstance(v,str): return None
    s=v.strip()
    if not s: return None
    try:
        if s.endswith("Z"): s=s[:-1]+"+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        pass
    m=re.match(r"^(\d{4}-\d{2}-\d{2})(?:[ T].*)?$",s)
    if m:
        try: return datetime.fromisoformat(m.group(1))
        except: return None
    return None

def date_only(v):
    d=parse_dt(v)
    return d.date().isoformat() if d else None

def choose_scalar(pairs, exact_leaves=(), must_tokens=(), prefer_tokens=()):
    candidates=[]
    for p,v in pairs:
        if not scalar(v) or v is None: continue
        pl=p.lower()
        leaf=path_leaf(p)
        score=0
        if leaf in exact_leaves: score+=100
        if must_tokens and all(t in pl for t in must_tokens): score+=40
        score+=sum(5 for t in prefer_tokens if t in pl)
        if score>0: candidates.append((score,-len(p),p,v))
    if not candidates: return (None,None)
    candidates.sort(reverse=True)
    _,_,p,v=candidates[0]
    return p,v

def verdict_from_pairs(pairs, verdict_path=None):
    if verdict_path:
        for p,v in pairs:
            if p==verdict_path and norm(v) in KNOWN_VERDICTS: return norm(v)
    vals=[(p,norm(v)) for p,v in pairs if norm(v) in KNOWN_VERDICTS]
    return vals[0][1] if vals else None

def city_exact_pairs(pairs):
    out=[]
    for p,v in pairs:
        if isinstance(v,str) and low(v) in KYIV_VALUES:
            out.append((p,v))
    return out

def evidence_flags(pairs):
    accepted=False; source_links=False; anyprov=False
    for p,v in pairs:
        if not has_truthy(v): continue
        pl=p.lower()
        leaf=path_leaf(p)
        if ("accepted" in pl and ("evidence" in pl or "observation" in pl or "source" in pl)):
            accepted=True
        if "source_link" in pl or "source_links" in pl:
            source_links=True
        # Conservative: require a field that is directly provenance/evidence/source related.
        if (
            ("accepted" in pl and ("evidence" in pl or "observation" in pl or "source" in pl))
            or "source_link" in pl
            or "observation_id" in pl
            or "evidence_payload" in pl
            or "evidence_excerpt" in pl
            or "evidence_text" in pl
            or "source_type" in pl
            or "source_family" in pl
            or "source_url" in pl
            or "originating_frozen_case" in pl
            or "campaign" in pl
        ):
            anyprov=True
    return accepted,source_links,anyprov

def classifier_versions(pairs):
    vals=set()
    for p,v in pairs:
        if not has_truthy(v): continue
        pl=p.lower()
        if "classifier" in pl and any(t in pl for t in ("version","blob","sha","methodology")):
            vals.add(norm(v))
    return sorted(vals)

def normalization_versions(pairs):
    vals=set()
    for p,v in pairs:
        if not has_truthy(v): continue
        pl=p.lower()
        if "normalization" in pl and any(t in pl for t in ("version","blob","sha")):
            vals.add(norm(v))
    return sorted(vals)

def campaign_values(pairs):
    vals=set()
    for p,v in pairs:
        if not has_truthy(v): continue
        pl=p.lower()
        if any(t in pl for t in ("originating_frozen_case","campaign","origin_artifact","source_artifact","replay_artifact","frozen_case")):
            if scalar(v): vals.add(norm(v))
    return sorted(vals)

def source_family_candidates(pairs):
    # First inspect explicit source-family/type/url/snippet provenance only.
    texts=[]
    for p,v in pairs:
        if not has_truthy(v): continue
        pl=p.lower()
        if any(t in pl for t in ("source_type","source_family","source_kind","source_url","source_link","publisher_fulltext","rss","telegram","snippet","title")):
            texts.append((pl,low(v)))
    found=[]
    joined=" | ".join([p+"="+v for p,v in texts])
    if re.search(r"(telegram|t\.me/)",joined): found.append("TELEGRAM")
    if re.search(r"(publisher[_ -]?fulltext|full[_ -]?text|publisher_page|article_fulltext)",joined):
        found.append("PUBLISHER_FULLTEXT")
    if ("rss" in joined and ("title" in joined or "snippet" in joined)) or re.search(r"rss[_ -]?(title|snippet)",joined):
        found.append("RSS_TITLE_SNIPPET")
    if not found and texts: found.append("OTHER")
    return found

def primary_source_family(pairs):
    c=source_family_candidates(pairs)
    if not c: return "UNKNOWN"
    # Prefer explicit source_type/family mentions over URL-only evidence and preserve deterministic order.
    explicit=[]
    for p,v in pairs:
        pl=p.lower(); vv=low(v)
        if not has_truthy(v): continue
        if "source_type" in pl or "source_family" in pl or "source_kind" in pl:
            if "telegram" in vv: explicit.append("TELEGRAM")
            if "publisher" in vv and "full" in vv: explicit.append("PUBLISHER_FULLTEXT")
            if "rss" in vv and ("title" in vv or "snippet" in vv): explicit.append("RSS_TITLE_SNIPPET")
    if explicit: return Counter(explicit).most_common(1)[0][0]
    if len(c)==1: return c[0]
    # Multiple families without explicit primary membership is not safely attributable.
    return "OTHER"

def success_mechanism(pairs, source_family):
    rel=[]
    review=[]
    for p,v in pairs:
        if not has_truthy(v): continue
        pl=p.lower(); vv=low(v)
        if any(t in pl for t in ("temporal","binding","reason","method","methodology","attribution","event_clock","event_interval")):
            rel.append(pl+"="+vv)
        if any(t in pl for t in ("review","curated","manual","human")):
            review.append(pl+"="+vv)
    txt=" | ".join(rel)
    rtxt=" | ".join(review)
    # Mechanism categories require direct stored provenance tokens; source family alone is insufficient.
    if re.search(r"(explicit[^|]{0,50}(event_?)?(interval|window)|(event_?)?interval[^|]{0,50}explicit)",txt):
        return "EXPLICIT_EVENT_INTERVAL"
    if re.search(r"(explicit[^|]{0,50}(event_?)?(clock|time)|event[_ -]?clock)",txt):
        return "EXPLICIT_EVENT_CLOCK"
    if re.search(r"(manual|curated|human)[^|]{0,80}(accept|bind|confirm|positive|reviewed)",rtxt) or re.search(r"(accept|bind|confirm)[^|]{0,80}(manual|curated|human)",rtxt):
        return "MANUALLY_REVIEWED_OR_CURATED_BINDING"
    if source_family=="TELEGRAM" and re.search(r"(telegram[^|]{0,80}(message|post)[_ -]?(time|timestamp)|message[_ -]?(time|timestamp)|post[_ -]?(time|timestamp)|contemporaneous)",txt):
        return "CONTEMPORANEOUS_TELEGRAM_MESSAGE_TIME"
    if source_family=="PUBLISHER_FULLTEXT" and re.search(r"(publisher[_ -]?fulltext|full[_ -]?text|publisher_page)",txt):
        return "PUBLISHER_FULLTEXT_TEMPORAL_BINDING"
    if source_family=="RSS_TITLE_SNIPPET" and re.search(r"(rss|title|snippet)",txt):
        return "RSS_TITLE_SNIPPET_TEMPORAL_BINDING"
    # Only call OTHER when an explicit temporal/binding reason exists but does not map cleanly.
    if any(re.search(t,txt) for t in (r"temporal",r"binding",r"attribution",r"reason_code",r"reason=")):
        return "OTHER_EXISTING_MECHANISM"
    return "UNKNOWN_FROM_FROZEN_PROVENANCE"

def provenance_excerpt(pairs,limit=120):
    keep=[]
    terms=("classifier","methodology","accepted","evidence","source_link","source_type","source_family",
           "observation_id","temporal","binding","review","campaign","originating_frozen_case","event_type",
           "evidence_payload","evidence_excerpt","source_url")
    for p,v in pairs:
        if any(t in p.lower() for t in terms) and has_truthy(v):
            sv=norm(v)
            if len(sv)>500: sv=sv[:500]+"…"
            keep.append({"path":p,"value":sv})
            if len(keep)>=limit: break
    return keep

def record_id(record,table_path):
    ids=id_pairs(record,table_path)
    pri=["classification_id","alert_episode_id","event_id","observation_id","source_id","source_link_id","review_id"]
    for k in pri:
        for kk,v in ids:
            if kk==k: return v
    return ids[0][1] if ids else None

def monthly(date_str):
    return date_str[:7] if date_str and len(date_str)>=7 else "UNKNOWN"

def ratio(a,b):
    return (a/b) if b else None

def pct(x):
    return None if x is None else round(100*x,3)

def main():
    snap_path=Path(os.environ.get("SNAPSHOT_PATH",FROZEN_PATH))
    actual_blob=os.environ.get("FROZEN_BLOB_ACTUAL","")
    result={
      "frozen_artifact_identity":{
        "path":FROZEN_PATH,"commit":FROZEN_COMMIT,"expected_blob":FROZEN_BLOB,
        "actual_blob":actual_blob,"blob_verified":actual_blob==FROZEN_BLOB
      },
      "verdict":"KYIV POSITIVE SUCCESS/CUTOFF AUDIT = PARTIAL",
      "diagnostics":[],
      "mutation_confirmation":{
        "classifier_mutations":0,"parser_mutations":0,"source_mutations":0,"alert_state_mutations":0,
        "historical_state_mutations":0,"queue_mutations":0,"persistence_mutations":0,
        "neon_db_queries":0,"neon_db_writes":0,"deployments":0
      }
    }
    if actual_blob!=FROZEN_BLOB:
        result["verdict"]="KYIV POSITIVE SUCCESS/CUTOFF AUDIT = BLOCKED"
        result["diagnostics"].append("FROZEN_BLOB_MISMATCH")
        Path(OUT).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        return 2

    with snap_path.open("r",encoding="utf-8") as f:
        data=json.load(f)

    arrays=discover_arrays(data)
    dict_arrays=[(p,a) for p,a in arrays if a and isinstance(a[0],dict)]
    result["diagnostics"].append({"array_inventory":[{"path":p,"rows":len(a)} for p,a in dict_arrays]})

    # Locate classification table mechanically by exact accepted verdict totals.
    best=None
    for p,a in dict_arrays:
        counts=Counter()
        verdict_paths=Counter()
        for row in a:
            for fp,v in flatten(row):
                sv=norm(v)
                if sv in KNOWN_VERDICTS:
                    counts[sv]+=1
                    verdict_paths[fp]+=1
        score=sum(min(counts[k],EXPECTED_ALL[k]) for k in EXPECTED_ALL)
        if best is None or score>best[0]:
            best=(score,p,a,counts,verdict_paths)
        if counts==EXPECTED_ALL:
            best=(10**9,p,a,counts,verdict_paths); break
    if best is None or best[3]!=EXPECTED_ALL:
        result["verdict"]="KYIV POSITIVE SUCCESS/CUTOFF AUDIT = BLOCKED"
        result["diagnostics"].append({"classification_table_not_found","best": None if best is None else {"path":best[1],"counts":best[3]}})
        Path(OUT).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        return 3
    _,class_path,class_rows,all_counts,vpaths=best
    verdict_path=vpaths.most_common(1)[0][0]
    result["classification_table"]={"path":class_path,"rows":len(class_rows),"verdict_path":verdict_path,"counts":dict(all_counts)}

    # Build relational index across top-level/nested-under-dict record arrays.
    # This permits frozen provenance to be joined without assuming one denormalized shape.
    id_index=defaultdict(list)
    table_records={}
    for tp,arr in dict_arrays:
        table_records[tp]=arr
        for i,r in enumerate(arr):
            for k,v in id_pairs(r,tp):
                id_index[(k,v)].append((tp,i))

    def context_for(class_i):
        base=class_rows[class_i]
        seen={(class_path,class_i)}
        q=deque(id_pairs(base,class_path))
        known=set(q)
        rounds=0
        while q and rounds<2000 and len(seen)<300:
            k,v=q.popleft(); rounds+=1
            for tp,i in id_index.get((k,v),[]):
                key=(tp,i)
                if key in seen: continue
                # Avoid pulling unrelated classification rows through shared alert IDs.
                if tp==class_path: continue
                seen.add(key)
                rec=table_records[tp][i]
                for kv in id_pairs(rec,tp):
                    if kv not in known:
                        known.add(kv); q.append(kv)
        pairs=[]
        pairs.extend([(f"classification.{p}",v) for p,v in flatten(base)])
        for tp,i in sorted(seen):
            if tp==class_path and i==class_i: continue
            rec=table_records[tp][i]
            prefix=f"related.{tp}[{i}]"
            pairs.extend([(f"{prefix}.{p}",v) for p,v in flatten(rec)])
        return pairs,seen

    # Determine the canonical Kyiv discriminator path by exact 2,456-row accepted total.
    city_path_counts=Counter()
    context_cache={}
    for i,row in enumerate(class_rows):
        pairs,seen=context_for(i)
        context_cache[i]=(pairs,seen)
        for p,v in city_exact_pairs(pairs):
            # strip relation indices so repeated records still point to semantic path
            semantic=re.sub(r"\[\d+\]","[]",p)
            city_path_counts[semantic]+=1
    exact_city_paths=[p for p,c in city_path_counts.items() if c==2456]
    if exact_city_paths:
        exact_city_paths.sort(key=lambda p:(0 if "city" in p.lower() else 1,len(p)))
        chosen_city_sem=exact_city_paths[0]
    else:
        chosen_city_sem=city_path_counts.most_common(1)[0][0] if city_path_counts else None
    result["kyiv_discriminator"]={"semantic_path":chosen_city_sem,"candidate_counts":dict(city_path_counts.most_common(20))}

    def is_kyiv(i):
        pairs,_=context_cache[i]
        for p,v in city_exact_pairs(pairs):
            if re.sub(r"\[\d+\]","[]",p)==chosen_city_sem:
                return True
        return False

    kyiv_idx=[i for i in range(len(class_rows)) if is_kyiv(i)]
    # If dynamic exact path failed, fall back to any explicitly city/location-keyed Kyiv field.
    if len(kyiv_idx)!=2456:
        kyiv_idx=[]
        for i,(pairs,_) in context_cache.items():
            hit=False
            for p,v in city_exact_pairs(pairs):
                pl=p.lower()
                if any(t in pl for t in ("city","settlement","municipality")):
                    hit=True; break
            if hit: kyiv_idx.append(i)

    kyiv_counts=Counter()
    for i in kyiv_idx:
        v=verdict_from_pairs(context_cache[i][0])
        if v: kyiv_counts[v]+=1
    if len(kyiv_idx)!=2456 or kyiv_counts!=EXPECTED_KYIV:
        result["verdict"]="KYIV POSITIVE SUCCESS/CUTOFF AUDIT = BLOCKED"
        result["diagnostics"].append({"KYIV_BASELINE_MISMATCH":{"rows":len(kyiv_idx),"counts":dict(kyiv_counts)}})
        Path(OUT).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        return 4

    # Infer alert-start field from context using semantic key preference and baseline extrema.
    start_candidates=Counter()
    for i in kyiv_idx:
        pairs,_=context_cache[i]
        for p,v in pairs:
            pl=p.lower()
            if parse_dt(v) and "alert" in pl and any(t in pl for t in ("start","started","begin")):
                start_candidates[re.sub(r"\[\d+\]","[]",p)]+=1
    start_sem=start_candidates.most_common(1)[0][0] if start_candidates else None

    def get_sem_value(pairs,sem):
        if not sem: return None
        vals=[]
        for p,v in pairs:
            if re.sub(r"\[\d+\]","[]",p)==sem and parse_dt(v):
                vals.append(v)
        return vals[0] if vals else None

    def get_alert_start(pairs):
        v=get_sem_value(pairs,start_sem)
        if v: return v
        # deterministic fallback
        for p,v in pairs:
            pl=p.lower()
            if parse_dt(v) and "alert" in pl and any(t in pl for t in ("start","started","begin")):
                return v
        return None

    all_dates=[date_only(get_alert_start(context_cache[i][0])) for i in kyiv_idx]
    all_dates=[d for d in all_dates if d]
    result["alert_start_semantic_path"]=start_sem
    result["kyiv_date_range"]={"earliest":min(all_dates) if all_dates else None,"latest":max(all_dates) if all_dates else None}

    # Positive ledger.
    pos_idx=[i for i in kyiv_idx if verdict_from_pairs(context_cache[i][0]) in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE")]
    ledger=[]
    mechanism_counts=Counter(); family_counts=Counter(); month_counts=Counter()
    classifier_cohorts=Counter(); campaign_cohorts=Counter()
    first_pos=None; last_pos=None
    for i in pos_idx:
        pairs,seen=context_cache[i]
        verdict=verdict_from_pairs(pairs)
        start=get_alert_start(pairs); d=date_only(start)
        _,end=choose_scalar(pairs, exact_leaves=("alert_end","alert_ended_at","ended_at","end_at"), must_tokens=("alert",), prefer_tokens=("end","ended"))
        fam=primary_source_family(pairs)
        mech=success_mechanism(pairs,fam)
        mechanism_counts[mech]+=1; family_counts[fam]+=1; month_counts[monthly(d)]+=1
        cvs=classifier_versions(pairs); nvs=normalization_versions(pairs); camps=campaign_values(pairs)
        for x in cvs or ["UNKNOWN"]: classifier_cohorts[x]+=1
        for x in camps or ["UNKNOWN"]: campaign_cohorts[x]+=1
        if d:
            first_pos=d if first_pos is None or d<first_pos else first_pos
            last_pos=d if last_pos is None or d>last_pos else last_pos
        accepted,links,anyprov=evidence_flags(pairs)
        # Extract identifiers.
        ids=defaultdict(list)
        for k,v in id_pairs(class_rows[i],class_path):
            if v not in ids[k]: ids[k].append(v)
        event_types=sorted({norm(v) for p,v in pairs if "event_type" in p.lower() and has_truthy(v)})
        obs_ids=sorted({norm(v) for p,v in pairs if "observation_id" in p.lower() and has_truthy(v)})
        source_links=sorted({norm(v) for p,v in pairs if ("source_link" in p.lower() or "source_url" in p.lower()) and has_truthy(v)})
        ledger.append({
            "classification_row_index":i,
            "alert_episode_id":(ids.get("alert_episode_id") or [None])[0],
            "classification_id":(ids.get("classification_id") or [None])[0],
            "alert_start":start,
            "alert_end":end,
            "verdict":verdict,
            "event_types":event_types,
            "classifier_versions_or_blobs":cvs,
            "normalization_versions":nvs,
            "accepted_evidence_membership_present":accepted,
            "source_links_present":links,
            "any_attack_event_evidence_provenance":anyprov,
            "observation_ids":obs_ids,
            "source_links":source_links[:30],
            "primary_success_mechanism":mech,
            "primary_source_family":fam,
            "source_family_candidates":source_family_candidates(pairs),
            "campaign_or_originating_artifacts":camps,
            "joined_record_count":len(seen),
            "provenance_fields":provenance_excerpt(pairs)
        })

    strict=sum(1 for x in ledger if x["verdict"]=="STRICT_EVENT_POSITIVE")
    sens=sum(1 for x in ledger if x["verdict"]=="SENSITIVITY_EVENT_POSITIVE")
    if len(ledger)!=145 or strict!=141 or sens!=4 or last_pos!="2025-02-12":
        result["diagnostics"].append({"POSITIVE_BASELINE_MISMATCH":{"ledger":len(ledger),"strict":strict,"sensitivity":sens,"last_positive":last_pos}})

    result["kyiv_positive_ledger"]=ledger
    result["success_mechanism_counts"]=dict(mechanism_counts)
    result["source_family_counts"]=dict(family_counts)
    result["monthly_positive_counts"]=dict(sorted(month_counts.items()))
    result["classifier_provenance_cohorts"]={
        "classifier_versions_or_blobs":dict(classifier_cohorts),
        "campaign_or_originating_artifacts":dict(campaign_cohorts)
    }
    result["positive_summary"]={
        "total":len(ledger),"strict":strict,"sensitivity":sens,
        "first_positive_date":first_pos,"last_positive_date":last_pos,
        "mechanism_identifiable_count":len(ledger)-mechanism_counts["UNKNOWN_FROM_FROZEN_PROVENANCE"],
        "mechanism_identifiable_share":round((len(ledger)-mechanism_counts["UNKNOWN_FROM_FROZEN_PROVENANCE"])/len(ledger),6) if ledger else None
    }

    # Pre/post comparison.
    periods={
      "PERIOD_1_THROUGH_2025_02_12":[],
      "PERIOD_2_AFTER_2025_02_12":[]
    }
    undated=[]
    for i in kyiv_idx:
        d=date_only(get_alert_start(context_cache[i][0]))
        if not d: undated.append(i); continue
        if d<=CUTOFF: periods["PERIOD_1_THROUGH_2025_02_12"].append(i)
        else: periods["PERIOD_2_AFTER_2025_02_12"].append(i)

    def period_stats(indices):
        vc=Counter(); accepted=links=anyprov=0
        cv=set(); nv=set(); fam_rows=Counter()
        for i in indices:
            pairs,_=context_cache[i]
            v=verdict_from_pairs(pairs)
            if v: vc[v]+=1
            a,l,e=evidence_flags(pairs)
            accepted+=int(a); links+=int(l); anyprov+=int(e)
            cv.update(classifier_versions(pairs)); nv.update(normalization_versions(pairs))
            # coverage can have multiple families per row; count row once per family candidate.
            cands=set(source_family_candidates(pairs))
            for f in cands: fam_rows[f]+=1
        return {
          "total_alert_episodes":len(indices),
          "STRICT_EVENT_POSITIVE":vc["STRICT_EVENT_POSITIVE"],
          "SENSITIVITY_EVENT_POSITIVE":vc["SENSITIVITY_EVENT_POSITIVE"],
          "confirmed_positives":vc["STRICT_EVENT_POSITIVE"]+vc["SENSITIVITY_EVENT_POSITIVE"],
          "NEEDS_REVIEW":vc["NEEDS_REVIEW"],
          "NO_CONFIRMED_EVENT":vc["NO_CONFIRMED_EVENT"],
          "rows_with_accepted_evidence_membership":accepted,
          "rows_with_source_links":links,
          "rows_with_any_attack_event_evidence_provenance":anyprov,
          "classifier_versions_represented":sorted(cv),
          "normalization_versions_represented":sorted(nv),
          "source_family_row_coverage":dict(fam_rows),
          "rates":{
             "accepted_evidence_membership":round(accepted/len(indices),6) if indices else None,
             "source_links":round(links/len(indices),6) if indices else None,
             "any_attack_event_evidence_provenance":round(anyprov/len(indices),6) if indices else None
          }
        }
    pre=period_stats(periods["PERIOD_1_THROUGH_2025_02_12"])
    post=period_stats(periods["PERIOD_2_AFTER_2025_02_12"])
    result["pre_post_cutoff_comparison"]={
      "cutoff":CUTOFF,
      "period_1":pre,
      "period_2":post,
      "undated_kyiv_rows":len(undated)
    }

    # Mechanically test hypotheses with explicit metrics and conservative thresholds.
    pre_er=pre["rates"]["any_attack_event_evidence_provenance"] or 0
    post_er=post["rates"]["any_attack_event_evidence_provenance"] or 0
    pre_lr=pre["rates"]["source_links"] or 0
    post_lr=post["rates"]["source_links"] or 0
    topfam=family_counts.most_common(1)[0][0] if family_counts else "UNKNOWN"
    pre_top_cov=pre["source_family_row_coverage"].get(topfam,0)/pre["total_alert_episodes"] if pre["total_alert_episodes"] else 0
    post_top_cov=post["source_family_row_coverage"].get(topfam,0)/post["total_alert_episodes"] if post["total_alert_episodes"] else 0
    cv_pre=set(pre["classifier_versions_represented"]); cv_post=set(post["classifier_versions_represented"])
    cv_overlap=sorted(cv_pre & cv_post)
    h1=(pre_er>0 and post_er <= 0.25*pre_er) or (pre_lr>0 and post_lr <= 0.25*pre_lr)
    # Campaign-stop support requires a preserved campaign/origin cohort and no such provenance later.
    positive_known_campaign=[k for k in campaign_cohorts if k!="UNKNOWN"]
    post_campaigns=set()
    for i in periods["PERIOD_2_AFTER_2025_02_12"]:
        post_campaigns.update(campaign_values(context_cache[i][0]))
    h2=bool(positive_known_campaign) and not bool(set(positive_known_campaign)&post_campaigns)
    h4=(topfam not in ("UNKNOWN","OTHER") and pre_top_cov>0 and post_top_cov <= 0.25*pre_top_cov)
    h5=bool(cv_pre and cv_post and not cv_overlap)
    comparable=(pre_er==0 and post_er==0) or (pre_er>0 and post_er>=0.8*pre_er)
    fam_comparable=(pre_top_cov==0 and post_top_cov==0) or (pre_top_cov>0 and post_top_cov>=0.8*pre_top_cov)
    classifier_comparable=(not cv_pre or not cv_post or bool(cv_overlap))
    h6=bool(post["total_alert_episodes"] and post["confirmed_positives"]==0 and comparable and fam_comparable and classifier_comparable)
    hypotheses={
      "H1_EVIDENCE_DISCOVERY_OR_BACKFILL_STOPS":{
        "status":"SUPPORTED" if h1 else "NOT_SUPPORTED",
        "evidence":{"pre_any_evidence_rate":pre_er,"post_any_evidence_rate":post_er,"pre_source_link_rate":pre_lr,"post_source_link_rate":post_lr}
      },
      "H2_CLASSIFICATION_CAMPAIGN_STOPS":{
        "status":"SUPPORTED" if h2 else ("NOT_ESTABLISHED" if not positive_known_campaign else "NOT_SUPPORTED"),
        "evidence":{"positive_campaign_values":positive_known_campaign,"post_campaign_values":sorted(post_campaigns)}
      },
      "H3_POSITIVE_PERSISTENCE_STOPS":{
        "status":"NOT_ESTABLISHED_FROM_FROZEN_PROVENANCE",
        "evidence":"This frozen snapshot alone cannot prove that later positive classifications exist elsewhere but failed persistence."
      },
      "H4_SOURCE_FAMILY_COVERAGE_CHANGES":{
        "status":"SUPPORTED" if h4 else "NOT_SUPPORTED",
        "evidence":{"dominant_positive_source_family":topfam,"pre_row_coverage_rate":round(pre_top_cov,6),"post_row_coverage_rate":round(post_top_cov,6)}
      },
      "H5_CLASSIFIER_OR_METHODOLOGY_CHANGE":{
        "status":"SUPPORTED" if h5 else ("NOT_ESTABLISHED" if not cv_pre or not cv_post else "NOT_SUPPORTED"),
        "evidence":{"pre_versions":sorted(cv_pre),"post_versions":sorted(cv_post),"overlap":cv_overlap}
      },
      "H6_REAL_ZERO_POSITIVES":{
        "status":"SUPPORTED" if h6 else "NOT_SUPPORTED",
        "evidence":{"evidence_coverage_comparable":comparable,"dominant_source_family_coverage_comparable":fam_comparable,"classifier_coverage_comparable":classifier_comparable}
      }
    }
    supported=[k for k,v in hypotheses.items() if v["status"]=="SUPPORTED"]
    if h1:
        primary="H1_EVIDENCE_DISCOVERY_OR_BACKFILL_STOPS"
    elif h2:
        primary="H2_CLASSIFICATION_CAMPAIGN_STOPS"
    elif h4:
        primary="H4_SOURCE_FAMILY_COVERAGE_CHANGES"
    elif h5:
        primary="H5_CLASSIFIER_OR_METHODOLOGY_CHANGE"
    elif h6:
        primary="H6_REAL_ZERO_POSITIVES"
    else:
        primary="H7_CANNOT_ESTABLISH_FROM_FROZEN_PROVENANCE"
        hypotheses[primary]={"status":"PRIMARY","evidence":"No tested frozen-provenance hypothesis is strong enough to select another primary explanation."}
    if primary!="H7_CANNOT_ESTABLISH_FROM_FROZEN_PROVENANCE":
        hypotheses["H7_CANNOT_ESTABLISH_FROM_FROZEN_PROVENANCE"]={"status":"NOT_PRIMARY","evidence":{"supported_hypotheses":supported}}

    # Sanity question: continuous current E2E vs bounded legacy/frozen set.
    top_classifier_share=(classifier_cohorts.most_common(1)[0][1]/len(ledger)) if ledger and classifier_cohorts else 0
    top_campaign_share=(campaign_cohorts.most_common(1)[0][1]/len(ledger)) if ledger and campaign_cohorts else 0
    bounded = post["total_alert_episodes"]>0 and post["confirmed_positives"]==0 and (h1 or h2 or h4 or last_pos==CUTOFF)
    accumulation="BOUNDED_HISTORICAL_SUCCESS_SET" if bounded else "CONTINUOUS_ACCUMULATION_NOT_ESTABLISHED"
    result["historical_campaign_assessment"]={
      "classification":accumulation,
      "is_evidence_of_continuous_current_end_to_end_classification":False if bounded else None,
      "top_classifier_cohort_share":round(top_classifier_share,6),
      "top_campaign_or_origin_cohort_share":round(top_campaign_share,6),
      "positive_span":{"first":first_pos,"last":last_pos},
      "alerts_continue_after_last_positive":post["total_alert_episodes"]>0,
      "quantitative_basis":{
        "post_cutoff_alerts":post["total_alert_episodes"],
        "post_cutoff_confirmed_positives":post["confirmed_positives"],
        "pre_evidence_provenance_rate":pre_er,
        "post_evidence_provenance_rate":post_er
      }
    }
    result["tested_hypotheses"]=hypotheses
    result["primary_cutoff_explanation"]=primary

    if primary in ("H1_EVIDENCE_DISCOVERY_OR_BACKFILL_STOPS","H2_CLASSIFICATION_CAMPAIGN_STOPS","H4_SOURCE_FAMILY_COVERAGE_CHANGES"):
        strategic="PRIMARY NEXT PROBLEM = HISTORICAL COVERAGE / BACKFILL"
    elif primary=="H3_POSITIVE_PERSISTENCE_STOPS":
        strategic="PRIMARY NEXT PROBLEM = PERSISTENCE / INTEGRATION"
    elif comparable and post["rows_with_any_attack_event_evidence_provenance"]>0 and post["NEEDS_REVIEW"]>0 and post["confirmed_positives"]==0:
        strategic="PRIMARY NEXT PROBLEM = TEMPORAL / EPISODE ATTRIBUTION"
    else:
        strategic="PRIMARY NEXT PROBLEM = NOT YET ESTABLISHED"
    result["strategic_implication"]=strategic

    # Main before/after difference in a compact machine-readable form.
    result["main_pre_vs_post_difference"]={
      "confirmed_positives":{"pre":pre["confirmed_positives"],"post":post["confirmed_positives"]},
      "any_evidence_provenance_rows":{"pre":pre["rows_with_any_attack_event_evidence_provenance"],"post":post["rows_with_any_attack_event_evidence_provenance"]},
      "any_evidence_provenance_rates":{"pre":pre_er,"post":post_er},
      "source_link_rows":{"pre":pre["rows_with_source_links"],"post":post["rows_with_source_links"]},
      "source_link_rates":{"pre":pre_lr,"post":post_lr},
      "dominant_positive_source_family":topfam,
      "dominant_family_row_coverage_rate":{"pre":round(pre_top_cov,6),"post":round(post_top_cov,6)}
    }

    # Complete only when all accepted baseline gates are exactly reproduced and dates are available.
    gates = (
      all_counts==EXPECTED_ALL and len(kyiv_idx)==2456 and kyiv_counts==EXPECTED_KYIV
      and len(ledger)==145 and strict==141 and sens==4
      and result["kyiv_date_range"]["earliest"]=="2022-02-28"
      and result["kyiv_date_range"]["latest"]=="2026-09-17"
      and last_pos=="2025-02-12"
      and len(undated)==0
    )
    result["verdict"]="KYIV POSITIVE SUCCESS/CUTOFF AUDIT = COMPLETE" if gates else "KYIV POSITIVE SUCCESS/CUTOFF AUDIT = PARTIAL"
    Path(OUT).write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True),encoding="utf-8")
    print(json.dumps({
      "verdict":result["verdict"],
      "positive_summary":result["positive_summary"],
      "mechanisms":result["success_mechanism_counts"],
      "families":result["source_family_counts"],
      "pre":pre,"post":post,
      "campaign":result["historical_campaign_assessment"],
      "primary_cutoff_explanation":primary,
      "strategic_implication":strategic
    },ensure_ascii=False,indent=2))
    return 0 if gates else 5

if __name__=="__main__":
    sys.exit(main())
