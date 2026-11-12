# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### C3-STATIC-KPI-FALLBACK-GENERATION-RISK-01 — real stale static KPI fallback confirmed; rollback BLOCKED (2026-11-12; proposed on merge)

- [Draft PR #101](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/101) `76d474fb`; exact-head [Actions #43260803310](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43260803310) SUCCESS, 6/6 offline policy checks, artifact #13963023002, GitHub digest `298d43510bff61ae746e99c6cd9de76c1c663594ca9ecb1178d801b8967efb2c`. Current `app.js` accepts stale Oct 23 static KPI on fallback against Nov 12 Git dashboard; it fails to verify generation equality. **New next task:** tiny frontend generation-parity guard with negative test; later pin fresh compatible Git-only rollback baseline and prove deploy/revert path, no full Git reset. No publication, cutover or DST. Rollback BLOCKED.

### C3-FRONTEND-SITEPROD-PR100-OFFLINE-PASS-01 — site-prod frontend compatibility offline PASS (2026-11-12; proposed on merge)

- [Draft PR #100](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/100) base `site-prod@68629fda`, HEAD `88ace201`; exact-head [Actions #43260329916](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43260329916) SUCCESS, artifact #13964062068 (GitHub SHA-256 `b83595de5ecb665765c10d73de10c4f4520065a9997fa922e1002175a55e079e`). Four C3-only files; 18/18 source hashes, 184/184 historical views, CSV 23/23, Git preview rollback 23/23, 0 browser/network errors. Git stays production source, PR #90 predicate scoped to pinned Neon preview; production C2/casualty untouched. Offline `FRONTEND_COMPATIBILITY_READY` only; no merge/deploy/publication, two-plane rollback and next C2 remain OPEN. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

### C6-NEON-GIT-DEFAULT-OFF-INTEGRATION-PREPARED-01 — default-OFF six-file Neon Git candidate offline PASS (2026-11-12; proposed on merge)

- [Draft PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) `c66cf00884e28b0d04d6eccd3bc5875a45c2e2b5`; [Actions #43254618233](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43254618233) SUCCESS **14/14**, artifact **#13961690528**. Frozen physical #43187464328 + C2 #43055353190 replay; six JSON + exact PR #93 parser; detached local Git commit without remote. Five runtime JSON plus root KPI index bound; automatic preparation default OFF, `publication_allowed=false`. Next: natural C2 23/23, compatible PR #90 frontend and two-plane rollback, separate release permission. No production push/cutover/DST.

### C6-NEON-PUBLICATION-GATE-OFFLINE-01 — six-JSON physical preflight PASS; NO PUBLISH (2026-11-12; proposed on merge)

- [Draft PR #94](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/94) `e61a43f1`; [CI #43237670242](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43237670242) SUCCESS 17/17, physical #43187464328. Six JSON/18 hashes/23 historical receipts checked; invalid/stale/forged evidence blocked. No publication, production unchanged. Next live 23/23 and same-run generator→atomic Git integration. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

### C6-SEVASTOPOL-OPEN-START-PR93-MERGED-01 — owner-approved Sevastopol C2 fix merged (2026-11-12; proposed on merge)

- [PR #93](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/93) exact HEAD `5dd44e87` squash-merged `site-prod@6704c483`; [CI #43224880978](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43224880978) 11/11 PASS. Only C2 parser/tests/offline workflow; Netlify production unchanged. Next regular C2 must prove 23/23 receipt; old `25006→25008` and open `25100` unclosed. No cutover; `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

### C3-ROLLBACK-OLD-DEPLOY-HTTP-SHA-PASS-01 — old deploy HTTP/SHA proof PASS; rollback BLOCKED (2026-11-12; proposed on merge)

- [PR #92](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/92), [Actions #43224744877](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43224744877) SUCCESS / artifact #13946647755: 7 immutable Netlify files, 5 pinned Git JSON, 23-city index HTTP/SHA PASS. Oct 23 static KPI source vs Nov 12 Git dashboard generations differ; operator Publish deploy + compatible data rollback OPEN. No cutover/rollback. `GLOBAL_CUTOVER=NO`.

### C3-NETLIFY-HOSTED-PREVIEW-PASS-01 — live public Netlify preview QA PASS (2026-11-12; proposed on merge)

- Owner-approved C3 draft deploy `6af5aecd8901ea2a40de09ad` ready, production `6adb629bc3ebc570117d82e1` unchanged. [Live Actions #43218752830](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43218752830) SUCCESS, artifact #13945375693: 12 exact Git+Neon JSON, 184 city/mode views, CSV 23, UI Git rollback, zero JS/HTTP/external errors; only Netlify RUM added to HTML. No cutover/current-source certification/DST; `GLOBAL_CUTOVER=NO`.

### C6-C3-PR90-FRONTEND-FIX-PASS-01 — PR #90 frontend compatibility PASS (2026-11-12; proposed on merge)

- Previous `C6-C3-SCOPED-NEON-INDEX-PREVIEW-PASS-01`: PR #87 runner-local QA #43201183617 PASS. **New Work A:** [Draft PR #90](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/90) exact `83f14e27bf4675f64aff72fa20010630f0305d52`, [Actions #43205095573](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43205095573) SUCCESS, artifact #13937630998: scoped real `app.js` KPI guard, 184/184 views, 23 CSV, Git rollback 23/23, 0 browser errors, 28 files restored. Work B #43208800105 package PASS, artifact #13940887007. Owner authorized ONE manual draft alias deploy `c3-neon-83f14e27` on 2026-11-12; pending authenticated CLI, no deploy yet. `GLOBAL_CUTOVER=NO`.

<!-- coordination:history:end -->
