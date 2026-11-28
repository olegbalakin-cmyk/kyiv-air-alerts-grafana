"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs"),path=require("node:path"),cp=require("node:child_process");
const ROOT=path.resolve(__dirname,"..");
const SITE=path.join(ROOT,"kyiv-air-alerts-grafana");
const BASE="58634812155ddc6b4324c26d694cf3de6cfb9bbe";
const MAIN="b35ca5c8d189a011c1b7158275f189a195192890";
const EXPECTED_C6={
  "kyiv-air-alerts-grafana/data/dashboard_data.json":"1dfd31f93dde9739013364cc5dcb827b448dd425",
  "kyiv-air-alerts-grafana/data/site_derived.json":"94a617cd2abea28a06b46d46a500948b5de25a66",
  "kyiv-air-alerts-grafana/data/alerts_combined.json":"7bed8531950bee4ffc2a61e3a906c5efc67cdcc7",
  "kyiv-air-alerts-grafana/data/kyiv_threat_mix.json":"d6cb500c296ef05f218ea0284233b87d459f3531",
  "kyiv-air-alerts-grafana/data/sevastopol_events.json":"7e1bee5f5b0a06fca1ac7c9b28956c074a9d7d52",
  "historical-daily-kpi.json":"5a88388445f0bb6c6ed58cb3972ca1b6bc577bc0"
};
const read=p=>fs.readFileSync(path.join(ROOT,p),"utf8");
const git=(...args)=>cp.execFileSync("git",args,{cwd:ROOT,encoding:"utf8"}).trim();
assert.equal(process.env.PROMOTE,"OFF","promotion must remain disabled");
assert.equal(process.env.CASUALTY_PUBLICATION_ALLOWED,"false");
const head=git("rev-parse","HEAD");
assert.match(head,/^[a-f0-9]{40}$/);
for(const [name,expected] of Object.entries(EXPECTED_C6))
  assert.equal(git("rev-parse","HEAD:"+name),expected,"untouched original C6 file: "+name);
const dashboard=JSON.parse(read("kyiv-air-alerts-grafana/data/dashboard_data.json"));
const derived=JSON.parse(read("kyiv-air-alerts-grafana/data/site_derived.json"));
const capture=JSON.parse(read("kyiv-air-alerts-grafana/data/active23_source_capture.json"));
const side=JSON.parse(read("kyiv-air-alerts-grafana/data/casualty_partial_months.json"));
const features=JSON.parse(read("kyiv-air-alerts-grafana/pages-preview/features.json"));
const html=read("kyiv-air-alerts-grafana/pages-preview/index.html");
const netlify=read("netlify.toml");
const manifest=capture.release_manifest_sha256;
assert.match(manifest,/^[a-f0-9]{64}$/);
assert.equal(dashboard.meta.publication_authority.release_manifest_sha256,manifest);
assert.equal(derived.meta.publication_authority.release_manifest_sha256,manifest);
// C6 dashboard and derived metadata can carry different legitimate generation timestamps;
// their common release-manifest SHA-256, not timestamps, is the same-release contract.
assert.ok(Number.isFinite(Date.parse(dashboard.meta.generated_at)));
assert.ok(Number.isFinite(Date.parse(derived.meta.generated_at)));
assert.equal(capture.count_cities,23);
assert.equal(Object.keys(capture.cities).length,23);
assert.equal(dashboard.multicity_meta.production_city_keys.length,23);
assert.deepEqual(Object.keys(dashboard.casualties_by_city).sort(),dashboard.multicity_meta.production_city_keys.map(k=>k.replace('ivano_frankivsk','ivano-frankivsk')).sort());
assert.equal(side.baseline_ref,"site-prod@"+BASE);
assert.equal(side.promotion,"OFF");
assert.equal(side.publication_allowed,false);
assert.equal(side.published_monthly_overwrite,false);
assert.equal(side.contains_exact_monthly_totals,false);
assert.equal(features.casualty_partial_preview,true);
assert.equal(features.casualty_partial_source,"canonical_site_prod");
assert.equal(features.isolated_test_only,undefined);
const scripts=[...html.matchAll(/<script src="([^"]+)"><\/script>/g)].map(m=>m[1]);
const ver="20261123-casualty-245";
assert.ok(scripts.includes("app.js?v="+ver));
for(const f of ["casualty-partial-preview.js","casualty-partial-source.js"]) {
  assert.ok(scripts.includes(f+"?v="+ver),"same-version UI source: "+f);
  assert.ok(netlify.includes("pages-preview/"+f+" _site/") ||
    netlify.includes("pages-preview/"+f+" kyiv-air-alerts-grafana/pages-preview/"),
    "production build copies "+f);
}
assert.ok(!/netlify deploy --prod|netlify deploy --prod/i.test(netlify));
const oneShot=read(".github/workflows/active23-production-once.yml");
assert.ok(oneShot.includes("github.event_name == 'push'") &&
  oneShot.includes("github.ref == 'refs/heads/site-prod'") &&
  oneShot.includes("github.actor == 'olegbalakin-cmyk'") &&
  oneShot.includes("startsWith(github.event.head_commit.message, 'Release active23 daily28 URL fix 2026-11-21')"),
  "non-PR owner-gated one-shot cannot deploy from research branch");
const adapter=require(path.join(SITE,"pages-preview/casualty-partial-preview.js"));
const result=adapter.validate(side,dashboard.casualties_by_city);
assert.equal(result.verified_event_groups,4);
assert.equal(result.verified_minimum,11);
assert.deepEqual(Object.fromEntries(Object.entries(side.cities)
  .filter(([_,m])=>m["2026-10"].confirmed_event_lower_bound!==null)
  .map(([k,m])=>[k,m["2026-10"].confirmed_event_lower_bound])),
  {"ivano-frankivsk":1,"khmelnytskyi":3,lutsk:6,poltava:1});
assert.equal(Object.values(side.cities).filter(m=>m["2026-09"].coverage_through!==null).length,4);
assert.equal(Object.values(side.cities).filter(m=>m["2026-10"].confirmed_event_lower_bound===null).length,19);
const sep=Object.values(side.cities).reduce((n,m)=>n+m["2026-09"].confirmed_baseline_deaths,0);
assert.equal(sep,56,"baseline 55+ already credited Sumy +1; no new September revisions");
assert.equal(side.cities.sumy["2026-09"].confirmed_baseline_deaths,4);
const report={
  schema:"casualty-251-read-only-gate-v1",base_site_prod:BASE,
  base_main:MAIN,candidate_head:head,
  c6_git_blobs:EXPECTED_C6,
  c6_release_manifest_sha256:manifest,
  c6_source_run_id:capture.c2_run_id,
  c6_source_capture_at:capture.source_generated_at,
  city_count:23,sept_partial_existing_baseline:sep,
  sept_known_cutoffs:4,sept_unknown_cutoffs:19,
  october_event_minimum:11,october_verified_events:4,october_unknown_city_cells:19,
  promotion:"OFF",production_mutated:false,
  canonical_mode:features.casualty_partial_source,
  checks:["C6_GIT_BLOBS_UNCHANGED","C6_RELEASE_MANIFEST_MATCH","CANONICAL_UI_ASSETS_IN_NETLIFY_BUILD",
    "ONE_SHOT_PR_NOT_DEPLOYABLE","FOUR_VERIFIED_OCT_EVENTS","SEPTEMBER_EXISTING_BASELINE_ONLY"]
};
fs.writeFileSync("casualty-251-release-gate.json",JSON.stringify(report,null,2)+"\n");
console.log("CASUALTY_251_RELEASE_GATE_OFFLINE_PASS",JSON.stringify({
  head,manifest,unchangedC6Files:Object.keys(EXPECTED_C6).length,
  cities:23,sept:sep,oct:11,promote:"OFF"
}));
