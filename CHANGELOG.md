# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### C6-C3-PR90-FRONTEND-FIX-PASS-01 — PR #90 frontend compatibility PASS (2026-11-12; proposed on merge)

- Previous `C6-C3-SCOPED-NEON-INDEX-PREVIEW-PASS-01`: PR #87 runner-local QA #43201183617 PASS. **New Work A:** [Draft PR #90](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/90) exact `83f14e27bf4675f64aff72fa20010630f0305d52`, [Actions #43205095573](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43205095573) SUCCESS, artifact #13937630998: scoped real `app.js` KPI guard, 184/184 views, 23 CSV, Git rollback 23/23, 0 browser errors, 28 files restored. Work B preview readiness next, no merge/deployment; `GLOBAL_CUTOVER=NO`.

### C6-PHYSICAL-SIX-JSON-READBACK-PASS-01 — physical Neon→six JSON PASS (2026-11-12; proposed on merge)

- Owner-authorized [#43187464328](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43187464328) `82a7cc77` SUCCESS, artifact #13929117121: 6/6 JSON +18/18 SHA, 23/23 historical receipts/freshness, 33,135 canonical, 262 old +75 later excluded. Read-only; no writes/publication. Current source, Kyiv provenance, DST and C3 preview/rollback remain OPEN; `GLOBAL_CUTOVER=NO`.

### C6-APPEND-ONLY-READBACK-OFFLINE-01 — 23-city exact-run after later inserts offline PASS (2026-11-12; proposed on merge)

- C2 #43055353190 = 33,135 canonical +262 older (Work B #74); old physical #43098776474 receipt BLOCKED, #43104972888 reached 23/23 historical freshness but frozen B2 blocked, #43180832950 on #79 blocked after 75 **new** later rows (0 old rows changed). Research PRs #75/#76/#77/#79 fix exact-ID selection, UA open-end and B2 evidence; latest [PR #82](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/82) `82a7cc775ed2f2a6fd0134440db709690f0c04d1` [offline #43181978935](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43181978935) PASS. Regular C2 #43172960738 has 33,210 but only 22/23 continuity; not ready as replacement freshness proof. PR #84 found no offline fixture; next is existing read-only physical E2E, new owner approval required. C3/DST OPEN, `GLOBAL_CUTOVER=NO`.

### C6-POSTMERGE-C2-EXPORT-23-01 — real C2 bundle and 23/23 checkpoints PASS (2026-11-11)

- [Scheduled C2 #43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED`, 33,135 episodes (+69), 23-city QA/Git JSON PASS (`site-prod@cf960d7c`). Real [artifact #13873291895](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190/artifacts/13873291895), ZIP SHA-256 `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`, manifest SHA `f64620936677b3a329a5e7823d3f4d52e4bc60c5b6a29bb8da6ff943adf3e433`; checkpoint 23/23 updated, Sevastopol event `25006` still unresolved. Independent exact-run readback/Neon→JSON parity remains OPEN; `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

### C6-REPLAY-SEVASTOPOL-MERGED-01 — narrow fixes merged, physical proof pending (2026-11-11)

- [PR #61](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/61) → `main@fe4ab1c1`, [16/16 offline Actions #42981135850](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42981135850); [PR #62](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/62) → `site-prod@6de49e3b`, [8/8 offline Actions #42982010821](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42982010821). Next regular C2 must prove real bundle SHA and 23/23 source continuity; independent Neon readback/Netlify deployment not confirmed. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

### C6-THREE-RUN-EXPORT-01 — C2 export blocked despite healthy writer (2026-11-11)

- [Manual 42902124611](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42902124611) and [scheduled 42908463331](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42908463331) SUCCESS; [scheduled 42970870607](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42970870607) writer/23-city QA/Git PASS (`site-prod@390e7635`, 33,066 episodes) but overall FAIL on GitHub diagnostic upload. Three exports blocked `CAPTURE_NAIVE_TIMESTAMP`, no bundle SHA. 22/23 refreshed checkpoints; Sevastopol stuck due unresolved recent pair anomaly. Next narrow time-source proof and 23/23 same-run readback. No cutover/DST.

### C6-EXPORT-DIAGNOSTIC-STAGED-01 — C2 export reason staged, still BLOCKED (2026-11-10)

- First enabled [run 42817288652](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42817288652) published `site-prod@15a3f15b` and 23/23 bootstrap checkpoints; export `C2_BUNDLE_BLOCKED`, no artifact. Owner-approved [PR #54](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/54) merged `main@ee96fa78` with safe allowlisted reason output; [offline run 42829359694](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42829359694) 4/4 PASS. Await next scheduled run for actual reason and cross-cycle receipts. No manual run/cutover/DST; `GLOBAL_CUTOVER=NO`.

### C6-CAPTURE-EXPORT-OPTINS-ON-01 — owner-approved opt-ins enabled; first capture pending (2026-11-10)

- After [updater 42774323341](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774323341) PASS (canonical writer/23-city QA/Git publication; export SKIPPED), owner separately approved two C2 opt-ins. Isolated read-only [Actions 42792678131](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42792678131) SUCCESS at `c12b2eb7`: both repository variables checked as `true`. First regular collector bootstrap/overlap **PENDING**; no manual updater, Neon readback proof, source switching or DST activation. `publication_allowed=false; GLOBAL_CUTOVER=NO`.

### C6-GATED-RECEIPTS-STAGED-01 — hooks staged OFF; offline CI PASS (2026-11-10)

- Owner-approved [PR #47](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/47) squash-merged to `site-prod@cc8bcbe577196e6484d3a5fd83b4addfabfb9456`, followed by [PR #46](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/46) to `main@2fbe9d1970c6508cbc9c1d66db55327120fe857a`. Exact-head [Actions 42686471326](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42686471326) **32/32 offline PASS**; [preflight 42774215008](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774215008) **capture/export OFF**. Main push triggered [updater 42774323341](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42774323341), outcome to verify. PR #48 research draft, DST OFF, real 23-city full receipts 0/23; no source switching, Neon cutover or flag activation. Next: post-merge updater check, separately owner-approved flags, bootstrap/overlap and read-only same-run proof. `GLOBAL_CUTOVER=NO`.

### C6-UA-CURRENT-ONEGET-01 — current API access PASS; active semantics OPEN (2026-10-31)

- Owner-authorized one GET `/api/v3/alerts`: HTTP 200, 72 rows, 9/21 mapped IDs directly present with AIR, 12 absent but UNKNOWN. [Actions 41219158954](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41219158954) SUCCESS; [proof d6a6340f](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/d6a6340f8941799d873f02a9bce27881bce81a01), encrypted artifact **13049271828**, 5/5 hashes verified. History 21/21 separately proven by existing production client.
- No status-negative/ancestor/cache completeness certification, Neon writes or production mutations; **C6/C3 PARTIAL; GLOBAL_CUTOVER NO**. Next: offline interpretation of official contract, no further API GET authorized.

<!-- coordination:history:end -->
