# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

Current accepted: **C6-C3-MERGE130-CAPTURE-DIAGNOSTIC-PASS-01.** GLOBAL_CUTOVER=YES; PILOT=FAIL; AUTO_NEON_GIT=OFF. Production unchanged. Earlier cutover PASS and stopped observations remain historical.

## Work S final execution observation (2026-11-13; publication not executed)

- Current pins `main@1dbacef1`, `site-prod@99648321`; exact Netlify production contract PASS, historical freshness 23/23, data/rollback identities 60/60 PASS. Registered dispatch UI worked; no release dispatch submitted.
- Automatic approval review rejected the temporary Netlify unlock as broader than a single production dispatch. Stopped before unlock/publication; original Netlify `6adb629bc3ebc570117d82e1` and site-prod unchanged. Removed Netlify grant and all 13 temporary variables; Git grant/flag never installed; both workflows disabled, pause=true, Netlify locked. Production release QA not run; rollback unnecessary. `CUTOVER_RESULT=BLOCKED; GLOBAL_CUTOVER=NO`. [Receipt](docs/work-s-final-execution-2026-11-13.json). Latest accepted Work T checkpoint below remains unchanged.

## Work S authorized execution observation (2026-11-13)

- Separate owner production GO received; execution stopped before dispatch. Physical FINAL/L/N SHA and 56 identity/preservation checks PASS; historical gate 23/23 PASS at real clock. Protected `c6-neon-git-release` created for owner review/main only, admin bypass OFF. Netlify variables/grant were installed, then removed after the dispatch blocker.
- Enabled Netlify workflow has no `Run workflow` control, including after reload; default `main` lacks that workflow file. Connected tools have no new dispatch operation and local CLI has no authenticated account. **Zero release dispatches/runs, zero deployments and zero Git publication commits.** No new code/default-branch change or merge.
- Final refs remain d68e35e3/99648321; Netlify before=after `6adb629bc3ebc570117d82e1`, ready/locked. Both workflows disabled, pause=true, all 13 temporary variables and Netlify grant removed; Git grant never installed. Protected environment retained empty. Casualty/aux unchanged; release production QA and rollback not run. `CUTOVER_RESULT=BLOCKED; GLOBAL_CUTOVER=NO`. [Receipt](docs/work-s-execution-2026-11-13.json). Latest accepted checkpoint below remains unchanged.

<!-- coordination:history:start -->
### C6-C3-MERGE130-CAPTURE-DIAGNOSTIC-PASS-01 — diagnostics merged (2026-11-14)

- [PR #130](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/130) squash-merged into `main@9576dd06beb6b905f5fc4001672e524ed0ba5d0b`; exact source HEAD `2920931f27bec8de3214ee6d83322626e44be9a5` and required offline CI PASS. Manual C2→Neon→Git [#43510482714](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510482714) FAIL at `capture()` step 46; Neon +129 PASS; Git publication 0. Diagnostics now expose only fixed allowed error codes; cause still unknown. Production `site-prod@54079326`, Netlify `6af76b2d` locked unchanged; auto OFF, no pilot GO.

### C6-C3-WORKS-NEON-CUTOVER-PASS-01 — production historical Neon cutover completed (2026-11-13; accepted)

- Owner-approved one Netlify dispatch #43496568449 SUCCESS on site-prod@99648321; actual production `6af76b2d67c5074986728b62` published 19:55:27Z, canonical KPI SHA `ce3cd92f…194d5`, generation 10:08:11+02:00 and 23 cities independently verified 19:55:58Z. One approved temporary unlock followed by relock; independent API `locked=true` before separate Git grant.
- One main@1dbacef1 publisher dispatch #43497605769 SUCCESS after protected owner review; site-prod publication `54079326ae2b4e691e2bfcf7cd1a51c9705404eb` at 20:03:12Z, parent99648321. Six FINAL JSON match Git/live HTTP; only four allowed JSON paths changed. Kyiv interval tuples 2,858→2,858 exact; casualty/aux preserved. QA 23 cities/184 views/23 CSV (644 rows), rendered Kyiv causes/casualty, site JS errors0. Both stages before 14 November12:40:40 Kyiv; real-clock freshness23/23 and60/60 identities rechecked, no bypass.
- Auto publishing OFF/approved deploy locked, both workflows disabled, pause=true, both grants/13 repository variables/Git release flag removed; environment empty. Rollback not needed. No C2/writer/source HTTP, old proof rerun, merge, DST or casualty/WIP change. Keep freeze; no automatic Git-only C2 resumption. `CUTOVER_RESULT=PASS; GLOBAL_CUTOVER=YES`. [Receipt](docs/work-s-final-execution-2026-11-13.json). Earlier stopped observations below remain historical.

### C6-C3-WORKT-MERGE123-DISPATCH-REGISTERED-01 — PR #123 merge under freeze (2026-11-13; accepted)

- Owner screenshots confirmed pause=true and both workflows disabled; Netlify current locked and no competing runs. PR #123 exact workflow from site-prod, two CI PASS; merged `main@1dbacef11367b97805c43be112cfeb2c23c12072`. Default-branch registration resolved, no deploy/dispatch/cutover. Re-pin Work S, recheck freshness before release. `GLOBAL_CUTOVER=NO`.


### C6-C3-WORKS-DISPATCH-DEFAULT-BRANCH-BLOCK-01 — verified dispatch prerequisite (2026-11-13; accepted)

- `main` lacks Netlify workflow (404); `site-prod` has `workflow_dispatch`. GitHub requires the default-branch file; CLI/REST alone cannot unblock. Next: minimal separately approved registration PR to `main`, safe job/trigger guards, re-pin main SHA. No merge or production changes; `GLOBAL_CUTOVER=NO`.


### C6-C3-WORKS-OWNER-GATES-NOGO-01 — data/freshness/rollback PASS; production authorization setup pending (2026-11-13; accepted)

- Merged SHA d68e35e3/99648321 confirmed; N/R code equals prior exact-head PASS. Physical FINAL #14025629654 SHA f2252da0…051ed and six hashes/23 cities verified; Work N backup #14028565807 remains current after code-only #120 (runtime, casualty, Kyiv, aux, frontend), Work P not repeated. Historical gate 23/23 PASS until **2026-11-14 12:40:40 Kyiv**. Pause=true, both workflows disabled, Netlify original ready/locked, five active/queued statuses 0. Missing `c6-neon-git-release` protected environment and new production grants/variables prevent execution. One minimal next action: distinct owner GO for pinned temporary gate setup and Netlify-first→Git sequence; [procedure](docs/work-s-release-2026-11-13.md), [receipt/templates](docs/work-s-release-2026-11-13.json). `FINAL_RELEASE_PREFLIGHT=FAIL; CUTOVER_READY=NO; ROLLBACK_READY=YES; ADMIN_FREEZE_VERIFIED=YES; GLOBAL_CUTOVER=NO`. Only requested coordination docs changed; no production actions.


<!-- coordination:history:end -->

