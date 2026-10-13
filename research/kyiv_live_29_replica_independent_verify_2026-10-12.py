#!/usr/bin/env python3
"""Independent verification of the frozen redacted database readback, not the primary output."""
import collections, csv, datetime as dt, hashlib, json, pathlib, sys

ROOT=pathlib.Path("replica_audit_results")
def h(x):return hashlib.sha256(x).hexdigest()
def load(p):return json.loads((ROOT/p).read_bytes())
def utc(x):
    if x is None:return None
    z=dt.datetime.fromisoformat(str(x).replace("Z","+00:00"))
    return z.astimezone(dt.timezone.utc)
def check(cond,reason):
    if not cond:raise ValueError(reason)
def main():
    raw=load("04_canonical_readback_redacted.json")
    report=load("05_kyiv_29_reconciliation.json")
    access=load("01_replica_identity_and_access.json")
    att=load("02_readonly_transaction_attestation.json")
    check(access.get("actual_connection_verified") is True and access.get("driver_actual_host")=="ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech","REPLICA_IDENTITY")
    check(access.get("verified_endpoint_type")=="read_only" and att.get("transaction_read_only")=="on" and att.get("isolation")=="repeatable read","SERVER_READ_ONLY")
    source=raw["frozen_identities"]
    check(len(source)==29 and len({x["episode_id"] for x in source})==29,"FROZEN_COHORT")
    check(len(report["episodes"])==29 and len({x["episode_id"] for x in report["episodes"]})==29,"OUTPUT_COHORT")
    check({(x["city_key"],x["episode_id"],utc(x["alert_start"]),utc(x["alert_end"])) for x in source}=={(x["city_key"],x["episode_id"],utc(x["alert_start"]),utc(x["alert_end"])) for x in report["episodes"]},"EXACT_COHORT_CROSSWALK")
    tabs=raw["tables"]
    for name in ["alert_episodes","attack_event_classifications","attack_event_sources","attack_events"]:
        check(isinstance(tabs.get(name),list),f"TABLE_MISSING:{name}")
    cl=tabs["attack_event_classifications"];p=tabs["alert_episodes"];l=tabs["attack_event_sources"];e=tabs["attack_events"]
    all_cids={str(x["classification_uid"]) for x in cl}
    check(all(str(x["classification_uid"]) in all_cids for x in l),"SOURCE_ORPHAN_IN_READBACK")
    own=[]
    for src in source:
        eid=src["episode_id"]
        pp=[x for x in p if x["city_key"]=="kyiv" and str(x["legacy_episode_id"])==eid]
        exact=[x for x in pp if x["alert_type"]=="AIR" and x["episode_state"]=="closed" and x["canonicalization_version"]=="alert-canonicalization-v1" and utc(x["start_at"])==utc(src["alert_start"]) and utc(x["end_at"])==utc(src["alert_end"])]
        c0=[x for x in cl if x["city_key"]=="kyiv" and str(x["historical_episode_id"])==eid]
        cc=[x for x in c0 if utc(x["alert_start_at"])==utc(src["alert_start"]) and utc(x["alert_end_at"])==utc(src["alert_end"]) and x.get("alert_type") in ("AIR",None)]
        ids={str(x["classification_uid"]) for x in cc}
        predecessors={str(x["supersedes_classification_uid"]) for x in cc if x.get("supersedes_classification_uid")}
        tips=[x for x in cc if str(x["classification_uid"]) not in predecessors]
        ss=[x for x in l if str(x["classification_uid"]) in ids]
        ee=[x for x in e if x["city_key"]=="kyiv" and str(x["historical_episode_id"])==eid]
        check(len({x["classification_uid"] for x in cc})==len(cc),f"CLASS_UID_DUPLICATE:{eid}")
        check(len({x["source_link_key"] for x in ss})==len(ss),f"SOURCE_DUPLICATE:{eid}")
        check(all(x.get("supersedes_classification_uid") in (None,"") or str(x["supersedes_classification_uid"]) in ids for x in cc),f"SUPERSESSION_OUT_OF_SCOPE:{eid}")
        q=next(x for x in report["episodes"] if x["episode_id"]==eid)
        expected={"canonical_parent_count_for_episode_id":len(pp),"canonical_exact_parent_count":len(exact),"classification_revisions":len(cc),"classification_outside_exact_tuple":len(c0)-len(cc),"current_tip_count":len(tips),"source_links_count":len(ss),"event_count":len(ee)}
        for k,v in expected.items():check(q[k]==v,f"INDEPENDENT_COUNT:{eid}:{k}")
        check(set(q["current_tip_uids"])=={str(x["classification_uid"]) for x in tips},f"TIP_UID:{eid}")
        check(set(q["source_link_keys"])=={str(x["source_link_key"]) for x in ss},f"SOURCE_KEYS:{eid}")
        check(set(q["event_uids"])=={str(x["attack_event_uid"]) for x in ee},f"EVENT_UID:{eid}")
        check(set(q["canonical_parent_uids"])=={str(x["episode_uid"]) for x in exact},f"PARENT_UID:{eid}")
        own.append(q)
    cnt=dict(sorted(collections.Counter(x["disposition"] for x in own).items()))
    check(cnt==report["summary"]["dispositions"],"DISPOSITION_COUNTS")
    check(sum(x["canonical_exact_parent_count"]==1 for x in own)==report["summary"]["exact_parent_count"],"PARENT_SUMMARY")
    check(sum(x["classification_revisions"] for x in own)==report["summary"]["classification_revisions"],"REVISION_SUMMARY")
    check(sum(x["current_tip_count"]==1 for x in own)==report["summary"]["episodes_with_unique_current_tip"],"TIP_SUMMARY")
    check(sum(x["source_links_count"] for x in own)==report["summary"]["source_links"],"SOURCE_SUMMARY")
    check(sum(x["event_count"] for x in own)==report["summary"]["event_records"],"EVENT_SUMMARY")
    with (ROOT/"06_kyiv_29_reconciliation.csv").open(encoding="utf-8",newline="") as f:
        records=list(csv.DictReader(f))
    check(len(records)==29 and {r["episode_id"] for r in records}=={r["episode_id"] for r in source},"CSV_CROSSWALK")
    rawhash=h((ROOT/"04_canonical_readback_redacted.json").read_bytes())
    return {"result":"PASS","method":"independent direct raw redacted readback traversal; no SQL; independently re-evaluates parent, revision, tip, source-link, event identities and CSV","same_readback_sha256":rawhash,"verified_episodes":29,"disposition_counts":cnt,"checks":["FROZEN_COHORT","EXACT_COHORT_CROSSWALK","REPLICA_IDENTITY","SERVER_READ_ONLY","PARENT_CARDINALITIES","CURRENT_TIP_IDS","SUPERSESSION_REFERENCES","SOURCE_LINK_INTEGRITY","EVENT_UIDS","TOTALS","CSV_CROSSWALK"]}
if __name__=="__main__":
    try:
        o=main()
        (ROOT/"09_independent_verification.json").write_text(json.dumps(o,sort_keys=True,indent=2)+"\n",encoding="utf-8")
        manifest={p.name:{"sha256":h(p.read_bytes()),"bytes":p.stat().st_size} for p in sorted(ROOT.iterdir()) if p.is_file() and p.name!="10_manifest.json"}
        (ROOT/"10_manifest.json").write_text(json.dumps({"members":manifest,"a_b_same_frozen_readback":True},sort_keys=True,indent=2)+"\n",encoding="utf-8")
        print("INDEPENDENT_VERIFIER_PASS "+json.dumps(o,sort_keys=True))
        print("OUTPUT_MEMBER_HASHES "+json.dumps(manifest,sort_keys=True))
    except Exception as ex:
        print("INDEPENDENT_VERIFIER_BLOCKED "+str(ex)[:180],file=sys.stderr)
        sys.exit(3)
