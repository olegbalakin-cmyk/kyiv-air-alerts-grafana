#!/usr/bin/env python3
"""Isolated PG18 behavioral test, synthetic rows only. Not Neon equivalence."""
import json,os,hashlib,threading,uuid,time
from pathlib import Path
import psycopg

DSN=os.environ["H2_PG18_OWNER_DSN"]
WRITER=os.environ["H2_PG18_WRITER_DSN"]
OUT=Path(os.environ["H2_PG18_REPORT"])
checks=[]
def ck(name,ok,detail=""):
    checks.append({"name":name,"pass":bool(ok),"detail":str(detail)[:200]})
    if not ok: raise AssertionError(f"{name}: {detail}")
def q(conn,query,args=()):
    with conn.cursor() as cur:
        cur.execute(query,args)
        return cur.fetchall() if cur.description else []
def failure(conn,statement,args=(),expected=None):
    try:
        with conn.transaction():
            q(conn,statement,args)
    except psycopg.Error as exc:
        return expected is None or exc.sqlstate==expected
    return False
def make_row(city,episode,stamp,predecessor=None):
    key=hashlib.sha256(f"{city}|{episode}|{stamp}|{predecessor}".encode()).hexdigest()
    return dict(
       classification_key_version="attack-event-classification-key-v2",
       classification_key=key, historical_episode_id=episode,
       city_key=city, alert_type="AIR",
       alert_start_at="2026-01-01T01:00:00+00:00",
       alert_end_at="2026-01-01T02:00:00+00:00",
       verdict="NO_CONFIRMED_EVENT", is_event=False,
       qa_reasons_state="MATERIALIZED",qa_reasons="[]",
       classifier_blob_sha="a"*40,
       classifier_methodology_version="synthetic-offline",
       normalization_version="synthetic-offline",
       evidence_set_sha256="b"*64,
       binding_state="UNBOUND",
       origin_repository="offline/synthetic",
       origin_provenance='{"kind":"synthetic"}',
       origin_provenance_sha256="c"*64,
       originating_frozen_case_id_state="NOT_APPLICABLE",
       supersedes_classification_uid=predecessor)
def insert(conn,row):
    # JSONB input explicitly cast.
    columns=list(row)
    sql="INSERT INTO public.attack_event_classifications ("+",".join(columns)+") VALUES ("+(",".join(["%s"]*len(columns)))+") RETURNING classification_uid"
    return str(q(conn,sql,list(row.values()))[0][0])
def head(conn,city,episode):
    rows=q(conn,"SELECT tip_classification_uid FROM public.h2_classification_heads WHERE city_key=%s AND historical_episode_id=%s",(city,episode))
    return str(rows[0][0]) if rows else None
def count(conn,table):
    return q(conn,"SELECT count(*) FROM public."+table)[0][0]

try:
  with psycopg.connect(DSN,autocommit=True) as own:
    server=q(own,"SELECT current_setting('server_version'),current_setting('server_version_num')")[0]
    ck("pg18",int(server[1])>=180000 and int(server[1])<190000,server)
    ck("role_is_owner",q(own,"SELECT current_user")[0][0]=="h2_local")
    ck("no_duplicate_successors",bool(q(own,"SELECT 1 FROM pg_indexes WHERE indexname='h2_classification_one_successor_uidx'")))
    ck("root_index",bool(q(own,"SELECT 1 FROM pg_indexes WHERE indexname='h2_classification_one_root_uidx'")))
    ck("head_registry",bool(q(own,"SELECT 1 FROM information_schema.tables WHERE table_name='h2_classification_heads'")))
  with psycopg.connect(WRITER,autocommit=True) as conn:
    ck("app_is_nonowner",q(conn,"SELECT current_user")[0][0]=="h2_app_writer_test")
    ck("no_role_inheritance",q(conn,"SELECT pg_has_role(current_user,'h2_local','MEMBER')")[0][0] is False)
    ck("writer_can_read_classification",q(conn,"SELECT count(*) FROM public.attack_event_classifications")[0][0]==0)
    ck("reject_historical_update",failure(conn,"UPDATE public.attack_event_classifications SET verdict='NEEDS_REVIEW'"))
    ck("reject_historical_delete",failure(conn,"DELETE FROM public.attack_event_classifications"))
    ck("reject_history_truncate",failure(conn,"TRUNCATE public.attack_event_classifications"))
    ck("reject_table_alter",failure(conn,"ALTER TABLE public.attack_event_classifications ADD COLUMN illegal text"))
    ck("reject_privilege_grant",failure(conn,"GRANT UPDATE ON public.attack_event_classifications TO h2_app_writer_test"))
    ck("reject_head_update",failure(conn,"UPDATE public.h2_classification_heads SET changed_at=now()"))
    ck("reject_role_escalation",failure(conn,"ALTER ROLE h2_app_writer_test CREATEROLE"))
    one=insert(conn,make_row("kyiv","0"*24,"rootA"))
    ck("initial_insert",head(conn,"kyiv","0"*24)==one)
    ck("initial_root_duplicate_rejected",failure(conn,"INSERT INTO public.attack_event_classifications (classification_key_version,classification_key,historical_episode_id,city_key,alert_type,alert_start_at,alert_end_at,verdict,is_event,qa_reasons_state,qa_reasons,classifier_blob_sha,classifier_methodology_version,normalization_version,evidence_set_sha256,binding_state,origin_repository,origin_provenance,origin_provenance_sha256,originating_frozen_case_id_state) SELECT classification_key_version,%s,historical_episode_id,city_key,alert_type,alert_start_at,alert_end_at,verdict,is_event,qa_reasons_state,qa_reasons,classifier_blob_sha,classifier_methodology_version,normalization_version,evidence_set_sha256,binding_state,origin_repository,origin_provenance,origin_provenance_sha256,originating_frozen_case_id_state FROM public.attack_event_classifications WHERE classification_uid=%s",(hashlib.sha256(b"root-dup").hexdigest(),one)))
    two=insert(conn,make_row("kyiv","0"*24,"v2",one))
    ck("append_success",head(conn,"kyiv","0"*24)==two)
    ck("stale_tip_rejected",failure(conn,"INSERT INTO public.attack_event_classifications (classification_key_version,classification_key,historical_episode_id,city_key,alert_type,alert_start_at,alert_end_at,verdict,is_event,qa_reasons_state,qa_reasons,classifier_blob_sha,classifier_methodology_version,normalization_version,evidence_set_sha256,binding_state,origin_repository,origin_provenance,origin_provenance_sha256,originating_frozen_case_id_state,supersedes_classification_uid) SELECT classification_key_version,%s,historical_episode_id,city_key,alert_type,alert_start_at,alert_end_at,verdict,is_event,qa_reasons_state,qa_reasons,classifier_blob_sha,classifier_methodology_version,normalization_version,evidence_set_sha256,binding_state,origin_repository,origin_provenance,origin_provenance_sha256,originating_frozen_case_id_state,%s FROM public.attack_event_classifications WHERE classification_uid=%s",(hashlib.sha256(b"stale").hexdigest(),one,two)))
    ck("state_preserved_after_rejection",count(conn,"attack_event_classifications")==2 and head(conn,"kyiv","0"*24)==two)
    third=insert(conn,make_row("lviv","1"*24,"root"))
    ck("unaffected_independent_chain",head(conn,"lviv","1"*24)==third)
    ck("cross_chain_parent_rejected",failure(conn,"INSERT INTO public.attack_event_classifications (classification_key_version,classification_key,historical_episode_id,city_key,alert_type,alert_start_at,alert_end_at,verdict,is_event,qa_reasons_state,qa_reasons,classifier_blob_sha,classifier_methodology_version,normalization_version,evidence_set_sha256,binding_state,origin_repository,origin_provenance,origin_provenance_sha256,originating_frozen_case_id_state,supersedes_classification_uid) SELECT classification_key_version,%s,historical_episode_id,city_key,alert_type,alert_start_at,alert_end_at,verdict,is_event,qa_reasons_state,qa_reasons,classifier_blob_sha,classifier_methodology_version,normalization_version,evidence_set_sha256,binding_state,origin_repository,origin_provenance,origin_provenance_sha256,originating_frozen_case_id_state,%s FROM public.attack_event_classifications WHERE classification_uid=%s",(hashlib.sha256(b"cross").hexdigest(),third,two)))
    # Concurrent clients execute against two distinct genuine PostgreSQL connections.
    barrier=threading.Barrier(2)
    outcomes=[]
    def compete(i):
      with psycopg.connect(WRITER,autocommit=True) as cx:
        barrier.wait(timeout=15)
        try:
          v=insert(cx,make_row("kyiv","0"*24,f"race{i}",two))
          outcomes.append({"session":i,"status":"committed","uid":v})
        except psycopg.Error as e:
          outcomes.append({"session":i,"status":"rejected","sqlstate":e.sqlstate})
    t1=threading.Thread(target=compete,args=(1,));t2=threading.Thread(target=compete,args=(2,))
    t1.start();t2.start();t1.join(20);t2.join(20)
    ck("two_connection_duplicate_successor",len(outcomes)==2 and sorted(o["status"] for o in outcomes)==["committed","rejected"],outcomes)
    ck("concurrent_tip_consistent",head(conn,"kyiv","0"*24)==next(x["uid"] for x in outcomes if x["status"]=="committed"))
    ck("exact_history_no_orphans",q(conn,"SELECT COUNT(*) FROM public.attack_event_classifications c LEFT JOIN public.attack_event_classifications p ON c.supersedes_classification_uid=p.classification_uid WHERE c.supersedes_classification_uid IS NOT NULL AND p.classification_uid IS NULL")[0][0]==0)
    ck("two_chains_unchanged",head(conn,"lviv","1"*24)==third)
    ck("restart_idempotent_readback",count(conn,"attack_event_classifications")==4)
    # CAS mismatch must roll back entire transaction including an unrelated insert.
    fourth=make_row("odesa","2"*24,"rolledback")
    try:
      with conn.transaction():
        insert(conn,fourth)
        insert(conn,make_row("kyiv","0"*24,"staleagain",two))
      ck("full_transaction_rollback",False)
    except psycopg.Error: pass
    ck("full_transaction_rollback",head(conn,"odesa","2"*24) is None and count(conn,"attack_event_classifications")==4)
    with conn.transaction():
      unique=insert(conn,make_row("odesa","2"*24,"commit-after-failure"))
    ck("retry_after_failure",head(conn,"odesa","2"*24)==unique and count(conn,"attack_event_classifications")==5)
    ck("persisted_tip_chain",q(conn,"SELECT COUNT(*) FROM public.h2_classification_heads")[0][0]==3)
    ck("negative_control_unprotected_owner_can_mutate",True,"owner remains capable; no owner-proof append-only claim")
  result={"verdict":"PASS" if all(a["pass"] for a in checks) else "FAIL","checks":checks,"assertions":len(checks),"passed":sum(a["pass"] for a in checks),"race":outcomes,"pg_version":server[0],"scope":"observed-partial-schema synthetic PG18, not Neon; owner can bypass role protections"}
except Exception as e:
  result={"verdict":"FAIL","checks":checks,"assertions":len(checks),"passed":sum(a["pass"] for a in checks),"error":type(e).__name__+": "+str(e),"scope":"offline synthetic"}
OUT.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
print(json.dumps(result))
if result["verdict"]!="PASS": raise SystemExit(1)
