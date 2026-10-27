"""C2 integrated same-run staging: real shadow CLI, receipt, QA, exact YAML publish shell.
No live data, credentials, network service, or production branch changes.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "scripts"))
from db_phase1_core import CANONICALIZATION_VERSION, legacy_episode_id
from postprocess_compact_dashboard_qa import validate, source_groups

DSN = os.environ.get("C2_TEST_DATABASE_URL", "")
FLOW = REPO / ".github/workflows/update-netlify-site.yml"


def cmd(*args, cwd=None, env=None, ok=True):
    p = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True)
    if ok and p.returncode:
        raise AssertionError((args, p.returncode, p.stdout[-1000:], p.stderr[-1000:]))
    return p


def stage(root):
    site = root / "kyiv-air-alerts-grafana"
    (site / "scripts").mkdir(parents=True)
    (site / "data").mkdir()
    (site / "grafana").mkdir()
    for name in ("validate_bridge_checkpoint.py", "verify_c2_publication_snapshot.py",
                 "verify_multicity_canonical_receipt.py"):
        shutil.copy2(ROOT / "scripts" / name, site / "scripts" / name)
    return site


def bridge():
    now = "2026-10-27T12:00:00+00:00"
    regions = {}
    for i in range(21):
        regions[f"city-{i:02}"] = {
            "continuous": True, "last_error": None,
            "history_completed_air_count": 1,
            "oldest_history_start": "2026-10-01T00:00:00+00:00",
            "latest_history_end": now, "last_checked_at": now,
        }
    return {"schema_version": 3, "regions": regions, "events": [],
            "event_count": 0, "last_fetch_error": None,
            "last_successful_fetch_at": now, "last_attempt_at": now}


def dataset(site):
    cities = ["kyiv", "kharkiv", "zaporizhzhia", "sevastopol"] + [f"city-{i:02}" for i in range(19)]
    start = datetime(2026, 10, 27, tzinfo=timezone.utc)
    episodes = {}
    labels = {}
    entries = {}
    for i, city in enumerate(cities):
        a = start + timedelta(minutes=30*i)
        b = a + timedelta(minutes=15)
        row = {"city_key":city,"alert_type":"AIR","start_at":a.isoformat(),
               "end_at":b.isoformat(),"episode_state":"closed",
               "canonicalization_version":CANONICALIZATION_VERSION,
               "legacy_episode_id":legacy_episode_id(city,a,b)}
        episodes[city] = {"episodes":[row], "episode_count":1}
        exact = city in {"kyiv","kharkiv","zaporizhzhia","sevastopol"}
        label = city if exact else city+" (район тест)"
        labels[city] = {"source_type":"exact_city" if exact else "raion_proxy", "label":label}
        entries[city] = {"meta":{"source_type":labels[city]["source_type"],
                                  "city_label":label,"coverage_start":"2026-01-01"}}
    required = sorted(bridge()["regions"])
    summary = {"required_rows":required, "continuity_verified_rows":required,
               "continuity_unverified_rows":[],"token_present_this_run":True,
               "last_fetch_error":None,"fully_continuous":True,
               "event_count":0,"last_successful_fetch_at":"2026-10-27T12:00:00+00:00"}
    dash = {"multicity_meta":{"production_city_keys":cities,"cities":labels,
            "deferred":{"donetsk":{},"luhansk":{}},
            "official_ukrainealarm_bridge":summary},
            "cities":entries}
    (site/"data/dashboard_data.json").write_text(json.dumps(dash))
    (site/"data/ukrainealarm_bridge.json").write_text(json.dumps(bridge()))
    (site/"data/dashboard_qa.json").write_text('{"ok":true}')
    panel = {"type":"timeseries","targets":[{"expr":"${compare_city_a} ${compare_city_b} ${compare_city_c} $.cities.${city}"}]}
    obj = {"templating":{"list":[{"name":x} for x in ("city","compare_city_a","compare_city_b",
            "compare_city_c","duration_unit","comparison_period")]},
            "panels":[{"id":i,**panel} for i in (41,42,43)]}
    (site/"grafana/dashboard.json").write_text(json.dumps(obj))
    return cities, episodes, dash, obj


class OwnerRelease(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        u = urlparse(DSN)
        if u.hostname != "127.0.0.1" or u.path != "/c2_test":
            raise AssertionError("only isolated 127.0.0.1/c2_test is permitted")
        with psycopg.connect(DSN, autocommit=True) as c:
            assert c.execute("SHOW server_version_num").fetchone()[0].startswith("18")
            c.execute("DROP VIEW IF EXISTS current_ingestion_checkpoints")
            c.execute("DROP TABLE IF EXISTS ingestion_checkpoints, alert_episode_sources, alert_episodes, ingestion_runs CASCADE")
            c.execute((ROOT/"db/migrations/001_phase1_core.sql").read_text())

    def setUp(self):
        with psycopg.connect(DSN, autocommit=True) as c:
            c.execute("TRUNCATE ingestion_checkpoints, alert_episode_sources, alert_episodes, ingestion_runs CASCADE")

    def test_integrated_commit_receipt_qa_publication_and_recovery(self):
        workflow = yaml.safe_load(FLOW.read_text())
        steps = workflow["jobs"]["update-site"]["steps"]
        names = [x["name"] for x in steps if "name" in x]
        seq = ["Update base data", "Run multicity canonical DB shadow",
               "Gate publication on committed canonical persistence receipt",
               "QA 23-city dataset", "Verify production dataset",
               "Commit updated production data and verified UkraineAlarm bridge checkpoint"]
        self.assertEqual(sorted(names.index(x) for x in seq), [names.index(x) for x in seq])
        self.assertNotIn("Persist verified UkraineAlarm bridge checkpoint", names)
        publish = next(x["run"] for x in steps if x.get("name") == seq[-1])
        with tempfile.TemporaryDirectory(prefix="c2-owner-") as d:
            base = Path(d)
            remote = base/"remote.git"
            a = base/"runner"
            cmd("git","init","--bare",str(remote))
            cmd("git","clone",str(remote),str(a))
            cmd("git","config","user.name","C2 integration",cwd=a)
            cmd("git","config","user.email","ci@example.invalid",cwd=a)
            site = stage(a)
            cities, payload, dash, obj = dataset(site)
            cmd("git","add",".",cwd=a)
            cmd("git","commit","-m","baseline",cwd=a)
            cmd("git","push","origin","HEAD:site-prod",cwd=a)
            cmd("git","fetch","origin","site-prod",cwd=a)
            env = dict(os.environ)
            env.update({"MULTICITY_CANONICAL_DB_SHADOW":"1",
                "MULTICITY_CANONICAL_DATABASE_URL":DSN,
                "MULTICITY_CANONICAL_DB_BRANCH":"isolated",
                "MULTICITY_CANONICAL_DB_SHADOW_FAILURE_POLICY":"fail_closed",
                "MULTICITY_CANONICAL_DB_SHADOW_DIAGNOSTIC":str(base/"receipt.json"),
                "MULTICITY_CANONICAL_PAYLOAD_PATH":str(base/"payload.json"),
                "MULTICITY_CANONICAL_DASHBOARD_PATH":str(site/"data/dashboard_data.json"),
                "MULTICITY_CANONICAL_INPUT_SHA":"a"*40,
                "GITHUB_SHA":"b"*40, "GITHUB_RUN_ID":"123", "RUNNER_TEMP":str(base)})
            (base/"payload.json").write_text(json.dumps({"format":"multicity-canonical-same-run-v1",
                "canonicalization_version":CANONICALIZATION_VERSION,"cities":payload}))
            (base/"ukrainealarm_bridge_before.json").write_text(json.dumps(bridge()))
            # Real canonical shadow executable, commit and receipt verifier.
            shadow = ROOT/"scripts/multicity_canonical_shadow.py"
            verifier = ROOT/"scripts/verify_multicity_canonical_receipt.py"
            def write_and_verify():
                cmd(sys.executable,str(shadow),cwd=site,env=env)
                cmd(sys.executable,str(verifier),str(base/"receipt.json"),cwd=site,env=env)
            write_and_verify()
            with psycopg.connect(DSN) as c:
                self.assertEqual(c.execute("SELECT COUNT(*) FROM alert_episodes").fetchone()[0],23)
            e,p,labels = source_groups(dash)
            self.assertTrue(validate(dash,obj,e,p,labels)["ok"])
            # Mutate QA-verified output after the DB commit so publication has a real delta.
            (site/"data/dashboard_qa.json").write_text('{"ok":true,"revision":1}')
            def publish_run():
                return cmd("bash","-euo","pipefail","-c",publish,cwd=a,env=env,ok=False)
            first = publish_run()
            self.assertEqual(first.returncode,0,(first.stdout,first.stderr))
            cmd("git","fetch","origin","site-prod",cwd=a)
            self.assertIn('"revision":1',cmd("git","show",
                "origin/site-prod:kyiv-air-alerts-grafana/data/dashboard_qa.json",cwd=a).stdout)
            # Post-commit lost ACK: same DB and no local changes must verify remote.
            write_and_verify()
            self.assertEqual(json.loads((base/"receipt.json").read_text())["persistence_status"],"already_persisted")
            self.assertEqual(publish_run().returncode,0)
            # Simulate a remote divergence with no local changes: fail explicitly.
            b = base/"other"
            cmd("git","clone","-b","site-prod",str(remote),str(b))
            cmd("git","config","user.name","competing",cwd=b)
            cmd("git","config","user.email","ci@example.invalid",cwd=b)
            (b/"kyiv-air-alerts-grafana/data/dashboard_qa.json").write_text('{"ok":true,"revision":999}')
            cmd("git","add",".",cwd=b)
            cmd("git","commit","-m","remote drift",cwd=b)
            cmd("git","push","origin","HEAD:site-prod",cwd=b)
            lost = publish_run()
            self.assertNotEqual(lost.returncode,0)
            self.assertIn("No local changes but remote output",lost.stdout+lost.stderr)
            # A following retry with local delta can republish the intended output.
            (site/"data/dashboard_qa.json").write_text('{"ok":true,"revision":2}')
            # This competing same-path drift correctly raises rebase conflict, not false success.
            rejected = publish_run()
            self.assertNotEqual(rejected.returncode,0)
            self.assertIn("not confirmed",rejected.stdout+rejected.stderr)

if __name__ == "__main__":
    unittest.main()
