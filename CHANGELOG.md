# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### C3-WORKO-CURRENT-GIT-ONLY-ALIAS-PASS-01 — authorized nonprod Netlify alias and hosted QA PASS (2026-11-13; accepted)

- [Work O Actions #43411738247](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43411738247) SUCCESS at `research-work-o-netlify-alias-2026-11-13@cb910c1ebb9a46c6e9a9c56134176eb4dc746c32`. Exact Work N artifact #14028565807, 18/18 hashes, 13 `netlify/_site/` files deployed **once** to Netlify nonprod branch deploy `6af6eac51390a92065e9164f` (ready, not published to primary). Actual hosted 13/13 HTTP/SHA (12 exact, 1 Netlify `index.html` RUM injection), 23/23 cities, 184/184 browser chart views, 23/23 CSV, KPI, Kyiv, 23-city deaths and zero JS errors. [Proof artifact #14029658328](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43411738247/artifacts/14029658328) independent outer SHA-256 `b0cfd9c0b8eed42d66d143ca272fbdda015ec892f4d985aa86eeee3de03eaf08`. `site-prod@f0cfcbc8` and Netlify production `6adb629bc3ebc570117d82e1` unchanged. **No production restore performed or authorized**; lock/auto-publish still unproven. `ROLLBACK_PACKAGE_READY=YES; NETLIFY_PREVIEW_READY=YES; ROLLBACK_OPERATIONAL_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.

### C3-WORKO-CURRENT-NETLIFY-ROLLBACK-PREFLIGHT-01 — unchanged current Work N Git-only package, Netlify rollback not physical (2026-11-13; accepted)

- `site-prod@f0cfcbc862ca3dbf1b853e72de07ffcf6042856f` remains current and matches Work N [PR #119](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/119), [Actions #43407785056](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056) SUCCESS, artifact #14028565807 SHA-256 `e2914fac206e0ec2d7c2d5ff466703126cd47d5c9023490a71c9ae816d9a727a`. The verified 18-file, 23-city Git-only package and no-loss tests can be reused until Git data changes; refresh before release. Netlify current production `6adb629bc3ebc570117d82e1`, old inactive Work I2 alias `6af629b311d9632a220e652a`; owner saw `Publish deploy` on inactive alias, without clicking. No new live alias, production republish test or independently verified auto-publish lock. **Next owner action: separately approve one nonproduction alias deployment from Work N `netlify/_site` only.** `ROLLBACK_PACKAGE_READY=YES; NETLIFY_PREVIEW_READY=NO; ROLLBACK_OPERATIONAL_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-C3-WORKN-PUBLISHER-ROLLBACK-OFFLINE-PASS-01 — code and Git-only recovery offline PASS (2026-11-13; accepted)

- [Draft PR #119](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/119) exact `6f8502e0`, [Actions #43407785056](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407785056) SUCCESS: 20 publisher tests, physical C2/Work L/Work M source/final ZIP SHA PASS; original missing C2 prep not substituted, separate owner publication receipt still required. Fresh 23-city `site-prod@f0cfcbc8` Git-only rollback 18-file package and 8 no-loss cases PASS; artifact #14028565807 SHA `e2914fac206e0ec2d7c2d5ff466703126cd47d5c9023490a71c9ae816d9a727a`. Physical Netlify production restoration authority unproven. `PUBLISHER_CODE_READY=YES; ROLLBACK_OFFLINE_READY=YES; ROLLBACK_OPERATIONAL_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.


### C6-WORKM-FINALZIP-INDEPENDENT-PASS-01 — physical prepare-only and independent eight-file ZIP PASS (2026-11-13; accepted)

- [Actions #43403595621](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43403595621) SUCCESS attempt 1 on PR #116 exact `9d846279`; only prepare job ran. [FINAL artifact #14025629654](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43403595621/artifacts/14025629654) independently SHA-256 `f2252da0014ce4ed28d5d52a7164e077b8fcd8c99380dd752ee0650412b051ed`; report #14025729121 SHA `f4f786b168d28f37bdf6a333d4e514b503e402e4fda25553d99ffa0a8d6a8648`; 8/8 final members, 6/6 JSON/sha, Work L 6/6 source sha, release binding/report PASS. No publication. Publisher original C2 prep contract and fresh rollback remain blocked: `FINAL_ZIP=PASS; ROLLBACK_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-WORKM-OWNER-GRANT-NODISPATCH-01 — one prepare-only owner grant, not dispatched (2026-11-13; accepted)

- Owner approved **one** prepare-only on exact PR [#116](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/116) SHA `9d846279b91b44b324a722ca00276a99956b4fca`. GitHub connector cannot enable workflow, configure repo variables/secret/environment or dispatch; one-shot permission **unconsumed**. Require `C6_GIT_ONLY_PUBLISHER_PAUSED=true` before any shared-workflow enable. Work M-specific CI, owner receipt, final ZIP and fresh rollback remain OPEN; no C2/writer/Git publish/Netlify/merge/cutover. `GLOBAL_CUTOVER=NO`.

### C6-WORKL-PHYSICAL-SIXJSON-PASS-01 — six JSON physically proven (2026-11-13; accepted)

- [#43390770985](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43390770985) SUCCESS at PR #113 `325669a4`; [artifact #14020616892](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43390770985/artifacts/14020616892) independently checked SHA `79acb3017dccefdf19def7fe15bdaf2033b27d8c8a6d41f146d7b0e903bd3954`, 18/18, 6/6 JSON, historical 23/23. Same original C2 attempt 1; zero writer, source HTTP or publication. Final ZIP original C2 prep missing; rollback/current alert/DST open. GLOBAL_CUTOVER=NO.

### C6-WORKL-RECOVERY-OFFLINE-PASS-01 — immutable C2 reusable (2026-11-13; accepted)

- [Draft PR #113](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/113) `325669a4`, [CI #43389706624](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43389706624) SUCCESS: 20/20 tests plus real run/job/ZIP gate PASS. C2 #43321997695 attempt 1, inner ZIP SHA `3f53c7ca4a0bc1d0f25cd228dcde003cd45ac247ecab76747405f556f75e8030`, writer 33,315 (+48), 23/23 receipts. Root cause unknown. Physical proof and FINAL ZIP still gated; no new C2/cutover.

<!-- coordination:history:end -->
