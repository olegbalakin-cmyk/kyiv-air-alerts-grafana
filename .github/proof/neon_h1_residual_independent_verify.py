#!/usr/bin/env python3
"""Independent residual H1 verifier: only original Git records and exact original keys."""
import collections,hashlib,json,subprocess,sys
from pathlib import Path
CAMP="71cb6f6fbe856cc7b96759310fe9cc9c71cc0453"
REP="5d18ef85a66384f189ede5ca5654d750f60f088b"
SEM="79d9fbbfffe64ba8be3535f78a47872b65092f5d"
def run(*args):return subprocess.check_output(["git",*args])
def sha(b):return hashlib.sha256(b).hexdigest()
def get(commit,path):return json.loads(run("show",commit+":"+path))
def ok(x,label):
 if not x:raise AssertionError(label)
p=Path(sys.argv[1]);data=p.read_bytes();x=json.loads(data)
repair=get(REP,"research/historical_offline_repair_recovery_scan_2026-10-02.json")
semantic=get(SEM,"research/neon_h1_47_semantic_adjudication_2026-10-12.json")
r={(v["city"],v["episode_id"]):v for v in repair["targets"]["changed_targets"]}
r_obs={v["observation_id"]:v for v in repair["observations"]["changed_observations"]}
original={};obs={};path_map={}
for m in x["batch_manifest"]:
 path=m["path"];blob=run("rev-parse",CAMP+":"+path).decode().strip()
 ok(blob==m["blob"],"BLOB_DRIFT")
 b=get(CAMP,path)
 for row in b["episode_results"]:
  k=(b["city_key"],row["episode_id"])
  ok(k not in original,"DUP_ORIGINAL_EPISODE")
  original[k]=row;path_map[k]=path
 for row in b["observations"]:
  oid=row["observation_id"];ok(oid not in obs,"DUP_ORIGINAL_OBSERVATION");obs[oid]=row
ok(len(original)==6863 and len(r)==25,"HISTORICAL_COUNTS")
classes=x["classifications"];links=x["source_links"];events=x["modeled_event_relationships"]
ok(len(classes)==6863 and len(links)==2340 and len(events)==119,"ALL_COUNTS")
classidx={(v["city_key"],v["historical_episode_id"]):v for v in classes}
linkidx={(v["city_key"],v["historical_episode_id"],v["observation_id"]):v for v in links}
eventidx={(v["city_key"],v["historical_episode_id"]):v for v in events}
ok(len(classidx)==6863 and len(linkidx)==2340 and len(eventidx)==119,"IDENTITY_UNIQUE")
flagged={(v["city_key"],v["historical_episode_id"],v["source_observation_id"]):v for v in semantic["47_case_decision_ledger"]}
ok(len(flagged)==47,"FLAG_47")
for key,row in original.items():
 c=classidx[key];rep=r.get(key)
 ok(c["source_field_sha256"]==sha(json.dumps(row,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()),"SOURCE_ROW_HASH")
 ok(c["origin_batch_path"]==path_map[key],"SOURCE_ROW_ORIGIN")
 ok(c["fields"]["verdict"]==("ACCEPTED_REPAIR_OVERLAY" if rep else "ORIGINAL_ACCEPTED"),"VERDICT_AUTHORITY")
 ok(c["fields"]["qa_reasons"]=="ORIGINAL_ACCEPTED","QA_AUTHORITY")
 ok(c["fields"]["classifier_blob_sha"]==("ACCEPTED_REPAIR_OVERLAY" if rep else "ORIGINAL_ACCEPTED"),"CLASSIFIER_AUTHORITY")
 expected=set(row.get("source_observation_ids") or [])|set(rep.get("contributing_observation_ids",[]) if rep else [])
 attached={z[2] for z in linkidx if z[:2]==key}
 ok(expected==attached,"SOURCE_RELATIONSHIP_WITNESSES")
 for oid in attached:
  l=linkidx[(key[0],key[1],oid)]
  ok(oid in obs,"ORIGINAL_SOURCE_MISSING")
  ok(l["fields"]["observation_id"]=="ORIGINAL_ACCEPTED","SOURCE_ID_AUTHORITY")
  if (key[0],key[1],oid) in flagged:
   expected_cat=flagged[(key[0],key[1],oid)]["exact_membership_historical_authority_verdict"]
   ok(l["fields"]["historical_target_membership"]==expected_cat,"ACCEPTED_SEMANTICS_CHANGED")
  elif oid in row.get("source_observation_ids",[]):
   ok(l["fields"]["historical_target_membership"] in ("ORIGINAL_ACCEPTED","INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT"),"UNEXPECTED_ORIGINAL_CATEGORY")
  else:
   ok(l["fields"]["historical_target_membership"] in ("ACCEPTED_REPAIR_OVERLAY","INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT"),"UNEXPECTED_REPAIR_CATEGORY")
  if not obs[oid].get("source_timestamp"):
   ok(l["fields"]["source_timestamp_utc_instant"]=="NOT_OBSERVABLE","INVENTED_SOURCE_TIME")
  if not l["event_timestamp_precision"]=="OFFSET_AWARE":
   ok(l["fields"]["event_timestamp_utc_instant"]=="NOT_OBSERVABLE","UNSUPPORTED_EVENT_UTC")
 verdict=rep["repaired_outcome"] if rep else row["classifier_result"]
 ok((key in eventidx)==(verdict in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE")),"EVENT_RELATIONSHIP_WRONG")
 if key in eventidx:
  ok(eventidx[key]["fields"]["physical_attack_identity"]=="NOT_OBSERVABLE","PHYSICAL_ATTACK_INFERRED")
  ok(eventidx[key]["fields"]["modeled_event_relationship"]=="INDEPENDENTLY_DERIVABLE_UNDER_FROZEN_CONTRACT","EVENT_RELATIONSHIP_AUTHORITY")
counter=collections.defaultdict(lambda:collections.defaultdict(collections.Counter))
for ent,rows in [("classifications",classes),("source_links",links),("attack_events",events)]:
 for row in rows:
  for f,cat in row["fields"].items():counter[ent][f][cat]+=1
for ent,fields in counter.items():
 for field,cats in fields.items():
  ok(dict(cats)==x["field_counts"][ent][field],"FIELD_AGGREGATE_DRIFT:"+ent+"."+field)
ok(all(x["negative_tests"].values()) and len(x["negative_tests"])>=11,"NEGATIVE_TESTS_NOT_RECORDED")
print("INDEPENDENT_ORIGINAL_GIT_FIELD_VERIFICATION=PASS")
print("INDEPENDENT_CLASSIFICATION_ROWS=6863")
print("INDEPENDENT_SOURCE_LINK_ROWS=2340")
print("INDEPENDENT_MODELED_EVENT_ROWS=119")
print("INDEPENDENT_SHA256="+sha(data))
