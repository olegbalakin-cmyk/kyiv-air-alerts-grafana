#!/usr/bin/env python3
import contextlib, hashlib, io, json, os, pathlib, subprocess, sys, tempfile, types
from datetime import datetime, timezone
from unittest.mock import patch
ROOT=pathlib.Path(__file__).resolve().parents[2]
SCRIPT=ROOT/"kyiv-air-alerts-grafana/scripts/monitor_casualty_candidates.py"
sys.path.insert(0,str(SCRIPT.parent))
BASE="1a8b57553ba66319db326d65080ade93ae6ca01c"
old=subprocess.check_output(["git","show",BASE+":kyiv-air-alerts-grafana/scripts/monitor_casualty_candidates.py"],cwd=ROOT).decode()
new=SCRIPT.read_text()
def module(text,name):
    m=types.ModuleType(name);m.__file__=str(SCRIPT);sys.modules[name]=m
    exec(compile(text,str(SCRIPT),"exec"),m.__dict__);return m
a=module(old,"casualty_old"),module(new,"casualty_new")
baseline,repaired=a
assert len(baseline.CITY_CONFIG)==len(repaired.CITY_CONFIG)==23
assert baseline.CITY_CONFIG==repaired.CITY_CONFIG
assert baseline.FOLLOWUP_HOURS==repaired.FOLLOWUP_HOURS
clock=datetime(2026,10,18,12,tzinfo=timezone.utc)
calls={"api_client":0,"api_history":0,"news":0,"other":0}
def forbidden(key):
    def f(*args,**kwargs):
        calls[key]+=1;raise AssertionError("Forbidden "+key)
    return f
class Response:
    content="""<rss><channel><item><title>У Києві загинула людина після атаки дрона</title><description>У Києві після атаки дрона загинула людина</description><link>https://example.org/kyiv</link><pubDate>Sun, 18 Oct 2026 11:10:00 GMT</pubDate></item></channel></rss>""".encode("utf-8")
    def raise_for_status(self):pass
def fake_news(url,**kwargs):
    assert url.startswith("https://news.google.com/rss/search")
    calls["news"]+=1;return Response()
def dump(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
def init(m,d,kind):
    d=pathlib.Path(d);data=d/"data";c=data/"casualties";c.mkdir(parents=True)
    m.BRIDGE_FILE=data/"ukrainealarm_bridge.json";m.KYIV_EVENTS_FILE=data/"alerts_combined.json"
    m.SEVASTOPOL_EVENTS_FILE=data/"sevastopol_events.json"
    m.STATE_FILE=c/"candidate_monitor_state.json";m.QUEUE_FILE=c/"multicity_review_queue.json"
    m.LAST_RUN_FILE=c/"candidate_monitor_last_run.json"
    interval={"start":"2026-10-17T08:00:00Z","end":"2026-10-17T09:00:00Z"}
    events=[dict(interval,city_key=v["alert_key"]) for k,v in m.CITY_CONFIG.items() if k not in ("kyiv","sevastopol")]
    if kind=="malformed_bridge":m.BRIDGE_FILE.write_text("{bad")
    elif kind!="missing_bridge":dump(m.BRIDGE_FILE,{"events":events[:1] if kind=="incomplete_history" else [] if kind=="missing_regions" else events})
    if kind!="missing_kyiv":dump(m.KYIV_EVENTS_FILE,[interval])
    if kind=="invalid_sevastopol":m.SEVASTOPOL_EVENTS_FILE.write_text("{bad")
    else:dump(m.SEVASTOPOL_EVENTS_FILE,{"pairs":[interval]})
    dump(m.STATE_FILE,{"schema_version":1,"created_at":"2026-10-15T00:00:00Z","cities":{
        k:{"city":v["label"],"alert_scope":v["scope"],"last_seen_alert_end":"2026-10-16T09:00:00Z","episodes":[]}
        for k,v in m.CITY_CONFIG.items()}})
    dump(m.QUEUE_FILE,[{"candidate_id":"human","city_key":"kyiv","status":"rejected",
        "source":"Google News RSS","title":"Human-reviewed","first_discovered_at":"2026-10-15T00:00:00Z"}])
def snapshot(m):
    return {name:(p.read_bytes() if p.exists() else None) for name,p in {
        "state":m.STATE_FILE,"queue":m.QUEUE_FILE,"report":m.LAST_RUN_FILE,"bridge":m.BRIDGE_FILE,
        "kyiv":m.KYIV_EVENTS_FILE,"sevastopol":m.SEVASTOPOL_EVENTS_FILE}.items()}
def run(m,d,kind,token):
    init(m,d,kind);outs=[]
    for _ in range(2):
        with patch.object(m,"now_utc",lambda:clock),\
             patch.object(m.requests,"get",fake_news),\
             patch.object(m.ua,"UkraineAlarmClient",forbidden("api_client")),\
             patch.object(m.ua,"history_rows",forbidden("api_history")),\
             patch.object(m.kyivdata,"http_session",forbidden("other")),\
             patch.object(m.sev,"update_event_store",forbidden("other")),\
             patch.dict(os.environ,{"UKRAINEALARM_API_TOKEN":"SYNTHETIC"} if token else {},clear=True),\
             patch.object(sys,"argv",["monitor","--local-only"]),\
             contextlib.redirect_stdout(io.StringIO()):
            m.main()
        snap=snapshot(m)
        assert json.loads(snap["report"])["mode"]=="local_only"
        assert json.loads(snap["report"])["city_count"]==23
        assert any(x["candidate_id"]=="human" and x["status"]=="rejected" for x in json.loads(snap["queue"]))
        outs.append(snap)
    return outs
cases=[]
for kind in ["valid","missing_bridge","malformed_bridge","missing_regions","missing_kyiv","invalid_sevastopol","incomplete_history"]:
    for token in [False,True]:
        with tempfile.TemporaryDirectory() as da,tempfile.TemporaryDirectory() as db:
            x,y=run(baseline,da,kind,token),run(repaired,db,kind,token)
            assert x==y,(kind,token,"A/B mismatch")
            counts=[json.loads(s["report"])["new_alert_episodes"] for s in x]
            cases.append({"scenario":kind,"token":token,"cycles":2,"new_episodes":counts,
                "state_sha256":hashlib.sha256(x[-1]["state"]).hexdigest(),
                "queue_sha256":hashlib.sha256(x[-1]["queue"]).hexdigest(),"differences":0})
assert any(c["new_episodes"][0]>0 and c["new_episodes"][1]==0 for c in cases)
assert calls["api_client"]==calls["api_history"]==calls["other"]==0
assert calls["news"]>0
with tempfile.TemporaryDirectory() as d:
    init(repaired,d,"valid");before=snapshot(repaired)
    with patch.object(sys,"argv",["monitor"]),patch.object(repaired,"ensure_state",forbidden("other")),\
         contextlib.redirect_stderr(io.StringIO()):
        try:repaired.main()
        except SystemExit as e:assert e.code==2
        else:raise AssertionError("missing switch accepted")
    assert before==snapshot(repaired)
    for f in [lambda:repaired.poll_all(False),repaired.poll_ukrainealarm]:
        try:f()
        except RuntimeError:pass
        else:raise AssertionError("legacy network call accepted")
with patch.dict(os.environ,{"UKRAINEALARM_API_TOKEN":"SYNTHETIC"},clear=True),\
     patch.object(baseline.ua,"UkraineAlarmClient",forbidden("api_client")):
    try:baseline.poll_ukrainealarm()
    except AssertionError:pass
    else:raise AssertionError("baseline vulnerability not detected")
assert calls["api_client"]==1 and calls["api_history"]==calls["other"]==0
result={"status":"PASS_OFFLINE_SYNTHETIC","baseline":BASE,"reference_clock":clock.isoformat(),
    "original_blob_sha256":hashlib.sha256(old.encode()).hexdigest(),
    "candidate_blob_sha256":hashlib.sha256(new.encode()).hexdigest(),
    "scenario_count":len(cases),"ab_cycle_pairs":len(cases)*2,"ab_differences":0,
    "real_api_requests":0,"original_synthetic_client_attempts":1,
    "repaired_synthetic_client_attempts":0,"mock_google_news_requests":calls["news"],
    "cases":cases,"scope":"Synthetic offline fixtures only; degraded-input semantics preserved, not repaired"}
print(json.dumps(result,ensure_ascii=False,indent=2))
