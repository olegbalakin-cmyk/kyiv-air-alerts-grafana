#!/usr/bin/env python3
"""Read-only effective-trigger/workflow writer audit, no mutation or dispatch."""
import json,os,re,subprocess,sys
from pathlib import Path
import yaml
ROOT=Path(__file__).resolve().parents[2]
OUT=Path(os.environ["C3_RC4_REPORT_DIR"]);OUT.mkdir(exist_ok=True,parents=True)
REFS={"main":os.environ["C3_RC4_MAIN_SHA"],"multicity-wip-2026-09-16":os.environ["C3_RC4_WIP_SHA"],
      "research-rc4":os.environ["GITHUB_SHA"]}
def git(*a):
    return subprocess.check_output(["git",*a],cwd=ROOT,text=True).strip()
matrix=[]
errors=[]
for logical,sha in REFS.items():
    paths=git("ls-tree","-r","--name-only",sha,".github/workflows").splitlines()
    for path in paths:
        if not path.endswith((".yml",".yaml")):continue
        raw=git("show",sha+":"+path)
        try: doc=yaml.load(raw,Loader=yaml.BaseLoader) or {}
        except Exception as e:
            errors.append({"ref":logical,"path":path,"error":"YAML:"+str(e)});continue
        triggers=doc.get("on",{}) or {}
        triggers=list(triggers) if isinstance(triggers,list) else list(triggers) if isinstance(triggers,dict) else [str(triggers)]
        jobs=doc.get("jobs",{}) or {}
        for job_name,job in jobs.items():
            if not isinstance(job,dict):continue
            body=json.dumps(job,ensure_ascii=False)
            writer=bool(re.search(r"(monitor_explosion_candidates|update_explosion_metric_live|persist_canonical_work|attack_event_canonical_persistence|explosion_candidate_monitor_state|explosion_review_queue|explosions_test|PHASE1_PROD_SHADOW_DATABASE_URL)",body,re.I))
            direct_write=bool(re.search(r"(git push|contents:\\s*write|PHASE1_PROD_SHADOW_DATABASE_URL|ATTACK_EVENT_DATABASE_URL|deploy-pages)",raw+body,re.I))
            target="Neon/WIP candidate or Git WIP" if writer else "unrelated/indirect or read-only"
            guard=str(job.get("if","")).strip()
            hard_hold=bool(re.fullmatch(r"\$\{\{\s*false\s*\}\}|false",guard,re.I))
            active_triggers=[x for x in triggers if x in ("workflow_dispatch","push","schedule","workflow_run","workflow_call","repository_dispatch")]
            default=logical=="main"
            # Nondefault workflow_run/schedule are not effective; dispatch on nondefault requires default-branch
            # workflow presence, but the job can check out WIP even if triggered on main.
            effective=("DEFAULT_BRANCH_ACTIVE" if default and active_triggers else
                       "NONDEFAULT_REF_NOT_AUTOMATICALLY_ELIGIBLE" if not default and active_triggers else "NO_RELEVANT_TRIGGER")
            if not default and "workflow_dispatch" in active_triggers:
                effective="NONDEFAULT_MANUAL_DISPATCH_CONDITIONAL_ON_DEFAULT_WORKFLOW_REGISTRATION"
            if default and "workflow_run" in active_triggers:
                effective="DEFAULT_BRANCH_WORKFLOW_RUN_FILTER_REQUIRES_SOURCE_AND_SHA_GUARD"
            verdict=("BLOCKED_BY_JOB_HOLD" if hard_hold else
                     "UNGUARDED_OPERATIONAL_ENTRY" if writer and direct_write and default and active_triggers else
                     "NOT_C3_WRITER" if not writer else "REQUIRES_DEPENDENCY_OR_REF_REVIEW")
            matrix.append({"workflow":path,"ref":logical,"sha":sha,"job":job_name,
              "trigger":triggers,"effective_eligibility":effective,"write_target":target,
              "write_capability":direct_write,"guard":guard or None,"hard_hold":hard_hold,
              "evidence":{"workflow_git_object":git("rev-parse",sha+":"+path),
                          "file_present_on_ref":True,"default_branch":default},
              "verdict":verdict})
missing=[x for x in ("explosion-monitor-wip.yml","update-explosion-wip.yml","live-due-orchestration-readback.yml") if not any(
      p["workflow"].endswith("/"+x) and p["ref"]=="main" for p in matrix)]
unheld=[x for x in matrix if x["verdict"]=="UNGUARDED_OPERATIONAL_ENTRY"]
# A complete all-entry hold is false if an unguarded writer exists even when only manually dispatchable.
held=not missing and not unheld and not errors
result={"gate":"C3-RC4","refs":REFS,"matrix":matrix,
 "ref_workflow_counts":{k:len(set(r["workflow"] for r in matrix if r["ref"]==k)) for k in REFS},
 "required_missing":missing,"parsing_errors":errors,
 "unguarded_operational_entries":unheld,"all_entry_containment_pass":held,
 "exhaustive_scope":"all .github/workflows on three pinned refs, conservative static job-level writer scan",
 "limitations":["GitHub Actions account-side enablement and environment rules not independently verified",
    "workflow_call and downstream GitHub APIs can require account-side trigger inspection",
    "default branch schedule and workflow_run semantics differ from nondefault branch file presence"],
 "result":"PASS" if held else "PARTIAL"}
(OUT/"c3_rc4_workflow_containment.json").write_text(json.dumps(result,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
print("C3_RC4_CONTAINMENT="+json.dumps({"result":result["result"],"unheld":len(unheld),
 "workflow_counts":result["ref_workflow_counts"],"missing":missing},sort_keys=True))
sys.exit(0 if held else 2)
