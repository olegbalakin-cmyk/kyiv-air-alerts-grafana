#!/usr/bin/env python3
"""Real frozen Kyiv source replay. Executes pinned accepted classifier, no live sources."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
import requests

from ledger import initialize, run_batch, load, isolated_regression_test, encoded

REPO="olegbalakin-cmyk/kyiv-air-alerts-grafana"
PROOF_SHA="906b9e18aa9e0a2056bcb798b9870ae35d8dee3d"
CLASSIFIER_BLOB="4019b8374dcc44846df04ed0cc41356652214bff"
PROOF_BLOB="65c32480c88c0e72824764b04515576b46a3e158"
SOURCE_IDS=((11608819645,"acquisition"),(11609004684,"replay"))
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent


def git(*args):
    return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()


def download_inputs(folder):
    token=os.getenv("GH_TOKEN","")
    if not token:
        raise RuntimeError("ACTIONS_READ_TOKEN_REQUIRED_FOR_ARCHIVED_INPUT")
    for artifact_id,label in SOURCE_IDS:
        response=requests.get(
            f"https://api.github.com/repos/{REPO}/actions/artifacts/{artifact_id}/zip",
            headers={"Authorization":"Bearer "+token,"Accept":"application/vnd.github+json",
                     "X-GitHub-Api-Version":"2022-11-28"},
            timeout=120)
        response.raise_for_status()
        data=response.content
        digest=hashlib.sha256(data).hexdigest()
        out=folder/label
        out.mkdir(parents=True,exist_ok=True)
        from io import BytesIO
        with zipfile.ZipFile(BytesIO(data)) as archive:
            for info in archive.infolist():
                target=(out/info.filename).resolve()
                if not target.is_relative_to(out.resolve()) or info.is_dir():
                    if info.is_dir(): continue
                    raise RuntimeError("UNSAFE_ARCHIVE_PATH")
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(archive.read(info))
        print("READONLY_ARTIFACT",artifact_id,label,"ZIP_SHA256",digest,flush=True)
    return folder/"acquisition",folder/"replay"/"runner-replay-1.json"


def run_classifier_twice(worktree, acquisition, prior, output):
    script=worktree/".github/proof/kyiv_0825_actual_classifier_repair_reproof.py"
    assert script.exists(),"MISSING_ACCEPTED_PROOF"
    outputs=[]
    for index in range(2):
        filename=output/f"classifier-{index+1}.json"
        command=[sys.executable,"-u",str(script),
                 "--mode","repaired","--corpus-dir",str(acquisition),
                 "--prior-replay",str(prior),"--output",str(filename)]
        env=dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"]="1"
        result=subprocess.run(command,cwd=worktree,env=env,check=True,text=True,
                              stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
        print(result.stdout[-2000:],flush=True)
        outputs.append(json.loads(filename.read_text(encoding="utf-8")))
    assert outputs[0]["episodes"]==outputs[1]["episodes"],"NONDETERMINISTIC_CLASSIFIER"
    assert outputs[0]["fingerprint"]==outputs[1]["fingerprint"],"CLASSIFIER_FINGERPRINT_MISMATCH"
    assert len(outputs[0]["episodes"])==67
    assert sum(len(e["candidates"]) for e in outputs[0]["episodes"])==105
    return outputs[0]


def cohort_from_accepted_classification(doc,acquisition):
    candidates=doc["episodes"]
    positive=next((x for x in candidates
                   if x["final"] in ("STRICT_EVENT_POSITIVE","SENSITIVITY_EVENT_POSITIVE")
                   and x["candidates"]),None)
    review=next((x for x in candidates if x["final"]=="NEEDS_REVIEW" and x["candidates"]
                 and x["episode_id"]!=(positive or {}).get("episode_id")),None)
    empty=next((x for x in candidates if not x["candidates"]
                and x["episode_id"] not in {(positive or {}).get("episode_id"),(review or {}).get("episode_id")}),None)
    selected=[x for x in (positive,review,empty) if x]
    assert positive is not None, "NO_REAL_SOURCE_POSITIVE_COHORT"
    assert len({x["episode_id"] for x in selected})==len(selected)
    discovery=json.loads((acquisition/"kyiv_historical_runner_discovery_snapshot_2026-10-09.json").read_text())
    native=json.loads((acquisition/"kyiv_historical_runner_native_corpus_2026-10-09.json").read_text())
    native_by_url={x["requested_native_url"]:x.get("native") or {} for x in native["records"]}
    meta_by_ep={x["episode_id"]:x for x in discovery["development_episodes"]}
    rows=[]
    for item in selected:
        match=meta_by_ep[item["episode_id"]]
        evidence=[]
        for c in item["candidates"]:
            n=native_by_url.get(c["url"],{})
            raw=n.get("text") or ""
            # Immutable source text is for local classification only. Reports use short excerpts.
            evidence.append({
                "candidate_id":c["candidate_id"],"family":c["family"],
                "source_url":c["url"],"publication_time":n.get("published_at"),
                "title":(n.get("title") or "")[:240],
                "excerpt":raw[:210],
                "source_text_sha256":c["text_sha256"],
                "classifier_outcome":c["classifier_outcome"],
                "matched_episode_id":c["classifier_episode_id"],
                "reason_codes":c["reason_codes"],
                "temporal_code":c.get("temporal_code"),
                "classifier_error":c.get("classifier_error"),
            })
        rows.append({
            "episode_id":item["episode_id"],"city":"Київ",
            "alert_start":match["alert_start"],"alert_end":match["alert_end"],
            "candidate_count":len(evidence),"source_complete":True,
            "source_scope":"CLOSED_VERIFIED_FROZEN_CORPUS_ONLY",
            "classifier_verdict":item["final"],"classifier_evidence":evidence,
            "classifier_fingerprint":doc["fingerprint"],
            "historical_frozen_verdict_preserved":True,
        })
    return rows


def report(out, items, state, tests, primary):
    data=[]
    for item in items:
        s=state["work"][item["episode_id"]]
        data.append({
            **item,
            "ledger_state":s["status"],"acknowledged_local_only":s["acknowledged"],
            "attempts":s["attempts"],"completed_at":s["completed_at"],
            "last_error":s["last_error"],
            "candidate_classifications":s.get("result",{}).get("candidates",[]) if s.get("result") else [],
        })
    payload={
        "verdict":"BOUNDED_RESEARCH_ONLY_NOT_SCHEDULED_LIVE",
        "source_type":"REAL_ARCHIVED_NEWS_NOT_SYNTHETIC",
        "source_artifacts":[x[0] for x in SOURCE_IDS],
        "pinned_classifier_proof_commit":PROOF_SHA,
        "classifier_blob_git_sha1":CLASSIFIER_BLOB,
        "classifier_fingerprint":primary["fingerprint"],
        "full_classifier_cohort_episodes":len(primary["episodes"]),
        "full_classifier_cohort_candidates":sum(len(e["candidates"]) for e in primary["episodes"]),
        "replay_selected_episodes":len(items),
        "replay_selected_candidates":sum(x["candidate_count"] for x in items),
        "local_acks":sum(state["work"][x["episode_id"]]["acknowledged"] for x in items),
        "local_ack_is_not_neon_or_canonical_commit":True,
        "fault_controls":tests,
        "canonical_writes":0,"neon_writes":0,"production_writes":0,
        "source_completeness":"COMPLETE_ONLY_WITHIN_ARCHIVED_SEARCH_CORPUS",
        "live_source_coverage_proven":False,
        "historical_rewrite":False,
        "human_review_required_for_non_strict_or_incomplete_cases":True,
        "episodes":data,
    }
    (out/"report.json").write_bytes(encoded(payload))
    html_rows=[]
    for row in data:
        src="".join("<li><a href='"+html.escape(s["source_url"],quote=True)+"'>"
                    +html.escape(s["family"]+" — "+s["title"])+"</a> "
                    +html.escape(str(s["publication_time"]))+" / "+
                    html.escape(str(s["classifier_outcome"]))+
                    " — "+html.escape(", ".join(s["reason_codes"]))+"</li>"
                    for s in row["classifier_evidence"])
        html_rows.append("<section><h2>"+html.escape(row["city"]+" "+row["episode_id"])+"</h2><p>Тривога: "+
                         html.escape(row["alert_start"]+" — "+row["alert_end"])+
                         "</p><p>Класифікатор: "+html.escape(row["classifier_verdict"])+
                         " · Кандидатів: "+str(row["candidate_count"])+
                         " · Local ACK: "+html.escape(str(row["acknowledged_local_only"]))+
                         " · Спроб: "+str(row["attempts"])+
                         "</p><ul>"+src+"</ul></section>")
    html_doc="<html lang='uk'><meta charset='utf-8'><title>Real frozen source Kyiv replay</title><body>"+\
      "<h1>Ізольований replay: реальні збережені новини — НЕ live/Neon</h1>"+\
      "<p>Висновки чинні лише для перевіреного історичного корпусу. "\
      "Відсутність знайденого джерела не доводить відсутності події. "\
      "Можливі коди STRICT — результат дослідницького класифікатора, не канонічні записи.</p>"+\
      "<p>Епізодів: "+str(len(items))+"; кандидатів: "+str(payload["replay_selected_candidates"])+\
      "; локальних ACK: "+str(payload["local_acks"])+".</p>"+\
      "".join(html_rows)+"</body></html>"
    (out/"report.html").write_text(html_doc,encoding="utf-8")
    return payload


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",type=Path,default=Path("out/research_live_real_source"))
    args=parser.parse_args()
    out=args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    tests=isolated_regression_test()
    assert git("rev-parse",f"{PROOF_SHA}:kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py")==CLASSIFIER_BLOB
    assert git("rev-parse",f"{PROOF_SHA}:.github/proof/kyiv_0825_actual_classifier_repair_reproof.py")==PROOF_BLOB
    with tempfile.TemporaryDirectory(prefix="real-archived-evidence-") as tmp:
        folder=Path(tmp)
        acquisition,prior=download_inputs(folder)
        worktree=folder/"accepted-proof"
        subprocess.run(["git","worktree","add","--detach",str(worktree),PROOF_SHA],
                       cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        try:
            verified=run_classifier_twice(worktree,acquisition,prior,out)
        finally:
            subprocess.run(["git","worktree","remove","--force",str(worktree)],
                           cwd=ROOT,check=True,stdout=subprocess.DEVNULL)
        items=cohort_from_accepted_classification(verified,acquisition)
    path=out/"ledger_state.json"
    initialize(path,items,CLASSIFIER_BLOB)
    indexed={x["episode_id"]:x for x in verified["episodes"]}
    def accept(item):
        frozen=indexed[item["episode_id"]]
        assert frozen["final"]==item["classifier_verdict"]
        assert len(frozen["candidates"])==item["candidate_count"]
        assert all(c["classifier_error"] is None for c in frozen["candidates"])
        return {
            "classifier_identity":CLASSIFIER_BLOB,
            "candidate_count":item["candidate_count"],
            "candidates":item["classifier_evidence"],
            "verdict":item["classifier_verdict"],
            "classifier_errors":[],
        }
    # First exercise source incompleteness, then prove retry and completion.
    eid=items[0]["episode_id"]
    first=run_batch(path,items,accept,limit=1,faults={eid:"source"})
    assert first[0]["status"]=="RETRYABLE_SOURCE_INCOMPLETE"
    for _ in range(len(items)):
        run_batch(path,items,accept,limit=1)
    state=load(path)
    assert all(state["work"][x["episode_id"]]["acknowledged"] for x in items)
    before=path.read_bytes()
    assert run_batch(path,items,accept,limit=1)==[]
    assert path.read_bytes()==before
    output=report(out,items,state,tests,verified)
    print("REAL_FROZEN_FULL_CLASSIFIER_EPISODES",output["full_classifier_cohort_episodes"])
    print("REAL_FROZEN_FULL_CLASSIFIER_CANDIDATES",output["full_classifier_cohort_candidates"])
    print("SELECTED_EPISODES",output["replay_selected_episodes"])
    print("SELECTED_REAL_CANDIDATES",output["replay_selected_candidates"])
    print("LOCAL_DURABLE_ACK",output["local_acks"])
    print("RESTART_IDEMPOTENCE_PASS")
    print("RESEARCH_ONLY_NO_OPERATIONAL_WRITES")
    print("RESULT=PASS BOUNDED RESEARCH ONLY")


if __name__=="__main__":
    main()
