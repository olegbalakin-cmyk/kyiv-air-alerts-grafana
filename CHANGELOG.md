# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### CASUALTY-FIVE-WIP-INPUTS-01 — five existing candidates pinned (2026-11-11)

- [Research commit `d342b791`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/d342b7919e54cf49cac618fa8b7586477d199508): five preserved Google RSS candidate IDs (Dnipro, Kharkiv ×2, Lutsk, Odesa) all uniquely present and `needs_review` in WIP queue blob `f3f7141aa6d7584c63ff42510b40239a18834d15`, 1,657 rows. URLs/title/date/city unchanged; selected_queue.json blob `050d8560` unchanged. `main`/WIP revisions header-only; site-prod Sumy revision unrelated. **Only input selection PASS**: publisher reachability/usable article evidence unverified; separate owner consent for ≤5 HTTP shadow test. No production, C6/Neon, WIP queue, revisions or automatic publication changes.

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
