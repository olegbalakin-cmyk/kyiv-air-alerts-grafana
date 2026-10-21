#!/usr/bin/env python3
"""Offline end-to-end demonstration of durable monitor acknowledgements.
Requires no external network and never mutates operational WIP, Neon, or production.
SYNTHETIC news/evidence may NEVER enter canonical/production data.
"""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import tempfile

ROOT=Path(__file__).resolve().parent
FIXTURE=ROOT/"input_fixture.json"

def serialize(v):
    return (json.dumps(v,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")

def atomic_json(path,obj,fail_before_replace=False):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,temp=tempfile.mkstemp(prefix="."+path.name+".",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(serialize(obj))
            f.flush()
            os.fsync(f.fileno())
        if fail_before_replace:
            raise RuntimeError("INJECTED_BEFORE_ATOMIC_REPLACE")
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)

def read(path,default):
    p=Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default

def validate_fixture(f):
    assert f["schema_version"]==1
    assert f["source_git_blob"]=="43f5dd38ad01d22cfce4810ac7f97025a8d85675"
    assert f["source_run_id"]==38575039007
    assert f["original_monitor_report_ok"] is False
    assert f["original_monitor_report_canonical_persisted"]==0
    assert f["episode"]["episode_id"]=="176a083e264eec607cdb1ea6"
    assert f["episode"]["alert_start"]=="2026-10-07T18:29:00Z"
    assert f["episode"]["alert_end"]=="2026-10-07T19:36:00Z"
    assert len(f["candidate_fixtures"])==2
    assert all(x.get("synthetic") is True and x["source_kind"]=="SYNTHETIC_TEST_ONLY" and x["url"].startswith("synthetic://") for x in f["candidate_fixtures"])

def classify(episode,candidate):
    """Explicit event time strictly inside episode + explicit during-alert wording; no publication-time substitution."""
    same_city=candidate["city"]==episode["city"]
    direct_time=candidate.get("explicit_event_time")
    within=bool(direct_time and episode["alert_start"]<=direct_time<=episode["alert_end"])
    strict=bool(same_city and candidate["aerial_context"] and candidate["explicit_during_alert"] and within)
    return {
      "candidate_id":candidate["candidate_id"],
      "status":"synthetic_strict_example" if strict else "needs_review",
      "reason":"explicit_event_time_inside_episode" if strict else "no_verified_event_time",
      "synthetic":True,
      "source_url":candidate["url"],
      "publication_time":candidate["publication_time"]
    }

def process_once(folder,*,fail_before_commit=False,missing_source=False):
    """Pure local source -> classify -> durable file -> durable ACK, written in *one* atomic envelope."""
    folder=Path(folder)
    f=read(FIXTURE,{})
    validate_fixture(f)
    statepath=folder/"synthetic_monitor_state.json"
    state=read(statepath,{"schema_version":1,"processed_episode_ids":[],"classifications":[],"attempts":0})
    assert state["schema_version"]==1
    episode=f["episode"]
    key=episode["episode_id"]
    if key in state["processed_episode_ids"]:
        return {"status":"already_acknowledged","new_records":0,"source_complete":True,"state":state}
    if missing_source:
        return {"status":"retryable_source_error","new_records":0,"source_complete":False,"state":state}
    records=[classify(episode,c) for c in f["candidate_fixtures"]]
    assert len({x["candidate_id"] for x in records})==len(records)
    next_state={
      "schema_version":1,
      "processed_episode_ids":sorted(set(state["processed_episode_ids"]+[key])),
      "classifications":state["classifications"]+[{"episode_id":key,"city":episode["city"],"source":"FROZEN_REAL_ALERT_EPISODE","synthetic_evidence":True,"records":records}],
      "attempts":state["attempts"]+1,
    }
    atomic_json(statepath,next_state,fail_before_replace=fail_before_commit)
    return {"status":"committed_and_acknowledged","new_records":len(records),"source_complete":True,"state":next_state}

def make_report(folder,out):
    f=read(FIXTURE,{})
    state=read(Path(folder)/"synthetic_monitor_state.json",{})
    total=sum(len(x["records"]) for x in state.get("classifications",[]))
    rows=[x for e in state.get("classifications",[]) for x in e["records"]]
    summary={"proof_scope":"OFFLINE SYNTHETIC CANDIDATES ON ONE FROZEN REAL ALERT EPISODE","real_confirmed_attack_count":None,"source_run_id":f["source_run_id"],"source_git_blob":f["source_git_blob"],"episodes_acknowledged":len(state.get("processed_episode_ids",[])),"classified_synthetic_candidates":total,"synthetic_strict_examples":sum(x["status"]=="synthetic_strict_example" for x in rows),"needs_review":sum(x["status"]=="needs_review" for x in rows),"non_authoritative":True,"safe_for_production":False}
    Path(out).mkdir(parents=True,exist_ok=True)
    atomic_json(Path(out)/"report.json",summary)
    detail=json.dumps(summary,ensure_ascii=False,indent=2)
    table="".join("<tr><td>"+html.escape(x["candidate_id"])+"</td><td>"+html.escape(x["status"])+"</td><td>"+html.escape(x["reason"])+"</td></tr>" for x in rows)
    page=("<!doctype html><html lang='uk'><meta charset='utf-8'><title>Offline evidence demo</title><body><h1>Лише синтетичний proof — не реальні події</h1><p>Епізод тривоги справжній (заморожений), новини синтетичні.</p><pre>"+html.escape(detail)+"</pre><table border='1'><tr><th>Кандидат</th><th>Тестовий результат</th><th>Причина</th></tr>"+table+"</table></body></html>")
    (Path(out)/"report.html").write_text(page,encoding="utf-8")
    return summary

def test():
    f=read(FIXTURE,{})
    validate_fixture(f)
    with tempfile.TemporaryDirectory(prefix="r6_event_cycle_") as tmp:
        p=Path(tmp)
        missing=process_once(p,missing_source=True)
        assert missing["status"]=="retryable_source_error"
        assert not (p/"synthetic_monitor_state.json").exists()
        try:
            process_once(p,fail_before_commit=True)
            raise AssertionError("injected failure allowed commit")
        except RuntimeError as e:
            assert "INJECTED_BEFORE_ATOMIC_REPLACE" in str(e)
        assert not (p/"synthetic_monitor_state.json").exists()
        first=process_once(p)
        assert first["status"]=="committed_and_acknowledged" and first["new_records"]==2
        assert first["state"]["classifications"][0]["records"][0]["status"]=="needs_review"
        assert first["state"]["classifications"][0]["records"][1]["status"]=="synthetic_strict_example"
        content_before=(p/"synthetic_monitor_state.json").read_bytes()
        second=process_once(p)
        third=process_once(p)
        assert second["new_records"]==third["new_records"]==0
        assert (p/"synthetic_monitor_state.json").read_bytes()==content_before
        summary=make_report(p,p/"view")
        assert summary["episodes_acknowledged"]==1
        assert summary["classified_synthetic_candidates"]==2
        assert summary["needs_review"]==1 and summary["synthetic_strict_examples"]==1
        assert summary["real_confirmed_attack_count"] is None
        assert summary["non_authoritative"] is True and summary["safe_for_production"] is False
        print("FROZEN_REAL_ALERT_EPISODE=1/1")
        print("SYNTHETIC_EVIDENCE_CLASSIFICATIONS=2/2")
        print("MISSING_SOURCE_RETRY=PASS")
        print("INJECTED_PRECOMMIT_FAILURE_NO_ACK=PASS")
        print("ATOMIC_STATE_AND_ACK=PASS")
        print("THREE_RUNS_NO_DUPLICATES=PASS")
        print("NO_PUBLICATION_TIME_AS_EVENT_TIME=PASS")
        print("OFFLINE_REPORT_HTML_JSON=PASS")
        print("NO_REAL_CONFIRMED_ATTACK_CLAIM=PASS")
        print("LIVE_MONITOR_OR_NEON_ACTIVATED=NO")
        print("RESULT=PASS BOUNDED OFFLINE ONLY")
        return tmp

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--test",action="store_true")
    p.add_argument("--output",default="out/offline_live_event_demo")
    args=p.parse_args()
    if args.test:
        test()
    else:
        with tempfile.TemporaryDirectory(prefix="r6_demo_") as tmp:
            first=process_once(tmp)
            second=process_once(tmp)
            third=process_once(tmp)
            summary=make_report(tmp,args.output)
            print(json.dumps({"runs":[first["status"],second["status"],third["status"]],"report":summary},ensure_ascii=False,indent=2))

if __name__=="__main__":
    main()
