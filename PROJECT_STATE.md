# Project State — coordination snapshot

**2026-11-14. Latest accepted: C6-C3-ARCHIVE-GIT-ONLY-PUBLISH-PASS-01. GLOBAL_CUTOVER=YES; GIT_ONLY_PUBLICATION=PASS; AUTO_NEON_GIT=OFF; DST_CORRECTION=OFF.**

Read main documentation first; newer accepted PR #78 checkpoints govern. Historical records below remain verbatim; root byte gate ≤12,288 B PASS.

## Current production

- Historical Neon cutover PASS; `GLOBAL_CUTOVER=YES`. One Git-only archive publication [#43578315871](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43578315871) SUCCESS: `site-prod@2fa9044ad498391e5d995140af5f4096f0d4a2aa` (five JSON, one fast-forward commit). Netlify `6af76b2d67c5074986728b62` still READY/locked/current. Public browser HTTP display not independently certified; automatic 4-hour updates and live-status certification remain OFF.
- Manual pilot [#43510482714](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510482714) failed at step 46 `capture()`; C2 writer PASS: 33,444 episodes (+129), 23 cities, zero Git publication. Root cause unproven.
- Diagnostic-only [PR #130](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/130) merged `main@9576dd06beb6b905f5fc4001672e524ed0ba5d0b`; exact-head offline CI PASS, fixed reason allowlist. No physical fix proven.
- Freeze: legacy pause=true, AUTO flag OFF; owner screenshot confirmed updater disabled manually after second pilot, Netlify workflow disabled and current production deploy locked. One-time pilot authorization consumed; no repeat or auto-schedule grant.
- Owner-approved [PR #133](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/133) merged `main@5606147a955b64e17474688c6a13596b21d93580`, offline CI PASS; pre-capture redacted Git status added. Physical second pilot [#43523629106](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43523629106) C2/Neon PASS, capture FAIL: `C6_BLOCK_REASON=C2_CHECKPOINTS_MISSING`, despite checkpoint blob at site-prod Git root nested data path. Pre-capture reported correct HEAD/branch but scoped changes 0 / checkpoint missing. No Git publication; static production unchanged.
- Root cause for second failure proven: `capture()` used nested checkout instead of repository root. [PR #134](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/134) source `cc1ab14fda62b441883792b39d721230d0e2e165`, exact-head three CI PASS, squash-merged to `main@50a5be9ee78dfa2b25977393916e0a57a3571df5`. Two script invocations now use `$GITHUB_WORKSPACE` with regression coverage; no physical Git publication yet.

- Third owner-triggered [Actions #43568691823](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43568691823) FAILED at UkraineAlarm bridge validation, before C2 canonical Neon writer, capture or Git publication. Mykolaiv (region 98) was the only unverified row (20/21); poll overlap false after 20 history rows. No current writer commit proved in this run; production unchanged.

## Next

- Next: independently confirm public HTTP/browser generation, investigate the current Mykolaiv region 98 bridge overlap/continuity 20/21 and restore 21/21 before a separate owner-approved controlled C2 → Neon → Git-only cycle. Enable 4-hour automation only after that cycle and a separate owner GO. Historical 23-city read-only audit can run in parallel. 
- Keep updater and Netlify production workflows disabled, legacy publisher paused, AUTO flag OFF and Netlify locked. No new physical C2 pilot until narrow offline investigation of Mykolaiv region 98 bridge continuity gap (history no longer reaches previous poll), and separate owner GO. Do not bypass 21/21, rewrite production records or mix casualty/WIP/DST tracks.

## Latest accepted checkpoints

<!-- coordination:history:start -->
## C6-C3-ARCHIVE-GIT-ONLY-PUBLISH-PASS-01 (2026-11-14)

- Owner-approved [Actions #43578315871](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43578315871) attempt 1 completed SUCCESS at `main@413d34acd3bf664aebb821ffe3c0b022906299e0`, after PR #138 squash merge. Physical publisher at-use SHA/freshness/23-city checks and one fast-forward Git publication PASS: `site-prod@54079326ae2b4e691e2bfcf7cd1a51c9705404eb` → `2fa9044ad498391e5d995140af5f4096f0d4a2aa`, exactly five JSON changed. Recovery archive #14106191796 reused; no new C2, Neon writer, source HTTP or production Netlify job.
- Independent readback: Netlify deployment `6af76b2d67c5074986728b62` remains current READY/locked, no new deploy established. Public website/browser generation not HTTP-certified. `GIT_ONLY_PUBLICATION=PASS; AUTO_NEON_GIT=OFF`; Mykolaiv current-source bridge 20/21 remains unresolved, separate from 23/23 historical recovery proof. Next: narrow current continuity + one approved controlled automatic-cycle pilot; 23-city historical audit parallel.

## C6-PR136-OWNER-SQUASH-MERGE-PASS-01 (2026-11-14)

- Owner-approved PR #136 exact head `1924de20a3c382aa862a00c0a882579c4a43c996`; exact-head CI #43573370103, #43573370102, #43573370092 SUCCESS; enforced main ruleset check PASS, bypass NONE. Native squash merge returned `main@5c9684c2f953eeb71b4e273906ba8bc6d5f9cdb1`; PR merged. Recovery proof branch retained at approved HEAD.
- Post-merge site-prod `54079326ae2b4e691e2bfcf7cd1a51c9705404eb` unchanged; Netlify `6af76b2d67c5074986728b62` ready/locked. Only code merge authorized; no C2, Neon write, physical proof, Git JSON publication, Netlify deploy/unlock or schedule. `RECOVERY_PACKAGE=BLOCKED` pending separately approved one read-only proof and immutable delta.

## C6-ARCHIVE-RECOVERY-STAGED-BLOCKED-01 (2026-11-14)

- Draft PR #136 `1924de20` exact failed-run archive recovery code; exact-head offline Actions #43573370103/#43573370102/#43573370092 SUCCESS. C2 #43523629106 writer PASS, 23 archived receipts; physical six-JSON proof and delta artifact NOT RUN. `RECOVERY_PACKAGE=BLOCKED`; at-use freshness, 262 retained rows and no-loss candidate remain unverified. No merge, writer, push or deploy.


## C6-C3-MYKOLAIV-CSV-CROSSCHECK-01 — independent alerts.in.ua CSV cross-check, read-only (2026-11-14)

- Owner CSV exports 13/14 Nov: Mykolaivskyi raion AIR 17+5 rows, 1 exact duplicate = 21 distinct completed alerts. Prior official checkpoint `2026-11-12T22:59:25Z`; failed 14 Nov poll `~07:15Z` returned 20 completed AIR rows with no overlap. Assuming local Kyiv CSV timestamps, a bounded 20-row response can miss the previous checkpoint. This corroborates, but does not prove, exact cross-source event parity or authorize manual continuity. Offline match/provenance required; keep 21/21 fail-closed and live pilots paused.

## C6-C3-PILOT3-MYKOLAIV-BRIDGE-NOGO-01 — third manual pilot blocked before Neon writer (2026-11-14)

- Owner manual [Actions #43568691823](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43568691823), attempt 1 on `main@50a5be9ee78dfa2b25977393916e0a57a3571df5`, FAILED at step 25, `Validate verified UkraineAlarm bridge checkpoint`: `ValueError: bridge continuity is not fully verified`. Bridge fetch printed 20/21 continuous regions; `mykolaiv`, region 98, `continuous=False history=20 static_match=False poll_overlap=False`. Existing `apply_ukrainealarm_bridge.py` classifies this case as `history_window_no_longer_reaches_previous_poll`. No evidence of C2 canonical Neon writer, `capture()`, Git JSON publication; following jobs SKIPPED.
- Independent post-run `site-prod@54079326ae2b4e691e2bfcf7cd1a51c9705404eb` unchanged and current Netlify deployment `6af76b2d67c5074986728b62` ready/locked. `GLOBAL_CUTOVER=YES; PILOT3=FAIL; AUTO_NEON_GIT=OFF; GIT_PUBLICATION=ZERO`. One-shot grant consumed. Do not rerun C2 or weaken 21/21. Next task: isolate Mykolaiv bridge gap offline, using existing checkpoint/evidence; new run only after separate GO.

## C6-C3-MERGE134-CHECKOUT-ROOT-FIX-STAGED-01 — approved checkout-root fix merged; publication still pending (2026-11-14)

- Owner screenshot confirms `Update Ukraine air-alert production data` manually disabled after failed pilot. Other prior gates: legacy publisher pause=true, new AUTO flag absent, Netlify workflow manually disabled; current Netlify ID `6af76b2d67c5074986728b62` independently ready/locked, `site-prod@54079326ae2b4e691e2bfcf7cd1a51c9705404eb` unchanged. No active/queued/waiting/pending/requested Actions at pre-merge gate.
- [PR #134](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/134) source `cc1ab14fda62b441883792b39d721230d0e2e165` squash-merged, independent `main@50a5be9ee78dfa2b25977393916e0a57a3571df5`. Exact-head [C6 offline #43568003654](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43568003654), [timestamp #43568003594](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43568003594), [coordination #43568003564](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43568003564) SUCCESS. Only C6 diagnostic and capture checkout arguments changed from nested `$GITHUB_WORKSPACE/kyiv-air-alerts-grafana` to repository root `$GITHUB_WORKSPACE`; narrow offline regression and existing offline workflow gate updated. Fail-closed guards and publisher unchanged.
- Post-merge: no Actions runs for merge SHA on initial independent readback; `site-prod@54079326` and locked Netlify production `6af76b2d` unchanged. `GLOBAL_CUTOVER=YES; MERGE_134=YES; PILOT2=FAIL; NEXT_PILOT=NOT_RUN; AUTO_NEON_GIT=OFF`. No live writer/source HTTP, Git JSON publication, deployment/unlock or casualty/WIP/DST changes. New manual pilot requires separate owner GO.

## C6-C3-PILOT2-CHECKOUT-ROOT-FAIL-PROVEN-01 — second physical pilot failed; Git checkout-root mismatch proven (2026-11-14)

- Manual one-time [Actions #43523629106](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43523629106) attempt 1 on `main@5606147a955b64e17474688c6a13596b21d93580`: `update-site` FAIL at pre-Git `capture()` after canonical persistence `NEON_SUCCEEDED` and same-run C2 export. `C6_BLOCK_REASON=C2_CHECKPOINTS_MISSING`, exit 2. Safe `C6_PRECAPTURE_DIAG` showed `head=54079326ae2b4e691e2bfcf7cd1a51c9705404eb`, branch `site-prod`, `head_matches_expected=true`, `checkpoint_file_regular=false`, `scoped_changes=0`. Same-run C2 artifact #14086255755 and status #14085756162 saved. `site-prod` remained `54079326ae2b4e691e2bfcf7cd1a51c9705404eb`; Netlify `6af76b2d67c5074986728b62` ready/locked and current. No Git publication.
- Exact immutable checkpoint exists at `site-prod:kyiv-air-alerts-grafana/data/c2_history_capture_checkpoints.json`; checkout `actions/checkout` is at Git root `$GITHUB_WORKSPACE`, but diagnostic and capture were passed nested `$GITHUB_WORKSPACE/kyiv-air-alerts-grafana`, while script `PREFIX=kyiv-air-alerts-grafana/data/` is repo-root relative. This deterministic mismatch explains both missing checkpoint and falsely empty scoped status. No need to rerun 27-minute C2 to reproduce.
- One minimal correction staged in [Draft PR #134](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/134), exact `cc1ab14fda62b441883792b39d721230d0e2e165`: use `$GITHUB_WORKSPACE` for both calls, narrow disposable-Git regression; C6 offline #43568003654 SUCCESS and timestamp regression #43568003594 SUCCESS. No merge or new pilot. Owner should re-disable updater if not already disabled; AUTO flag OFF, old publisher paused, Netlify locked. Previous one-time pilot grant consumed. `GLOBAL_CUTOVER=YES; PILOT2=FAIL; ROOT_CAUSE=CHECKOUT_ROOT_MISMATCH; AUTO_NEON_GIT=OFF`.

## C6-C3-MERGE133-PRECAPTURE-DIAGNOSTIC-STAGED-01 — redacted pre-capture diagnostic merged, pilot not run (2026-11-14)

- [PR #133](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/133) owner-approved squash-merged to `main@5606147a955b64e17474688c6a13596b21d93580` from exact source `c0a90abd82e48f77f2f19018387a1010c59f9a8f`. Exact-head offline Actions [#43522310073](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43522310073), timestamp regression [#43522310133](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43522310133) and coordination docs [#43522310077](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43522310077) SUCCESS. Added redacted, read-only Git status before `capture()`, no changed fail-closed/publication logic.
- Screenshots: `C6_GIT_ONLY_PUBLISHER_PAUSED=true`; `C6_AUTO_NEON_GIT_ENABLED` absent; both production workflows `disabled_manually`. Pre/post: `site-prod@54079326ae2b4e691e2bfcf7cd1a51c9705404eb`, Netlify production `6af76b2d67c5074986728b62` ready/locked, merge-SHA production Actions 0. No C2/source HTTP, Neon writer, Git publication, Netlify deploy/unlock, casualty/WIP/DST changes.
- `GLOBAL_CUTOVER=YES; MERGE_133=YES; ROOT_CAUSE=UNKNOWN; PILOT=NOT_RUN; AUTO_NEON_GIT=OFF`. Owner authorized one conditional pilot subject to fresh gates; GitHub connector lacks workflow enable/dispatch actions. No cron activation or pilot repeat authorized.

## C6-C3-MERGE130-CAPTURE-DIAGNOSTIC-PASS-01 — diagnostic merge (2026-11-14)

- [PR #130](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/130) squash-merged `main@9576dd06beb6b905f5fc4001672e524ed0ba5d0b` from exact HEAD `2920931f27bec8de3214ee6d83322626e44be9a5`; offline CI and coordination-docs checks PASS. [Pilot #43510482714](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510482714) failed at capture step 46 after Neon writer PASS (+129), zero Git publication. Root cause unproven; diagnostic only. `site-prod@54079326`, locked Netlify `6af76b2d` unchanged. Auto OFF; no new pilot grant.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Archive index](docs/coordination-archive/README.md), [manifest](docs/coordination-archive/manifest.json), and [maintenance CLI](docs/coordination-maintenance.md) retain historical proofs; archive via a PR, no direct main push.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged `main@3735f359`; [Actions #41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) PASS. Ten archived records indexed above. Bot archival PR permission unverified; not a Neon release.
- **2026-11-13 archive housekeeping:** full pre-archive PR #78 root blobs are indexed in the manifest with source ref `421054a20f93a87a548cdebbe9a14fce669be293`; six older records from each root moved to immutable snapshots. No release gate changed.
