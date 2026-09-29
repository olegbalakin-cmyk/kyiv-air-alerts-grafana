import copy,json,sqlite3,tempfile,unittest,urllib.error
from pathlib import Path
from unittest.mock import patch
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"scripts"))
import proof_differentiated_alert_shadow_ingestion as p
F=ROOT/"tests/fixtures/differentiated_alert_shadow"
UA=json.loads((F/"ukrainealarm_overlap_stored_raw_2026-09-14.json").read_text())
AIU=json.loads((F/"alerts_in_ua_stored_raw_2026-09-16.json").read_text())
KYIV=json.loads((F/"kyiv_stored_raw_2026-09-29.json").read_text())

class T(unittest.TestCase):
 def store(self):
  f=tempfile.NamedTemporaryFile(suffix=".sqlite",delete=False);f.close();s=p.ShadowStore(f.name);self.addCleanup(s.close);return s
 def test_01_kyiv_snapshot(self):
  r=p.canonicalize_kyiv(KYIV,observed_at="2026-09-29T09:36:10Z");self.assertEqual(r["snapshot"]["source_geography"]["scope"],"CITY");self.assertEqual(len(r["threat_observations"]),1)
 def test_02_zero_threat_clear(self):
  r=p.canonicalize_kyiv({"current":{"state":0,"causes":[],"last_cause":None,"created_at":"2026-09-29 11:13:00"}},observed_at="2026-09-29T11:13:05Z");self.assertEqual(r["threat_observations"],[]);s=self.store();self.assertEqual(s.persist(p.bind(r,[]))["inserted_observations"],0)
 def test_03_ua_overlap(self):
  r=p.canonicalize_ukrainealarm(UA,observed_at="2026-09-14T17:47:00Z",target_city_key="zaporizhzhia",region_id="147");self.assertEqual({x["level_raw"] for x in r["threat_observations"]},{"Red","Yellow"});self.assertEqual({x["snapshot_key"] for x in r["threat_observations"]},{r["snapshot"]["snapshot_key"]})
 def test_04_aiu_fields(self):
  r=p.canonicalize_alerts_in_ua(AIU,observed_at="2026-09-16T04:43:10Z",target_city_key="donetsk");x=r["threat_observations"][0];self.assertEqual((r["snapshot"]["source_alert_id"],r["snapshot"]["source_alert_level_raw"],x["cause_raw"],x["source_message_raw"]),("261769","red","unspecified_missiles","Ракетна загроза (червоний рівень)"))
 def test_05_exact_replay_idempotent(self):
  s=self.store();r=p.bind(p.canonicalize_ukrainealarm(UA,observed_at="2026-09-14T17:47:00Z",target_city_key="x",region_id="147"),[]);self.assertEqual(s.persist(r),{"inserted_snapshots":1,"inserted_observations":2});self.assertEqual(s.persist(r),{"inserted_snapshots":0,"inserted_observations":0})
 def test_06_unchanged_later_poll(self):
  a=p.canonicalize_ukrainealarm(UA,observed_at="2026-09-14T17:47:00Z",target_city_key="x",region_id="147");b=p.canonicalize_ukrainealarm(UA,observed_at="2026-09-14T17:48:00Z",target_city_key="x",region_id="147");self.assertNotEqual(a["snapshot"]["snapshot_key"],b["snapshot"]["snapshot_key"]);self.assertEqual({x["component_signature"] for x in a["threat_observations"]},{x["component_signature"] for x in b["threat_observations"]})
 def test_07_restart_replay(self):
  f=tempfile.NamedTemporaryFile(suffix=".sqlite",delete=False);f.close();r=p.bind(p.canonicalize_alerts_in_ua(AIU,observed_at="2026-09-16T04:43:10Z",target_city_key="x"),[]);s=p.ShadowStore(f.name);self.assertEqual(s.persist(r)["inserted_snapshots"],1);s.close();s=p.ShadowStore(f.name);self.addCleanup(s.close);self.assertEqual(s.persist(r),{"inserted_snapshots":0,"inserted_observations":0})
 def test_08_binding_states(self):
  base={"episode_id":"e1","city_key":"kyiv","alert_type":"AIR","start_at":"2026-09-29T09:00:00Z","end_at":"2026-09-29T10:00:00Z"};r=p.canonicalize_kyiv(KYIV,observed_at="2026-09-29T09:36:10Z");self.assertEqual(p.bind(r,[base])["snapshot"]["binding_state"],"BOUND");self.assertEqual(p.bind(r,[])["snapshot"]["episode_id"],None);self.assertEqual(p.bind(r,[base,{**base,"episode_id":"e2"}])["snapshot"]["episode_id"],None)
 def test_09_raion_preserved(self):
  r=p.canonicalize_ukrainealarm(UA,observed_at="2026-09-14T17:47:00Z",target_city_key="zaporizhzhia",region_id="147");self.assertEqual(r["snapshot"]["source_geography"]["scope"],"RAION")
 def test_10_unknown_raw_preserved(self):
  a=copy.deepcopy(AIU);a["alert_level"]="Orange";a["threats"][0]["threat_type"]="future_enum_value";a["threats"][0]["level"]="Orange";r=p.canonicalize_alerts_in_ua(a,observed_at="2026-09-16T04:43:10Z",target_city_key="x");x=r["threat_observations"][0];self.assertEqual((r["snapshot"]["source_alert_level_raw"],x["cause_raw"],x["level_raw"]),("Orange","future_enum_value","Orange"));self.assertEqual((x["threat_type_normalized"],x["severity_normalized"]),("unknown","unknown"))
 def test_11_persistence_failure_atomic(self):
  s=self.store();r=p.bind(p.canonicalize_alerts_in_ua(AIU,observed_at="2026-09-16T04:43:10Z",target_city_key="x"),[]);self.assertRaises(sqlite3.OperationalError,s.persist,r,True);self.assertEqual(s.counts(),{"snapshots":0,"observations":0})
 def test_12_cross_source_coexist(self):
  s=self.store();u=p.bind(p.canonicalize_ukrainealarm(UA,observed_at="2026-09-14T17:47:00Z",target_city_key="x",region_id="147"),[]);a=p.bind(p.canonicalize_alerts_in_ua(AIU,observed_at="2026-09-16T04:43:10Z",target_city_key="x"),[]);s.persist(u);s.persist(a);self.assertEqual(s.counts(),{"snapshots":2,"observations":3});self.assertEqual({x[1] for x in s.snapshot_rows()},{"ukrainealarm","alerts_in_ua"})
 def test_13_parent_mutation_impossible(self):
  self.assertFalse(any(hasattr(p.ShadowStore,n) for n in ["create_episode","update_episode_start","update_episode_end","delete_episode"]))
 def test_14_parent_input_unchanged(self):
  eps=[{"episode_id":"e","city_key":"kyiv","alert_type":"AIR","start_at":"2026-09-29T09:00:00Z","end_at":"2026-09-29T10:00:00Z"}];before=json.dumps(eps,sort_keys=True);p.bind(p.canonicalize_kyiv(KYIV,observed_at="2026-09-29T09:36:10Z"),eps);self.assertEqual(before,json.dumps(eps,sort_keys=True))
 def test_15_poll_progression(self):
  t0=copy.deepcopy(UA);t0["activeAlerts"][0]["activeAlertLevels"]=t0["activeAlerts"][0]["activeAlertLevels"][1:];t2=copy.deepcopy(t0);t2["activeAlerts"][0]["lastUpdate"]="2026-09-14T17:50:00Z";t3={"regionId":"147","regionType":"District","activeAlerts":[]};rs=[p.canonicalize_ukrainealarm(t0,observed_at="2026-09-14T17:30:00Z",target_city_key="x",region_id="147"),p.canonicalize_ukrainealarm(UA,observed_at="2026-09-14T17:47:00Z",target_city_key="x",region_id="147"),p.canonicalize_ukrainealarm(t2,observed_at="2026-09-14T17:50:00Z",target_city_key="x",region_id="147"),p.canonicalize_ukrainealarm(t3,observed_at="2026-09-14T18:00:00Z",target_city_key="x",region_id="147")];self.assertEqual(len({r["snapshot"]["snapshot_key"] for r in rs}),4);ints=p.component_intervals(rs);red=[x for x in ints if x["reason_raw"].startswith("Ракетна")][0];self.assertIsNone(red["source_ended_at"]);self.assertEqual(red["end_basis"],p.schema.END_SNAPSHOT)
 def test_16_http_failure(self):
  with patch("urllib.request.urlopen",side_effect=urllib.error.URLError("offline")):self.assertRaises(urllib.error.URLError,p.fetch_json,"https://example.invalid")
 def test_17_invalid_json(self):
  self.assertRaises(json.JSONDecodeError,json.loads,"{bad")
 def test_18_source_failure_isolated(self):
  s=self.store();good=p.bind(p.canonicalize_ukrainealarm(UA,observed_at="2026-09-14T17:47:00Z",target_city_key="x",region_id="147"),[]);s.persist(good);bad=p.bind(p.canonicalize_alerts_in_ua(AIU,observed_at="2026-09-16T04:43:10Z",target_city_key="x"),[]);self.assertRaises(sqlite3.OperationalError,s.persist,bad,True);self.assertEqual(s.counts(),{"snapshots":1,"observations":2})

if __name__=="__main__":unittest.main(verbosity=2)
