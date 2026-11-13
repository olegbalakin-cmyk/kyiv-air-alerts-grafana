# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### C6-C3-ADMIN-FREEZE-VERIFIED-01 — Cloud Browser administrative freeze verified (2026-11-13; accepted)

- At 12:22:49 UTC: persisted repo pause **true → true**; production Netlify Actions workflow **manually disabled → manually disabled**; Netlify **Auto publishing ON → locked/OFF**. Production `6adb629bc3ebc570117d82e1` remains published and locked. All GitHub in-progress/queued/waiting/pending/requested filters 0; no competing production publisher observed. No other workflows or casualty/WIP settings changed; no merge, C2/writer, JSON publication, deployment or cutover. Restore later: retain original GitHub guards, inspect pending/newer deployments, unlock approved Netlify production, verify ON and pointer. Next requires separate owner approval for #119/#120 merges; production GO remains distinct. `ADMIN_FREEZE_VERIFIED=YES; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-C3-PREMERGE-GUARDS-UNVERIFIED-01 — cutover preparation read-only; admin locks unverified (2026-11-13; accepted)

- Owner prep-only approval. `main@712c9e35`, `site-prod@f0cfcbc8`, PR #119/#120 Draft, CI 43407785056/43422122898 PASS, Work N rollback #14028565807 available, Netlify original `6adb629bc3ebc570117d82e1` live. **No switches changed**: GitHub repo pause variable and Netlify Actions workflow/Auto publishing cannot be configured via connected tools. Merging #119 risks C2 workflow push; merging #120 triggers GitHub Netlify `--prod` workflow push. Operator must verify pause/disable before separate merge authorization; release then needs new data/rollback proof, Netlify-first static KPI + independent owner GO. `CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.


### C6-C3-WORKR-NETLIFY-RECOVERY-OFFLINE-PASS-01 — Work R 16/16 offline PASS (2026-11-13; accepted)

- Draft [PR #120](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/120) `ac32540fcb0074afaed20ec9f6849b32777dc9c7`, [exact-head CI #43422122898](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43422122898) SUCCESS 16/16 offline incl. legacy path, SHA/run/approval negatives; initial #43421545056/#43422060631 failures fixed by test assertion corrections only. No merge or production action. `NETLIFY_CONTRACT_READY=YES` offline; PR #119/120 merge and fresh publisher/Netlify gates require separate GO. `CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-C3-WORKQ-NETLIFY-CONTRACT-NOGO-01 — accepted Netlify recovery-proof release blocker (2026-11-13)

- Verified `main@712c9e35`, `site-prod@f0cfcbc8`, Work L/M/N artifacts and Netlify restored production unchanged; Work P rollback operational PASS. Work N publisher PR #119 Draft. Netlify Neon release requires successful C2 `update-netlify-site.yml` C6 preparation artifact absent from C2 #43321997695 (update-site job PASS, overall FAIL); isolated Work L #43390770985 does not satisfy. Scope one fail-closed Netlify recovery-proof contract fix; then separately approved merges, effective workflow rights/owner gate and fresh no-loss manifest. `FINAL_PREFLIGHT=FAIL; ROLLBACK_OPERATIONAL_READY=YES` (tested setup); `CUTOVER_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

### C3-WORKP-PRODUCTION-RESTORE-PASS-01 — physical Netlify publish-and-restore PASS (2026-11-13; accepted)

- Owner-approved Work P temporarily published ready Work O alias `6af6eac51390a92065e9164f` then republished original `6adb629bc3ebc570117d82e1`. Independently verified Netlify `published_at` 11:22:01Z/11:23:02Z; original current/ready, `site-prod@f0cfcbc8` unchanged. Uploaded operator receipt: browser before/during/after rendered text identical, 23 cities/casualties present, Auto publishing ON restored. No new CDN byte-hash audit or code deploy; previous Work N/O files/proofs reused. `ROLLBACK_OPERATIONAL_READY=YES` (tested setup); cutover-time no-loss/auto-publish and release-owner gates OPEN. `CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.


### C3-WORKO-CURRENT-GIT-ONLY-ALIAS-PASS-01 — authorized nonprod Netlify alias and hosted QA PASS (2026-11-13; accepted)

- [Work O Actions #43411738247](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43411738247) SUCCESS at `research-work-o-netlify-alias-2026-11-13@cb910c1ebb9a46c6e9a9c56134176eb4dc746c32`. Exact Work N artifact #14028565807, 18/18 hashes, 13 `netlify/_site/` files deployed **once** to Netlify nonprod branch deploy `6af6eac51390a92065e9164f` (ready, not published to primary). Actual hosted 13/13 HTTP/SHA (12 exact, 1 Netlify `index.html` RUM injection), 23/23 cities, 184/184 browser chart views, 23/23 CSV, KPI, Kyiv, 23-city deaths and zero JS errors. [Proof artifact #14029658328](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43411738247/artifacts/14029658328) independent outer SHA-256 `b0cfd9c0b8eed42d66d143ca272fbdda015ec892f4d985aa86eeee3de03eaf08`. `site-prod@f0cfcbc8` and Netlify production `6adb629bc3ebc570117d82e1` unchanged. **No production restore performed or authorized**; lock/auto-publish still unproven. `ROLLBACK_PACKAGE_READY=YES; NETLIFY_PREVIEW_READY=YES; ROLLBACK_OPERATIONAL_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.

<!-- coordination:history:end -->
