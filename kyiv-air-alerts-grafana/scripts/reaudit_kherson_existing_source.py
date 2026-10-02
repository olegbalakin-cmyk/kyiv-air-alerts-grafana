#!/usr/bin/env python3
from __future__ import annotations
import argparse,bisect,csv,hashlib,importlib,json,re,subprocess,sys,time
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

UTC=timezone.utc; KYIV=ZoneInfo("Europe/Kyiv")
CHANNEL="suspilnekherson"; LABEL="Суспільне Херсон"
START_LOCAL=datetime(2025,8,30,0,0,tzinfo=KYIV); END_LOCAL=datetime(2026,9,18,0,0,tzinfo=KYIV)
START=START_LOCAL.astimezone(UTC); END=END_LOCAL.astimezone(UTC)
CASE73="5637257d7f33efa630943077"; MAX_PAGES=3000; MAX_RETRIES=4; RATE=0.25
ROOT=Path("kyiv-air-alerts-grafana")
SLICE=ROOT/"data/explosion_metric_handoff/source_slices/kherson-historical-recovery_alerts.json"
FINAL=ROOT/"data/explosion_research/kherson/final_evidence.json"
CLASSIFIER=ROOT/"scripts/monitor_explosion_candidates.py"; ADAPTER=ROOT/"scripts/historical_attack_event_sources.py"
BLOBS={str(SLICE):"32c0f8085161985a258d927f4a4968d4b192a708",str(FINAL):"ae816bbc412fbe62f086adb4cefb2a5af65b2a07",str(CLASSIFIER):"927dc89df0b52edd52cb31a126b0d57ca492a278",str(ADAPTER):"0ceb3ea480de9b401000ba9d8b0bb02b22d83c89"}
PROTECTED=[FINAL,ROOT/"data/explosion_audited_baseline.json",ROOT/"data/explosion_review_queue.json",ROOT/"data/explosion_candidate_monitor_state.json",ROOT/"data/explosion_candidate_monitor_last_run.json",ROOT/"data/explosions_test.json",ROOT/"data/dashboard_data.json",SLICE]
SLICES={"P1":("2025-08-30","2026-02-14",469),"P2":("2026-02-15","2026-06-21",473),"P3":("2026-06-22","2026-09-17",470)}
SIGNAL=re.compile(r"(?:вибух|влуч|прил[іi]т|удар|атак|пожеж|загор|займан|пошкод|\bппо\b|протиповітр|ракет|\bбпла\b|безпілот|дрон|shahed|шахед|\bкаб\b|авіабомб|\bгучно\b|\bчутно\b)",re.I)

def dt(v):
    if not v:return None
    x=datetime.fromisoformat(str(v).replace("Z","+00:00"))
    return (x if x.tzinfo else x.replace(tzinfo=UTC)).astimezone(UTC)
def iso(x): return x.astimezone(UTC).isoformat().replace("+00:00","Z")
def sha(b): return hashlib.sha256(b).hexdigest()
def git(repo,*a):
    p=subprocess.run(["git",*a],cwd=repo,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if p.returncode: raise RuntimeError(p.stderr.strip())
    return p.stdout.strip()
def fingerprint(repo,head):
    actual={p:git(repo,"rev-parse",f"{head}:{p}") for p in BLOBS}
    return {"pass":actual==BLOBS,"expected":BLOBS,"actual":actual,"head":head}
def modules(repo):
    sys.path.insert(0,str(repo/ROOT/"scripts"))
    return importlib.import_module("monitor_explosion_candidates"),importlib.import_module("historical_attack_event_sources")
def validate(obj):
    eps=list(obj.get("episodes") or []); ids=[str(e.get("episode_id") or "") for e in eps]
    if len(eps)!=1412 or len(set(ids))!=1412 or "" in ids: raise ValueError("BLOCKED_CANONICAL_INPUT")
    c={k:0 for k in SLICES}
    for e in eps:
        d=str(e.get("alert_start_date_kyiv") or "")
        for k,(a,b,_) in SLICES.items():
            if a<=d<=b:c[k]+=1;break
    if c!={k:v[2] for k,v in SLICES.items()}: raise ValueError(f"BLOCKED_CANONICAL_INPUT:{c}")
    return eps
def part(e):
    d=str(e.get("alert_start_date_kyiv") or "")
    return next((k for k,(a,b,_) in SLICES.items() if a<=d<=b),"OUTSIDE")
def url(cursor=None):
    if CHANNEL!="suspilnekherson": raise ValueError("allowlist")
    u=f"https://t.me/s/{CHANNEL}" if cursor is None else f"https://t.me/s/{CHANNEL}?before={int(cursor)}"
    p=urlparse(u)
    if p.scheme!="https" or p.hostname not in {"t.me","telegram.me"} or p.path!=f"/s/{CHANNEL}": raise ValueError("allowlist")
    return u
def parse_page(html,page,src):
    soup=src.BeautifulSoup(html,"html.parser"); rows=[]; errors=[]
    for msg in soup.select(".tgme_widget_message"):
        m=re.fullmatch(rf"{CHANNEL}/(\d+)",str(msg.get("data-post") or ""),re.I)
        if not m: continue
        mid=int(m.group(1)); t=msg.select_one("time[datetime]")
        if not t or not t.get("datetime"): errors.append(f"{mid}:missing_time"); continue
        try: published=src.parse_dt(str(t.get("datetime")))
        except Exception as e: errors.append(f"{mid}:bad_time:{e}"); continue
        te=msg.select_one(".tgme_widget_message_text"); text=" ".join(te.stripped_strings) if te else ""
        rows.append({"channel":CHANNEL,"message_id":mid,"source_url":f"https://t.me/{CHANNEL}/{mid}","published_at_utc":iso(published),"published_at_europe_kyiv":published.astimezone(KYIV).isoformat(),"text":text,"content_hash":src.content_hash(CHANNEL,mid,iso(published),text),"retrieval_page":page})
    return sorted(rows,key=lambda r:(r["published_at_utc"],r["message_id"])),errors
def live_fetch(src):
    adapter=src.PublicTelegramAdapter(src.NetworkBounds(timeout_seconds=30,max_retries=0,rate_limit_seconds=RATE,max_telegram_pages=MAX_PAGES))
    def get(cursor):
        u=url(cursor)
        for n in range(1,MAX_RETRIES+2):
            try:
                r=adapter.http.get(u,timeout_seconds=30); host=urlparse(str(r.url)).hostname
                if host not in {"t.me","telegram.me"}: return {"request_url":u,"http_status":r.status_code,"attempt_count":n,"error":f"redirect:{host}"}
                return {"request_url":u,"http_status":r.status_code,"attempt_count":n,"html":r.text}
            except src.requests.RequestException as e:
                status=getattr(getattr(e,"response",None),"status_code",None)
                if n>=MAX_RETRIES+1 or (status not in {None,429,500,502,503,504}): return {"request_url":u,"http_status":status,"attempt_count":n,"error":f"{type(e).__name__}:{e}"}
                ra=0
                try: ra=float(e.response.headers.get("Retry-After") or 0) if e.response is not None else 0
                except Exception: pass
                time.sleep(max(ra,RATE*(2**(n-1))))
    return get
def traverse(fetch,parser,max_pages=MAX_PAGES):
    cursor=None; prev=None; seen={}; ledger=[]; lower=False; upper=False; loops=0; failures=0; maxed=False; perrors=[]
    for i in range(1,max_pages+1):
        q=fetch(cursor); u=q.get("request_url") or url(cursor)
        if q.get("error"):
            failures+=1; ledger.append({"request_index":i,"request_url":u,"cursor_before":cursor,"http_status":q.get("http_status"),"attempt_count":q.get("attempt_count",0),"returned_post_count":0,"min_message_id":None,"max_message_id":None,"min_published_at":None,"max_published_at":None,"normalized_content_sha256":None,"next_cursor":None,"coverage_intersection":False,"error":q["error"]}); break
        rows,errs=parser(q.get("html") or "",i); perrors+=errs
        if not rows:
            failures+=0 if lower else 1; ledger.append({"request_index":i,"request_url":u,"cursor_before":cursor,"http_status":q.get("http_status",200),"attempt_count":q.get("attempt_count",1),"returned_post_count":0,"min_message_id":None,"max_message_id":None,"min_published_at":None,"max_published_at":None,"normalized_content_sha256":sha(b"[]"),"next_cursor":None,"coverage_intersection":False,"error":None if lower else "empty_before_lower"}); break
        ids=[r["message_id"] for r in rows]; times=[dt(r["published_at_utc"]) for r in rows]; nxt=min(ids)
        if cursor is not None and nxt>=cursor: loops+=1
        if prev is not None and nxt>=prev: loops+=1
        prev=nxt; lower=lower or min(times)<START; upper=upper or max(times)>=END
        norm=json.dumps([[r["message_id"],r["published_at_utc"],r["text"]] for r in rows],ensure_ascii=False,separators=(",",":")).encode()
        ledger.append({"request_index":i,"request_url":u,"cursor_before":cursor,"http_status":q.get("http_status",200),"attempt_count":q.get("attempt_count",1),"returned_post_count":len(rows),"min_message_id":min(ids),"max_message_id":max(ids),"min_published_at":iso(min(times)),"max_published_at":iso(max(times)),"normalized_content_sha256":sha(norm),"next_cursor":nxt,"coverage_intersection":min(times)<END and max(times)>=START,"error":None})
        for r in rows: seen[(r["channel"].casefold(),r["message_id"])]=r
        if loops or lower: break
        cursor=nxt
        if i==max_pages:maxed=True
    snap=sorted(seen.values(),key=lambda r:(r["published_at_utc"],r["message_id"]))
    chronology=[]; byid=sorted(snap,key=lambda r:r["message_id"])
    for a,b in zip(byid,byid[1:]):
        if dt(b["published_at_utc"])<dt(a["published_at_utc"]): chronology.append([a["message_id"],b["message_id"]])
        if len(chronology)>=20:break
    complete=bool(ledger) and lower and upper and not loops and not failures and not maxed and not perrors and not chronology
    status="COMPLETE" if complete else ("BLOCKED_MAX_PAGES" if maxed else "BLOCKED")
    return snap,ledger,{"public_history_coverage":status,"lower_boundary_crossed":lower,"upper_boundary_bracketed":upper,"pagination_loops":loops,"unrecovered_request_failures":failures,"max_pages_exhausted":maxed,"parse_errors":perrors[:50],"chronology_errors":chronology,"requests_made":len(ledger),"pages_retrieved":sum(x["returned_post_count"]>0 for x in ledger)}
def index_eps(eps):
    x=sorted([(dt(e["alert_start"]),dt(e["alert_end"]),e) for e in eps],key=lambda z:z[0]); return x,[z[0] for z in x]
def nearby(moment,ordered,starts):
    i=bisect.bisect_right(starts,moment+timedelta(minutes=15)); out=[]
    for j in range(max(0,i-8),min(len(ordered),i+4)):
        s,e,ep=ordered[j]
        if s-timedelta(minutes=15)<=moment<=e+timedelta(minutes=30):out.append(str(ep["episode_id"]))
    return sorted(set(out))
def row(post):
    text=str(post.get("text") or "")
    return {"source":f"Telegram / {LABEL}","title":text[:240] or f"Telegram post {post['message_id']}","url":post["source_url"],"publisher":LABEL,"publisher_url":f"https://t.me/{CHANNEL}","published_at":post["published_at_utc"],"snippet":text[:1200],"discovery_basis":"full_public_history_local_snapshot"}
def strict_event_time(record):
    v=str(record.get("event_time") or "")
    if re.fullmatch(r"~?\d{1,2}:\d{2}",v):
        anchor=str(record.get("episode_start") or record.get("matched_alert_episode_start") or "")
        base=anchor[:10]; offm=re.search(r"([+-]\d{2}:\d{2})$",anchor); off=offm.group(1) if offm else "+00:00"
        return dt(f"{base}T{v.lstrip('~')}:00{off}")
    return dt(v)

def baseline_ids(final,eps):
    out=[]
    for record in final.get("strict_events") or []:
        moment=strict_event_time(record)
        hits=[str(e["episode_id"]) for e in eps if moment and dt(e["alert_start"])<=moment<=dt(e["alert_end"])]
        if len(hits)!=1: raise ValueError(f"retained strict control not uniquely bound by event_time:{record.get('event_time')}:{hits}")
        out.append(hits[0])
    if len(out)!=2 or len(set(out))!=2: raise ValueError("baseline strict controls !=2")
    return sorted(out)
def classify(snapshot,eps,clf,src):
    ordered,starts=index_eps(eps); candidates=[]; obs=[]; items=[]; epmsgs=defaultdict(set); byep=defaultdict(list); cidmid={}
    for p in snapshot:
        moment=dt(p["published_at_utc"])
        if not moment or moment<START-timedelta(minutes=30) or moment>=END+timedelta(minutes=30):continue
        near=nearby(moment,ordered,starts)
        if not SIGNAL.search(str(p.get("text") or "")) and not near:continue
        r=row(p); cid=clf.candidate_id("kherson",r["url"],r["title"]); matching=clf.match_candidate_to_episodes(r,eps); dec=clf.classify_candidate(r,"kherson",eps,matching)
        item={**r,"candidate_id":cid,"city_key":"kherson","status":dec["proposed_outcome"],"matched_episode_id":None}; clf.apply_matching_result(item,matching)
        if dec["proposed_outcome"] in {"approved_strict","approved_sensitivity"}:item["matched_episode_id"]=dec.get("proposed_matched_episode_id")
        items.append(item); cidmid[cid]=p["message_id"]; rel=set(near)|set(map(str,matching.get("matched_episode_ids") or []))
        for eid in rel:epmsgs[eid].add(p["message_id"])
        o={"observation_id":src.canonical_observation_id(CHANNEL,int(p["message_id"])),"candidate_id":cid,"channel":CHANNEL,"message_id":p["message_id"],"source_url":p["source_url"],"source_timestamp":p["published_at_utc"],"excerpt":str(p.get("text") or "")[:700],"event_types_supported":list(dec.get("event_types") or []),"exact_city_binding":bool((dec.get("exact_city_classification_evidence") or {}).get("present")),"strict_event_evidence":bool((dec.get("strict_explosion_evidence") or {}).get("present")),"air_attack_context":bool((dec.get("air_military_context") or {}).get("present")),"same_attack_context":bool((dec.get("same_attack_context") or {}).get("present")),"temporal_binding":dec.get("temporal_binding"),"matching_result":matching,"classification_outcome":dec.get("proposed_outcome"),"classification_episode_id":dec.get("proposed_matched_episode_id"),"reason_codes":list(dec.get("reason_codes") or []),"content_hash":p["content_hash"],"nearby_episode_ids":near}
        obs.append(o); candidates.append({**p,"candidate_id":cid,"nearby_episode_ids":near,"matching":matching})
        for eid in rel:byep[eid].append(o)
    groups=defaultdict(list)
    for it in items:
        if it.get("matched_episode_id"):groups[str(it["matched_episode_id"])].append(it)
    epmap={str(e["episode_id"]):e for e in eps}; comps={}
    for eid,g in groups.items():
        if len(g)>=2 and eid in epmap: comps[eid]=clf.compose_episode_candidates("kherson",epmap[eid],g,eps)
    ds=defaultdict(list); ss=defaultdict(list); rr=defaultdict(list)
    for o in obs:
        eid=str(o.get("classification_episode_id") or "")
        if o["classification_outcome"]=="approved_strict" and eid:ds[eid].append(o)
        elif o["classification_outcome"]=="approved_sensitivity" and eid:ss[eid].append(o)
        elif o["classification_outcome"]=="needs_review":
            for x in o["matching_result"].get("matched_episode_ids") or o["nearby_episode_ids"]:rr[str(x)].append(o)
    strict=set(ds); compids=defaultdict(list)
    for eid,c in comps.items():
        if c.get("final_composed_verdict")=="approved_strict":
            strict.add(eid); compids[eid]=[cidmid[x] for x in c.get("contributing_candidate_ids") or [] if x in cidmid]
    sens=set(ss)-strict; review=set(rr)-strict-sens
    return {"candidates":candidates,"observations":obs,"by_episode":byep,"episode_messages":epmsgs,"direct_strict":ds,"direct_sens":ss,"direct_review":rr,"compositions":comps,"composition_messages":compids,"strict_ids":strict,"sensitivity_ids":sens,"review_ids":review}
def case73(c):
    obs=list(c["by_episode"].get(CASE73) or []); relevant=[o for o in obs if o["exact_city_binding"] and o["strict_event_evidence"]]; retrieved=bool(relevant)
    if CASE73 in c["strict_ids"]:return {"source_retrieved":retrieved,"classification":"STRICT","recovered_strict":True,"failure_stage":None}
    cls="SENSITIVITY" if CASE73 in c["sensitivity_ids"] else ("REVIEW" if CASE73 in c["review_ids"] or obs else "NONE")
    if not retrieved:return {"source_retrieved":False,"classification":cls,"recovered_strict":False,"failure_stage":None}
    b=max(relevant,key=lambda o:sum(bool(o.get(k)) for k in ["exact_city_binding","strict_event_evidence","air_attack_context","same_attack_context"])+bool((o.get("temporal_binding") or {}).get("present")))
    stage="AIR_CONTEXT" if not b["air_attack_context"] else ("SAME_ATTACK_CONTEXT" if not b["same_attack_context"] else ("TEMPORAL_BINDING" if not (b.get("temporal_binding") or {}).get("present") else "EPISODE_MATCHING"))
    return {"source_retrieved":True,"classification":cls,"recovered_strict":False,"failure_stage":stage}
def retired(final,snapshot,c,eps):
    recs=[x for x in final.get("review_events") or [] if x.get("current_metric_role")=="REVIEW_NON_COUNTED_RETIRED_LEGACY_POSITIVE"]; context=0; cur=0
    epmap={str(e["episode_id"]):e for e in eps}
    for r in recs:
        v=((r.get("normalization_provenance") or {}).get("best_supported_event_time") or {}).get("utc"); vals=[v] if isinstance(v,str) else (v or []); moments=[dt(x) for x in vals if dt(x)]
        if moments and any(any(abs((dt(p["published_at_utc"])-m).total_seconds())<=2700 and SIGNAL.search(str(p.get("text") or "")) for p in snapshot) for m in moments):context+=1
        if any(any(dt(epmap[eid]["alert_start"])<=m<=dt(epmap[eid]["alert_end"]) for m in moments) for eid in c["strict_ids"] if eid in epmap):cur+=1
    return {"total":len(recs),"source_context_retrieved":context,"currently_strict":cur,"remain_non_counted":len(recs)-cur}
def ledger(eps,c,coverage,base):
    out=[]
    for e in sorted(eps,key=lambda x:(x["alert_start"],x["episode_id"])):
        eid=str(e["episode_id"]); d=c["direct_strict"].get(eid,[]); s=c["direct_sens"].get(eid,[]); r=c["direct_review"].get(eid,[]); comp=c["compositions"].get(eid) or {}; compok=comp.get("final_composed_verdict")=="approved_strict"
        outcome="SOURCE_COVERAGE_BLOCKED" if coverage!="COMPLETE" else ("STRICT_EVENT_POSITIVE" if eid in c["strict_ids"] else ("SENSITIVITY_EVENT_POSITIVE" if eid in c["sensitivity_ids"] else ("NEEDS_REVIEW" if eid in c["review_ids"] else "NO_QUALIFYING_EVIDENCE_IN_SUSPILNE_KHERSON")))
        reasons=[x for o in d+s+r for x in o.get("reason_codes",[])]+list(comp.get("reason_codes") or [])
        if outcome=="NO_QUALIFYING_EVIDENCE_IN_SUSPILNE_KHERSON":reasons.append("NO_QUALIFYING_EVIDENCE_IN_COMPLETE_CONFIGURED_SOURCE_PASS")
        ids=[f"{o['channel']}/{o['message_id']}" for o in d]+[f"{CHANNEL}/{x}" for x in c["composition_messages"].get(eid,[])]
        out.append({"episode_id":eid,"alert_start_utc":iso(dt(e["alert_start"])),"alert_end_utc":iso(dt(e["alert_end"])),"alert_start_europe_kyiv":dt(e["alert_start"]).astimezone(KYIV).isoformat(),"alert_end_europe_kyiv":dt(e["alert_end"]).astimezone(KYIV).isoformat(),"slice":part(e),"existing_retained_state":"STRICT" if eid in base else "NON_STRICT","source_history_coverage":coverage,"candidate_message_count":len(c["episode_messages"].get(eid,set())),"candidate_message_ids":sorted(c["episode_messages"].get(eid,set())),"strict_observation_count":len(d)+(1 if compok and not d else 0),"sensitivity_observation_count":len(s),"review_observation_count":len(r),"reaudit_outcome":outcome,"strict_source_ids":sorted(set(ids)),"reason_codes":sorted(set(reasons))})
    if len(out)!=1412:raise AssertionError("ledger !=1412")
    return out
def slice_summary(rows,base):
    out={}
    for k,(_,_,n) in SLICES.items():
        z=[r for r in rows if r["slice"]==k]
        if len(z)!=n:raise AssertionError(f"{k}:{len(z)}")
        out[k]={"episodes":len(z),"existing_strict":sum(r["episode_id"] in base for r in z),"full_pass_strict":sum(r["reaudit_outcome"]=="STRICT_EVENT_POSITIVE" for r in z),"new_strict_vs_current_retained":sum(r["reaudit_outcome"]=="STRICT_EVENT_POSITIVE" and r["episode_id"] not in base for r in z),"sensitivity":sum(r["reaudit_outcome"]=="SENSITIVITY_EVENT_POSITIVE" for r in z),"review":sum(r["reaudit_outcome"]=="NEEDS_REVIEW" for r in z),"source_negative":sum(r["reaudit_outcome"]=="NO_QUALIFYING_EVIDENCE_IN_SUSPILNE_KHERSON" for r in z),"blocked":sum(r["reaudit_outcome"]=="SOURCE_COVERAGE_BLOCKED" for r in z)}
    return out
def write_jsonl(p,rows):
    with p.open("w",encoding="utf-8") as f:
        for r in rows:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n")
def main():
    a=argparse.ArgumentParser(); a.add_argument("--repo",default="."); a.add_argument("--proof-base-head",required=True); a.add_argument("--current-authoritative-head-at-start",required=True); a.add_argument("--out",required=True); x=a.parse_args()
    repo=Path(x.repo).resolve(); out=Path(x.out).resolve(); out.mkdir(parents=True,exist_ok=True)
    fp=fingerprint(repo,x.proof_base_head)
    if not fp["pass"]:raise SystemExit("BLOCKED_CANONICAL_INPUT:fingerprint")
    eps=validate(json.loads((repo/SLICE).read_text())); final=json.loads((repo/FINAL).read_text()); base=baseline_ids(final,eps)
    if len([r for r in final.get("review_events") or [] if r.get("current_metric_role")=="REVIEW_NON_COUNTED_RETIRED_LEGACY_POSITIVE"])!=7:raise SystemExit("BLOCKED_CANONICAL_INPUT:retired")
    clf,src=modules(repo); snap,pages,cov=traverse(live_fetch(src),lambda h,i:parse_page(h,i,src)); c=classify(snap,eps,clf,src); rows=ledger(eps,c,cov["public_history_coverage"],base); ss=slice_summary(rows,base)
    redis=sum(e in c["strict_ids"] for e in base); c73=case73(c); old=retired(final,snap,c,eps)
    p=subprocess.run(["git","diff","--exit-code","--",*[str(z) for z in PROTECTED]],cwd=repo,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True); clean=p.returncode==0
    strict=sum(r["reaudit_outcome"]=="STRICT_EVENT_POSITIVE" for r in rows); sens=sum(r["reaudit_outcome"]=="SENSITIVITY_EVENT_POSITIVE" for r in rows); review=sum(r["reaudit_outcome"]=="NEEDS_REVIEW" for r in rows); neg=sum(r["reaudit_outcome"]=="NO_QUALIFYING_EVIDENCE_IN_SUSPILNE_KHERSON" for r in rows); blocked=sum(r["reaudit_outcome"]=="SOURCE_COVERAGE_BLOCKED" for r in rows)
    snapbytes=b"".join((json.dumps(r,ensure_ascii=False,sort_keys=True)+"\n").encode() for r in snap); snapsha=sha(snapbytes); win=[r for r in snap if START<=dt(r["published_at_utc"])<END]
    coverage=cov["public_history_coverage"]; proven=coverage=="COMPLETE" and redis==2 and c73["recovered_strict"] and blocked==0 and clean
    verdict="PROVEN" if proven else ("BLOCKED_SOURCE_HISTORY_NOT_DEEP_ENOUGH" if coverage!="COMPLETE" else ("BLOCKED_BASELINE_CONTROL_REGRESSION" if redis!=2 else ("BLOCKED_CASE73_NOT_IN_EXISTING_SOURCE" if not c73["source_retrieved"] else ("BLOCKED_CASE73_CLASSIFIER_GAP" if not c73["recovered_strict"] else "BLOCKED_PROTECTED_STATE_MUTATION"))))
    summary={"final_verdict":verdict,"channel":"Telegram / @suspilnekherson","audit_window":{"local_start":START_LOCAL.isoformat(),"local_end":END_LOCAL.isoformat()},"requests_made":cov["requests_made"],"pages_retrieved":cov["pages_retrieved"],"unique_posts_in_window":len(win),"first_post_in_window":win[0]["published_at_utc"] if win else None,"last_post_in_window":win[-1]["published_at_utc"] if win else None,"snapshot_sha256":snapsha,**cov,"canonical_episodes":1412,"episode_ledger_rows":len(rows),"current_strict":2,"full_pass_strict":strict if coverage=="COMPLETE" else None,"new_strict":len(c["strict_ids"]-set(base)) if coverage=="COMPLETE" else None,"strict_share":round(strict/1412*100,2) if coverage=="COMPLETE" and redis==2 else None,"sensitivity":sens,"review":review,"source_negative":neg,"blocked":blocked,"baseline_strict_controls_total":2,"baseline_strict_controls_recovered":redis,"baseline_strict_control":"PASS" if redis==2 else "FAIL","baseline_strict_episode_ids":base,"case_73_recovered_strict":c73["recovered_strict"],"case_73":c73,"retired_controls_total":old["total"],"retired_controls_source_context_retrieved":old["source_context_retrieved"],"retired_controls_currently_strict":old["currently_strict"],"retired_controls_remain_non_counted":old["remain_non_counted"],"slice_accounting":ss,"protected_files_unchanged":clean,"original_forensic_base":"acd01dfbe8e520a93ccf827f3179e3cdc6cfc3e5","current_authoritative_head_at_proof_start":x.current_authoritative_head_at_start,"proof_base_head":x.proof_base_head,"historical_input_fingerprint":fp,"direct_existing_source_network_retrieval":True,"generic_web_search":False,"new_source_discovery":False,"new_source_family":False,"historical_evidence_mutations":0 if clean else 1,"canonical_alert_mutations":0 if clean else 1,"db_neon_mutations":0,"incorporation":False,"deploy":False}
    write_jsonl(out/"kherson-page-ledger.jsonl",pages); write_jsonl(out/"kherson-suspilnekherson-snapshot.jsonl",snap); write_jsonl(out/"kherson-episode-coverage-ledger.jsonl",rows)
    with (out/"kherson-episode-coverage-ledger.csv").open("w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0])); w.writeheader()
        for r in rows:w.writerow({k:json.dumps(v,ensure_ascii=False,sort_keys=True) if isinstance(v,(list,dict)) else v for k,v in r.items()})
    write_jsonl(out/"kherson-candidates.jsonl",c["candidates"]); write_jsonl(out/"kherson-observations.jsonl",c["observations"])
    (out/"kherson-review-queue.json").write_text(json.dumps([r for r in rows if r["reaudit_outcome"]=="NEEDS_REVIEW"],ensure_ascii=False,indent=2)+"\n")
    (out/"kherson-source-coverage-summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
    (out/"kherson-source-coverage-summary.md").write_text(f"# Kherson existing-source re-audit\n\n- verdict: **{verdict}**\n- coverage: **{coverage}**\n- strict: **{strict}**\n- share: **{summary['strict_share']}**\n- case 73 strict: **{c73['recovered_strict']}**\n\nNO_QUALIFYING_EVIDENCE_IN_SUSPILNE_KHERSON means only no qualifying evidence in this configured source pass; it does not mean no attack occurred.\n")
    files=[p for p in out.iterdir() if p.is_file() and p.name!="manifest.json"]; manifest={"schema_version":1,"artifact":"historical-kherson-existing-source-reaudit","proof_base_head":x.proof_base_head,"files":{p.name:{"sha256":sha(p.read_bytes()),"bytes":p.stat().st_size} for p in sorted(files)}}; (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps(summary,ensure_ascii=False,indent=2))
    if verdict!="PROVEN":raise SystemExit(3)
if __name__=="__main__":main()
