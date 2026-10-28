#!/usr/bin/env python3
"""C4-E3 strict bidirectional frozen-Git <-> read-only Neon JSONL parity verifier.

Inputs are separately acquired; never make Neon the expectation authority.
A snapshot manifest must attest BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY
for the three exported Neon tables, or the result is NOT_CERTIFIED.
Run: python3 verify_c4_e3.py --inputs ./inputs --out ./result
"""
import argparse, csv, datetime, hashlib, json
from collections import Counter
from pathlib import Path

COHORTS = ("H1", "H2")
KINDS = {"classifications": "classification_key", "sources": "source_link_key", "events": "attack_event_key"}
DENOMINATORS = {"H1": (6863, 2340, 119), "H2": (19542, 1429, 961)}
FIELDS = {
 "classifications": ["classification_uid","classification_key_version","classification_key","historical_episode_id","city_key","alert_type","alert_start_at","alert_end_at","verdict","is_event","positive_tier","event_types","qa_reasons_state","qa_reasons","classifier_reason_codes","classifier_blob_sha","classifier_methodology_version","normalization_version","evidence_set_sha256","review_provenance_sha256","human_review_state","origin_provenance_sha256","binding_state","alert_episode_uid"],
 "sources": ["source_link_key_version","source_link_key","classification_key","observation_id","source_family","source_type","source_url","telegram_channel","telegram_message_id","source_timestamp","event_timestamp_if_stated","excerpt","content_sha256","content_hash_basis","observation_classification_outcome","classification_episode_id","evidence_payload","retrieval_provenance"],
 "events": ["attack_event_key_version","attack_event_key","event_grain","historical_episode_id","city_key","alert_type","alert_start_at","alert_end_at","event_status","current_classification_key","binding_state","alert_episode_uid"]
}
TIME_FIELDS = {"alert_start_at","alert_end_at","source_timestamp","event_timestamp_if_stated"}
JSON_FIELDS = {"qa_reasons","evidence_payload","retrieval_provenance"}
SET_FIELDS = {"event_types","classifier_reason_codes"}
NA = object()

def normalize(field, value):
    if value is None:
        return None
    if field in TIME_FIELDS:
        if not isinstance(value, str):
            raise ValueError("timestamp must be an offset-aware ISO string: " + field)
        dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None or dt.utcoffset() is None:
            raise ValueError("naive timestamp not allowed")
        return dt.astimezone(datetime.timezone.utc).isoformat(timespec="microseconds")
    if field in JSON_FIELDS:
        if isinstance(value, str):
            value = json.loads(value)
        return json.dumps(value, sort_keys=True, separators=(",",":"), ensure_ascii=False)
    if field in SET_FIELDS:
        if not isinstance(value, list):
            raise ValueError("set-valued field is not array")
        if len(set(map(str, value))) != len(value):
            raise ValueError("duplicate set member")
        return sorted(value)
    return value

def load_jsonl(path):
    rows = []
    with path.open(encoding="utf-8") as h:
        for i, line in enumerate(h, 1):
            if line.strip():
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError(f"{path}:{i}: non-object")
                rows.append(row)
    return rows

def compare(inputs, output):
    output.mkdir(parents=True, exist_ok=True)
    anomalies = []
    counts = {}
    missing_inputs = []
    def add(cohort, kind, key, field, expected, actual, typ, source):
        anomalies.append({"cohort":cohort,"kind":kind,"exact_uid_key":str(key),
          "field":field,"expected":json.dumps(expected,ensure_ascii=False,default=str),
          "actual":json.dumps(actual,ensure_ascii=False,default=str),
          "frozen_git_blob":source,"reason":typ})
    for cohort in COHORTS:
        counts[cohort] = {}
        for idx, (kind, key_field) in enumerate(KINDS.items()):
            expfile = inputs / f"{cohort}_{kind}_expected.jsonl"
            actfile = inputs / f"{cohort}_{kind}_neon.jsonl"
            if not expfile.exists() or not actfile.exists():
                missing = [str(p) for p in (expfile,actfile) if not p.exists()]
                missing_inputs.extend(missing)
                counts[cohort][kind] = {"status":"NOT_PROVABLE","required_files_missing":missing}
                for f in missing:
                    add(cohort,kind,"*", "input",f,None,"NOT_PROVABLE_REQUIRED_INPUT_ABSENT",None)
                continue
            exp, act = load_jsonl(expfile),load_jsonl(actfile)
            refs = [r.get("_frozen_git_blob") for r in exp]
            if any(not v for v in refs):
                add(cohort,kind,"*","_frozen_git_blob","each expected row must have independent Git SHA",None,"NOT_PROVABLE_GIT_PROVENANCE_ABSENT",None)
            ecounts, acounts = Counter(r.get(key_field) for r in exp), Counter(r.get(key_field) for r in act)
            for rows, cts, label in ((exp,ecounts,"expected"),(act,acounts,"actual")):
                for key, n in cts.items():
                    if key is None or n != 1:
                        add(cohort,kind,key,key_field,1,n,"DUPLICATE_OR_NULL_KEY_"+label.upper(),None)
            emap={r.get(key_field):r for r in exp}
            amap={r.get(key_field):r for r in act}
            for key in sorted(emap.keys()-amap.keys(),key=str):
                add(cohort,kind,key,"record",emap[key],None,"MISSING_IN_NEON",emap[key].get("_frozen_git_blob"))
            for key in sorted(amap.keys()-emap.keys(),key=str):
                add(cohort,kind,key,"record",None,amap[key],"EXTRA_IN_NEON",None)
            for key in sorted(emap.keys() & amap.keys(),key=str):
                e,a=emap[key],amap[key]
                for field in FIELDS[kind]:
                    if field not in e:
                        add(cohort,kind,key,field,"FROZEN_FIELD_ABSENT",a.get(field),"NOT_PROVABLE_FROZEN_FIELD_ABSENT",e.get("_frozen_git_blob"))
                        continue
                    if field not in a:
                        add(cohort,kind,key,field,e[field],"NEON_FIELD_ABSENT","NOT_PROVABLE_NEON_EXPORT_FIELD_ABSENT",e.get("_frozen_git_blob"))
                        continue
                    try:
                        x,y=normalize(field,e[field]),normalize(field,a[field])
                        if x != y:
                            add(cohort,kind,key,field,e[field],a[field],"FIELD_MISMATCH",e.get("_frozen_git_blob"))
                    except (ValueError,TypeError) as ex:
                        add(cohort,kind,key,field,e[field],a[field],"NORMALIZATION_REJECTED:"+str(ex),e.get("_frozen_git_blob"))
            counts[cohort][kind]={"expected":len(exp),"actual":len(act),
                "denominator":DENOMINATORS[cohort][idx],
                "missing":len(emap.keys()-amap.keys()),"extra":len(amap.keys()-emap.keys()),
                "duplicate_expected":sum(n-1 for n in ecounts.values() if n>1),
                "duplicate_actual":sum(n-1 for n in acounts.values() if n>1)}
            if len(exp)!=DENOMINATORS[cohort][idx]:
                add(cohort,kind,"*","denominator",DENOMINATORS[cohort][idx],len(exp),"FROZEN_DENOMINATOR_MISMATCH",None)
    snapshot=inputs/"neon_snapshot_manifest.json"
    snapshot_ok=False
    if snapshot.exists():
        m=json.loads(snapshot.read_text(encoding="utf-8"))
        snapshot_ok=bool(m.get("repeatable_read_read_only") and m.get("single_transaction_all_six_exports") and m.get("read_only_replica") and m.get("server_snapshot_id"))
    if not snapshot_ok:
        add("ALL","snapshot","*","consistency","single repeatable read read-only snapshot",None,"NOT_PROVABLE_SNAPSHOT_ATTESTATION_ABSENT",None)
    exceptions=inputs/"25_unbound_expected.json"
    if not exceptions.exists():
        add("ALL","UNBOUND","*","25_parent_exceptions","Git-frozen exact 25 UID registry",None,"NOT_PROVABLE_25_REGISTRY_INPUT_ABSENT",None)
    else:
        xx=json.loads(exceptions.read_text(encoding="utf-8"))
        if len(xx)!=25 or len(set(str(x["classification_uid"]) for x in xx))!=25:
            add("ALL","UNBOUND","*","denominator",25,len(xx),"EXCEPTION_DENOMINATOR_INVALID",None)
        actual_cls={}
        for cohort in COHORTS:
            f=inputs/f"{cohort}_classifications_neon.jsonl"
            if f.exists():
                actual_cls.update({r.get("classification_uid"):r for r in load_jsonl(f)})
        for x in xx:
            uid=x["classification_uid"]; row=actual_cls.get(uid)
            if row is None:
                add(x.get("cohort"),"UNBOUND",uid,"classification_uid",uid,None,"MISSING_IN_NEON",x.get("_frozen_git_blob"))
            elif row.get("binding_state")!="UNBOUND" or row.get("alert_episode_uid") is not None:
                add(x.get("cohort"),"UNBOUND",uid,"binding_state/alert_episode_uid","UNBOUND/NULL",str((row.get("binding_state"),row.get("alert_episode_uid"))),"FIELD_MISMATCH",x.get("_frozen_git_blob"))
    categories=Counter(r["reason"].split(":")[0] for r in anomalies)
    result={"verdict":"C4_PASS_CANDIDATE" if not anomalies and snapshot_ok else "C4_PARTIAL",
      "certified":not anomalies and snapshot_ok,"counts":counts,"mismatch_categories":dict(categories),
      "missing_required_inputs":missing_inputs,
      "snapshot_certified":snapshot_ok,
      "caution":"Never infer owner acceptance of 25 parent exceptions; this verifier cannot authorize it."}
    with (output/"c4_e3_mismatches.csv").open("w",newline="",encoding="utf-8") as h:
        w=csv.DictWriter(h,fieldnames=["cohort","kind","exact_uid_key","field","expected","actual","frozen_git_blob","reason"]); w.writeheader(); w.writerows(anomalies)
    (output/"c4_e3_exact_field_parity.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"verdict":result["verdict"],"categories":result["mismatch_categories"]}))
    return result
if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--inputs",type=Path,required=True); p.add_argument("--out",type=Path,required=True)
    a=p.parse_args(); compare(a.inputs,a.out)
