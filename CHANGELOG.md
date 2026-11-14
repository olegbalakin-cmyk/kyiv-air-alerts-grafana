# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

Current accepted: **C6-C3-MYKOLAIV-CSV-CROSSCHECK-01.** GLOBAL_CUTOVER=YES; PILOT=FAIL; AUTO_NEON_GIT=OFF. Production unchanged. Earlier cutover PASS and stopped observations remain historical.

## Work S final execution observation (2026-11-13; publication not executed)

- Current pins `main@1dbacef1`, `site-prod@99648321`; exact Netlify production contract PASS, historical freshness 23/23, data/rollback identities 60/60 PASS. Registered dispatch UI worked; no release dispatch submitted.
- Automatic approval review rejected the temporary Netlify unlock as broader than a single production dispatch. Stopped before unlock/publication; original Netlify `6adb629bc3ebc570117d82e1` and site-prod unchanged. Removed Netlify grant and all 13 temporary variables; Git grant/flag never installed; both workflows disabled, pause=true, Netlify locked. Production release QA not run; rollback unnecessary. `CUTOVER_RESULT=BLOCKED; GLOBAL_CUTOVER=NO`. [Receipt](docs/work-s-final-execution-2026-11-13.json). Latest accepted Work T checkpoint below remains unchanged.

## Work S authorized execution observation (2026-11-13)

- Separate owner production GO received; execution stopped before dispatch. Physical FINAL/L/N SHA and 56 identity/preservation checks PASS; historical gate 23/23 PASS at real clock. Protected `c6-neon-git-release` created for owner review/main only, admin bypass OFF. Netlify variables/grant were installed, then removed after the dispatch blocker.
- Enabled Netlify workflow has no `Run workflow` control, including after reload; default `main` lacks that workflow file. Connected tools have no new dispatch operation and local CLI has no authenticated account. **Zero release dispatches/runs, zero deployments and zero Git publication commits.** No new code/default-branch change or merge.
- Final refs remain d68e35e3/99648321; Netlify before=after `6adb629bc3ebc570117d82e1`, ready/locked. Both workflows disabled, pause=true, all 13 temporary variables and Netlify grant removed; Git grant never installed. Protected environment retained empty. Casualty/aux unchanged; release production QA and rollback not run. `CUTOVER_RESULT=BLOCKED; GLOBAL_CUTOVER=NO`. [Receipt](docs/work-s-execution-2026-11-13.json). Latest accepted checkpoint below remains unchanged.

<!-- coordination:history:start -->
### C6-C3-MYKOLAIV-CSV-CROSSCHECK-01 — owner CSV cross-check (2026-11-14)

- Offline: alerts.in.ua exports 13/14 Nov contain 17+5 Mykolaivskyi-raion AIR records, 1 overlap, 21 unique completed. Official last checked `2026-11-12T22:59:25Z`; 14 Nov `regionHistory` returned 20 records, overlap false. CSV timing assumed Kyiv local; consistent with finite history window overflow, NOT proof of exact source parity or permission to override 21/21. No code, Neon, Git or Netlify writes.

### C6-C3-PILOT3-MYKOLAIV-BRIDGE-NOGO-01 — manual pilot halted by Mykolaiv continuity guard (2026-11-14)

- Owner [#43568691823](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43568691823), `main@50a5be9ee78dfa2b25977393916e0a57a3571df5`, FAIL at `Validate verified UkraineAlarm bridge checkpoint`; 20/21 rows continuous. Mykolaiv region 98 `continuous=False; history=20; poll_overlap=False`: fetched history did not reach previous verified poll, so the existing fail-closed validator rejected it. Stopped before C2 canonical Neon writer, `capture()` and Git publication. `site-prod@54079326` and Netlify `6af76b2d` ready/locked unchanged. `GLOBAL_CUTOVER=YES; PILOT3=FAIL; AUTO_NEON_GIT=OFF`. New pilot requires separate GO; investigate only this gap offline, without weakening 21/21.

### C6-C3-MERGE134-CHECKOUT-ROOT-FIX-STAGED-01 — approved PR #134 merge; manual pilot still required (2026-11-14)

- Screenshot confirms `Update Ukraine air-alert production data` manually disabled following second failed pilot; legacy pause=true, AUTO flag absent, Netlify workflow disabled at prior owner gate. [PR #134](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/134) source `cc1ab14fda62b441883792b39d721230d0e2e165` merged `main@50a5be9ee78dfa2b25977393916e0a57a3571df5`; exact-head offline #43568003654, timestamp #43568003594, coordination #43568003564 SUCCESS. Changed only pre-capture diagnostic and `capture()` checkout arguments to repository root `$GITHUB_WORKSPACE` with regression test; existing fail-closed logic unchanged. Independent postmerge `site-prod@54079326` and Netlify `6af76b2d` ready/locked unchanged; zero production Actions on new merge SHA initial readback. `GLOBAL_CUTOVER=YES; MERGE_134=YES; NEXT_PILOT=NOT_RUN; AUTO_NEON_GIT=OFF`. Previous one-time pilot grant consumed; new physical pilot requires new owner GO. No Git publication, C2/writer, Netlify deployment or casualty/WIP/DST change.

### C6-C3-PILOT2-CHECKOUT-ROOT-FAIL-PROVEN-01 — physical pilot FAIL, checkout-root mismatch proven (2026-11-14)

- Owner-triggered manual [#43523629106](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43523629106) at `main@5606147a955b64e17474688c6a13596b21d93580`: C2 writer `NEON_SUCCEEDED`, bundle #14086255755 and status #14085756162; `capture()` exit 2, `C6_BLOCK_REASON=C2_CHECKPOINTS_MISSING`. Redacted diagnostic confirmed correct `site-prod@54079326` HEAD, branch site-prod, but 0 scoped changes/checkpoint missing. Checkpoint Git blob actually exists at nested repository path. Proven mismatch: caller passed nested `$GITHUB_WORKSPACE/kyiv-air-alerts-grafana` while script expects root `$GITHUB_WORKSPACE`. Git publication 0, current locked Netlify `6af76b2d` unchanged. Minimal root-only correction staged [Draft PR #134](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/134) HEAD `cc1ab14fda62b441883792b39d721230d0e2e165`, offline CI #43568003654/#43568003594 SUCCESS; not merged, no pilot repeat. Owner to confirm updater disabled; AUTO OFF, Netlify locked. `GLOBAL_CUTOVER=YES; PILOT2=FAIL; ROOT_CAUSE=CHECKOUT_ROOT_MISMATCH; AUTO_NEON_GIT=OFF`.

### C6-C3-MERGE133-PRECAPTURE-DIAGNOSTIC-STAGED-01 — PR #133 diagnostic merged, pilot not run (2026-11-14)

- Owner-approved [PR #133](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/133), source `c0a90abd82e48f77f2f19018387a1010c59f9a8f`, squash-merged to `main@5606147a955b64e17474688c6a13596b21d93580`. Exact-head C6 offline [#43522310073](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43522310073), timestamp [#43522310133](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43522310133), coordination docs [#43522310077](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43522310077) SUCCESS. Redacted read-only Git status added immediately before existing `capture()`; fail-closed logic unchanged. Owner screenshots confirmed legacy pause=true, new AUTO flag absent, both workflows disabled. `site-prod@54079326` and Netlify `6af76b2d` locked unchanged, no production runs from merge. `GLOBAL_CUTOVER=YES; ROOT_CAUSE=UNKNOWN; MERGE_133=YES; PILOT=NOT_RUN; AUTO_NEON_GIT=OFF`. One manual pilot authorized only after fresh gates; GitHub connector cannot enable/dispatch workflow. No production publication or deployment.

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

