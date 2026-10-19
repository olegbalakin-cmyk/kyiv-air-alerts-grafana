#!/usr/bin/env python3
"""Verify exact original PG18 A/B ZIP and JSON evidence, reject corruption."""
import hashlib, json, sys, zipfile
from pathlib import Path

R=Path(__file__).resolve().parent
EXPECTED={
"A":{"zip":"2b1a25077c3fbccd72e45032184dca15fcdefb86166cd9a8b8f360dd396636d0",
"json":"e77d27c99ea25b55fe24497381a9b14f17781ea239474737dcc7bfc052720b84",
"artifact_id":12219934083,"job_id":118298743563},
"B":{"zip":"e3eb64fca6c90052c16849ddc5cc0ce3b549a4a3306ec4ae24a51b7096abceb8",
"json":"28e72763334b92925fb9c20ccead204f56a95e629565d29a3a0970b2883c84ec",
"artifact_id":12220721947,"job_id":118298743705}}
TESTED="96b1d7b894fb11f7a5f1fd899d4ba5d3d822f5d9"
RUN=39322183236

def digest(b):return hashlib.sha256(b).hexdigest()

def inspect_payload(copy, zdata, jdata):
    p=EXPECTED[copy]
    assert digest(zdata)==p["zip"], ("ZIP mismatch",copy,digest(zdata))
    assert digest(jdata)==p["json"], ("JSON mismatch",copy,digest(jdata))
    import io
    with zipfile.ZipFile(io.BytesIO(zdata)) as archive:
        assert archive.testzip() is None
        assert archive.namelist()==["h2_mutation_report.json"],archive.namelist()
        assert archive.read("h2_mutation_report.json")==jdata
    j=json.loads(jdata)
    assert j["copy"]==copy and j["schema"]=="h2-offline-mutation-operational-v1"
    assert j["test_commit"]==TESTED
    assert j["pg_version"].startswith("18.6")
    assert j["operational_writer_git_blob"]=="0118ca9e5f1308173e657257f1b49fe91cc19fe1"
    assert j["assertions_total"]==83 and j["assertions_passed"]==83
    assert not j["unexpected"] and not j["failed_assertions"]
    assert j["harness_verdict"]=="EXECUTED_COMPLETE"
    assert [case["id"] for case in j["cases"]]==["A1","A2","A3","A4","A5","OP","COMMIT"]
    assert len(j["assertions"])==83
    assert all(x["pass"] and x["expected"]==x["observed"] for x in j["assertions"])
    names={x["name"] for x in j["assertions"]}
    for k in ["A2.rejection_is_CAS_not_unique","A3.detect_head_mismatch",
              "A4.two_tips_detected","A4.duplicate_successor_detected",
              "A5.owner_update_executed","A5.owner_trigger_disable_executed",
              "A5.owner_DDL_executed","A5.owner_delete_executed",
              "A5.owner_truncate_executed","OP.initial_classification_durable",
              "OP.source_link_durable","OP.revision_inserted","OP.concurrent_graph_consistent",
              "OP.concurrent_no_expected_tip_reject","COMMIT.own_batch_independent_visible",
              "COMMIT.explicit_commit_second_connection",
              "COMMIT.external_rollback_undoes_return"]:
        assert k in names,(copy,k)
    return {"artifact_id":p["artifact_id"],"job_id":p["job_id"],
            "zip_size":len(zdata),"zip_sha256":p["zip"],
            "report_size":len(jdata),"report_sha256":p["json"],
            "assertions":j["assertions_total"],
            "trace_count":len(j["traces"]),"cases":[c["id"] for c in j["cases"]]}

def main():
    outputs={}
    for copy in ("A","B"):
        z=(R/("original_"+copy+".zip")).read_bytes()
        j=(R/("original_"+copy+".json")).read_bytes()
        outputs[copy]=inspect_payload(copy,z,j)
    manifest={"source_run_id":RUN,"source_test_commit":TESTED,
              "source_workflow_run_conclusion":"success",
              "report_verification":"EXACT_SHA256_AND_CRC_AND_FULL_83_ASSERTIONS",
              "scope":"two ephemeral synthetic PostgreSQL 18.6 containers; not Neon",
              "results":outputs}
    if "--write-manifest" in sys.argv:
        (R/"AB_original_evidence_manifest.json").write_text(
            json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
            encoding="utf-8")
    else:
        actual=json.loads((R/"AB_original_evidence_manifest.json").read_text())
        assert manifest==actual
    print("PASS_GIT_ONLY", json.dumps(manifest,sort_keys=True))
if __name__=="__main__":main()
