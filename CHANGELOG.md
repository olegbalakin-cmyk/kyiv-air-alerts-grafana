# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### C6-C3-MERGE119-120-FREEZE-PASS-01 — both approved code merges completed under freeze (2026-11-13; accepted)

- #119 main squash `d68e35e35c8d50954a77adf99a7dda668724734b` at 12:43:55Z retained; fresh guard preflight allowed Cloud Browser #120 site-prod squash **`99648321e64037a6dcf3ae0072d66eedcccc2839`** at 14:38:55Z, exact source `ac32540f`, Work R CI #43422122898 PASS. All three guards reconfirmed at 14:39:50Z. #120 merge SHA has 0 Actions runs, no automatic production deploy; active/queued runs 0; Netlify latest deploy remains 10:47Z Work O, current production `6adb629bc3ebc570117d82e1` ready/locked. No C2/writer, Git JSON publication, deployment, unlock or cutover. `MERGE_119=YES; MERGE_120=YES; ADMIN_FREEZE_VERIFIED=YES; PRODUCTION_UNCHANGED=YES; GLOBAL_CUTOVER=NO`. Next: read-only merged-SHA release preflight, then distinct owner production GO. Prior hold and history retained exactly in current/archived roots.

### C6-C3-MERGE119-PASS-MERGE120-HOLD-01 — #119 merged; #120 held by guard stop (2026-11-13; accepted)

- With all three guards initially confirmed and exact-head CI PASS, Cloud Browser squash-merged #119 at 12:43:55Z: `main@d68e35e35c8d50954a77adf99a7dda668724734b`. Post-merge Coordination docs #43427654796 SUCCESS; no C2/writer/publisher run. After reload, GitHub pause=true and Netlify workflow disabled remained confirmed, but Netlify lock heading probe returned false. Automatic approval review rejected the follow-up wait under the owner's stop-on-unconfirmed-guard condition. Stopped before #120; remains Draft at `ac32540f`, merge SHA=null; `site-prod@f0cfcbc8` unchanged. Final read-only Netlify current `6adb629bc3ebc570117d82e1` ready; no deploy/publish/unlock. `MERGE_119=YES; MERGE_120=NO; ADMIN_FREEZE_VERIFIED=NO` (Netlify lock unconfirmed, no actual unlock established); `PRODUCTION_UNCHANGED=YES; GLOBAL_CUTOVER=NO`. Next: owner-approved new read-only guard preflight before resuming #120.

### C6-C3-ADMIN-FREEZE-VERIFIED-01 — Cloud Browser administrative freeze verified (2026-11-13; accepted)

- At 12:22:49 UTC: persisted repo pause **true → true**; production Netlify Actions workflow **manually disabled → manually disabled**; Netlify **Auto publishing ON → locked/OFF**. Production `6adb629bc3ebc570117d82e1` remains published and locked. All GitHub in-progress/queued/waiting/pending/requested filters 0; no competing production publisher observed. No other workflows or casualty/WIP settings changed; no merge, C2/writer, JSON publication, deployment or cutover. Restore later: retain original GitHub guards, inspect pending/newer deployments, unlock approved Netlify production, verify ON and pointer. Next requires separate owner approval for #119/#120 merges; production GO remains distinct. `ADMIN_FREEZE_VERIFIED=YES; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-C3-PREMERGE-GUARDS-UNVERIFIED-01 — cutover preparation read-only; admin locks unverified (2026-11-13; accepted)

- Owner prep-only approval. `main@712c9e35`, `site-prod@f0cfcbc8`, PR #119/#120 Draft, CI 43407785056/43422122898 PASS, Work N rollback #14028565807 available, Netlify original `6adb629bc3ebc570117d82e1` live. **No switches changed**: GitHub repo pause variable and Netlify Actions workflow/Auto publishing cannot be configured via connected tools. Merging #119 risks C2 workflow push; merging #120 triggers GitHub Netlify `--prod` workflow push. Operator must verify pause/disable before separate merge authorization; release then needs new data/rollback proof, Netlify-first static KPI + independent owner GO. `CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.


### C6-C3-WORKR-NETLIFY-RECOVERY-OFFLINE-PASS-01 — Work R 16/16 offline PASS (2026-11-13; accepted)

- Draft [PR #120](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/120) `ac32540fcb0074afaed20ec9f6849b32777dc9c7`, [exact-head CI #43422122898](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43422122898) SUCCESS 16/16 offline incl. legacy path, SHA/run/approval negatives; initial #43421545056/#43422060631 failures fixed by test assertion corrections only. No merge or production action. `NETLIFY_CONTRACT_READY=YES` offline; PR #119/120 merge and fresh publisher/Netlify gates require separate GO. `CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-C3-WORKQ-NETLIFY-CONTRACT-NOGO-01 — accepted Netlify recovery-proof release blocker (2026-11-13)

- Verified `main@712c9e35`, `site-prod@f0cfcbc8`, Work L/M/N artifacts and Netlify restored production unchanged; Work P rollback operational PASS. Work N publisher PR #119 Draft. Netlify Neon release requires successful C2 `update-netlify-site.yml` C6 preparation artifact absent from C2 #43321997695 (update-site job PASS, overall FAIL); isolated Work L #43390770985 does not satisfy. Scope one fail-closed Netlify recovery-proof contract fix; then separately approved merges, effective workflow rights/owner gate and fresh no-loss manifest. `FINAL_PREFLIGHT=FAIL; ROLLBACK_OPERATIONAL_READY=YES` (tested setup); `CUTOVER_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

<!-- coordination:history:end -->
