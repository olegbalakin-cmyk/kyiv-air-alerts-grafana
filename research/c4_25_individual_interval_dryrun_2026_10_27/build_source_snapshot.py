#!/usr/bin/env python3
"""C4 source-only 25 individual intervals. No database, production or site writes."""
from __future__ import annotations
import csv
import hashlib
import io
import json
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "source_snapshot.json"
REPO = "olegbalakin-cmyk/kyiv-air-alerts-grafana"
ORIGINAL_COMMIT = "d1c0e55830f0cdf89bb38140321567f997405719"
SITE_COMMIT = "e3fc98eeaa7bce5f7a5fe941c886624a0af24df4"
VADIMKIN_COMMIT = "0b243d3986da01e176ff2a3e7d7bc669652a1065"
VADIMKIN_BLOB = "71d70c0ca54968f530d596cf315616fa858800e1"
MUNICIPAL = ("https://data.kyivcity.gov.ua/dataset/"
    "statystyka-povitrianykh-tryvoh-u-misti-kyievi-dep-municipal/"
    "resource/5e4fb8a8-f0c8-4a12-885f-192d1f0dba75/data/download")
CSV_URL = ("https://raw.githubusercontent.com/Vadimkin/"
    "ukrainian-air-raid-sirens-dataset/" + VADIMKIN_COMMIT +
    "/datasets/official_data_uk.csv")
UTC = timezone.utc
KYIV = ZoneInfo("Europe/Kyiv")
RAW = "https://raw.githubusercontent.com/" + REPO + "/"
CONFIG = {
    "lviv": {"oblast":"Львівська область","raion":"Львівський район",
             "start":"2025-09-01","kind":"raion_proxy"},
    "sumy": {"oblast":"Сумська область","raion":"Сумський район",
             "start":"2025-08-06","kind":"raion_proxy"},
    "kharkiv": {"hromada":"м. Харків та Харківська територіальна громада",
                "start":"2025-02-17T19:02:05+00:00","kind":"exact_hromada"},
    "zaporizhzhia": {"hromada":"м. Запоріжжя та Запорізька територіальна громада",
                    "start":"2025-03-19T14:25:36+00:00","kind":"exact_hromada"}
}
SLICES = {
 "lviv": ( "312262dfa268476a24716bbe08e8c7d19334a9d3", "lviv-replay_alerts.json"),
 "sumy": ( "312262dfa268476a24716bbe08e8c7d19334a9d3", "sumy-P4c_alerts.json"),
 "zaporizhzhia": ("312262dfa268476a24716bbe08e8c7d19334a9d3", "zaporizhzhia-P4c_alerts.json"),
 "kharkiv": ( "0800a7382bcea65e6c6ca9683d6eb5a0d5895d87", "kharkiv-P6c_alerts.json"),
 "kyiv": ( "e460bc30524deb8abc37923276d78f6dab1450a4", "kyiv-P5b_alerts.json")
}
SOURCE_SLICE_DIR = "kyiv-air-alerts-grafana/data/explosion_metric_handoff/source_slices/"
def fetch(url: str, timeout: int=180) -> tuple[bytes, dict]:
    req = urllib.request.Request(url, headers={"User-Agent":"C4-public-readonly-reconstruction/1.0","Accept":"*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        return data, {"etag":r.headers.get("ETag"), "last_modified":r.headers.get("Last-Modified"),
                      "content_type":r.headers.get("Content-Type"),"bytes":len(data),
                      "sha256":hashlib.sha256(data).hexdigest()}
def source_json(commit: str,path: str):
    return json.loads(fetch(RAW + commit + "/" + path)[0])
def dt(raw: str, allow_naive=False):
    v = datetime.fromisoformat(str(raw).replace("Z","+00:00"))
    if v.tzinfo is None:
        if not allow_naive: raise ValueError("naive timestamp: "+str(raw))
        v = v.replace(tzinfo=KYIV)
    return v.astimezone(UTC)
def iso(d): return d.astimezone(UTC).isoformat().replace("+00:00","Z")
def eid(city, a, b):
    return hashlib.sha256((city+"|"+iso(a)+"|"+iso(b)).encode()).hexdigest()[:24]
def normalize(series, city):
    result = []
    for obj in series:
        s,e = obj.pop("_start"),obj.pop("_end")
        obj.update({"start_at":iso(s),"end_at":iso(e),"legacy_episode_id":eid(city,s,e)})
        result.append(obj)
    return sorted(result,key=lambda x:(x["start_at"],x["end_at"]))
def union(items, city):
    items = sorted(items,key=lambda x:(x["_start"],x["_end"]))
    out=[]
    for x in items:
        if not out or x["_start"] > out[-1]["_end"]:
            out.append(dict(x))
        else:
            q=out[-1]
            if x["_end"]>q["_end"]:q["_end"]=x["_end"]
            q["source_row_numbers"]+=x["source_row_numbers"]
    for v in out: v["source_row_numbers"]=sorted(set(v["source_row_numbers"]))
    return normalize(out, city)
def municipal_rows(content):
    obj=json.loads(content)
    if not isinstance(obj,list): raise ValueError("official municipal API JSON not an array")
    res=[]
    for i,x in enumerate(obj):
        if not isinstance(x,dict) or x.get("type")!="Повітряна тривога":continue
        try:
            s=dt(x["dateTimeStart"],allow_naive=True);e=dt(x["dateTimeEnd"],allow_naive=True)
            if e<=s:continue
        except (KeyError,ValueError,TypeError):continue
        native=next((str(x[k]) for k in ("id","_id","alertId","Id") if x.get(k) is not None),None)
        res.append({"_start":s,"_end":e,"source_row_numbers":[i],
                    "source_native_id":native,"source_geography":"Kyiv municipality",
                    "upstream_type":x["type"]})
    return normalize(res,"kyiv")
def vadimkin_rows(content):
    raw=content.decode("utf-8-sig")
    reader=csv.DictReader(io.StringIO(raw))
    if not {"level","oblast","raion","hromada","started_at","finished_at"}.issubset(reader.fieldnames or []):
        raise ValueError("Vadimkin CSV required columns absent")
    series={k:[] for k in CONFIG}
    seen={k:set() for k in CONFIG}
    for i,row in enumerate(reader,start=2):
        level=(row.get("level") or "").strip()
        for city,c in CONFIG.items():
            if c["kind"]=="raion_proxy":
                if row.get("oblast","").strip()!=c["oblast"]:continue
                if level!="oblast" and not (level=="raion" and row.get("raion","").strip()==c["raion"]):continue
            else:
                if level!="hromada" or row.get("hromada","").strip()!=c["hromada"]:continue
            s_raw=(row.get("started_at") or "").strip()
            e_raw=(row.get("finished_at") or "").strip()
            marker=(level,s_raw,e_raw) if c["kind"]=="raion_proxy" else (s_raw,e_raw)
            if not s_raw or not e_raw or marker in seen[city]:continue
            try:
                s=dt(s_raw);e=dt(e_raw)
                cutoff=dt(c["start"]) if c["kind"]=="exact_hromada" else dt(c["start"]+"T00:00:00",allow_naive=True)
            except ValueError:continue
            if e<=s:continue
            if c["kind"]=="exact_hromada" and s<cutoff:continue
            if c["kind"]=="raion_proxy":
                if e<=cutoff:continue
                s=max(s,cutoff)
            seen[city].add(marker)
            series[city].append({"_start":s,"_end":e,"source_row_numbers":[i],
                                 "source_geography":level+":"+(row.get("raion") or row.get("hromada") or row.get("oblast") or ""),
                                 "source_native_id":None})
    for city in series:
        if CONFIG[city]["kind"]=="raion_proxy":
            series[city]=union(series[city],city)
        else:
            series[city]=normalize(series[city],city)
    return series
def local_window(case,series):
    start=dt(case["original_alert_start_at"])
    end=dt(case["original_alert_end_at"])
    intersect=[x for x in series if dt(x["start_at"])<end and dt(x["end_at"])>start]
    if not intersect:
        return {"status":"BOUNDARY_UNVERIFIED","blocker":"Authoritative-series does not overlap accepted original; not proof of zero alerts",
                "A":None,"B":None,"inside":[],"source_overlapping_original":[]}
    lo=min(dt(x["start_at"]) for x in intersect)
    hi=max(dt(x["end_at"]) for x in intersect)
    before=[x for x in series if dt(x["end_at"])<=lo]
    after=[x for x in series if dt(x["start_at"])>=hi]
    A=max(before,key=lambda x:(x["end_at"],x["start_at"])) if before else None
    B=min(after,key=lambda x:(x["start_at"],x["end_at"])) if after else None
    if not A or not B:
        return {"status":"BOUNDARY_UNVERIFIED","blocker":"Missing adjacent completed event in authoritative series",
                "A":A,"B":B,"inside":intersect,"source_overlapping_original":intersect}
    Aend=dt(A["end_at"]); Bstart=dt(B["start_at"])
    inside=[x for x in series if dt(x["start_at"])>=Aend and dt(x["end_at"])<=Bstart
                               and x["legacy_episode_id"] not in (A["legacy_episode_id"],B["legacy_episode_id"])]
    crossing=[x for x in series if dt(x["start_at"])<Bstart and dt(x["end_at"])>Aend and x not in inside]
    if crossing:
        return {"status":"SOURCE_INCOMPLETE","blocker":"Source events cross A/B anchors or overlap them; boundary requires manual review",
                "A":A,"B":B,"inside":inside,"crossing":crossing,
                "source_overlapping_original":intersect}
    return {"status":"SOURCE_WINDOW_OBSERVED","A":A,"B":B,"inside":inside,
            "source_overlapping_original":intersect}
def main():
    reg=source_json(ORIGINAL_COMMIT,
       "research/c4_unbound_25_parent_adjudication_2026_10_27/registry.json")
    records=reg["decisions"]
    assert len(records)==25
    errors={}
    sources={}
    metadata={}
    try:
        b,m=fetch(MUNICIPAL)
        sources["kyiv"]=municipal_rows(b)
        metadata["kyiv"]={"url":MUNICIPAL,"source_name":"Kyiv municipal airAlert.json",
          "geography":"exact_city","download":m,"rows":len(sources["kyiv"])}
    except Exception as exc:errors["kyiv"]=type(exc).__name__+": "+str(exc)[:200]
    try:
        b,m=fetch(CSV_URL)
        git_hash=hashlib.sha1(("blob "+str(len(b))+"\0").encode()+b).hexdigest()
        if git_hash!=VADIMKIN_BLOB: raise ValueError("Vadimkin Git blob SHA mismatch: "+git_hash)
        tmp=vadimkin_rows(b)
        sources.update(tmp)
        for city,cfg in CONFIG.items():
            metadata[city]={"url":CSV_URL,"source_name":"Vadimkin official_data_uk.csv",
                "geography":cfg,"git_commit":VADIMKIN_COMMIT,"git_blob_sha":git_hash,
                "download":m,"rows":len(sources[city])}
    except Exception as exc:
        for city in CONFIG: errors[city]=type(exc).__name__+": "+str(exc)[:200]
    try:
        prod=source_json(SITE_COMMIT,"kyiv-air-alerts-grafana/data/alerts_combined.json")
    except Exception as exc:
        prod=[];errors["production_kyiv_json"]=type(exc).__name__+": "+str(exc)[:200]
    slices={}
    for city,(ref,name) in SLICES.items():
        try:
            obj=source_json(ref,SOURCE_SLICE_DIR+name)
            assert obj["city_key"]==city
            slices[city]={"commit":ref,"path":SOURCE_SLICE_DIR+name,
                "episode_count":len(obj["episodes"]),"episodes":obj["episodes"]}
        except Exception as exc:
            errors["slice_"+city]=type(exc).__name__+": "+str(exc)[:200]
    # Kharkiv 2025 episode is in an older source-slice; source data here is independently retrieved.
    output=[]
    for case in records:
        city=case["city"]
        source_window=local_window(case,sources[city]) if city in sources else {
            "status":"SOURCE_INCOMPLETE","blocker":errors.get(city,"Primary source unavailable"),
            "A":None,"B":None,"inside":[],"source_overlapping_original":[]}
        a,b=source_window["A"],source_window["B"]
        # Historical archived slices are corroborating derivative evidence, never themselves authoritative.
        hist=slices.get(city,{})
        old=next((x for x in hist.get("episodes",[]) if x.get("episode_id")==case["episode_id"]),None)
        old_index=hist["episodes"].index(old) if old else None
        predecessor=hist["episodes"][old_index-1] if old_index is not None and old_index>0 else None
        successor=hist["episodes"][old_index+1] if old_index is not None and old_index+1<len(hist["episodes"]) else None
        production=[]
        if city=="kyiv" and a and b:
            aend=dt(a["end_at"]); bstart=dt(b["start_at"])
            for i,row in enumerate(prod):
                try:
                    ps=dt(row["start"]);pe=dt(row["end"])
                except (KeyError, ValueError):continue
                if ps<bstart and pe>aend:
                    production.append({"index":i,"start_at":iso(ps),"end_at":iso(pe),
                        "legacy_episode_id":eid("kyiv",ps,pe),"source":row.get("source")})
        output.append({
            "ordinal":case["ordinal"],"city":city,"cohort":case["cohort"],
            "original":{"id":case["episode_id"],"start_at":iso(dt(case["original_alert_start_at"])),
                        "end_at":iso(dt(case["original_alert_end_at"])),
                        "classification_uid":case["classification_uid"]},
            "authoritative_source":metadata.get(city),
            "source_window":source_window,
            "historic_archived_slice":{"commit":hist.get("commit"),"path":hist.get("path"),
                "original_found":bool(old),"original_episode":old,
                "archived_neighbor_before":predecessor,"archived_neighbor_after":successor},
            "production_json":{"representation":"stored_list" if city=="kyiv" else "aggregate_only",
                               "site_prod_commit":SITE_COMMIT,
                               "stored_alerts_inside_source_gap":production if city=="kyiv" else None,
                               "note":"For other cities, dashboard_data.json holds aggregates; per-episode source snapshot must be reconstructed." if city!="kyiv" else None}
        })
    result={"schema_version":"c4-25-primary-source-window-v1",
        "rule":"Separate A/B for each original incident; no interval coalescing or automatic bindings",
        "source_snapshots":metadata,"errors":errors,"cases":output}
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    stats={}
    for x in output:stats[x["source_window"]["status"]]=stats.get(x["source_window"]["status"],0)+1
    print(json.dumps({"cases":len(output),"statuses":stats,"errors":errors,
        "sources":{k:v.get("rows") for k,v in metadata.items()}},ensure_ascii=False))
    assert len(output)==25
if __name__=="__main__":main()
