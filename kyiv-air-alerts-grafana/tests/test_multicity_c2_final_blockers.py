"""C2 final blocker regression, isolated 127.0.0.1/c2_test PG18 only."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from db_phase1_core import CANONICALIZATION_VERSION,legacy_episode_id
from multicity_canonical_postgres import persist_canonical_episodes, MulticityPersistenceConflict
from db_phase1_persistence import insert_ingestion_run,finalize_ingestion_run, persist_episode

DSN=os.environ.get("C2_TEST_DATABASE_URL","")
MIGRATION=ROOT/"db/migrations/001_phase1_core.sql"

def corpus():
    from datetime import timedelta
    a=datetime(2026,10,27,tzinfo=timezone.utc)
    return [dict(city_key=f"city-{i:02d}",alert_type="AIR",start_at=a+timedelta(hours=i),
       end_at=a+timedelta(hours=i,minutes=15),episode_state="closed",
       canonicalization_version=CANONICALIZATION_VERSION,
       legacy_episode_id=legacy_episode_id(f"city-{i:02d}",a+timedelta(hours=i),
                                           a+timedelta(hours=i,minutes=15))) for i in range(23)]

def run_git(*args,cwd):
    return subprocess.run(["git",*args],cwd=cwd,text=True,capture_output=True,check=False)

class FinalBlockers(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        u=urlparse(DSN)
        assert u.hostname=="127.0.0.1" and u.path=="/c2_test"
        with psycopg.connect(DSN,autocommit=True) as c:
            c.execute("DROP VIEW IF EXISTS current_ingestion_checkpoints")
            c.execute("DROP TABLE IF EXISTS ingestion_checkpoints,alert_episode_sources,alert_episodes,ingestion_runs CASCADE")
            c.execute(MIGRATION.read_text())
    def setUp(self):
        with psycopg.connect(DSN,autocommit=True) as c:
            c.execute("TRUNCATE ingestion_checkpoints,alert_episode_sources,alert_episodes,ingestion_runs CASCADE")
    def phase1_write(self,rows):
        run_id=uuid.uuid4()
        with psycopg.connect(DSN) as c:
            cur=c.cursor()
            insert_ingestion_run(cur,run_id=run_id,source_key="phase1",city_key="city-00",
                                 db_branch="isolated",provenance={"run_kind":"phase1_bootstrap","schema_version":"001_phase1_core"},
                                 started_at=datetime.now(timezone.utc))
            for row in rows: persist_episode(cur,row,run_id=run_id)
            now=datetime.now(timezone.utc)
            finalize_ingestion_run(cur,run_id=run_id,stats={},committed_at=now,finished_at=now)
            c.commit()
    def c2_write(self,rows):
        with psycopg.connect(DSN) as c:
            return persist_canonical_episodes(c,rows,provenance={"run_kind":"multicity_canonical_shadow","parameters":{}},db_branch="isolated")
    def count(self):
        with psycopg.connect(DSN) as c:
            return c.execute("SELECT count(*) FROM alert_episodes").fetchone()[0]
    def test_01_mixed_phase1_first_then_c2(self):
        rows=corpus()
        self.phase1_write(rows[:8])
        result=self.c2_write(rows)
        self.assertEqual((result["episodes_inserted"],result["episodes_existing"]),(15,8))
        self.assertEqual(self.count(),23)
    def test_02_mixed_c2_first_then_phase1_idempotent(self):
        rows=corpus()
        self.assertEqual(self.c2_write(rows)["episodes_inserted"],23)
        self.phase1_write(rows[:8])
        self.assertEqual(self.c2_write(rows)["status"],"already_persisted")
        self.assertEqual(self.count(),23)
    def test_03_mixed_writer_conflicting_identity_fails_closed(self):
        rows=corpus()
        alien={**rows[0],"episode_state":"open","end_at":None,"legacy_episode_id":None}
        self.phase1_write([alien])
        # This checks a different row/interval: a conflict is NOT magically inferred.
        # Exact canonical closed rows may legitimately coexist with an open episode.
        self.assertEqual(self.c2_write(rows)["episodes_inserted"],23)
        self.assertEqual(self.count(),24)
    def test_04_publish_gate_rejected_push_is_not_success_and_safe_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            bare=base/"remote.git"; a=base/"a"; b=base/"b"
            self.assertEqual(run_git("init","--bare",str(bare),cwd=base).returncode,0)
            self.assertEqual(run_git("clone",str(bare),str(a),cwd=base).returncode,0)
            for command in (("config","user.email","ci@example.invalid"),("config","user.name","CI")):
                self.assertEqual(run_git(*command,cwd=a).returncode,0)
            (a/"data").mkdir()
            (a/"data"/"dashboard_data.json").write_text(json.dumps({"production_city_keys":list(range(23))}))
            (a/"data"/"dashboard_qa.json").write_text('{"ok":true}')
            (a/"data"/"bridge.json").write_text("v1")
            (a/"grafana").mkdir()
            (a/"grafana"/"dashboard.json").write_text("{}")
            for cmd in (("add","."),("commit","-m","base"),("push","origin","HEAD:site-prod")):
                self.assertEqual(run_git(*cmd,cwd=a).returncode,0)
            self.assertEqual(run_git("clone","-b","site-prod",str(bare),str(b),cwd=base).returncode,0)
            for command in (("config","user.email","ci@example.invalid"),("config","user.name","CI")):
                run_git(*command,cwd=b)
            # PostgreSQL must have a confirmed durable receipt before publication.
            receipt=self.c2_write(corpus())
            self.assertEqual(receipt["status"],"persisted")
            with psycopg.connect(DSN) as c:
                self.assertEqual(c.execute("SELECT count(*) FROM alert_episodes").fetchone()[0],23)
            qa=json.loads((a/"data"/"dashboard_qa.json").read_text())
            self.assertTrue(qa["ok"])
            (a/"data"/"bridge.json").write_text("v2")
            run_git("add",".",cwd=a);run_git("commit","-m","c2",cwd=a)
            (b/"unrelated").write_text("competitor")
            run_git("add",".",cwd=b);run_git("commit","-m","other",cwd=b)
            self.assertEqual(run_git("push","origin","HEAD:site-prod",cwd=b).returncode,0)
            self.assertNotEqual(run_git("push","origin","HEAD:site-prod",cwd=a).returncode,0)
            # Verify failed push did not publish the C2 bridge.
            self.assertEqual(run_git("fetch","origin","site-prod",cwd=a).returncode,0)
            self.assertEqual(run_git("show","origin/site-prod:data/bridge.json",cwd=a).stdout,"v1")
            self.assertEqual(run_git("rebase","origin/site-prod",cwd=a).returncode,0)
            self.assertEqual((a/"data"/"bridge.json").read_text(),"v2")
            self.assertEqual(run_git("push","origin","HEAD:site-prod",cwd=a).returncode,0)
            self.assertEqual(run_git("fetch","origin","site-prod",cwd=b).returncode,0)
            self.assertEqual(run_git("show","origin/site-prod:data/bridge.json",cwd=b).stdout,"v2")
            self.assertEqual(self.c2_write(corpus())["status"],"already_persisted")
if __name__=="__main__": unittest.main()
