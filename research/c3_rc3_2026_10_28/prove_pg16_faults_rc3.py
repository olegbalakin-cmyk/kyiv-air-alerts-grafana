#!/usr/bin/env python3
"""Executed PG16 observations. Every nonexecuted fault remains NOT_PROVEN."""
import json
import os
import subprocess
import sys
from pathlib import Path
import psycopg

ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.getenv("C3_RC3_REPORT_DIR","/tmp/c3-rc3-proof"))
OUT.mkdir(parents=True,exist_ok=True)
DSN=os.environ["LOCAL_PROOF_POSTGRES_DSN"]
SCENARIOS=[
"two_concurrent_workers",
"post_commit_pre_ack",
"independent_readback_failure",
"classification_conflict",
"source_identity_conflict",
"stale_current_tip",
"pruned_state_legacy_checked_at",
"event_stage_rollback",
"source_failure_retry",
"repeated_normal_execution",
]
result={"gate":"C3-RC3","test_engine":"disposable PostgreSQL 16",
        "scenarios":{x:{"status":"NOT_PROVEN","reason":"No scenario-specific executable independent SQL proof obtained"} for x in SCENARIOS},
        "baseline_monitor_main":{"status":"NOT_EXECUTED"},"sql_snapshots":[],"result":"PARTIAL"}
def snapshot(label):
    with psycopg.connect(DSN,autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SHOW server_version")
            v=cur.fetchone()[0]
            if not v.startswith("16."):raise AssertionError("not PostgreSQL 16: "+v)
            counts={}
            for table in ["alert_episodes","attack_event_classifications","attack_events","attack_event_sources"]:
                cur.execute("SELECT count(*) FROM public."+table)
                counts[table]=cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM (SELECT classification_key FROM public.attack_event_classifications GROUP BY classification_key HAVING count(*)>1) x")
            counts["duplicate_classification_keys"]=cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM (SELECT attack_event_key FROM public.attack_events GROUP BY attack_event_key HAVING count(*)>1) x")
            counts["duplicate_event_keys"]=cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM public.attack_event_classifications c WHERE c.supersedes_classification_uid IS NOT NULL")
            counts["revision_count"]=cur.fetchone()[0]
    result["sql_snapshots"].append({"point":label,"counts":counts})
    return counts
try:
    before=snapshot("before")
    run=subprocess.run(
        [sys.executable,str(ROOT/"kyiv-air-alerts-grafana/tests/prove_pg16_monitor_main.py")],
        cwd=ROOT,capture_output=True,text=True,timeout=240
    )
    (OUT/"monitor_main_execution.log").write_text(run.stdout+"\n--- STDERR ---\n"+run.stderr)
    rows=[x for x in run.stdout.splitlines() if x.startswith("MAIN_INTEGRATION_REPORT=")]
    if run.returncode==0 and len(rows)==1:
        receipt=json.loads(rows[0].split("=",1)[1])
        after=snapshot("after_two_real_main_calls")
        good=(receipt.get("pass") is True and receipt.get("monitor_main_calls")==2
              and receipt.get("first_committed")==1 and receipt.get("first_independent_readback")==1
              and receipt.get("second_committed")==0
              and after["duplicate_classification_keys"]==0 and after["duplicate_event_keys"]==0
              and after["attack_event_classifications"]-before["attack_event_classifications"]==1)
        result["baseline_monitor_main"]={"status":"PASS" if good else "FAIL","receipt":receipt}
        if good:
            result["scenarios"]["repeated_normal_execution"]={"status":"PASS","SQL_before":before,"SQL_after":after,"receipt":receipt}
    else:
        result["baseline_monitor_main"]={"status":"FAIL","returncode":run.returncode,"receipt_count":len(rows)}
except Exception as exc:
    result["errors"]=[str(exc)]
finally:
    out=OUT/"c3_rc3_fault_results.json"
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True,default=str)+"\n")
    print("C3_RC3_FAULT_RESULT="+json.dumps({
        "result":result["result"],"scenario_statuses":{k:v["status"] for k,v in result["scenarios"].items()},
        "baseline_monitor_main":result["baseline_monitor_main"].get("status"),
    },sort_keys=True))
# Fail closed: the full PG16 fault suite has NOT passed.
sys.exit(0 if all(x["status"]=="PASS" for x in result["scenarios"].values()) else 2)
