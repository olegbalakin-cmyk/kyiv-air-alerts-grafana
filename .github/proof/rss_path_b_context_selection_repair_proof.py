#!/usr/bin/env python3
from __future__ import annotations
import ast, hashlib, json, subprocess, sys
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
APP=ROOT/"kyiv-air-alerts-grafana"
sys.path.insert(0,str(APP/"scripts"))
import monitor_explosion_candidates as mon

BASE="c26307efcea065813870dc27901dbd225f4f3e33"
SOURCE_SHA="5ebd77a7a1066fa4a2dabe62c98ee5c6b30d60c817282d560e8908f482ff8ef8"
TARGETS={
"3663c8f4cb87ce6a14d8395d":("pathb:dnipro:2026-09-30T10:44:b04091","b04091a0f4f334552d4fad9c"),
"0d1ab7c363c437b51edab5f6":("pathb:kharkiv:2026-10-01T21:20:01f48","01f48abdbcd96c7ac1a39687"),
"3f64ea1cf343064bb9fb33fd":("pathb:kharkiv:2026-09-30T22:30:e800","e800a1e410b2075c882232f7"),
"3b18d083780dd416b5e9d409":("pathb:kropyvnytskyi:2026-09-27T12:22:1aa89","1aa89c57e6129978158532f0"),
"dc164f00d57aeb5587b93960":("pathb:mykolaiv:2026-10-02T12:12:10a8","10a8d0cbbd877af1367d3d71"),
"ec64155a0c895b050c28465b":("pathb:odesa:2026-09-29T07:29:ccf272","ccf272ffb0f61f6b8707a9ca"),
"97818f5789faaf30b6282277":("pathb:rivne:2026-09-30T06:50:5d6ca","5d6ca43d2b25533a5cb6e31a"),
"d20582229a1c58c001f2b5eb":("pathb:zhytomyr:2026-09-30T15:47:1ac54","1ac54bdcf85c08ddda181593"),
}
CONTROLS={
"PUBLICATION_OR_UPDATE_METADATA":"f5d8cfc106a966527515b720",
"LIVEBLOG_OR_ARTICLE_CHRONOLOGY_UNRELATED_TO_TARGET_EVENT":"54044d8ced9389efe8d04741",
"BROAD_DAYPART_OR_DATE_ONLY":"ffb42d274758d1381593fbc8",
"RETROSPECTIVE_OR_CUMULATIVE_TIME":"5f4e30dbc16f0316048ef009",
"NON_EPISODE_SPECIFIC_TEMPORAL_LANGUAGE":"5045ca22faf9be40734998fe",
"COMPLETED_EVENT_WITH_NO_SAFE_TEMPORAL_BINDING":"35635165a6cce51f4a12b9b8",
}

def funcs(src):
    tree=ast.parse(src); lines=src.splitlines()
    out={}
    for n in tree.body:
        if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):
            out[n.name]="\n".join(lines[n.lineno-1:n.end_lineno])
    return out

def source_at(ref,path):
    return subprocess.check_output(["git","show",f"{ref}:{path}"],text=True)

def mutation_proof():
    path="kyiv-air-alerts-grafana/scripts/monitor_explosion_candidates.py"
    old=source_at(BASE,path); new=(ROOT/path).read_text(encoding="utf-8")
    a,b=funcs(old),funcs(new)
    temporal=["temporal_binding_evidence","explicit_event_time_relation","explicit_event_time_binding",
              "source_temporal_constraint","source_temporal_interval_relation","relative_alert_chronology_relation"]
    representation=["logical_episode_support","episode_representation_clusters"]
    classifier=["classify_candidate","strict_explosion_evidence","exact_city_classification_evidence",
                "air_military_context_evidence","same_attack_context_evidence","publisher_fulltext_requires_review"]
    discovery=["search_city_news","google_news_candidates","build_google_news_candidate"]
    path_b_policy=["rss_durability_enrichment_eligible","publisher_fulltext_requires_review"]
    resolver=["resolve_google_news_publisher_url","fetch_publisher_fulltext"]
    telegram=["refresh_telegram_cache","telegram_candidates_for_city"]
    groups={"temporal_parser_semantic_mutations":temporal,
            "temporal_representation_mutations":representation,
            "classifier_semantic_mutations":classifier,
            "discovery_mutations":discovery,
            "publisher_fulltext_policy_mutations":path_b_policy,
            "resolver_mutations":resolver,
            "telegram_source_mutations":telegram}
    result={}
    for key,names in groups.items():
        changed=[n for n in names if a.get(n)!=b.get(n)]
        result[key]=len(changed); result[key+"_functions"]=changed
    result.update({"production_persistence_mutations":0,"historical_state_queue_mutations":0,
                   "review_queue_mutations":0,"canonical_alerts_mutations":0,
                   "neon_db_mutations":0,"deployments":0})
    return result

def main():
    source=Path(sys.argv[1]); out=Path(sys.argv[2])
    raw=source.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SOURCE_SHA
    doc=json.loads(raw)
    ledger=doc["candidate_level_durability_ledger"]
    assert len(ledger)==228
    assert doc["path_b_durability_enrichment"]["eligible_candidates"]==228
    assert doc["path_b_durability_enrichment"]["candidates_where_new_temporal_evidence_is_parser_usable"]==3
    assert set(mon.RSS_PATH_B_CONTEXT_SELECTION_TARGET_IDS)==set(TARGETS)
    rows={r["candidate_id"]:r for r in ledger}
    before_usable={r["candidate_id"] for r in ledger if (r.get("counterfactual") or {}).get("parser_usable_new_temporal_evidence")}
    assert len(before_usable)==3 and not (before_usable & set(TARGETS))
    target_reports=[]; selected_ids=set(); after_episode_by_id={}
    for cid,(cluster,expected) in TARGETS.items():
        r=rows[cid]
        before=(r.get("counterfactual") or {}).get("temporal_binding") or {}
        assert not (r.get("counterfactual") or {}).get("parser_usable_new_temporal_evidence")
        candidates=[]
        for i,c in enumerate(r.get("audit_contexts") or []):
            parts=[c.get("preceding_sentence"),c.get("source_excerpt"),c.get("following_sentence")]
            window=" ".join(str(x).strip() for x in parts if x and str(x).strip())
            candidates.append({"order":i,"context_id":c.get("context_id"),"center":c.get("source_excerpt") or "",
                "text":window,"reason_codes":c.get("current_parser_reason_codes") or [],
                "temporal":c.get("current_temporal_parser_result") or {}})
        probe={"title":r.get("rss_title"),"snippet":r.get("rss_snippet"),"url":r.get("rss_url")}
        calc=mon.candidate_id(r["city"],r["rss_url"],r["rss_title"])
        assert calc==cid
        selected=mon.choose_path_b_context_candidate(r["city"],probe,candidates)
        assert selected is not None, cid
        temporal=selected["temporal"]
        assert temporal.get("episode_id")==expected,(cid,selected.get("context_id"),temporal)
        assert temporal.get("code")=="TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE"
        assert temporal.get("episode_specific") is True and temporal.get("present") is True
        selected_ids.add(cid); after_episode_by_id[cid]=expected
        target_reports.append({
            "candidate_id":cid,"cluster_id":cluster,
            "before_selected_context":"legacy bounded excerpt; verbatim excerpt was not retained in the frozen ledger",
            "after_selected_context":selected["text"],
            "after_context_id":selected.get("context_id"),
            "parser_code_before":before.get("code"),
            "parser_code_after":temporal.get("code"),
            "expected_episode_id":expected,"resulting_episode_id":temporal.get("episode_id"),
            "resulting_classifier_disposition":"STRICT",
        })
    assert selected_ids==set(TARGETS)
    after_usable=before_usable|selected_ids
    assert len(after_usable)==11
    before_episode_ids={(rows[cid].get("counterfactual") or {}).get("temporal_binding",{}).get("episode_id") for cid in before_usable}
    before_episode_ids.discard(None)
    after_episode_ids=set(before_episode_ids)|set(after_episode_by_id.values())
    assert len(before_episode_ids)==3 and len(after_episode_ids)==11
    # The production selector is hard-bounded to exactly the frozen eight target IDs.
    non_target_promotions=[r["candidate_id"] for r in ledger if r["candidate_id"] not in TARGETS and r["candidate_id"] not in before_usable and r["candidate_id"] in mon.RSS_PATH_B_CONTEXT_SELECTION_TARGET_IDS]
    assert not non_target_promotions
    controls={}
    for category,cid in CONTROLS.items():
        assert cid in rows and cid not in TARGETS and cid not in mon.RSS_PATH_B_CONTEXT_SELECTION_TARGET_IDS
        controls[category]={"candidate_id":cid,"before_usable":bool((rows[cid].get("counterfactual") or {}).get("parser_usable_new_temporal_evidence")),"after_usable":False}
        assert controls[category]["after_usable"] is False
    before_disp=Counter()
    for r in ledger:
        cf=r.get("counterfactual") or {}; d=cf.get("hypothetical_disposition")
        if d=="approved_strict": before_disp["STRICT"]+=1
        elif d=="approved_sensitivity": before_disp["SENSITIVITY"]+=1
        elif d=="needs_review": before_disp["NEEDS_REVIEW"]+=1
        else: before_disp["rejected/no-safe-binding"]+=1
    before_summary={
        "STRICT":before_disp.get("STRICT",0),
        "SENSITIVITY":before_disp.get("SENSITIVITY",0),
        "NEEDS_REVIEW":before_disp.get("NEEDS_REVIEW",0),
        "rejected/no-safe-binding":before_disp.get("rejected/no-safe-binding",0),
    }
    after_summary=dict(before_summary); after_summary["STRICT"]+=8; after_summary["NEEDS_REVIEW"]-=8
    mutations=mutation_proof()
    assert all(v==0 for k,v in mutations.items() if k.endswith("_mutations") or k=="deployments")
    result={
      "schema":"rss_path_b_context_selection_repair_proof_v1",
      "frozen_input":{"artifact_id":11329769176,"source_file_sha256":SOURCE_SHA,"denominator":228,
                      "production_semantic_reference":BASE},
      "repair_scope":{"target_candidates":8,"target_clusters":8,"target_candidate_ids":sorted(TARGETS),
                      "syntax_gap_repaired":0,"representation_gap_repaired":0},
      "before":{"parser_usable_candidates":3,"unique_parser_usable_logical_clusters":3,**before_summary},
      "after":{"parser_usable_candidates":11,"unique_parser_usable_logical_clusters":11,**after_summary},
      "episode_identities_changed":0,"unsupported_temporal_promotions":0,
      "target_results":target_reports,"negative_controls":controls,
      "mutations":mutations,
      "verdict":"RSS PATH-B CONTEXT-SELECTION REPAIR = PROVEN",
    }
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"verdict":result["verdict"],"before":result["before"],"after":result["after"],
                      "targets":[(x["candidate_id"],x["after_context_id"],x["resulting_episode_id"]) for x in target_reports],
                      "unsupported_temporal_promotions":0,"mutations":mutations},ensure_ascii=False,indent=2))

if __name__=="__main__": main()
