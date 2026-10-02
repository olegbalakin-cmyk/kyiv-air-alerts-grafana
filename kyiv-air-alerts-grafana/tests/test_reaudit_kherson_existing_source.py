import importlib.util
from datetime import timedelta
from urllib.parse import urlparse
from pathlib import Path
import pytest

P=Path(__file__).resolve().parents[1]/"scripts/reaudit_kherson_existing_source.py"
S=importlib.util.spec_from_file_location("reaudit",P); m=importlib.util.module_from_spec(S); S.loader.exec_module(m)

def post(mid,when):
    return {"channel":m.CHANNEL,"message_id":mid,"source_url":f"https://t.me/{m.CHANNEL}/{mid}","published_at_utc":m.iso(when),"published_at_europe_kyiv":when.astimezone(m.KYIV).isoformat(),"text":"У Херсоні вибухи через атаку КАБ","content_hash":str(mid),"retrieval_page":1}

def fake(pages):
    calls=[]
    def fetch(cursor):
        i=len(calls); calls.append(cursor)
        return {"request_url":m.url(cursor),"http_status":200,"attempt_count":1,"html":str(i)}
    def parse(html,idx): return pages[int(html)],[]
    return fetch,parse,calls

def test_backward_pagination_monotonic():
    pages=[[post(120,m.END+timedelta(days=1)),post(100,m.END+timedelta(hours=1))],[post(99,m.START+timedelta(hours=1)),post(80,m.START-timedelta(hours=1))]]
    f,p,c=fake(pages); _,led,meta=m.traverse(f,p,max_pages=3)
    assert c==[None,100] and led[1]["next_cursor"]==80 and meta["public_history_coverage"]=="COMPLETE"

def test_dedup_identity():
    pages=[[post(120,m.END+timedelta(days=1)),post(100,m.END)],[post(100,m.END),post(80,m.START-timedelta(hours=1))]]
    f,p,_=fake(pages); snap,_,_=m.traverse(f,p,max_pages=3)
    assert len([x for x in snap if x["message_id"]==100])==1

def test_pagination_loop_blocks():
    pages=[[post(120,m.END+timedelta(days=1)),post(100,m.END)],[post(120,m.START+timedelta(hours=1)),post(100,m.START-timedelta(hours=1))]]
    f,p,_=fake(pages); _,_,meta=m.traverse(f,p,max_pages=3)
    assert meta["pagination_loops"]>0 and meta["public_history_coverage"]!="COMPLETE"

def test_empty_before_lower_blocks():
    pages=[[post(120,m.END+timedelta(days=1)),post(100,m.END)],[]]
    f,p,_=fake(pages); _,_,meta=m.traverse(f,p,max_pages=3)
    assert meta["unrecovered_request_failures"]==1 and meta["public_history_coverage"]=="BLOCKED"

def test_max_pages_blocks():
    pages=[[post(120,m.END+timedelta(days=1)),post(100,m.END)]]
    f,p,_=fake(pages); _,_,meta=m.traverse(f,p,max_pages=1)
    assert meta["max_pages_exhausted"] and meta["public_history_coverage"]=="BLOCKED_MAX_PAGES"

def test_unrecovered_failure_never_negative():
    def fetch(cursor): return {"request_url":m.url(cursor),"http_status":503,"attempt_count":5,"error":"503"}
    _,_,meta=m.traverse(fetch,lambda h,i:([],[]),max_pages=2)
    assert meta["public_history_coverage"]=="BLOCKED"

def test_publication_not_event_time():
    r=m.row(post(1,m.START))
    assert "event_time" not in r and r["published_at"]==m.iso(m.START)

def make_eps(n=1412):
    out=[]
    for i in range(n):
        s=m.START+timedelta(minutes=60*i); e=s+timedelta(minutes=30)
        out.append({"episode_id":f"e{i:04d}","alert_start":m.iso(s),"alert_end":m.iso(e),"alert_start_date_kyiv":s.astimezone(m.KYIV).date().isoformat()})
    return out

def test_denominator_rejects_wrong_count():
    with pytest.raises(ValueError):m.validate({"episodes":make_eps(10)})

def test_ledger_exact_1412():
    eps=make_eps(); c={"strict_ids":set(),"sensitivity_ids":set(),"review_ids":set(),"direct_strict":{},"direct_sens":{},"direct_review":{},"compositions":{},"composition_messages":{},"episode_messages":{}}
    assert len(m.ledger(eps,c,"COMPLETE",[]))==1412

def test_multiple_strict_observations_count_once():
    eps=make_eps(); eid=eps[0]["episode_id"]; o={"channel":m.CHANNEL,"message_id":1,"reason_codes":[]}; o2={"channel":m.CHANNEL,"message_id":2,"reason_codes":[]}
    c={"strict_ids":{eid},"sensitivity_ids":set(),"review_ids":set(),"direct_strict":{eid:[o,o2]},"direct_sens":{},"direct_review":{},"compositions":{},"composition_messages":{},"episode_messages":{eid:{1,2}}}
    rows=m.ledger(eps,c,"COMPLETE",[])
    assert sum(r["reaudit_outcome"]=="STRICT_EVENT_POSITIVE" for r in rows)==1 and rows[0]["strict_observation_count"]==2

def test_allowlist():
    assert urlparse(m.url()).hostname=="t.me"
    old=m.CHANNEL
    try:
        m.CHANNEL="other"
        with pytest.raises(ValueError):m.url()
    finally:m.CHANNEL=old

def test_blocked_marks_all_blocked():
    eps=make_eps(); c={"strict_ids":set(),"sensitivity_ids":set(),"review_ids":set(),"direct_strict":{},"direct_sens":{},"direct_review":{},"compositions":{},"composition_messages":{},"episode_messages":{}}
    assert all(r["reaudit_outcome"]=="SOURCE_COVERAGE_BLOCKED" for r in m.ledger(eps,c,"BLOCKED",[]))

def test_frozen_blobs_exact():
    assert m.BLOBS[str(m.SLICE)]=="32c0f8085161985a258d927f4a4968d4b192a708"
    assert m.BLOBS[str(m.FINAL)]=="ae816bbc412fbe62f086adb4cefb2a5af65b2a07"
    assert m.BLOBS[str(m.CLASSIFIER)]=="927dc89df0b52edd52cb31a126b0d57ca492a278"
    assert m.BLOBS[str(m.ADAPTER)]=="0ceb3ea480de9b401000ba9d8b0bb02b22d83c89"


def test_retry_recovers_transient(monkeypatch):
    class E(Exception): response=None
    class Req: RequestException=E
    class NB:
        def __init__(self,**kw): pass
    class HTTP:
        def __init__(self): self.n=0
        def get(self,u,timeout_seconds=None):
            self.n+=1
            if self.n==1: raise E("reset")
            return type("R",(),{"url":u,"status_code":200,"text":"ok"})()
    class PTA:
        def __init__(self,b): self.http=HTTP()
    src=type("S",(),{"NetworkBounds":NB,"PublicTelegramAdapter":PTA,"requests":Req})
    monkeypatch.setattr(m.time,"sleep",lambda _:None)
    r=m.live_fetch(src)(None)
    assert r.get("error") is None and r["attempt_count"]==2

class FakeClassifier:
    def __init__(self): self.city=[]
    def candidate_id(self,city,u,t): return "c"
    def match_candidate_to_episodes(self,r,eps): return {"outcome":"unique_match","matched_episode_ids":[eps[0]["episode_id"]],"matched_episode_id":eps[0]["episode_id"],"logical_episode_groups":[]}
    def classify_candidate(self,r,city,eps,matching):
        self.city.append(city)
        return {"proposed_outcome":"needs_review","proposed_matched_episode_id":None,"event_types":["explosion"],"exact_city_classification_evidence":{"present":True},"strict_explosion_evidence":{"present":True},"air_military_context":{"present":False},"same_attack_context":{"present":False},"temporal_binding":{"present":False},"reason_codes":["X"]}
    def apply_matching_result(self,item,matching): item["matched_episode_id"]=matching["matched_episode_id"]
    def compose_episode_candidates(self,*a,**k): return {"final_composed_verdict":"no_composed_strict"}
class FakeSource:
    @staticmethod
    def canonical_observation_id(ch,mid): return f"o{mid}"

def test_classifier_city_key_kherson():
    eps=[{"episode_id":"e","alert_start":m.iso(m.START),"alert_end":m.iso(m.START+timedelta(hours=1)),"alert_start_date_kyiv":"2025-08-30"}]
    fc=FakeClassifier(); m.classify([post(1,m.START+timedelta(minutes=5))],eps,fc,FakeSource)
    assert fc.city==["kherson"]

def test_seven_retired_not_auto_restored():
    rec=[]
    for i in range(7):
        rec.append({"current_metric_role":"REVIEW_NON_COUNTED_RETIRED_LEGACY_POSITIVE","normalization_provenance":{"best_supported_event_time":{"utc":m.iso(m.START+timedelta(days=i))}}})
    eps=[{"episode_id":"e","alert_start":m.iso(m.START),"alert_end":m.iso(m.START+timedelta(minutes=1))}]
    r=m.retired({"review_events":rec},[],{"strict_ids":set()},eps)
    assert r=={"total":7,"source_context_retrieved":0,"currently_strict":0,"remain_non_counted":7}

def test_case73_oracle_reads_normal_pipeline_output_only():
    c={"by_episode":{},"strict_ids":set(),"sensitivity_ids":set(),"review_ids":set()}
    r=m.case73(c)
    assert r["source_retrieved"] is False and r["classification"]=="NONE" and r["recovered_strict"] is False

def test_protected_paths_include_all_required_live_outputs():
    names={str(x) for x in m.PROTECTED}
    for suffix in ["data/explosion_candidate_monitor_state.json","data/explosion_candidate_monitor_last_run.json","data/explosion_review_queue.json","data/explosions_test.json","data/dashboard_data.json"]:
        assert any(x.endswith(suffix) for x in names)
