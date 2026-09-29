import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
import proof_differentiated_alert_schema_v2 as p
F=ROOT/'tests/fixtures/differentiated_alerts'
def load(n):return json.loads((F/n).read_text())
class T(unittest.TestCase):
 def ua(self,n,t):return p.ua(load(n),observed_at=t,target_city_key='chernihiv',region_id='R1')
 def test_case_a(self):
  a=self.ua('ukrainealarm_t0_yellow.json','2026-09-29T09:10:00Z');z=self.ua('ukrainealarm_t3_clear.json','2026-09-29T09:40:00Z');self.assertTrue(a['snapshot']['source_active']);self.assertFalse(z['snapshot']['source_active']);self.assertEqual(len(a['threat_observations']),1)
 def test_case_b_overlap_one_parent(self):
  xs=[self.ua('ukrainealarm_t0_yellow.json','2026-09-29T09:10:00Z'),self.ua('ukrainealarm_t1_yellow_red.json','2026-09-29T09:20:00Z'),self.ua('ukrainealarm_t2_yellow.json','2026-09-29T09:30:00Z'),self.ua('ukrainealarm_t3_clear.json','2026-09-29T09:40:00Z')]
  self.assertEqual([len(x['threat_observations']) for x in xs],[1,2,1,0]);it=p.intervals(xs);self.assertEqual(len(it),2);red=[x for x in it if x['reason_raw']=='Ракетна загроза'][0];self.assertEqual(red['end_basis'],p.END_SNAPSHOT);self.assertIsNone(red['derived_end_at']);self.assertEqual((red['end_lower_bound'],red['end_upper_bound']),('2026-09-29T09:20:00Z','2026-09-29T09:30:00Z'))
 def test_case_c_same_severity_multiple_causes(self):
  raw={'id':'c','location_uid':'R1','location_type':'raion','started_at':'2026-09-29T09:00:00Z','finished_at':None,'updated_at':'2026-09-29T09:20:00Z','alert_type':'AIR','alert_level':'red','threats':[{'threat_type':'unspecified_missiles','level':'red','started_at':'2026-09-29T09:05:00Z','source_message':'missile'},{'threat_type':'drones','level':'red','started_at':'2026-09-29T09:18:00Z','source_message':'drone'}]}
  x=p.aiu(raw,observed_at='2026-09-29T09:20:00Z',target_city_key='x');self.assertEqual(len(x['threat_observations']),2);self.assertEqual({r['severity_normalized'] for r in x['threat_observations']},{'red'});self.assertEqual({r['threat_type_normalized'] for r in x['threat_observations']},{'missile_unspecified','drone'});self.assertEqual(p.effective(x)['effective_severity'],'red')
 def test_case_d_repeat_poll_no_fake_start(self):
  a=self.ua('ukrainealarm_t0_yellow.json','2026-09-29T09:10:00Z');b=self.ua('ukrainealarm_t0_yellow.json','2026-09-29T09:11:00Z');it=p.intervals([a,b]);self.assertEqual(len(it),1);self.assertEqual(it[0]['first_seen_active_at'],'2026-09-29T09:10:00Z');self.assertEqual(it[0]['last_seen_active_at'],'2026-09-29T09:11:00Z')
 def test_case_e_disappear_is_uncertain(self):
  a=self.ua('ukrainealarm_t1_yellow_red.json','2026-09-29T09:20:00Z');b=self.ua('ukrainealarm_t2_yellow.json','2026-09-29T09:30:00Z');red=[x for x in p.intervals([a,b]) if x['reason_raw']=='Ракетна загроза'][0];self.assertIsNone(red['source_ended_at']);self.assertIsNone(red['derived_end_at']);self.assertEqual(red['end_basis'],p.END_SNAPSHOT)
 def test_case_f_episode_close(self):
  a=p.kyiv(load('kyiv_drone_only.json'),observed_at='2026-09-29T10:00:00Z');it=p.intervals([a],episode_end_at='2026-09-29T10:10:00Z');self.assertEqual(it[0]['end_basis'],p.END_EPISODE);self.assertIsNone(it[0]['derived_end_at'])
 def test_case_g_restart_replay_idempotent(self):
  a=self.ua('ukrainealarm_t1_yellow_red.json','2026-09-29T09:20:00Z');b=self.ua('ukrainealarm_t1_yellow_red.json','2026-09-29T09:20:00Z');self.assertEqual(a['snapshot']['snapshot_key'],b['snapshot']['snapshot_key']);self.assertEqual([x['observation_key'] for x in a['threat_observations']],[x['observation_key'] for x in b['threat_observations']])
 def test_case_h_cross_source_independent(self):
  u=self.ua('ukrainealarm_t1_yellow_red.json','2026-09-29T09:20:00Z');a=p.aiu(load('alerts_in_ua_multi_threat.json'),observed_at='2026-09-29T09:20:00Z',target_city_key='chernihiv');self.assertNotEqual(u['snapshot']['source'],a['snapshot']['source']);self.assertNotEqual({x['component_signature'] for x in u['threat_observations']},{x['component_signature'] for x in a['threat_observations']})
 def test_alerts_parent_level_separate(self):
  a=p.aiu(load('alerts_in_ua_multi_threat.json'),observed_at='2026-09-29T09:20:00Z',target_city_key='chernihiv');self.assertEqual(a['snapshot']['source_alert_level_raw'],'red');self.assertEqual([x['level_raw'] for x in a['threat_observations']],['red','yellow'])
 def test_kyiv_multiple_no_fake_start_or_level(self):
  a=p.kyiv(load('kyiv_multi_cause.json'),observed_at='2026-09-29T10:00:00Z');self.assertEqual(len(a['threat_observations']),2);self.assertTrue(all(x['source_started_at'] is None and x['level_raw'] is None for x in a['threat_observations']))
 def test_missile_drone_not_exploded(self):
  a=p.kyiv(load('kyiv_missile_drone.json'),observed_at='2026-09-29T10:00:00Z');self.assertEqual(len(a['threat_observations']),1);self.assertEqual(a['threat_observations'][0]['threat_type_normalized'],'missile_drone_combined')
 def test_all_threats_disappear_air_active(self):
  a=p.kyiv(load('kyiv_drone_only.json'),observed_at='2026-09-29T10:00:00Z');b=p.kyiv(load('kyiv_active_no_causes.json'),observed_at='2026-09-29T10:05:00Z');it=p.intervals([a,b]);self.assertTrue(b['snapshot']['source_active']);self.assertEqual(it[0]['end_basis'],p.END_SNAPSHOT)
 def test_poll_gap_bounds(self):
  a=self.ua('ukrainealarm_t1_yellow_red.json','2026-09-29T10:05:00Z');b=self.ua('ukrainealarm_t2_yellow.json','2026-09-29T10:20:00Z');red=[x for x in p.intervals([a,b]) if x['reason_raw']=='Ракетна загроза'][0];self.assertEqual((red['end_lower_bound'],red['end_upper_bound']),('2026-09-29T10:05:00Z','2026-09-29T10:20:00Z'))
 def test_changed_message_same_component(self):
  raw=load('alerts_in_ua_multi_threat.json');a=p.aiu(raw,observed_at='2026-09-29T09:20:00Z',target_city_key='x');raw2=json.loads(json.dumps(raw));raw2['threats'][0]['source_message']='changed';b=p.aiu(raw2,observed_at='2026-09-29T09:21:00Z',target_city_key='x');x=next(r for r in a['threat_observations'] if r['cause_raw']=='drones');y=next(r for r in b['threat_observations'] if r['cause_raw']=='drones');self.assertEqual(x['component_signature'],y['component_signature']);self.assertNotEqual(x['observation_key'],y['observation_key'])
 def test_bind_states_and_no_mutation(self):
  r=p.kyiv(load('kyiv_drone_only.json'),observed_at='2026-09-29T10:00:00Z');eps=[{'episode_id':'e1','city_key':'kyiv','alert_type':'AIR','start_at':'2026-09-29T09:30:00Z','end_at':'2026-09-29T10:20:00Z'}];before=json.dumps(eps,sort_keys=True);self.assertEqual(p.bind(r,eps)['snapshot']['binding_state'],'BOUND');self.assertEqual(before,json.dumps(eps,sort_keys=True));self.assertEqual(p.bind(r,[])['snapshot']['binding_state'],'UNBOUND');self.assertEqual(p.bind(r,eps+[{**eps[0],'episode_id':'e2'}])['snapshot']['binding_state'],'AMBIGUOUS')
 def test_geography_separate_target(self):
  a=self.ua('ukrainealarm_t0_yellow.json','2026-09-29T09:10:00Z');self.assertEqual(a['snapshot']['source_geography']['scope'],'RAION');self.assertEqual(a['snapshot']['target_city_key'],'chernihiv')
 def test_effective_severity(self):
  a=self.ua('ukrainealarm_t1_yellow_red.json','2026-09-29T09:20:00Z');self.assertEqual(p.effective(a),{'effective_severity':'red','basis':'COMPONENT_MAX'})
 def test_parent_entity_unchanged(self): self.assertEqual(p.entities()['alert_episode'],'EXISTING_PARENT_UNCHANGED')
 def test_source_explicit_end_distinct(self):
  a=self.ua('ukrainealarm_t0_yellow.json','2026-09-29T09:10:00Z');a['threat_observations'][0]['source_ended_at']='2026-09-29T09:12:00Z';it=p.intervals([a]);self.assertEqual(it[0]['end_basis'],p.END_SOURCE);self.assertEqual(it[0]['derived_end_at'],'2026-09-29T09:12:00Z')
 def test_array_order_component_signatures(self):
  raw=load('alerts_in_ua_multi_threat.json');a=p.aiu(raw,observed_at='2026-09-29T09:20:00Z',target_city_key='x');raw['threats'].reverse();b=p.aiu(raw,observed_at='2026-09-29T09:20:00Z',target_city_key='x');self.assertEqual({x['component_signature'] for x in a['threat_observations']},{x['component_signature'] for x in b['threat_observations']})
if __name__=='__main__':unittest.main()
