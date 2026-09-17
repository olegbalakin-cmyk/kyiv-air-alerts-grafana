#!/usr/bin/env python3
from __future__ import annotations

import base64, csv, gzip, io, json, os, time
from datetime import datetime, timezone
from pathlib import Path
import requests
from update_data import Alert, TZ

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_FILE = ROOT / "data" / "alerts_in_ua_bridge_additional_2026-09-07_16.csv.gz.b64"
BRIDGE_META = ROOT / "data" / "alerts_in_ua_bridge_additional_2026-09-07_16.meta.json"
REPORT_FILE = ROOT / "data" / "additional_proxy_bridge_probe.json"
API_BASE = "https://api.ukrainealarm.com/api/v3"
REGIONS_URL = f"{API_BASE}/regions"
HISTORY_URL = f"{API_BASE}/alerts/regionHistory"
TOKEN_ENV = "UKRAINEALARM_API_TOKEN"
UTC = timezone.utc
TOLERANCE_SECONDS = 5
MIN_API_INTERVAL_SECONDS = float(os.getenv("UKRAINEALARM_MIN_INTERVAL_SECONDS", "65"))

SPECS = {
    "lutsk": {"raion": "Луцький район", "oblast": "Волинська область"},
    "uzhhorod": {"raion": "Ужгородський район", "oblast": "Закарпатська область"},
    "ivano_frankivsk": {"raion": "Івано-Франківський район", "oblast": "Івано-Франківська область"},
    "chernivtsi": {"raion": "Чернівецький район", "oblast": "Чернівецька область"},
    "ternopil": {"raion": "Тернопільський район", "oblast": "Тернопільська область"},
    "kherson": {"raion": "Херсонський район", "oblast": "Херсонська область"},
    "mykolaiv": {"raion": "Миколаївський район", "oblast": "Миколаївська область"},
}

def parse_dt(value):
    if not value: return None
    dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None: dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)

def norm(s):
    return " ".join(str(s).casefold().replace("’", "'").split())

def headers(token):
    return {"Accept":"application/json","Authorization":token,"User-Agent":"kyiv-air-alerts-grafana/additional-proxy-probe"}

def load_bridge():
    meta=json.loads(BRIDGE_META.read_text(encoding="utf-8"))
    raw=gzip.decompress(base64.b64decode(BRIDGE_FILE.read_text(encoding="ascii").strip())).decode("utf-8")
    out={}
    for row in csv.DictReader(io.StringIO(raw)):
        s=parse_dt(row.get("start")); e=parse_dt(row.get("end")); key=(row.get("city_key") or "").strip()
        if key and s and e and e>s:
            out.setdefault(key,[]).append(Alert(start=s.astimezone(TZ), end=e.astimezone(TZ), source="alerts_in_ua"))
    return out,meta

def collect_nodes(payload):
    nodes=[]; seen=set()
    def walk(v, ancestors=()):
        if isinstance(v,list):
            for x in v: walk(x,ancestors)
            return
        if not isinstance(v,dict): return
        rid=v.get("regionId"); name=str(v.get("regionName") or "").strip(); child=ancestors
        if rid is not None and name:
            k=(str(rid),name)
            if k not in seen:
                seen.add(k); nodes.append({"regionId":str(rid),"regionName":name,"ancestors":list(ancestors)})
            child=(*ancestors,name)
        for x in v.values():
            if isinstance(x,(dict,list)): walk(x,child)
    walk(payload); return nodes

def resolve(nodes,raion,oblast):
    ms=[n for n in nodes if norm(n["regionName"])==norm(raion)]
    scoped=[n for n in ms if norm(oblast) in {norm(a) for a in n.get("ancestors",[])}]
    if scoped: ms=scoped
    return ms[-1] if ms else None

class Client:
    def __init__(self,token): self.token=token; self.last=None; self.s=requests.Session()
    def get(self,url,params=None):
        if self.last is not None:
            wait=MIN_API_INTERVAL_SECONDS-(time.monotonic()-self.last)
            if wait>0:
                print(f"rate-limit guard: sleeping {wait:.1f}s",flush=True); time.sleep(wait)
        r=self.s.get(url,headers=headers(self.token),params=params,timeout=60); self.last=time.monotonic()
        if not r.ok: raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
        return r

def api_rows(client,node):
    p=client.get(HISTORY_URL,{"regionId":node["regionId"]}).json()
    groups=[p] if isinstance(p,dict) else [x for x in p if isinstance(x,dict)]
    out=[]
    for g in groups:
        for a in g.get("alarms") or []:
            if str(a.get("alertType") or "").upper()!="AIR": continue
            s=parse_dt(a.get("startDate")); e=parse_dt(a.get("endDate"))
            if s and e and e>s: out.append({"start":s,"end":e})
    return sorted(out,key=lambda x:x["start"])

def match_event(api,bridge):
    for a in api:
        for b in bridge:
            ds=abs((a["start"]-b.start.astimezone(UTC)).total_seconds()); de=abs((a["end"]-b.end.astimezone(UTC)).total_seconds())
            if ds<=TOLERANCE_SECONDS and de<=TOLERANCE_SECONDS:
                return {"api_start":a["start"].isoformat(),"api_end":a["end"].isoformat(),"bridge_start":b.start.isoformat(),"bridge_end":b.end.isoformat(),"start_delta_seconds":round(ds,3),"end_delta_seconds":round(de,3)}
    return None

def main():
    token=os.getenv(TOKEN_ENV,"").strip()
    if not token: raise RuntimeError(f"{TOKEN_ENV} missing")
    bridge,meta=load_bridge(); client=Client(token)
    nodes=collect_nodes(client.get(REGIONS_URL).json())
    rows={}
    for i,(key,cfg) in enumerate(SPECS.items(),1):
        node=resolve(nodes,cfg["raion"],cfg["oblast"])
        result={"raion":cfg["raion"],"oblast":cfg["oblast"],"static_completed_events":len(bridge.get(key,[]))}
        if not node:
            result.update({"api_region_found":False,"continuous":False,"reason":"api_region_not_found"}); rows[key]=result; print(f"[{i}/7] {key}: region not found",flush=True); continue
        try:
            api=api_rows(client,node); match=match_event(api,bridge.get(key,[])); oldest=min((x["start"] for x in api),default=None); latest=max((x["end"] for x in api),default=None)
            result.update({"api_region_found":True,"api_region_id":node["regionId"],"api_region_name":node["regionName"],"api_history_completed_air":len(api),"api_oldest_start":oldest.isoformat() if oldest else None,"api_latest_end":latest.isoformat() if latest else None,"matched_overlap_event":match,"continuous":bool(match),"reason":"matched_static_and_api_event" if match else "no_verified_overlap"})
        except Exception as exc:
            result.update({"api_region_found":True,"api_region_id":node["regionId"],"continuous":False,"reason":f"api_error: {type(exc).__name__}: {exc}"})
        rows[key]=result; print(f"[{i}/7] {key}: continuous={result['continuous']} region={result.get('api_region_id')} history={result.get('api_history_completed_air')} match={bool(result.get('matched_overlap_event'))}",flush=True)
    verified=sorted(k for k,v in rows.items() if v["continuous"])
    report={"generated_at":datetime.now(UTC).isoformat(),"bridge_source":meta.get("source_url"),"coverage_start":meta.get("coverage_start"),"coverage_end_exclusive":meta.get("coverage_end_exclusive"),"required_rows":sorted(rows),"verified_rows":verified,"unverified_rows":sorted(set(rows)-set(verified)),"fully_continuous":len(verified)==len(rows),"rows":rows}
    REPORT_FILE.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Additional continuity verified: {len(verified)}/{len(rows)}",flush=True)
    if not report["fully_continuous"]: raise SystemExit(2)

if __name__=="__main__": main()
