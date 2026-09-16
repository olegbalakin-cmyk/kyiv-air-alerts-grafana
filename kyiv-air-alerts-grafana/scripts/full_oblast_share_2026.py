#!/usr/bin/env python3
from __future__ import annotations
import csv, io, json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import requests

DATA_URL='https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/datasets/official_data_uk.csv'
STATES_URL='https://raw.githubusercontent.com/Vadimkin/ukrainian-air-raid-sirens-dataset/main/processors/states.json'
UTC=timezone.utc
START=datetime(2026,1,1,tzinfo=UTC)
END=datetime(2027,1,1,tzinfo=UTC)


def pdt(s):
    try:
        d=datetime.fromisoformat((s or '').strip())
    except Exception:
        return None
    return d.replace(tzinfo=UTC) if d.tzinfo is None else d.astimezone(UTC)

def clipped(s,e):
    s=max(s,START); e=min(e,END)
    return (s,e) if e>s else None

def merge(xs):
    xs=sorted(xs)
    out=[]
    for s,e in xs:
        if not out or s>out[-1][1]: out.append([s,e])
        elif e>out[-1][1]: out[-1][1]=e
    return [(s,e) for s,e in out]

def duration(xs): return sum((e-s).total_seconds() for s,e in xs)

def union(*groups): return merge([x for g in groups for x in g])

def intersect_all(groups):
    if not groups or any(not g for g in groups): return []
    pts=[]
    for i,g in enumerate(groups):
        for s,e in g: pts.append((s,1,i)); pts.append((e,-1,i))
    pts.sort(key=lambda x:(x[0],x[1]))
    counts=[0]*len(groups); active=0; start=None; out=[]
    for t,delta,i in pts:
        was=(active==len(groups))
        if delta==-1:
            counts[i]-=1
            if counts[i]==0: active-=1
        else:
            if counts[i]==0: active+=1
            counts[i]+=1
        now=(active==len(groups))
        if not was and now: start=t
        elif was and not now and start is not None:
            if t>start: out.append((start,t))
            start=None
    return merge(out)

def episode_reaches(ep, full):
    s,e=ep
    for fs,fe in full:
        if fe<=s: continue
        if fs>=e: return False
        if min(e,fe)>max(s,fs): return True
    return False

def main():
    ses=requests.Session(); ses.headers['User-Agent']='kyiv-air-alerts-grafana/full-oblast-share'
    states=ses.get(STATES_URL,timeout=60).json()['states']
    raions={s['stateName']:[d['districtName'] for d in s.get('districts',[])] for s in states if s['stateName'].endswith('область')}
    text=ses.get(DATA_URL,timeout=180).content.decode('utf-8-sig')
    oblast_iv=defaultdict(list); raion_iv=defaultdict(lambda: defaultdict(list)); max_end=None
    for r in csv.DictReader(io.StringIO(text)):
        oblast=(r.get('oblast') or '').strip()
        if oblast not in raions: continue
        s=pdt(r.get('started_at')); e=pdt(r.get('finished_at'))
        if not s or not e: continue
        if max_end is None or e>max_end: max_end=e
        ce=clipped(s,e)
        if not ce: continue
        level=(r.get('level') or '').strip()
        if level=='oblast': oblast_iv[oblast].append(ce)
        elif level=='raion':
            rr=(r.get('raion') or '').strip()
            if rr in raions[oblast]: raion_iv[oblast][rr].append(ce)
    rows=[]
    for oblast in sorted(raions):
        ob=merge(oblast_iv[oblast])
        rg={r:merge(raion_iv[oblast].get(r,[])) for r in raions[oblast]}
        any_raion=union(*rg.values()) if rg else []
        any_alert=union(ob,any_raion)
        all_raions=intersect_all(list(rg.values())) if rg else []
        full=union(ob,all_raions)
        any_sec=duration(any_alert); ob_sec=duration(ob); full_sec=duration(full)
        eps=any_alert
        full_eps=sum(1 for ep in eps if episode_reaches(ep,full))
        rows.append({
            'oblast':oblast,'raion_count':len(raions[oblast]),
            'any_alert_hours':round(any_sec/3600,3),
            'explicit_oblast_hours':round(ob_sec/3600,3),
            'full_coverage_hours':round(full_sec/3600,3),
            'explicit_oblast_share_pct':round(ob_sec/any_sec*100,1) if any_sec else None,
            'full_coverage_share_pct':round(full_sec/any_sec*100,1) if any_sec else None,
            'episodes':len(eps),'episodes_reaching_full':full_eps,
            'episodes_reaching_full_pct':round(full_eps/len(eps)*100,1) if eps else None,
            'raions_with_2026_data':sum(bool(v) for v in rg.values()),
        })
    out={'meta':{'source':DATA_URL,'period':'2026','latest_finished_at_in_dataset':max_end.isoformat() if max_end else None,
                 'definition':'full coverage = explicit oblast alert OR simultaneous active alerts in every raion listed in states.json; denominator = union of time when oblast or at least one raion is under alert'},'oblasts':rows}
    Path('data/full_oblast_share_2026.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with open('data/full_oblast_share_2026.csv','w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)
    print('latest',out['meta']['latest_finished_at_in_dataset'])
    for r in sorted(rows,key=lambda x:(x['full_coverage_share_pct'] is None, -(x['full_coverage_share_pct'] or -1))):
        print(f"{r['oblast']}\t{r['full_coverage_share_pct']}\t{r['explicit_oblast_share_pct']}\t{r['episodes_reaching_full_pct']}\t{r['raions_with_2026_data']}/{r['raion_count']}\t{r['any_alert_hours']}")
if __name__=='__main__': main()
