#!/usr/bin/env python3
"""Independent raw-Git and frozen readback verifier, no producer imports."""
import json,zipfile,subprocess,datetime as dt,hashlib,pathlib,collections
OUT=pathlib.Path("kyiv_28_results/A")
PIN="92d57bbbfad60e6c09bb92372b1e84f38fa6ced4"
def raw(name):return subprocess.check_output(["git","show",PIN+":kyiv-air-alerts-grafana/data/"+name])
def utc(x):return dt.datetime.fromisoformat(x.replace("Z","+00:00"))
def test():
 state=json.loads(raw("explosion_candidate_monitor_state.json"));q=json.loads(raw("explosion_review_queue.json"));run=json.loads(raw("explosion_candidate_monitor_last_run.json"))
 receipt=json.loads(subprocess.check_output(["git","show","2648aea950f489e5547869ca422e463dda84648d:research/kyiv_live_29_semantic_audit_verified_receipt_2026-10-12.json"]))
 with zipfile.ZipFile("frozen_input/accepted_29_readback.zip") as z:
  d=json.loads(z.read(next(k for k in z.namelist() if k.endswith("05_kyiv_29_reconciliation.json"))))
 rows={x["episode_id"]:x for x in d["episodes"]}
 assert len(rows)==29 and len([x for x in rows.values() if x["classification_revisions"]==0])==28
 assert set(rows)=={x["episode_id"] for x in receipt["episode_rows"]}
 due=0;checked=0
 for eid in rows:
  episode=next(e for e in state["cities"]["kyiv"]["episodes"] if e["episode_id"]==eid)
  for h,check in zip((0,24,72,168),episode["checks"]):
   assert utc(check["due_at"])==utc(episode["alert_end"])+dt.timedelta(hours=h)
   if utc(check["due_at"])<=utc(run["finished_at"]):due+=1
   if check["checked_at"]:checked+=1
 assert (due,checked)==(55,55)
 a=[];seen=set()
 for city,cs in state["cities"].items():
  for e in cs["episodes"]:
   key=city,e["episode_id"]
   if key in seen or e.get("identity_superseded_by_episode_id") or utc(e["alert_end"])<utc("2026-10-07T19:05:00Z"):continue
   seen.add(key);a.append((utc(e["alert_end"]),utc(e["alert_start"]),city,e["episode_id"]))
 a.sort()
 selected=[(x["city"],x["episode_id"]) for x in run["parent_ordering"]["records"]]
 assert len(a)==479 and selected==[(x[2],x[3]) for x in a[:10]]
 control="176a083e264eec607cdb1ea6";target="191d71f593ca42db0c8f5ba4"
 assert [e for city,e in selected if city=="kyiv"]==[control]
 assert run["canonical_persistence"]["episodes_considered"]==0
 targetrows=[(i,x) for i,x in enumerate(q) if isinstance(x.get("classification_evidence"),dict) and x["classification_evidence"].get("classification_episode_id")==target]
 assert len(targetrows)==1 and rows[target]["classification_revisions"]==0 and rows[control]["classification_revisions"]==2
 result=json.loads((OUT/"07_kyiv_28_recovery_assessment.json").read_text())
 assert len(result["unclassified"])==28 and result["classified_control"]["episode_id"]==control
 assert {x["episode_id"] for x in result["unclassified"]}==set(rows)-{control}
 for e in result["unclassified"]:
  assert e["queue_global_rank_at_frozen_run"]>10 and not e["frozen_run_persistence_selected"]
  assert not e["ready_for_canonical_processing"] and e["canonical_classification_revisions"]==0
  assert e["candidate_any_count"]==next(r["unique_candidates_any"] for r in receipt["episode_rows"] if r["episode_id"]==e["episode_id"])
  assert e["candidate_stored_matching_or_classifier_count"]==next(r["unique_candidates_with_stored_match_or_classifier"] for r in receipt["episode_rows"] if r["episode_id"]==e["episode_id"])
 assert result["summary"]["queue_starvation_episode_proven_in_frozen_run"]==28
 assert result["summary"]["required_source_coverage_confirmed_episodes"]==0
 cross=json.loads((OUT/"06_two_episode_cross_layer_provenance.json").read_text())
 assert len(cross[target]["frozen_queue_classifier_target_references"])==1
 assert len(cross[control]["accepted_canonical_revision_provenance_sanitized"])==2
 files=sorted(p for p in OUT.iterdir() if p.is_file())
 manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
 proof={"result":"PASS","independent_source":"original frozen Git plus accepted canonical readback","original_queue_rows":len(q),"canonical_episodes":len(rows),"due_checked":due,"global_eligible":len(a),"selected_ten":len(selected),"unclassified_verified":28,"classifier_target":target,"classified_control":control,"primary_file_sha256":manifest}
 (OUT/"10_independent_verification.json").write_text(json.dumps(proof,sort_keys=True,indent=2)+"\n")
 print("INDEPENDENT_SEMANTIC_VERIFIER_PASS",json.dumps({k:v for k,v in proof.items() if k!="primary_file_sha256"},sort_keys=True))
if __name__=="__main__":test()
