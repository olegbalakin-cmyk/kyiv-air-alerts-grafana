#!/usr/bin/env python3
"""Real monitor.main offline integration on disposable PostgreSQL, no source network."""
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import psycopg
BASE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BASE/"scripts"))
sys.path.insert(0,str(BASE/"tests/fixtures/parent_contract"))
import db_phase1_core as core
import monitor_explosion_candidates as monitor
import live_canonical_queue as queue

DSN=os.environ["LOCAL_PROOF_POSTGRES_DSN"]
os.environ["ATTACK_EVENT_DATABASE_URL"]=DSN
os.environ["CANONICAL_PARENT_CONTRACT_DIR"]=str(BASE/"tests/fixtures/parent_contract")
os.environ["CANONICAL_PARENT_DB_BRANCH"]="offline-disposable-postgres-16"
NOW=datetime(2026,10,15,12,tzinfo=timezone.utc)
start=datetime(2026,10,9,1,tzinfo=timezone.utc)
end=start+timedelta(minutes=30)
epid=core.legacy_episode_id("kyiv",start,end)
episode={"city_key":"kyiv","episode_id":epid,"alert_start":start.isoformat(),
         "alert_end":end.isoformat(),"alert_source":"kyiv_combined_exact_city",
         "checks":[{"label":"immediate","due_at":end.isoformat(),"checked_at":None,
                    "new_candidates":None}]}
evidence={"url":"https://example.invalid/kyiv-frozen-observation","title":"У Києві чули вибухи під час тривоги",
          "publisher":"Offline synthetic source","published_at":(start+timedelta(minutes=20)).isoformat(),
          "source":"Google News RSS", "snippet":"Київ, вибухи вночі під час повітряної тривоги"}
original_now=monitor.now_utc
original_poll=monitor.poll_cached_bridge
original_refresh=monitor.refresh_telegram_cache
original_telegram=monitor.telegram_candidates_for_city
original_search=monitor.search_city_news
original_argv=list(sys.argv)
original_paths=(monitor.STATE_FILE,monitor.QUEUE_FILE,monitor.LAST_RUN_FILE)
with tempfile.TemporaryDirectory(prefix="kyiv-pg16-monitor-") as folder:
    root=Path(folder)
    monitor.STATE_FILE=root/"monitor_state.json"
    monitor.QUEUE_FILE=root/"queue.json"
    monitor.LAST_RUN_FILE=root/"report.json"
    monitor.STATE_FILE.write_text(json.dumps({"schema_version":1,"cities":{"kyiv":{"episodes":[episode]}}}))
    monitor.QUEUE_FILE.write_text("[]")
    monitor.now_utc=lambda: NOW
    monitor.poll_cached_bridge=lambda *_args: ({city:[] for city in monitor.CITY_CONFIG}, {})
    monitor.refresh_telegram_cache=lambda *_args: {}
    monitor.telegram_candidates_for_city=lambda *_args: []
    monitor.search_city_news=lambda city,*_args: (
        [evidence] if city=="kyiv" else [],None,
        {"fulltext_fetches":0,"fulltext_rescued_candidates":0})
    sys.argv=["monitor_explosion_candidates.py","--local-only"]
    try:
        before=monitor.authoritative_classifier_runtime_identity()["invocations"]
        monitor.main()
        first=json.loads(monitor.LAST_RUN_FILE.read_text())
        after=monitor.authoritative_classifier_runtime_identity()["invocations"]
        assert after>before,("authoritative classifier not invoked",before,after)
        assert first["canonical_persistence"]["committed"]==1,first["canonical_persistence"]
        assert first["canonical_persistence"]["readback_verified"]==1
        persisted=json.loads(monitor.STATE_FILE.read_text())
        assert len(queue.store(persisted))==1
        assert next(iter(queue.store(persisted).values()))["status"]=="committed"
        monitor.main()
        second=json.loads(monitor.LAST_RUN_FILE.read_text())
        assert second["canonical_persistence"]["committed"]==0,second["canonical_persistence"]
        with psycopg.connect(DSN,autocommit=True) as connection:
            with connection.cursor() as cur:
                cur.execute("SELECT count(*), count(DISTINCT classification_key) FROM public.attack_event_classifications WHERE historical_episode_id=%s",(epid,))
                row=cur.fetchone()
                assert row==(1,1),row
                cur.execute("SELECT verdict, alert_episode_uid IS NOT NULL FROM public.attack_event_classifications WHERE historical_episode_id=%s",(epid,))
                verdict,parent_exact=cur.fetchone()
                assert parent_exact
                cur.execute("SELECT count(*) FROM public.attack_event_sources s JOIN public.attack_event_classifications c USING(classification_uid) WHERE c.historical_episode_id=%s",(epid,))
                source_count=cur.fetchone()[0]
                assert source_count==1,source_count
        result={"pass":True,"monitor_main_calls":2,"classifier_invocations":after-before,
                "episode_id":epid,"first_committed":1,"first_independent_readback":1,
                "second_committed":0,"final_classifications":1,"source_links":source_count,
                "verdict":verdict,"cities_configured":len(monitor.CITY_CONFIG),
                "state_paths_isolated":True,"network_sources":"frozen_offline"}
        print("MAIN_INTEGRATION_REPORT="+json.dumps(result,sort_keys=True))
    finally:
        sys.argv=original_argv
        monitor.now_utc=original_now
        monitor.poll_cached_bridge=original_poll
        monitor.refresh_telegram_cache=original_refresh
        monitor.telegram_candidates_for_city=original_telegram
        monitor.search_city_news=original_search
        monitor.STATE_FILE,monitor.QUEUE_FILE,monitor.LAST_RUN_FILE=original_paths
