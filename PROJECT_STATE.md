# Project State — coordination snapshot

**2026-11-13: Work Q FINAL PREFLIGHT FAIL (Netlify recovery-proof binding). Latest accepted: C6-C3-WORKQ-NETLIFY-CONTRACT-NOGO-01. ROLLBACK_OPERATIONAL_READY=YES (tested configuration); CUTOVER_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF.**

Read main documentation first; PR #78 newer accepted checkpoints govern. Keep production, Neon, casualty and DST separate.

## Current gates

- **C2:** #43321997695 attempt 1: update-site SUCCESS, Neon 33,315 (+48), 23/23 capture receipts; dependent C6 failed pre-run. No repeat C2.
- **Work L:** [#43390770985](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43390770985), artifact #14020616892, 6/6 JSON and 23/23 historical freshness PASS; read-only, no publication.
- **Work M:** [prepare-only #43403595621](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43403595621) SUCCESS at exact PR #116 `9d846279b91b44b324a722ca00276a99956b4fca`. FINAL artifact #14025629654 SHA-256 `f2252da0014ce4ed28d5d52a7164e077b8fcd8c99380dd752ee0650412b051ed`. Independently downloaded: 8/8 final members, 6/6 parseable JSON and hashes, six source hashes matched original Work L; binding/manifest/report hashes PASS. Prepare report #14025729121 independently SHA-256 checked. No publisher/C2/Netlify job ran.
- **Work N:** Draft PR #119 exact `6f8502e043b5c57d4e44db4b435d9a885a1abe79`, [offline #43407785056](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056) SUCCESS: publisher 20/20, physical C2→Work L→Work M ZIP/source SHA, and refreshed `site-prod@f0cfcbc8` Git-only 23-city rollback, 18 entries, eight no-loss cases. Artifact #14028565807 SHA `e2914fac206e0ec2d7c2d5ff466703126cd47d5c9023490a71c9ae816d9a727a`. Publisher code offline-ready; subsequent Work P physical Netlify restore PASS supersedes earlier recovery blocker. Fresh no-loss recapture still required immediately before cutover. `ROLLBACK_OFFLINE_READY=YES; CUTOVER_READY=NO`.

- **Work O / Netlify:** #43411738247 SUCCESS, hosted alias `6af6eac51390a92065e9164f` ready; 13/13 HTTP, 23/23 cities, 184/184 browser views, 23 CSV PASS, JS errors 0. Original Netlify production unchanged before Work P. Full evidence in accepted Work O checkpoint below.

- **Work P / operational Netlify rollback:** Owner-authorized one temporary production publication of Work O alias `6af6eac51390a92065e9164f`, followed by real restoration of original `6adb629bc3ebc570117d82e1`. Netlify API independently shows candidate `published_at=2026-11-13T11:22:01Z` and original `published_at=2026-11-13T11:23:02Z`; original now current/ready. Git `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f` unchanged. Owner Work P receipt reports identical rendered UI before/during/after, 23 cities, casualties present, and Netlify Auto publishing restored ON. Work P did not perform a fresh CDN byte-hash audit; inherited Work N/O historical per-file checks. `ROLLBACK_OPERATIONAL_READY=YES` for the tested configuration only; fresh cutover-time data/auto-publish locks, release-code promotion and distinct production release approval remain OPEN.

## Next

Only narrow Netlify Neon recovery-provenance gate + negative tests. Then separately authorized PR #119/`site-prod` merges, owner receipt, effective Actions write/environment permissions, paused competing publishers and Netlify Auto publishing, plus current no-loss Git/C2/casualty/aux/freshness check. One explicit release GO required. No C2/writer/source HTTP/publish/merge/cutover now.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-C3-WORKQ-NETLIFY-CONTRACT-NOGO-01 — static release gate mismatch (2026-11-13)

- Verified unchanged `main@712c9e35`, `site-prod@f0cfcbc8`, Work L #43390770985 (23/23), Work M #43403595621 FINAL #14025629654 SHA `f2252da0…51ed`, Work N #43407785056, and restored Netlify production `6adb629bc3ebc570117d82e1`. Work P operational rollback PASS (tested setup); PR #119 remains Draft.
- **BLOCK:** Netlify `site-prod:.github/workflows/netlify-production.yml` requires successful `update-netlify-site.yml` C6 preparation artifact; C2 #43321997695 overall FAIL, artifact absent. Work L uses a different isolated workflow, so cannot meet this gate. Fix only allowlisted Work L recovery provenance + negatives; then authorized merges, owner gates, fresh no-loss hashes, one release. `FINAL_PREFLIGHT=FAIL; CUTOVER_READY=NO; ROLLBACK_OPERATIONAL_READY=YES; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C3-WORKP-PRODUCTION-RESTORE-PASS-01 — one controlled production publication restored PASS (2026-11-13)

- **Owner-authorized physical Work P:** temporary Netlify production publication of ready Work O `6af6eac51390a92065e9164f`, then reinstatement of original production `6adb629bc3ebc570117d82e1`. Independently read-only verified Netlify publication timestamps 2026-11-13 11:22:01Z / 11:23:02Z respectively, original currently published/ready. `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f` unchanged. Uploaded `WORK_P_RESULT.json` reports identical rendered UI across three states (23 cities, casualties visible), Netlify Auto publishing restored ON, no C2/writer/Git publication/merge/Neon cutover; no new Netlify deploy.
- **Evidence scope:** Netlify publish/restore pointers physically PASS; Work P browser rendered UI PASS; no new independent CDN per-file byte SHA audit or new C2/casualty source capture performed. Work N/O packages and proof retained. `ROLLBACK_OPERATIONAL_READY=YES` **for tested configuration**, but future cutover requires fresh no-loss hash/freshness check, safe auto-publish sequencing, release-code readiness and distinct owner production GO. `CUTOVER_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.


## C3-WORKO-CURRENT-GIT-ONLY-ALIAS-PASS-01 — physical hosted Git-only recovery preview PASS (2026-11-13)

- Owner approved **one** non-production alias deploy and hosted HTTP/browser QA only. Research branch `research-work-o-netlify-alias-2026-11-13@cb910c1ebb9a46c6e9a9c56134176eb4dc746c32`; [Actions #43411738247](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43411738247) attempt 1 SUCCESS. Exact Work N [artifact #14028565807](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056/artifacts/14028565807) downloaded, outer SHA `e2914fac206e0ec2d7c2d5ff466703126cd47d5c9023490a71c9ae816d9a727a`, inner package SHA `79e6a1ba0339c9f02d4089933cd91f77db060221a572e49df3c7d11fb2d31ff5`, manifest SHA `e1d859fa97535dcb10745239f4de786e3674fda331bdfa9d16d074e335e47c4b`; 18/18 entries and Git blobs verified, only the 13 `netlify/_site/` files deployed. No Git JSON publication.
- Netlify deploy `6af6eac51390a92065e9164f` ready, `branch-deploy`, `published_at=null`, URL https://work-o-git-only-f0cfcbc8--ukraine-air-alerts.netlify.app/. Hosted HTTP/bytes 13/13 PASS (12 exact, one `index.html` Netlify injected RUM); browser 23 cities / 184 views / 23 CSV, same-generation KPI, Kyiv, fatalities and historical display PASS, JavaScript errors 0. Independent proof [artifact #14029658328](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43411738247/artifacts/14029658328), ZIP SHA `b0cfd9c0b8eed42d66d143ca272fbdda015ec892f4d985aa86eeee3de03eaf08`, includes browser.json/http_qa.json/preflight/deploy receipt/screenshot.
- Pre/post production Netlify `6adb629bc3ebc570117d82e1` unchanged; Git `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f` unchanged. This is **not** physical production restoration and does not prove Netlify auto-publishing lock or authority. `ROLLBACK_PACKAGE_READY=YES; NETLIFY_PREVIEW_READY=YES; ROLLBACK_OPERATIONAL_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`. No C2, source HTTP, Neon writer, Git publication, merge or production deployment.

## C3-WORKO-CURRENT-NETLIFY-ROLLBACK-PREFLIGHT-01 — pinned package unchanged; current alias/operational restore pending (2026-11-13)

- Read-only `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f` matches [Work N PR #119](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/119) evidence; [Actions #43407785056](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056) SUCCESS, artifact [#14028565807](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056/artifacts/14028565807), outer SHA-256 `e2914fac206e0ec2d7c2d5ff466703126cd47d5c9023490a71c9ae816d9a727a`. Reused 18-file Git-only package, same-generation 23-city KPI, 5 runtime JSON, casualty/aux hashes and 8 no-loss simulations; no duplicate tests or changes. Must refresh if source data change.
- Read-only connected Netlify: `ukraine-air-alerts` site `b5aafc46-7468-4070-baf1-db80a4d30501`, current production `6adb629bc3ebc570117d82e1` ready/published 2026-10-23; old Work I2 alias `6af629b311d9632a220e652a` ready/branch-deploy, never production-published. Owner already saw `Publish deploy` on inactive alias, not clicked. October static and stale branch alias are not current rollback. Auto publishing/lock state and physical production restore unverified.
- **Disposition:** `ROLLBACK_PACKAGE_READY=YES; NETLIFY_PREVIEW_READY=NO` (current alias not deployed); `ROLLBACK_OPERATIONAL_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`. Next: one owner-approved non-prod alias from pinned Work N `netlify/_site`, then hosted checks. A separate future production test needs owner authorization, Netlify auto-publishing lock, competing publisher pause, latest no-loss Git snapshot, compatible static publish and production HTTP/browser QA. No publish/merge/C2/writer/Neon/source HTTP/cutover.

## C6-C3-WORKN-PUBLISHER-ROLLBACK-OFFLINE-PASS-01 — exact publisher compatibility and current Git-only rollback offline PASS (2026-11-13)

- [Draft PR #119](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/119) exact `6f8502e043b5c57d4e44db4b435d9a885a1abe79`: [Actions #43407785056](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056) SUCCESS, publisher 20/20 offline tests, positive physical publisher validation (synthetic approval, no push), and physically verified C2 #43321997695 → Work L #43390770985 → Work M #43403595621 final ZIP/report identity. Original C2 preparation remains absent, never fabricated; distinct expiring production owner receipt and existing protections retained. No publisher dispatch.
- Fresh Git-only rollback on `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f`, C2 23/23 receipts; 18-entry 23-city same-generation static/Git package, tracked casualty/aux SHA and 8 synthetic no-loss scenarios PASS. [Artifact #14028565807](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056/artifacts/14028565807) GitHub SHA-256 `e2914fac206e0ec2d7c2d5ff466703126cd47d5c9023490a71c9ae816d9a727a`. **Not cutover-time fresh.**
- Netlify nonprod alias deployment previously proven, **inactive-production republish authority and physical rollback unproven**. Further owner UI check required. No C2, Neon writer, HTTP source, Git publication, Netlify deploy, merge or cutover. `PUBLISHER_CODE_READY=YES; ROLLBACK_OFFLINE_READY=YES; ROLLBACK_OPERATIONAL_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.


<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Archive index](docs/coordination-archive/README.md), [manifest](docs/coordination-archive/manifest.json), and [maintenance CLI](docs/coordination-maintenance.md) retain historical proofs; archive via a PR, no direct main push.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged `main@3735f359`; [Actions #41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) PASS. Ten archived records indexed above. Bot archival PR permission unverified; not a Neon release.
