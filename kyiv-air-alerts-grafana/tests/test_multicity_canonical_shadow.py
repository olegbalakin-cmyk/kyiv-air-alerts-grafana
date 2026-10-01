import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import multicity_canonical_shadow as shadow
import multicity_shadow_payload as payload
from update_data import Alert
from datetime import datetime, timezone


UTC = timezone.utc


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class TestSameRunPayload(unittest.TestCase):
    def test_disabled_payload_is_noop(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "payload.json"
            with mock.patch.dict(os.environ, {}, clear=True):
                payload.record_city_alerts(
                    "kyiv",
                    [Alert(datetime(2026,1,1,tzinfo=UTC), datetime(2026,1,1,0,10,tzinfo=UTC), "x")],
                    producer="test",
                )
            self.assertFalse(p.exists())

    def test_payload_records_exact_closed_episode(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "payload.json"
            with mock.patch.dict(os.environ, {payload.PAYLOAD_ENV: str(p)}, clear=True):
                payload.record_city_alerts(
                    "kyiv",
                    [Alert(datetime(2026,1,1,tzinfo=UTC), datetime(2026,1,1,0,10,tzinfo=UTC), "x")],
                    producer="test",
                )
            obj=json.loads(p.read_text())
            row=obj["cities"]["kyiv"]["episodes"][0]
            self.assertEqual(row["city_key"],"kyiv")
            self.assertEqual(row["episode_state"],"closed")
            self.assertEqual(obj["cities"]["kyiv"]["episode_count"],1)


class TestShadowRuntime(unittest.TestCase):
    def make_inputs(self, td):
        root=Path(td)
        dashboard=root/"dashboard_data.json"
        bridge=root/"ukrainealarm_bridge.json"
        payload_path=root/"payload.json"
        keys=[f"city{i:02d}" for i in range(23)]
        dashboard.write_text(json.dumps({"multicity_meta":{"production_city_keys":keys},"sentinel":"dashboard"}))
        bridge.write_text(json.dumps({"sentinel":"bridge"}))
        cities={}
        for i,key in enumerate(keys):
            start=f"2026-01-{(i%28)+1:02d}T00:00:00Z"
            end=f"2026-01-{(i%28)+1:02d}T00:10:00Z"
            from db_phase1_core import legacy_episode_id, CANONICALIZATION_VERSION
            cities[key]={"producer":"test","episode_count":1,"episodes":[{
                "city_key":key,"alert_type":"AIR","start_at":start,"end_at":end,
                "episode_state":"closed","legacy_episode_id":legacy_episode_id(key,start,end),
                "canonicalization_version":CANONICALIZATION_VERSION,
            }]}
        payload_path.write_text(json.dumps({
            "format":"multicity-canonical-same-run-v1",
            "canonicalization_version":"alert-canonicalization-v1",
            "cities":cities,
        }))
        return dashboard,bridge,payload_path

    def env(self,dashboard,payload_path,diag,enabled=True):
        return {
            shadow.FLAG_ENV:"1" if enabled else "0",
            shadow.DB_ENV:"postgresql://invalid:invalid@127.0.0.1:1/nope?connect_timeout=1",
            shadow.BRANCH_ENV:"br-proof",
            shadow.FAILURE_ENV:"fail_open",
            shadow.DIAGNOSTIC_ENV:str(diag),
            shadow.PAYLOAD_ENV:str(payload_path),
            shadow.DASHBOARD_ENV:str(dashboard),
            shadow.INPUT_REPOSITORY_ENV:"repo",
            shadow.INPUT_REF_ENV:"site-prod",
            shadow.INPUT_SHA_ENV:"abc",
        }

    def test_fixed_output_equivalence_off_vs_fail_open_on(self):
        with tempfile.TemporaryDirectory() as td:
            dashboard,bridge,payload_path=self.make_inputs(td)
            before=(sha(dashboard),sha(bridge))
            offdiag=Path(td)/"off.json"
            with mock.patch.dict(os.environ,self.env(dashboard,payload_path,offdiag,enabled=False),clear=True):
                out=shadow.execute()
            self.assertEqual(out["status"],"disabled")
            self.assertEqual(before,(sha(dashboard),sha(bridge)))

            ondiag=Path(td)/"on.json"
            with mock.patch.dict(os.environ,self.env(dashboard,payload_path,ondiag,enabled=True),clear=True):
                out=shadow.execute()
            self.assertEqual(out["status"],"failed")
            self.assertEqual(out["failure_policy"],"fail_open")
            self.assertFalse(out["production_output_mutation"])
            self.assertEqual(before,(sha(dashboard),sha(bridge)))
            diag=json.loads(ondiag.read_text())
            self.assertNotIn("DATABASE_URL",json.dumps(diag))
            self.assertNotIn("invalid:invalid",json.dumps(diag))

    def test_success_path_reports_noop_without_output_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            dashboard,bridge,payload_path=self.make_inputs(td)
            before=(sha(dashboard),sha(bridge))
            diag=Path(td)/"ok.json"
            fake_conn=mock.Mock()
            fake_connect=mock.Mock(return_value=fake_conn)
            fake_psycopg=mock.Mock(connect=fake_connect)
            result={"status":"already_persisted","run_id":None,"episodes_inserted":0,
                    "episodes_existing":23,"episodes_updated":0,"writes":0}
            with mock.patch.dict(sys.modules,{"psycopg":fake_psycopg}),                  mock.patch("multicity_canonical_postgres.persist_canonical_episodes",return_value=result),                  mock.patch.dict(os.environ,self.env(dashboard,payload_path,diag,enabled=True),clear=True):
                out=shadow.execute()
            self.assertEqual(out["status"],"succeeded")
            self.assertEqual(out["persistence_status"],"already_persisted")
            self.assertEqual(out["city_count"],23)
            self.assertEqual(out["canonical_episode_count"],23)
            self.assertEqual(out["writes"],0)
            self.assertEqual(before,(sha(dashboard),sha(bridge)))

    def test_rejects_missing_city_payload_fail_open(self):
        with tempfile.TemporaryDirectory() as td:
            dashboard,bridge,payload_path=self.make_inputs(td)
            obj=json.loads(payload_path.read_text())
            obj["cities"].pop(next(iter(obj["cities"])))
            payload_path.write_text(json.dumps(obj))
            diag=Path(td)/"bad.json"
            with mock.patch.dict(os.environ,self.env(dashboard,payload_path,diag,enabled=True),clear=True):
                out=shadow.execute()
            self.assertEqual(out["status"],"failed")
            self.assertEqual(out["error_type"],"RuntimeError")


if __name__=="__main__":
    unittest.main()
