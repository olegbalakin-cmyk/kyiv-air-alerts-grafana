"""Immutable physical offline proof: synthetic articles only; no external HTTP."""
import hashlib
import json
import os
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(root/"research/casualty_workag_2026_11_15"))
from test_workag import URLS, NOW, html_page
sys.path.insert(0,str(root/"kyiv-air-alerts-grafana/scripts"))
import casualty_workac_capture as capture

out=Path("/tmp/workag")
out.mkdir(exist_ok=True)
details=[]
for shape,url in URLS.items():
    page=html_page(shape)
    parsed=capture.ArticleText()
    parsed.feed(page.decode())
    result=capture.analyze_direct_article(
        url,offline_html=page,city_key="zaporizhzhia",now=NOW)
    row=result["card"]
    details.append({
        "fixture_shape":shape,"fixture_kind":"SYNTHETIC_PUBLISHER_SHAPED",
        "article_title_extracted":bool(parsed.title()),
        "publication_datetime_extracted":bool(parsed.publication_time()),
        "body_extracted":len(parsed.body())>=180,
        "body_length":len(parsed.body()),
        "count_kind":row["count_kind_claimed"],
        "claimed_total_not_credited":row["fatal_total_claimed_not_credited"],
        "safe_excerpt_count":len(row["source_excerpts"]),
        "decision":row["decision"],
        "incident_id":row["incident_id"],
        "automatic_credits":row["automatic_credits"],
        "publication_allowed":row["publication_allowed"],
    })
assert len(details)==4
assert all(x["body_extracted"] and x["claimed_total_not_credited"]==3 and
           x["safe_excerpt_count"]>=1 and x["automatic_credits"]==0
           for x in details),details
summary={
    "checkpoint":"CASUALTY-WORKAG-ARTICLE-FIRST-OFFLINE",
    "exact_head":os.environ.get("GITHUB_SHA","LOCAL"),
    "synthetic_html_fixtures":len(details),
    "synthetic_body_success":sum(x["body_extracted"] for x in details),
    "synthetic_cumulative_parse_success":sum(x["claimed_total_not_credited"]==3
                                            for x in details),
    "real_saved_full_html_available":0,
    "real_saved_short_excerpts_available":True,
    "real_article_html_parsing_verified":False,
    "source_http_gets":0,"rss_http_gets":0,
    "active_wip_writes":0,"production_writes":0,
    "automatic_death_credits":0,"PROMOTE":"OFF",
    "publication_allowed":False,
    "details":details,
}
(out/"offline_proof.json").write_text(
    json.dumps(summary,ensure_ascii=False,sort_keys=True,indent=2)+"\n")
manifest={"offline_proof.json":hashlib.sha256((out/"offline_proof.json").read_bytes()).hexdigest()}
(out/"sha256_manifest.json").write_text(
    json.dumps(manifest,sort_keys=True,indent=2)+"\n")
for file,digest in manifest.items():
    assert hashlib.sha256((out/file).read_bytes()).hexdigest()==digest
print(json.dumps({"manifest":manifest,"summary":summary},ensure_ascii=False))
