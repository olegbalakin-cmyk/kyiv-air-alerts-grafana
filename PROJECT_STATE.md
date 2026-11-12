# Project State — current coordination snapshot

**Date:** 2026-11-12. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C3-ROLLBACK-OLD-DEPLOY-HTTP-SHA-PASS-01** (old production HTTP/SHA PASS; rollback BLOCKED). Live C3 preview #43218752830 PASS. Production unchanged. `GLOBAL_CUTOVER=NO`.

## Working instructions

1. Read root state and CHANGELOG before action; newer accepted checkpoints supersede chat memory.
2. Verify immutable SHA, Actions/artifacts. Research proof is not a production release.
3. Keep production/WIP/historical/backfill/casualty/Neon separate; no forced shared pushes, credential exposure or inferred deployments.
4. Keep blockers/tasks outside history; accepted records inside. Preserve archived evidence. Maintain 5–10 CHANGELOG transitions.
5. UTF-8 gate ≤12 KiB PASS, >12 KiB WARNING, >16 KiB FAIL. Archive safely with `scripts/coordination_docs.py` when needed; see [maintenance](docs/coordination-maintenance.md).
6. Read bounded proof, not complete archives or large dumps; save work promptly.

## Current tracks and open release gates

- **Production:** Netlify deploy `6adb629bc3ebc570117d82e1` current/ready; runtime Git `site-prod@fc726166`, no Neon cutover. Old HTTP/SHA #43224744877 PASS; operator production rollback untested.
- **Neon reader / historical parity:** [PR #74](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/74) exact 33,135 C2 IDs/fields 23/23 with 262 older episodes retained; [PR #75](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/75) canonical selection offline PASS. Full provenance OPEN.
- **Live writer / provenance:** C2 #43055353190 33,135 episodes/23 checkpoints PASS; later #43172960738 33,210 (+75), only 22/23 same-run continuity (Sevastopol). Historical `25006→25008` OPEN.
- **23-city generator / publication:** physical [#43187464328](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43187464328) PASS: six JSON, 18 hashes, 23 receipts, 33,135 canon; 262 old +75 later excluded. No publication. Current source/Kyiv/DST OPEN.
- **UkraineAlarm current API (research):** [run 41219158954](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41219158954): 9/21 mapped IDs direct AIR, 12 UNKNOWN. Active/negative/cache semantics OPEN.
- **DST / Kyiv:** 4-case offline fix `14e1b0b9` passed tests; rolling guard BLOCKED pending private raw baseline. DST OFF; Kyiv provenance OPEN.
- **Preview / C3:** Netlify draft `6af5aecd8901ea2a40de09ad` ready; [live #43218752830](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43218752830) PASS (184 views/23 CSV/UI fallback). [PR #92](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/92) HTTP/SHA #43224744877 PASS; Publish deploy and compatible Git rollback OPEN.
- **Operational WIP / historical reference / backfill / casualty:** separate tracks; no change or promotion is established by these research or documentation checkpoints. Consult the relevant pinned evidence through the archive index before acting on a track.

## Concrete next tasks

1. **Rollback PR #92:** owner/operator checks `Publish deploy` exists without clicking. HTTP/SHA #43224744877 PASS. Pin compatible Git data/index rollback generation.
2. **Main pre-cutover:** regular Neon→JSON→Git delivery fail-closed, protect C2/casualty and draft reversible production plan; no deployment now.
3. Current source/Kyiv provenance, DST and Sevastopol remain OPEN. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C3-ROLLBACK-OLD-DEPLOY-HTTP-SHA-PASS-01 — immutable old production HTTP/SHA PASS (2026-11-12)

- [PR #92](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/92); read-only [Actions #43224744877](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43224744877) SUCCESS, artifact #13946647755: seven old Netlify assets + five pinned Git JSON HTTP 200/SHA, 23-city KPI index, matching main-domain static hashes. Old index Oct 23 generation differs from current Git Nov 12: two-plane rollback needs compatible baseline. Operator Publish deploy and production rollback untested; NO-GO. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C3-NETLIFY-HOSTED-PREVIEW-PASS-01 — public C3 browser/CSV/rollback PASS (2026-11-12)

- Owner-approved draft Netlify `6af5aecd8901ea2a40de09ad` ready at alias `c3-neon-83f14e27`; production `6adb629bc3ebc570117d82e1` remains current. Pinned Work B #43208800105 / artifact #13940887007. [Live QA #43218752830](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43218752830) SUCCESS, artifact #13945375693: 12/12 candidate+Git JSON SHA exact, 184/184 views, CSV 23/23, Neon→Git→Neon UI rollback, 0 browser errors, noindex. Netlify inserted its own RUM script into `index.html` only. Current-source/Kyiv provenance and production rollback/cutover remain OPEN; `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-C3-PR90-FRONTEND-FIX-PASS-01 — real frontend isolated QA PASS (2026-11-12)

- Previous accepted `C6-C3-SCOPED-NEON-INDEX-PREVIEW-PASS-01`: PR #87 runner-only Neon index QA #43201183617 PASS. **Work A accepted:** [Draft PR #90](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/90) exact `83f14e27`, base `site-prod`; [CI #43205095573](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43205095573) SUCCESS, artifact #13937630998: real `validIndex()` guarded, 184/184 views, CSV 23/23, rollback 23/23, 0 errors, 28 restored files. Work B package PASS; one draft deploy authorized but not performed. No merge/cutover. `GLOBAL_CUTOVER=NO`.

## C6-PHYSICAL-SIX-JSON-READBACK-PASS-01 — protected six-JSON physical PASS (2026-11-12)

- Owner-authorized [#43187464328](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43187464328) SUCCESS on PR #82 `82a7cc77`, C2 #43055353190. Artifact #13929117121: 18/18 hashes, 6/6 JSON, 23/23 historical receipts/freshness, canonical 33,135; 262 historical +75 later excluded; Kyiv frozen B2 382→198. No Neon writes, source HTTP or deployment. Current source/Kyiv provenance and DST not certified. Preview/C3 rollback remains OPEN; `GLOBAL_CUTOVER=NO`.

## C6-APPEND-ONLY-READBACK-OFFLINE-01 — exact-run snapshot after later inserts, offline PASS (2026-11-12)

- Work A physical #43098776474 failed at historical receipt replay; Work B #74 confirmed C2 33,135 exact rows and 262 stale historical versions; Work C #75 selected only exact C2 IDs; PR #76 fixed UkraineAlarm open-end sentinel. Combined PR #77 offline #43102701988 PASS.
- Physical [#43104972888](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43104972888) verified 23/23 historical freshness but blocked at old Kyiv B2 382-parent proof. PR #79 keeps 382 frozen proof parents (184 stale evidence, 198 canonical display), never reintroducing stale stats; offline #43105919875 PASS.
- Owner-approved physical [#43180832950](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43180832950) on #79 failed closed at C2 selection; artifact #13926356418. Independent read-only Neon: 75 *new* post-C2 rows, **zero** previously present closed AIR rows modified. [PR #82](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/82) `82a7cc775ed2f2a6fd0134440db709690f0c04d1` excludes only proven post-C2 inserts, rejects post-cutoff mutation of historic/C2 rows, [offline #43181978935](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43181978935) SUCCESS. No physical six-file PASS. PR #84: full offline E2E BLOCKED (no full private fixture); existing physical reader already captures all seven tables. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-POSTMERGE-C2-EXPORT-23-01 — physical same-run export and checkpoints PASS (2026-11-11)

- [Actions #43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) scheduled C2 SUCCESS (16:08:40–16:36:22 UTC), after Work A `main@fe4ab1c1` and Work B `site-prod@6de49e3b`. `NEON_SUCCEEDED`: 33,135 canonical episodes (+69), 23-city QA, Git JSON publication `site-prod@cf960d7c` PASS.
- Actual C2 ZIP artifact [#13873291895](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190/artifacts/13873291895) uploaded (`c2-shadow-inputs-43055353190-1`, 3,669,061 bytes), export ZIP SHA-256 `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`, manifest SHA-256 `f64620936677b3a329a5e7823d3f4d52e4bc60c5b6a29bb8da6ff943adf3e433`. `CAPTURE_NAIVE_TIMESTAMP` absent; 23/23 persistent source checkpoints share GitHub run ID `43055353190`; Sevastopol now updated, historical `25006→25008` remains unresolved.
- **Proof boundary:** successful export/capture does not establish independent Neon readback/parity, source freshness all-city PASS in readback, Netlify deployment, approved DST/rollback or permission for global source switch. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-REPLAY-SEVASTOPOL-MERGED-01 — two scoped fixes staged in production branches (2026-11-11)

- Owner-approved [PR #61](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/61) squash-merged to `main@fe4ab1c14bffa03ff58f1f9debc3cc510f1099b0`, exact-head [Actions #42981135850](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42981135850) **16/16 offline PASS** (UkraineAlarm event timestamp replay only).
- Owner-approved [PR #62](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/62) squash-merged to `site-prod@6de49e3b0cf9692c7bb242672e92f062e516af20`, exact-head [Actions #42982010821](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42982010821) **8/8 offline PASS** (Sevastopol checkpoint eligibility only). No synthetic event closure, no cutover.
- First post-merge C2 and exact ZIP/SHA, source receipt continuity across all 23 cities, independent Neon readback and any Netlify deployment **not yet verified**. Prior source checkpoint 22/23; `25006` still unresolved. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-THREE-RUN-EXPORT-01 — exact blockers after activated cycles (2026-11-11)

- [42902124611](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42902124611) and [42908463331](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42908463331) SUCCESS; [42970870607](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42970870607) data/Neon/23-city QA/Git PASS (`site-prod@390e7635`, 33,066 episodes), overall FAIL at artifact upload.
- All three bundle exports BLOCKED `CAPTURE_NAIVE_TIMESTAMP`, no ZIP/SHA; 22/23 checkpoints refreshed, Sevastopol stuck since bootstrap. Cutover NO.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
