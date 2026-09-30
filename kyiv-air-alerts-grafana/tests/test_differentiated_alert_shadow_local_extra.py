import copy, json, tempfile, unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/"scripts"))
import proof_differentiated_alert_shadow_ingestion as p
F=ROOT/"tests/fixtures/differentiated_alert_shadow"
UA=json.loads((F/"ukrainealarm_overlap_stored_raw_2026-09-14.json").read_text())
AIU=json.loads((F/"alerts_in_ua_stored_raw_2026-09-16.json").read_text())
KYIV=json.loads((F/"kyiv_stored_raw_2026-09-29.json").read_text())

class ExtraLocalFocusedCases(unittest.TestCase):
 def store(self):
  f=tempfile.NamedTemporaryFile(suffix=".sqlite",delete=False);f.close();s=p.ShadowStore(f.name);self.addCleanup(s.close);return s
 def test_19_changed_state_changes_snapshot(self):
  a=p.canonicalize_kyiv(KYIV,observed_at="2026-09-29T09:36:10Z");b=copy.deepcopy(KYIV);b["current"]["causes"]=["missile"];b=p.canonicalize_kyiv(b,observed_at="2026-09-29T09:36:10Z");self.assertNotEqual(a["snapshot"]["snapshot_key"],b["snapshot"]["snapshot_key"])
 def test_20_missing_geography_preserved_as_other(self):
  a=copy.deepcopy(AIU);a["location_type"]=None;r=p.canonicalize_alerts_in_ua(a,observed_at="2026-09-16T04:43:10Z",target_city_key="x");self.assertEqual(r["snapshot"]["source_geography"]["scope"],"OTHER")
 def test_21_parent_fingerprint_deterministic(self):
  c={"x":[{"episode_id":"e2","alert_start":"2026-01-02T00:00:00Z","alert_end":"2026-01-02T01:00:00Z"},{"episode_id":"e1","alert_start":"2026-01-01T00:00:00Z","alert_end":"2026-01-01T01:00:00Z"}]};self.assertEqual(p.parent_fingerprint(c),p.parent_fingerprint(copy.deepcopy(c)))
 def test_22_metric_fingerprint_deterministic(self):
  m={"x":{"denominator":10,"strict":2,"sensitivity":3,"qa":1,"positive_identity":["b","a"]}};self.assertEqual(p.metric_fingerprint(m),p.metric_fingerprint(copy.deepcopy(m)))
 def test_23_clear_persistence(self):
  r=p.bind(p.canonicalize_kyiv({"current":{"state":0,"causes":[],"last_cause":None,"created_at":"2026-09-29 11:13:00"}},observed_at="2026-09-29T11:13:05Z"),[]);s=self.store();self.assertEqual(s.persist(r),{"inserted_snapshots":1,"inserted_observations":0});self.assertEqual(s.counts(),{"snapshots":1,"observations":0})
 def test_24_component_interval_progression(self):
  a=p.canonicalize_ukrainealarm(UA,observed_at="2026-09-14T17:47:00Z",target_city_key="x",region_id="147");b=copy.deepcopy(UA);b["activeAlerts"][0]["activeAlertLevels"]=[];b["activeAlerts"][0]["lastUpdate"]="2026-09-14T17:50:00Z";b=p.canonicalize_ukrainealarm(b,observed_at="2026-09-14T17:50:00Z",target_city_key="x",region_id="147");ints=p.component_intervals([a,b]);self.assertTrue(ints);self.assertTrue(all(x["end_basis"] in {"SNAPSHOT_INFERRED","UNKNOWN"} for x in ints))
 def test_25_effective_severity_red_wins(self):
  r=p.canonicalize_ukrainealarm(UA,observed_at="2026-09-14T17:47:00Z",target_city_key="x",region_id="147");self.assertEqual(p.schema.effective(r),{"effective_severity":"red","basis":"COMPONENT_MAX"})

if __name__=="__main__":unittest.main(verbosity=2)
