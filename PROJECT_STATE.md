# Project State — coordination snapshot

**2026-11-14. Latest accepted: C6-C3-PILOT2-CHECKOUT-ROOT-FAIL-PROVEN-01. GLOBAL_CUTOVER=YES; PILOT=FAIL; AUTO_NEON_GIT=OFF; DST_CORRECTION=OFF.**

Read main documentation first; newer accepted PR #78 checkpoints govern. Historical records below remain verbatim; root byte gate ≤12,288 B PASS.

## Current production

- Historical Neon cutover PASS; `GLOBAL_CUTOVER=YES`. Git `site-prod@54079326ae2b4e691e2bfcf7cd1a51c9705404eb`; Netlify `6af76b2d67c5074986728b62` ready/locked. [Work S receipt](docs/work-s-final-execution-2026-11-13.json). No automatic updates or live-status certification.
- Manual pilot [#43510482714](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43510482714) failed at step 46 `capture()`; C2 writer PASS: 33,444 episodes (+129), 23 cities, zero Git publication. Root cause unproven.
- Diagnostic-only [PR #130](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/130) merged `main@9576dd06beb6b905f5fc4001672e524ed0ba5d0b`; exact-head offline CI PASS, fixed reason allowlist. No physical fix proven.
- Freeze: legacy pause=true and AUTO flag OFF at owner preflight; Netlify workflow disabled and production deploy locked. Updater was temporarily enabled for pilot; its present disabled state requires owner UI confirmation. Manual pilot authorization consumed; no repeat and no auto-schedule grant.
- Owner-approved [PR #133](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/133) merged `main@5606147a955b64e17474688c6a13596b21d93580`, offline CI PASS; pre-capture redacted Git status added. Physical second pilot [#43523629106](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43523629106) C2/Neon PASS, capture FAIL: `C6_BLOCK_REASON=C2_CHECKPOINTS_MISSING`, despite checkpoint blob at site-prod Git root nested data path. Pre-capture reported correct HEAD/branch but scoped changes 0 / checkpoint missing. No Git publication; static production unchanged.
- Root cause for second failure proven: capture used `$GITHUB_WORKSPACE/kyiv-air-alerts-grafana` instead of `$GITHUB_WORKSPACE`, although script `PREFIX` expects repo-root-relative nested path. Minimal correction staged only in [Draft PR #134](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/134), HEAD `cc1ab14fda62b441883792b39d721230d0e2e165`; C6 offline and timestamp CI PASS; not merged.

## Next

- Stop all live pilots: one-time grant consumed. Owner should verify `Update Ukraine air-alert production data` manually DISABLED after the run. Keep legacy publisher paused, AUTO flag OFF, Netlify locked and its deployment workflow disabled. Review PR #134 offline tests/coordination CI and only then consider separately authorized merge; physical repilot requires a new explicit owner GO. Casualty/WIP/DST separate.

## Latest accepted checkpoints

<!-- coordination:history:start -->
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
