# Project State — coordination snapshot

**2026-11-13: Work N publisher integration + current Git-only rollback offline PASS; Netlify production recovery NOT proven. Latest accepted: C6-C3-WORKN-PUBLISHER-ROLLBACK-OFFLINE-PASS-01. GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF.**

Read main documentation first; PR #78 newer accepted checkpoints govern. Keep production, Neon, casualty and DST separate.

## Current gates

- **C2:** #43321997695 attempt 1: update-site SUCCESS, Neon 33,315 (+48), 23/23 capture receipts; dependent C6 failed pre-run. No repeat C2.
- **Work L:** [#43390770985](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43390770985), artifact #14020616892, 6/6 JSON and 23/23 historical freshness PASS; read-only, no publication.
- **Work M:** [prepare-only #43403595621](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43403595621) SUCCESS at exact PR #116 `9d846279b91b44b324a722ca00276a99956b4fca`. FINAL artifact #14025629654 SHA-256 `f2252da0014ce4ed28d5d52a7164e077b8fcd8c99380dd752ee0650412b051ed`. Independently downloaded: 8/8 final members, 6/6 parseable JSON and hashes, six source hashes matched original Work L; binding/manifest/report hashes PASS. Prepare report #14025729121 independently SHA-256 checked. No publisher/C2/Netlify job ran.
- **Work N:** Draft PR #119 exact `6f8502e043b5c57d4e44db4b435d9a885a1abe79`, [offline #43407785056](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056) SUCCESS: publisher 20/20, physical C2→Work L→Work M ZIP/source SHA, and refreshed `site-prod@f0cfcbc8` Git-only 23-city rollback, 18 entries, eight no-loss cases. Artifact #14028565807 SHA `e2914fac206e0ec2d7c2d5ff466703126cd47d5c9023490a71c9ae816d9a727a`. Publisher code ready; operational Netlify production restoration authority unproven. Fresh recapture required immediately before cutover. `ROLLBACK_OFFLINE_READY=YES; ROLLBACK_OPERATIONAL_READY=NO; CUTOVER_READY=NO`. Owner reports temporary switches restored; not independently readable.

## Next

Next: independently establish permission to restore an inactive Netlify production deployment and verify fresh cutover-time compatible Git/static no-loss baseline, then seek a separate explicit owner release GO. No new C2/Neon writer/source HTTP or production publishing until all gates PASS.

d. GLOBAL_CUTOVER=NO.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-C3-WORKN-PUBLISHER-ROLLBACK-OFFLINE-PASS-01 — exact publisher compatibility and current Git-only rollback offline PASS (2026-11-13)

- [Draft PR #119](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/119) exact `6f8502e043b5c57d4e44db4b435d9a885a1abe79`: [Actions #43407785056](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056) SUCCESS, publisher 20/20 offline tests, positive physical publisher validation (synthetic approval, no push), and physically verified C2 #43321997695 → Work L #43390770985 → Work M #43403595621 final ZIP/report identity. Original C2 preparation remains absent, never fabricated; distinct expiring production owner receipt and existing protections retained. No publisher dispatch.
- Fresh Git-only rollback on `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f`, C2 23/23 receipts; 18-entry 23-city same-generation static/Git package, tracked casualty/aux SHA and 8 synthetic no-loss scenarios PASS. [Artifact #14028565807](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056/artifacts/14028565807) GitHub SHA-256 `e2914fac206e0ec2d7c2d5ff466703126cd47d5c9023490a71c9ae816d9a727a`. **Not cutover-time fresh.**
- Netlify nonprod alias deployment previously proven, **inactive-production republish authority and physical rollback unproven**. Further owner UI check required. No C2, Neon writer, HTTP source, Git publication, Netlify deploy, merge or cutover. `PUBLISHER_CODE_READY=YES; ROLLBACK_OFFLINE_READY=YES; ROLLBACK_OPERATIONAL_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.


<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Archive index](docs/coordination-archive/README.md), [manifest](docs/coordination-archive/manifest.json), and [maintenance CLI](docs/coordination-maintenance.md) retain historical proofs; archive via a PR, no direct main push.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged `main@3735f359`; [Actions #41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) PASS. Ten archived records indexed above. Bot archival PR permission unverified; not a Neon release.
