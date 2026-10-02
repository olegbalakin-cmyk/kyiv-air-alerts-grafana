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
