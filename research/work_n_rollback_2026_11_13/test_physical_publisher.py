#!/usr/bin/env python3
"""Offline-only positive Work N validation against physical GitHub artifacts.

Creates a synthetic in-memory grant for verification, NEVER a production receipt.
No push, deployment, Neon connection, or non-GitHub source HTTP.
"""
import json
import subprocess
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from scripts import c6_neon_one_shot_publisher as pub
from scripts import c6_neon_final_prepare as work_m

ROOT=Path("/tmp/work-n-physical")
REPO=work_m.REPO

def gh(path):
    return json.loads(subprocess.check_output(["gh","api",f"repos/{REPO}/{path}"]))

def main():
    l=ROOT/"work-l"
    f=ROOT/"work-m-final"
    a=ROOT/"work-m-report"
    for ident,dest in ((14020616892,l),(14025629654,f),(14025729121,a)):
        dest.mkdir(exist_ok=True)
        with zipfile.ZipFile(ROOT/f"{ident}.zip") as z:
            for item in z.infolist():
                p=Path(item.filename)
                assert not p.is_absolute() and ".." not in p.parts
                assert item.file_size<=64*1024*1024
            z.extractall(dest)
    proofs=list(l.rglob("sha256_manifest.json"))
    reports=list(a.rglob("PREPARE_REPORT.json"))
    assert len(proofs)==len(reports)==1
    proof=proofs[0].parent
    released=[p for p in f.rglob("RELEASE_MANIFEST.json")]
    assert len(released)==1
    released=released[0].parent
    report=json.loads(reports[0].read_text())
    manifest=json.loads((released/"RELEASE_MANIFEST.json").read_text())
    binding=json.loads((released/"RELEASE_BINDING.json").read_text())
    gate=json.loads((proof/"historical_freshness_gate.json").read_text())
    from scripts.c6_neon_publication_gate import utc
    now=utc(gate["evaluated_at_utc"])
    c2=gh("actions/runs/43321997695")
    work_l=gh("actions/runs/43390770985")
    work_m_run=gh("actions/runs/43403595621")
    jobs=gh("actions/runs/43321997695/jobs?per_page=100")
    artifacts={i:gh(f"actions/artifacts/{i}") for i in
               (13991878472,14020616892,14025629654,14025729121)}
    # Deliberately synthetic authorization: never exported to any environment.
    approval={
        "schema":pub.WORK_N_SCHEMA,"decision":pub.APPROVAL,
        "global_cutover":"OWNER_SEPARATELY_APPROVED",
        "dst_correction":"OFF","repository":REPO,
        "expires_at":(now+timedelta(hours=1)).isoformat(),
        "provenance_contract":work_m.RECOVERY_CONTRACT,
        "release_id":binding["release_id"],
        "site_prod_head_sha":"f0cfcbc862ca3dbf1b853e72de07ffcf6042856f",
        "approved_netlify_deploy_id":"OFFLINE_FIXTURE_NOT_DEPLOYED",
        "netlify_http_static_verified":True,
        "git_only_publisher_paused":True,
        "approved_netlify_static_kpi_sha256":manifest["files"]["historical-daily-kpi.json"],
        "approved_generation":binding["generation"],
        "files":manifest["source_files"],"final_files":manifest["files"],
        "release_manifest_sha256":manifest["release_manifest_sha256"],
        "c2_artifact_id":13991878472,
        "c2_artifact_sha256":work_m.RECOVERY_PINS["c2_bundle_artifact_sha256"],
        "work_a_artifact_id":14020616892,
        "work_a_artifact_sha256":work_m.RECOVERY_PINS["work_a_artifact_sha256"],
        "final_release_artifact_id":14025629654,
        "final_release_artifact_sha256":pub.WORK_M_FINAL_SHA256,
        "final_prepare_report_artifact_id":14025729121,
        "final_prepare_report_artifact_sha256":pub.WORK_M_REPORT_SHA256,
        "final_release_code_sha":pub.WORK_M_CODE_SHA,
    }
    for prefix,run in (("c2",c2),("work_a",work_l),("final_release",work_m_run)):
        approval[prefix+"_run_id"]=run["id"]
        approval[prefix+"_run_attempt"]=run["run_attempt"]
        approval[prefix+"_head_sha"]=run["head_sha"]
    for k in ("c2_run_id","c2_run_attempt","c2_workflow_sha","c2_input_sha",
              "c2_corpus_sha256","c2_bundle_sha256","neon_branch"):
        approval[k]=report[k]
    approved=pub.validate_work_m(
        approval,report,proof,released,
        c2_run=c2,work_a_run=work_l,final_run=work_m_run,
        c2_artifact=artifacts[13991878472],
        work_a_artifact=artifacts[14020616892],
        final_artifact=artifacts[14025629654],
        report_artifact=artifacts[14025729121],
        c2_jobs=jobs,repository=REPO,now=now)
    assert approved["status"]=="OWNER_AND_WORK_L_WORK_M_APPROVED_ONE_SHOT"
    pub.verify_pinned_final_zip(ROOT/"14025629654.zip",released,approved,
                                approval,artifacts[14025629654],work_m_run)
    # No call to publish(). No real approval was created.
    print("WORK_N_FULL_PHYSICAL_PUBLISHER_PREFLIGHT_PASS_SYNTHETIC_GRANT_NO_PUSH")
if __name__=="__main__":
    main()
