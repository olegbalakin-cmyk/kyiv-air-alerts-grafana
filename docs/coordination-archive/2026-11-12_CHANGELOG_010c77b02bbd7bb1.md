# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
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

<!-- coordination:history:end -->
