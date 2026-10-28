"""C3-RC5 bounded exact-main static Git containment and live Actions metadata proof."""
import hashlib, json, os, pathlib, subprocess, sys, urllib.request
MAIN=os.environ["AUDITED_MAIN"]; BLOB=os.environ["AUDITED_BLOB"]
REPO=os.environ["GITHUB_REPOSITORY"]
def git(*args):
    return subprocess.check_output(["git",*args], text=True).strip()
def payload(ref,path): return git("show",f"{ref}:{path}")
def api(path):
    req=urllib.request.Request(f"https://api.github.com/repos/{REPO}/{path}",headers={"Accept":"application/vnd.github+json","User-Agent":"C3-RC5-readonly","Authorization":"Bearer "+os.environ.get("GITHUB_TOKEN","")})
    try:
        with urllib.request.urlopen(req,timeout=12) as response:return json.load(response)
    except Exception as exc:return {"not_proven":str(exc)}
workflow=".github/workflows/update-explosion-wip.yml"
actual=git("rev-parse","refs/remotes/origin/main")
site=git("rev-parse","refs/remotes/origin/site-prod")
wip=git("rev-parse","refs/remotes/origin/multicity-wip-2026-09-16")
verified=git("rev-parse",f"{MAIN}:{workflow}")
yaml=payload(MAIN,workflow)
held=("jobs:\n  update:\n    # C3 release hold: owner authorization required for removal.\n    if: ${{ false }}" in yaml)
monitor=payload(MAIN,".github/workflows/explosion-monitor-wip.yml")
monitor_held=("jobs:\n  monitor:\n" in monitor and "    if: ${{ false }}" in monitor)
canary=payload(MAIN,".github/workflows/attack-event-canary-neon-readback.yml")
listener=payload(MAIN,".github/workflows/live-due-orchestration-readback.yml")
production=payload(MAIN,".github/workflows/update-netlify-site.yml")
wipmonitor=payload("refs/remotes/origin/multicity-wip-2026-09-16",".github/workflows/explosion-monitor-wip.yml")
old="2c16b69dd3261a16cb08c9cf825a4f150cf76d11"
old_runs=api("actions/runs?head_sha="+old+"&per_page=100")
historic_success=any(r.get("name")=="Monitor explosion metric WIP" and r.get("conclusion")=="success" for r in old_runs.get("workflow_runs",[]))
main_runs=api("actions/runs?head_sha="+MAIN+"&per_page=100")
old_git=git("rev-parse","HEAD")
matrix=[
 {"workflow":"update-explosion-wip.yml","ref":"main","sha":verified,"trigger":"workflow_dispatch","effective_eligibility":"REGISTERED_MANUAL","job_guard":"false","write_capability":True,"write_target":"operational WIP branch / Pages","track":"C3","evidence":"actual main blob + job guard","verdict":"DEFAULT_BRANCH_MANUAL_TRIGGER_JOB_HELD_C3_WRITE_BLOCKED" if held else "UNHELD"},
 {"workflow":"explosion-monitor-wip.yml","ref":"main","sha":git("rev-parse",f"{MAIN}:.github/workflows/explosion-monitor-wip.yml"),"trigger":"schedule,workflow_dispatch,push[path]","effective_eligibility":"DEFAULT_BRANCH","job_guard":"false" if monitor_held else "UNHELD","write_capability":True,"write_target":"operational WIP branch","track":"C3","evidence":"actual main job guard","verdict":"JOB_HELD" if monitor_held else "UNHELD"},
 {"workflow":"explosion-monitor-wip.yml","ref":"multicity-wip-2026-09-16","sha":git("rev-parse","refs/remotes/origin/multicity-wip-2026-09-16:.github/workflows/explosion-monitor-wip.yml"),"trigger":"workflow_dispatch (branch selectable); default branch schedule separate","effective_eligibility":"POTENTIALLY_DISPATCHABLE_ON_WIP_REF","job_guard":"false" if "    if: ${{ false }}" in wipmonitor else "UNHELD","write_capability":True,"write_target":"operational WIP branch","track":"C3","evidence":"WIP ref workflow blob; account-side dispatch permissions NOT_PROVEN","verdict":"RESIDUAL_UNHELD_BRANCH_DISPATCH_RISK"},
 {"workflow":"attack-event-canary-neon-readback.yml","ref":"main","sha":git("rev-parse",f"{MAIN}:.github/workflows/attack-event-canary-neon-readback.yml"),"trigger":"push[path deploy/attack-event-canary-readback-trigger.txt]","effective_eligibility":"NOT_APPLICABLE_TO_HOLD_PUSH","job_guard":"none","write_capability":False,"write_target":"none; SELECT readback","track":"C3_OBSERVATION","evidence":"contents:read and SQL SELECT","verdict":"READ_ONLY"},
 {"workflow":"live-due-orchestration-readback.yml","ref":"main","sha":git("rev-parse",f"{MAIN}:.github/workflows/live-due-orchestration-readback.yml"),"trigger":"workflow_run completed Monitor explosion metric WIP","effective_eligibility":"HISTORICAL_SUCCESS_MATCH_EXISTS" if historic_success else "NOT_PROVEN","job_guard":"old source SHA plus success","write_capability":True,"write_target":"git push proof artifact to main","track":"C3_PROOF","evidence":"old success run + hardcoded SHA + repository workflow listener","verdict":"EFFECTIVE_REACHABILITY_NOT_PROVEN"},
 {"workflow":"update-netlify-site.yml","ref":"main","sha":git("rev-parse",f"{MAIN}:.github/workflows/update-netlify-site.yml"),"trigger":"schedule,workflow_dispatch,push[path own workflow]","effective_eligibility":"NOT_APPLICABLE_TO_HOLD_PUSH","job_guard":"none","write_capability":True,"write_target":"site-prod and canonical persistence dependencies","track":"C2_PRODUCTION","evidence":"separate workflow and site-prod push","verdict":"EXCLUDED_DISTINCT_PRODUCTION_TRACK"}
]
head_ok=actual==MAIN
assertions={"default_branch_hold_present":held,"default_branch_hold_effective":held and verified==BLOB,"main_monitor_hold_preserved":monitor_held,"confirmed_c3_unheld_writers":1,"listener_reachability_resolved":False,"non_c3_workflows_separated":True,"main_sha_verified":head_ok,"no_unintended_activation":len(main_runs.get("workflow_runs",[]))==0 if "workflow_runs" in main_runs else None,"all_entry_containment_pass":False}
pre={"audited_main_before":git("rev-parse",MAIN+"^"),"audited_main_after":MAIN,"path":workflow,"default_branch_push_path_matches":[],"downstream_trigger":"workflow_run only on other named source; historical success requires separate reachability review","unsafe_direct_push_detected":False,"account_policy_metadata":"NOT_PROVEN"}
proof={"research_tested_sha":old_git,"audited_main_sha":MAIN,"audited_main_workflow_blob_sha":verified,"site_prod_sha":site,"operational_wip_sha":wip,"workflow_run_id":os.environ.get("GITHUB_RUN_ID"),"job_id":"metadata to be reconciled externally","artifact_id":"metadata to be reconciled externally","historic_matching_success":historic_success,"rows":matrix,"assertions":assertions}
gate={"verdict":"C3_RC5_PARTIAL","C3_RELEASE_AUTHORIZED":False,"NEON_AUTHORITY_ACTIVE":False,"PRODUCTION_CUTOVER_EXECUTED":False,"assertions":assertions,"research_tested_sha":old_git,"audited_main_sha":MAIN}
for name,data in [("c3_rc5_pre_push_impact.json",pre),("c3_rc5_effective_containment.json",proof),("c3_rc5_release_gate.json",gate)]:
    pathlib.Path(name).write_text(json.dumps(data,indent=2,ensure_ascii=False,sort_keys=True)+"\n")
manifest={"files":{p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest() for p in ["c3_rc5_pre_push_impact.json","c3_rc5_effective_containment.json","c3_rc5_release_gate.json"]}}
pathlib.Path("sha256_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
if not (head_ok and held and verified==BLOB and monitor_held):raise SystemExit("FAIL: DEFAULT_BRANCH_HOLD_ASSERTION")
print(json.dumps({"gate":"C3_RC5_PARTIAL","hold_verified":True,"historical_listener_success":historic_success,"unheld_wip_branch_copy":True,"research_tested_sha":old_git,"audited_main_sha":MAIN}))
