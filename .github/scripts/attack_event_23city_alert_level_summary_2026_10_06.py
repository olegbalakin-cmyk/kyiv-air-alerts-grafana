import json, os, re, subprocess, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

SOURCE_COMMIT="efefa399e69eadd3d7fc8393ac1553cfde35f138"
SOURCE_PATH="research/attack_event_23city_persistence_snapshot_v2_2026-10-04.json"
EXPECTED_BLOB="8a2f6bd33f879be9db978da59c12c34e61f6f843"
OUTPUT_FILE="attack_event_23city_alert_level_summary_2026-10-06.json"
EXPECTED_TOTAL=26405
EXPECTED={"STRICT_EVENT_POSITIVE":1017,"SENSITIVITY_EVENT_POSITIVE":63,"NO_CONFIRMED_EVENT":23530,"NEEDS_REVIEW":1795}
ALLOWED=set(EXPECTED)

def git(*a): return subprocess.check_output(["git",*a],text=True).strip()
def parse_dt(v):
    if v is None:return None
    if isinstance(v,(int,float)):
        try:return datetime.fromtimestamp(v if v<1e12 else v/1000,tz=timezone.utc)
        except:return None
    s=str(v).strip()
    if not s:return None
    try:
        d=datetime.fromisoformat(s.replace("Z","+00:00"))
        if d.tzinfo is None:d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except:return None

def walk_scalars(x,p=(),depth=0):
    if depth>6:return
    if isinstance(x,dict):
        for k,v in x.items():
            np=p+(str(k),)
            if isinstance(v,dict): yield from walk_scalars(v,np,depth+1)
            elif not isinstance(v,list): yield np,v

def find_city(rec):
    for p,v in walk_scalars(rec):
        if p[-1]=="city_key" and isinstance(v,str) and v:return v
    return None

def find_verdict(rec):
    vals=[]
    for p,v in walk_scalars(rec):
        if isinstance(v,str) and v in ALLOWED: vals.append(v)
    u=list(dict.fromkeys(vals))
    return u[0] if len(u)==1 else None

def discover_time_path(records,want):
    c=Counter()
    for rec in records[:5000]:
        for p,v in walk_scalars(rec):
            if parse_dt(v) is None: continue
            leaf=p[-1].lower()
            path=".".join(p).lower()
            if want=="start":
                hit=("start" in leaf or "begin" in leaf) and ("alert" in path or "episode" in path or len(p)==1)
            else:
                hit=("end" in leaf or "finish" in leaf or "clear" in leaf) and ("alert" in path or "episode" in path or len(p)==1)
            if hit:c[p]+=1
    if not c:return None
    return c.most_common(1)[0][0]

def get_path(rec,p):
    x=rec
    try:
        for k in p:x=x[k]
        return x
    except:return None

def date_str(raw,dt):
    if isinstance(raw,str):
        m=re.match(r"^(\d{4}-\d{2}-\d{2})",raw.strip())
        if m:return m.group(1)
    return dt.strftime("%Y-%m-%d") if dt else None

def month_str(raw,dt):
    if isinstance(raw,str):
        m=re.match(r"^(\d{4})-(\d{2})",raw.strip())
        if m:return m.group(1)+"-"+m.group(2)
    return dt.strftime("%Y-%m") if dt else None

actual_blob=git("rev-parse",f"{SOURCE_COMMIT}:{SOURCE_PATH}")
raw=subprocess.check_output(["git","show",f"{SOURCE_COMMIT}:{SOURCE_PATH}"])
root=json.loads(raw)

records=root.get("classifications") if isinstance(root,dict) else None
if not isinstance(records,list):
    records=None
    def scan(x):
        global records
        if records is not None:return
        if isinstance(x,list) and len(x)==EXPECTED_TOTAL and all(isinstance(i,dict) for i in x[:3]): records=x; return
        if isinstance(x,dict):
            for v in x.values(): scan(v)
    scan(root)

if not isinstance(records,list):
    records=[]

global_counts=Counter()
city_counts=defaultdict(Counter)
cities={}
bad_identity=0
for rec in records:
    city=find_city(rec); verdict=find_verdict(rec)
    if not city or verdict not in ALLOWED:
        bad_identity+=1; continue
    global_counts[verdict]+=1
    city_counts[city][verdict]+=1
    city_counts[city]["total"]+=1

sum_city_totals=sum(v["total"] for v in city_counts.values())
sum_city_pos=sum(v["STRICT_EVENT_POSITIVE"]+v["SENSITIVITY_EVENT_POSITIVE"] for v in city_counts.values())
validation={
 "source_blob_exact":{"passed":actual_blob==EXPECTED_BLOB,"expected":EXPECTED_BLOB,"actual":actual_blob},
 "classifications_count":{"passed":len(records)==EXPECTED_TOTAL,"expected":EXPECTED_TOTAL,"actual":len(records)},
 "aggregate_verdict_distribution":{"passed":all(global_counts[k]==v for k,v in EXPECTED.items()),"expected":EXPECTED,"actual":{k:global_counts[k] for k in EXPECTED}},
 "sum_city_totals":{"passed":sum_city_totals==EXPECTED_TOTAL,"expected":EXPECTED_TOTAL,"actual":sum_city_totals},
 "sum_city_confirmed_positives":{"passed":sum_city_pos==1080,"expected":1080,"actual":sum_city_pos},
}
order=["source_blob_exact","classifications_count","aggregate_verdict_distribution","sum_city_totals","sum_city_confirmed_positives"]
first_fail=next((g for g in order if not validation[g]["passed"]),None)

start_path=discover_time_path(records,"start")
end_path=discover_time_path(records,"end")
validation["timestamp_paths"]={"start":".".join(start_path) if start_path else None,"end":".".join(end_path) if end_path else None,"identity_parse_errors":bad_identity}

city_meta=defaultdict(lambda:{"emin":None,"eraw":None,"lmax":None,"lraw":None})
parsed=[]
for rec in records:
    city=find_city(rec); verdict=find_verdict(rec)
    if not city or verdict not in ALLOWED: continue
    sr=get_path(rec,start_path) if start_path else None
    er=get_path(rec,end_path) if end_path else None
    sd=parse_dt(sr); ed=parse_dt(er)
    parsed.append((city,verdict,sr,sd,er,ed))
    m=city_meta[city]
    if sd is not None and (m["emin"] is None or sd<m["emin"]):m["emin"],m["eraw"]=sd,sr
    if ed is not None and (m["lmax"] is None or ed>m["lmax"]):m["lmax"],m["lraw"]=ed,er

per_city={}
for city in sorted(city_counts):
    c=city_counts[city]; m=city_meta[city]
    per_city[city]={
      "total_classifications":c["total"],
      "STRICT_EVENT_POSITIVE":c["STRICT_EVENT_POSITIVE"],
      "SENSITIVITY_EVENT_POSITIVE":c["SENSITIVITY_EVENT_POSITIVE"],
      "confirmed_positives":c["STRICT_EVENT_POSITIVE"]+c["SENSITIVITY_EVENT_POSITIVE"],
      "NO_CONFIRMED_EVENT":c["NO_CONFIRMED_EVENT"],
      "NEEDS_REVIEW":c["NEEDS_REVIEW"],
      "earliest_alert_start":m["eraw"],
      "latest_alert_end":m["lraw"],
    }

keys=sorted(per_city)
kc=[k for k in keys if k.lower()=="kyiv"]
if not kc:kc=[k for k in keys if k.lower() in {"kyiv_city","kyiv-city","kiev"}]
if not kc:kc=[k for k in keys if "kyiv" in k.lower() and "oblast" not in k.lower() and "region" not in k.lower()]
kyiv=kc[0] if len(kc)==1 else None

monthly=defaultdict(Counter); lastp=None; lastpraw=None
if kyiv:
    for city,verdict,sr,sd,er,ed in parsed:
        if city!=kyiv or sd is None:continue
        mon=month_str(sr,sd)
        monthly[mon]["total"]+=1;monthly[mon][verdict]+=1
        if verdict in {"STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE"} and (lastp is None or sd>lastp):lastp,lastpraw=sd,sr

monthly_out=[]
for mon in sorted(monthly):
    m=monthly[mon]
    monthly_out.append({"month":mon,"total_alert_episodes":m["total"],"STRICT_EVENT_POSITIVE":m["STRICT_EVENT_POSITIVE"],"SENSITIVITY_EVENT_POSITIVE":m["SENSITIVITY_EVENT_POSITIVE"],"confirmed_positives":m["STRICT_EVENT_POSITIVE"]+m["SENSITIVITY_EVENT_POSITIVE"],"NO_CONFIRMED_EVENT":m["NO_CONFIRMED_EVENT"],"NEEDS_REVIEW":m["NEEDS_REVIEW"]})

kyiv_summary=None
if kyiv:
    k=per_city[kyiv]
    kyiv_summary={"city_key":kyiv,"total_alert_episodes":k["total_classifications"],"confirmed_positives":k["confirmed_positives"],"STRICT_EVENT_POSITIVE":k["STRICT_EVENT_POSITIVE"],"SENSITIVITY_EVENT_POSITIVE":k["SENSITIVITY_EVENT_POSITIVE"],"earliest_alert_start":k["earliest_alert_start"],"latest_alert_end":k["latest_alert_end"],"last_confirmed_positive_alert_date":date_str(lastpraw,lastp) if lastp else None,"last_confirmed_positive_month":month_str(lastpraw,lastp) if lastp else None}

validation["first_failing_gate"]=first_fail
complete=first_fail is None
out={
 "verdict":"23-CITY ALERT-LEVEL SUMMARY = COMPLETE" if complete else "23-CITY ALERT-LEVEL SUMMARY = BLOCKED",
 "frozen_source":{"path":SOURCE_PATH,"commit":SOURCE_COMMIT,"expected_blob":EXPECTED_BLOB,"actual_blob":actual_blob,"blob_verified":actual_blob==EXPECTED_BLOB},
 "validation":validation,
 "global_totals":{"total_classifications":len(records),"STRICT_EVENT_POSITIVE":global_counts["STRICT_EVENT_POSITIVE"],"SENSITIVITY_EVENT_POSITIVE":global_counts["SENSITIVITY_EVENT_POSITIVE"],"confirmed_positives":global_counts["STRICT_EVENT_POSITIVE"]+global_counts["SENSITIVITY_EVENT_POSITIVE"],"NO_CONFIRMED_EVENT":global_counts["NO_CONFIRMED_EVENT"],"NEEDS_REVIEW":global_counts["NEEDS_REVIEW"]},
 "per_city_summary":per_city,
 "kyiv_summary":kyiv_summary,
 "kyiv_monthly_summary":monthly_out,
 "run":{"github_run_id":os.getenv("GITHUB_RUN_ID"),"workflow_commit":os.getenv("GITHUB_SHA")},
 "mutation_confirmation":{"classifier_mutations":0,"parser_mutations":0,"source_mutations":0,"alert_state_mutations":0,"persistence_mutations":0,"neon_db_queries":0,"neon_db_writes":0,"deployments":0},
}
with open(OUTPUT_FILE,"w",encoding="utf-8") as f: json.dump(out,f,ensure_ascii=False,indent=2,default=str);f.write("\n")
sys.exit(0 if complete else 1)
