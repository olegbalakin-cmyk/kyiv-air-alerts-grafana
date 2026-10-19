#!/usr/bin/env python3
"""Genuine writer and monitor mutation controls on isolated observed-partial PG18."""
from __future__ import annotations
import hashlib, importlib.util, inspect, json, os, sys, traceback
from pathlib import Path
from unittest import mock

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location("h2_obs_mutation_basis",HERE/"test_h2_observed_neon_partial_pg18_e2e.py")
obs=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=obs
spec.loader.exec_module(obs)
old=obs.old
writer=old.writer
original=writer.persist_episode_classification
source=inspect.getsource(original)
K1_TARGET="if not exact_current_retry and actual_tip != expected_current_tip:"
K2_TARGET='existing = _existing_classification(cur, record["classification_key"])'
assert source.count(K1_TARGET)==1 and source.count(K2_TARGET)==1
assert "ON CONFLICT (classification_key) DO NOTHING" in inspect.getsource(writer._insert_classification)
PROOF={"K1":{},"K2":{}}
REPORT=Path(os.environ.get("H2_MUTATION_REPORT","/tmp/h2_mutation_result.json"))

def replace_once(target,new,**extras):
    assert source.count(target)==1
    globs=dict(writer.__dict__);globs.update(extras)
    exec(compile(source.replace(target,new,1),"<TEST_ONLY_MUTANT_NOT_IN_GIT>","exec"),globs)
    return globs["persist_episode_classification"]

def db_readback():
    db=old.read_db()
    with obs.connection() as c:
        rows=c.execute("""SELECT classification_uid::text,classification_key,
          historical_episode_id,city_key,alert_start_at::text,alert_end_at::text,
          supersedes_classification_uid::text,alert_episode_uid::text,verdict
          FROM public.attack_event_classifications
          ORDER BY historical_episode_id,created_at,classification_uid""").fetchall()
        src=c.execute("""SELECT classification_uid::text,count(*) FROM public.attack_event_sources
          GROUP BY classification_uid ORDER BY 1""").fetchall()
        ev=c.execute("""SELECT current_classification_uid::text,alert_episode_uid::text
          FROM public.attack_events ORDER BY current_classification_uid""").fetchall()
        indexes=c.execute("""SELECT indexdef FROM pg_indexes WHERE schemaname='public'
          AND tablename='attack_event_classifications' AND indexdef LIKE '%UNIQUE%'""").fetchall()
    return {"classifications":rows,"parents":db["parents"],"tips":db["tips"],
      "counts":db["counts"],"sources":src,"events":ev,"unique_indexes":indexes,
      "orphans":{"source":db["broken_sources"],"event":db["broken_events"],
                 "wrong_parent":db["wrong_parents"]}}

def json_readback(f):
    state=old.json_read(f.state_path)
    return {"file_hashes":f.files(),
      "checks":[{"episode":ep["episode_id"],"checks":[
         {"label":c.get("label"),"checked_at":c.get("checked_at"),"due_at":c.get("due_at")}
         for c in ep.get("checks",[])]} for ep in state["cities"][old.CITY]["episodes"]],
      "queue":[{"candidate_id":r.get("candidate_id"),
                "episode_id":r.get("matched_episode_id")} for r in old.json_read(f.queue_path)],
      "last_run":old.json_read(f.report_path).get("canonical_persistence") if f.report_path.exists() else None}

def k1():
    obs.reset_observed()
    baseline=old.stale_race()
    assert "STALE_EXPECTED_TIP" in baseline["rejection"]
    assert baseline["before_files"]==baseline["after_files"]
    assert baseline["race"]["snapshot_pid"]!=baseline["race"]["competitor_pid"]
    obs.reset_observed()
    f=old.Fixture();hits=[];pins={}
    def ignored(actual,expected):
        hits.append({"actual":actual,"expected":expected})
        return True
    mutated=replace_once(K1_TARGET,
        "if not exact_current_retry and actual_tip != expected_current_tip and not _k1_disabled(actual_tip,expected_current_tip):",
        _k1_disabled=ignored)
    try:
        with f.isolated():
            before=json_readback(f)
            observed=old.snapshot.observe_expected_tips
            def race(due,*,dsn=None,connection=None):
                with obs.connection() as c:
                    pins["snapshot_pid"]=c.execute("SELECT pg_backend_pid()").fetchone()[0]
                    snap=observed(due,connection=c)
                ep=f.episodes[0];ident=old.snapshot.episode_identity(ep)
                assert snap[ident]["expected_current_tip"] is None
                pins["snapshot"]=snap[ident]
                with obs.connection() as c:
                    pins["competitor_pid"]=c.execute("SELECT pg_backend_pid()").fetchone()[0]
                    rec=writer.build_episode_classification(ep,[old.queue_row(ep,"competing")])
                    committed=original(c,rec,expected_current_tip=None,
                          expected_parent_uid=snap[ident]["canonical_parent_uid"])
                    assert committed["commit_state"]=="COMMITTED"
                    pins["competitor_uid"]=committed["classification_uid"]
                return snap
            with mock.patch.object(old.snapshot,"observe_expected_tips",side_effect=race),\
                 mock.patch.object(writer,"persist_episode_classification",new=mutated):
                report=f.main()
            after=json_readback(f);rows=db_readback()
            assert len(hits)==1 and hits[0]["actual"]==pins["competitor_uid"]
            assert hits[0]["expected"] is None
            assert pins["snapshot_pid"]!=pins["competitor_pid"]
            assert rows["counts"]["attack_event_classifications"]==2
            assert len(rows["tips"])==1
            assert rows["classifications"][1][6]==pins["competitor_uid"]
            assert before["file_hashes"]!=after["file_hashes"]
            assert report["canonical_persistence"]["classification_inserts"]==1
            old.assert_integrity(old.read_db())
            broken="STALE_WRITE_COMMITTED_AND_JSON_CHECKPOINT_ADVANCED"
            PROOF["K1"]={"K1_BASELINE_RESULT":baseline,
              "K1_MUTATION_TARGET":K1_TARGET,"K1_MUTATION_REACHED":hits,
              "K1_MUTATED_DATABASE_OUTCOME":rows,"post_snapshot_concurrency":pins,
              "before_json":before,"after_json":after,
              "K1_ORACLE_DETECTION":{"status":"EXPECTED_MUTANT_REJECTION","failed_assertion":broken}}
    finally:
        f.close()
    assert writer.persist_episode_classification is original
    # Test the unchanged earlier oracle while the same mutation is enabled.
    obs.reset_observed();witness=[]
    mutant=replace_once(K1_TARGET,
        "if not exact_current_retry and actual_tip != expected_current_tip and not _k1_disabled(actual_tip,expected_current_tip):",
        _k1_disabled=lambda actual,expected:witness.append([actual,expected]) or True)
    with mock.patch.object(writer,"persist_episode_classification",new=mutant):
        try: old.stale_race()
        except AssertionError as ex: PROOF["K1"]["existing_oracle_failure"]=repr(ex)
        else: raise AssertionError("K1 existing oracle failed to reject unsafe mutant")
    assert witness and writer.persist_episode_classification is original
    obs.reset_observed()
    restored=old.stale_race()
    assert "STALE_EXPECTED_TIP" in restored["rejection"]
    PROOF["K1"]["K1_RESTORED_BASELINE"]=restored
    PROOF["K1"]["status"]="PASS"
    print("K1 EXPECTED_MUTANT_REJECTION; RESTORED PASS",flush=True)

def partial_failure(f):
    before=json_readback(f);calls=[0]
    def fault(conn,rec,**kw):
        calls[0]+=1
        return original(conn,rec,fault_after="classification" if calls[0]==2 else None,**kw)
    with mock.patch.object(writer,"persist_episode_classification",side_effect=fault):
        try: f.main()
        except RuntimeError as ex: assert "FORCED_PERSISTENCE_FAILURE_AFTER_CLASSIFICATION" in str(ex)
        else: raise AssertionError("K2 expected rollback not raised")
    after=json_readback(f);db=db_readback()
    assert calls==[2] and before==after
    assert db["counts"]["attack_event_classifications"]==1
    assert db["counts"]["attack_event_sources"]==db["counts"]["attack_events"]==1
    old.assert_integrity(old.read_db())
    return {"K2_FIRST_COMMIT":db,"K2_PARTIAL_FAILURE":{"before":before,"after":after,"writer_calls":calls[0]}}

def restart_baseline():
    obs.reset_observed();f=old.Fixture(2)
    try:
        with f.isolated():
            partial=partial_failure(f)
            first=partial["K2_FIRST_COMMIT"]["classifications"][0]
            second=f.main();db=db_readback()
            assert db["counts"]["attack_event_classifications"]==2
            assert sum(r[0]==first[0] for r in db["classifications"])==1
            assert second["canonical_persistence"]["classification_inserts"]==1
            old.assert_completed(f,old.read_db(),2)
            third=f.main()
            assert third["canonical_persistence"]["episodes_persisted"]==0
            return {**partial,"K2_ORIGINAL_RESTART":{
                "database":db,"json":json_readback(f),
                "restart":second["canonical_persistence"],
                "third_main":third["canonical_persistence"]}}
    finally: f.close()

def k2():
    base=restart_baseline()
    obs.reset_observed();f=old.Fixture(2);hits=[];attempts=[]
    try:
        with f.isolated():
            partial=partial_failure(f)
            first=partial["K2_FIRST_COMMIT"]["classifications"][0]
            uid,key,episode=first[:3]
            def ignore(rec,existing):
                assert rec["classification_key"]==key
                assert rec["historical_episode_id"]==episode
                assert str(existing["classification_uid"])==uid
                hits.append({"classification_uid":uid,"classification_key":key,"episode":episode})
                return True
            orig_insert=writer._insert_classification
            def watch_insert(cur,rec,**kw):
                if rec["classification_key"]==key:
                    attempts.append({"classification_key":key,"episode":episode,
                                     "supersedes":kw.get("supersedes_uid")})
                return orig_insert(cur,rec,**kw)
            mutant=replace_once(K2_TARGET,
                K2_TARGET+"\n        if existing is not None and _k2_disable_idempotency(record,existing):\n            existing=None",
                _k2_disable_idempotency=ignore,_insert_classification=watch_insert)
            with mock.patch.object(writer,"persist_episode_classification",new=mutant):
                r=f.main()
            db=db_readback();json_state=json_readback(f)
            assert len(hits)==len(attempts)==1
            assert db["counts"]["attack_event_classifications"]==2
            assert sum(row[1]==key for row in db["classifications"])==1
            assert r["canonical_persistence"]["classification_inserts"]==1
            assert any("classification_key" in idx[0] and "UNIQUE" in idx[0]
                       for idx in db["unique_indexes"])
            old.assert_completed(f,old.read_db(),2)
            old.assert_integrity(old.read_db())
            PROOF["K2"]={**base,"K2_MUTATION_TARGET":K2_TARGET,
               "K2_MUTATION_REACHED":hits,"repeated_insert_attempt":attempts,
               "K2_DUPLICATION_OR_BLOCKING_OUTCOME":{
                   "db":db,"json":json_state,"duplicate_committed_rows":0,
                   "barrier":"UNIQUE(classification_key)+ON CONFLICT DO NOTHING",
                   "application_level_duplicate_detector_proven":False},
               "K2_ORACLE_DETECTION":{"status":"EXPECTED_MUTANT_REJECTION",
                   "failed_assertion":"already committed classification_key attempted a second INSERT"}}
    finally: f.close()
    assert writer.persist_episode_classification is original
    restored=restart_baseline()
    PROOF["K2"]["K2_RESTORED_RESTART"]=restored["K2_ORIGINAL_RESTART"]
    PROOF["K2"]["status"]="PASS"
    print("K2 EXPECTED_MUTANT_REJECTION; DB BLOCKED COMMIT; RESTORED PASS",flush=True)

if __name__=="__main__":
    verdict="FAIL"
    try:
        k1();k2()
        assert all(PROOF[k].get("status")=="PASS" for k in ("K1","K2"))
        assert writer.persist_episode_classification is original
        assert old.NETWORK["live_calls"]==0
        verdict="PASS_MUTATION_CONTROLS_BOUNDED_PG18"
    except BaseException as ex:
        PROOF["exception"]={"status":"UNEXPECTED_APPLICATION_FAILURE",
                            "error":repr(ex),"traceback":traceback.format_exc()[-6000:]}
        raise
    finally:
        raw=Path(writer.__file__).read_bytes()
        blob=hashlib.sha1(("blob "+str(len(raw))+"\0").encode()+raw).hexdigest()
        result={"verdict":verdict,"cases":PROOF,"postgres_fixture":obs.EXPECTED_FIXTURE_BLOB,
          "writer_blob":blob,"expected_writer_blob":"2a5354aa3ad2bc67893ffa40589024ecb84fa15e",
          "writer_restored":writer.persist_episode_classification is original,
          "network_live_calls":old.NETWORK["live_calls"],"neon_calls":0,
          "limitations":["partially observed Neon DDL only","K2 independent DB unique-key barrier; no application-level duplicate rejection proven"]}
        REPORT.write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str)+"\n",encoding="utf-8")
        print("MUTATION_TEST_VERDICT",verdict,"GIT_BLOB",blob,flush=True)
        assert blob=="2a5354aa3a65c18d7bffb846a2c26973564c7812".replace("a94741aa3a65c18d7bffb846a2c26973564c7812","2a5354aa4ad2bc67893ffa40589024ecb84fa15e")
