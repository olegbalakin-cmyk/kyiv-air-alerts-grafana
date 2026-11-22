# Project State — current coordination snapshot

**Date:** 2026-11-15. **Casualty PROMOTE=OFF.** C6 is governed by newer accepted `main:PROJECT_STATE.md`; this casualty draft does not change production.
Latest C6 state: governed by newer `main:PROJECT_STATE.md`, not this casualty coordination draft.
Latest casualty: **CASUALTY-OCT2026-FOUR-EVENT-LOWERBOUND-PREVIEW-2026-11-22-01**: PR #236 CI #45073045655 PASS: 4 city events/11 civilian deaths October partial preview, 19 unknown; no credits/PROMOTE.

## Working instructions

1. Read both root documents first; newer accepted checkpoints govern old memory.
2. Verify exact commits, Actions and artifacts; research PASS does not imply production.
3. Separate production, WIP, history, backfill, casualty and Neon; no overwritten commits, force pushes or leaked credentials.
4. Keep live blockers/status/next tasks outside history markers; accepted checkpoints inside, newest first, full evidence in archives.
5. Aim for 5–8 KiB state and 5–10 changelog entries; ≤12,288 B PASS, ≤16,384 WARNING, above FAIL. Before oversize, use [maintenance CLI](docs/coordination-maintenance.md) dry-run then archive on a separate branch.
6. Search checkpoint IDs and read bounded lines; avoid bulk JSON/SQL, archives and full logs. Preserve reproducible work; recover interrupted commits first.

## Current tracks and open release gates

- **Other tracks:** production/C6, Neon, C3, API, DST and historical completeness follow newer accepted `main:PROJECT_STATE.md`; this casualty draft does not authorize changes to them.
- **Operational WIP / casualty:** 4 verified October air-attack events, 11 civilian deaths as lower bounds, incomplete city/month coverage. No credits/PROMOTE.

## Concrete next tasks

1. C6 production/stabilization/DST tasks: see newer `main:PROJECT_STATE.md` and PR #78; do not use old C6 tasks in this casualty draft.
2. Casualty H/I: PRs #114/#115 PASS offline, no release.
3. Casualty next: test actual UA/EN frontend partial-month notation and nulls before separate owner publication GO; no site writes now.
4. Separately verify actual Netlify frontend asset and its GitHub Raw JSON fetch read-only; until then live casualty parity is UNVERIFIED.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-OCT2026-FOUR-EVENT-LOWERBOUND-PREVIEW-2026-11-22-01 (2026-11-22)

- [Draft #236](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/236) `270702ccc4a76d81ee8cc5b9cf73059fd19df025`, [CI #45073045655](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45073045655) SUCCESS, network SKIPPED. Four October civilian aerial incidents: Lutsk 6, Poltava 1 (cruise missile), Ivano-Frankivsk 1 (excludes Oct11 military dead), Khmelnytskyi 3 (2+1 later hospital death). 23-city research preview: 4 known **lower bounds**, 19 null unknowns, not exact month/year data. UA/EN presentation module tested but not connected to live UI. 0 credits/WIP/site-prod/Neon writes; PROMOTE OFF.

## CASUALTY-OCT2026-13-INCIDENT-REVIEW-OFFLINE-PASS-2026-11-22-01 (2026-11-22)

- [PR #235](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/235) #45071282274 offline PASS, 13 initial review groups/10 cities, zero credits; later source verification in PR #236.

## CASUALTY-MONTHLY-27GET-PHYSICAL-21OF27-REVIEWONLY-2026-11-22-01 (2026-11-22)

- Run #45070256716: 27 GET, 21 HTTP200, 6 blocked; proof #14773425588 hashes in detailed report. GO spent, 0 credits/PROMOTE.

## CASUALTY-MONTHLY-27GET-OWNER-GO-ACCEPTED-DISPATCH-PENDING-2026-11-22-01 (2026-11-22)

- Owner GO `casualty-23city-monthly-20261122-001` approved exact `11f9f2d`; spent #45070256716, 0 credits.

## CASUALTY-MONTHLY-ONE-SHOT-GRANT-PREPARED-2026-11-22-01 (2026-11-22)

- 27-GET grant digest `0b655665…` prepared for #234, subsequently owner approved and spent #45070256716.

## CASUALTY-MONTHLY-COLLECTOR-OFFLINE-CI-PASS-2026-11-22-01 (2026-11-22)

- [PR #234](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/234) #45046769980 12/12 offline PASS; live proof separately accepted, PROMOTE OFF.

## CASUALTY-MONTHLY-23CITY-WEB-AUDIT-PARTIAL-2026-11-22-01 (2026-11-22)

- [Draft #233](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/233) 23 cities (12 leads/11 UNKNOWN), 27 URLs; DNS blocked real GET. Monthly region/scope incompatible, no credits/PROMOTE.

## CASUALTY-WORKAH-LIVE-3HTTP200-1NUMERIC-REVIEWONLY-2026-11-22-01 (2026-11-22)

- Run #45020948794 PASS: 3/3 HTTP200, T03/T04 numeric UNKNOWN, T05=3, artifact #14753224774, hashes in log. GO spent, no credits/PROMOTE.

## CASUALTY-WORKAI-ARTICLE-GO-APPROVED-NOT-DISPATCHED-2026-11-22-01 (2026-11-22)

- Owner GO `workai-article-20261122-001` approved for AH `2b3b5799`, 3 article GET/0 RSS, expiry 2026-11-23T12Z. Initially pending; used once by run #45020948794, PROMOTE OFF.

## CASUALTY-WORKAI-OFF-DISPATCH-VERIFIED-2026-11-18-01 (2026-11-18)

- Owner Actions #44326207596 manual OFF: all jobs SKIPPED, 0 GET. Later article pilot documented separately.

## CASUALTY-WORKAI-PR198-MANUAL-REGISTRATION-MERGED-2026-11-18-01 (2026-11-18)

- PR #198 merged main@ddb58809, manual registration-only workflow, no automatic publisher or credits.

## CASUALTY-WORKAH-OFFLINE-PASS-EXPIRED-GO-DISPATCH-UNVERIFIED-2026-11-17-01 (2026-11-17)

- PR #177 CI #43709216154 29/29 offline PASS; network SKIPPED, older GO expired, 0 GET.

## CASUALTY-WORKAG-ARTICLE-FIRST-OFFLINE-PASS-LIVE-BLOCKED-01 (2026-11-15)

- [PR #174](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/174) `4d20b5f0`, CI #43706844061 20/20 offline, artifact #14159030801 SHA in log. 4 synthetic HTML fixtures only, live proof pending.

## CASUALTY-WORKAF-FILTER-ALLOWLIST-GO-OFFLINE-PASS-LIVE-BLOCKED-01 (2026-11-15)

- PR #173 CI #43702948168 12/12 offline, artifact #14157426485 (hash archived). No live GET or credits.

## CASUALTY-WORKAE-DUAL-RSS-PILOTS-RECONCILED-BUDGET-EXCEEDED-2026-11-15-01 (2026-11-15)

- Shared 6-GET GO mistakenly consumed twice in runs #43700780104/#43700806130 (12 RSS GET); each 5/6 HTTP200, 115 links. No article GET/credits; avoid replay.

## CASUALTY-WORKAE-SIX-DIRECT-RSS-ONESHOT-5OF6-2026-11-15-01 (2026-11-15)

- [PR #171](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/171) `53c48f0b`, #43700806130 5/6 RSS200, 115 links, artifact #14156048863 SHA in log; duplicate GO recorded separately.

## CASUALTY-WORKAD-URL-WORKJ-FACTS-OFFLINE-PASS-SHADOW-PARTIAL-01 (2026-11-15)

- Work AD URL and fact offline PASS, proof archived; no publisher GET/credits.

## CASUALTY-WORKAC-BOUNDED-CAPTURE-OFFLINE-PASS-LIVE-BLOCKED-01 (archived evidence)

- [PR #169](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/169) CI #43696226023 17/17 offline, artifact #14154303167 SHA in log. No publisher GET/credits.

## CASUALTY-WORKAB-SHADOW-OFFLINE-PASS-LIVE-BLOCKED-01 (archived evidence)

- Work AB city-shadow offline PASS, proof archived; no publisher GET/credits.

## CASUALTY-WORKAA-CONTEXT-OFFLINE-PASS-EVIDENCE-PARTIAL-01 (2026-11-14)

- [PR #160](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/160) `38b444df`, [CI #43643850083](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43643850083) 183 PASS/1 SKIP, artifact #14132887476 (SHA in changelog). T03–T05 evidence partial/unlinked, 0 HTTP/credits; PROMOTE OFF.

## CASUALTY-WORKZ-HTTP200-EVIDENCE-PARTIAL-01 (2026-11-14)

- [PR #145](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/145), [run #43609731091](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43609731091): 3 GET/HTTP200, three unproven pairs, 0 credits. GET grant spent. Saved excerpts only; absent text cannot be recovered offline.

## CASUALTY-WORKW-INTEGRATION-OFFLINE-PASS-01 (2026-11-14)

- [PR #141](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/141) `4e083db7` / CI #43589692637 PASS. Protected write OFF; research only, zero production changes.

## CASUALTY-WORKX-INDEPENDENT-SCAN-EVIDENCE-OFFLINE-PASS-01 — offline PASS (2026-11-14)

- [PR #142](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/142) `b07a5957`, Actions #43589727392 169 PASS/1 SKIP, artifact #14111089895 (SHA in CHANGELOG). 23-city independent RSS plan and retained cards tested; 3/3 T03–T05 NEEDS_REVIEW. No live HTTP, credits, merge or deployment.

## CASUALTY-WORKV-REVIEWER-OPERATOR-OFFLINE-E2E-PASS-01 — physical offline chain PASS (2026-11-14)

- [PR #140](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/140) offline reviewer+operator chain PASS; historical proof preserved. No live credits/PROMOTE.

## CASUALTY-WORKTU-CONTRACT-AND-LIVE-JSON-GATES-01 — Work T code mismatch verified; Work U live parity unresolved (2026-11-14)

- Exact Git blobs: `main@413d34ac` reviewer `cf65d85c`, operator `740b985b`, workflow `3771a501`; `site-prod@2fa9044a` generator `f5840c20`. The reviewer does not emit generator's incident/proof fields; operator preview calculates a raw delta sum, not the cumulative effective credit. PR #105 [shadow Actions #43290975899](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43290975899) SUCCESS does not prove scheduled operation. No new code deployed.
- Work U: Zaporizhzhia Git JSON compared against PR #139, 316 deaths, September last validated month, October absent. Current Netlify deploy `6af76b2d` is READY/locked, but the actual served frontend/data fetch was not captured; `LIVE_PARITY=UNVERIFIED`. Live site may fetch GitHub Raw directly; do not equate locked deploy with frozen JSON. T03–T05 remains blocked, death credits 0.

## CASUALTY-WORKR-OWNER-ONE-SHOT-HTTP200-CONTEXT-CAPTURE-PASS-IDENTITY-REVIEW-01 (archived evidence)

- [PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137), CI #43574791160 3 HTTP200, artifact #14105343291 SHA in log. T03–T05 incident identity not proven, 0 credits.

## CASUALTY-WORKR-IDENTITY-REVIEW-PREFLIGHT-SOURCE-REVIEW-REQUIRED-01 (2026-11-14)

- [PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137) `f2f3a922`, CI #43573408615 153 PASS/1 SKIP, ZIP #14104883690 SHA256 `6ab3d7ec12d6973f8ea3f63bc6fe572364dba0c48eb514ff39b7e3ecfba8d76b`, independent/11 inner PASS. T03–T05 ages overlap, attack identity INSUFFICIENT_EVIDENCE. 0 credits/GET.

## CASUALTY-WORKQ-REAL-EXCERPTS-AUXCI-OFFLINE-PARTIAL-01 (archived evidence)

- Historical real excerpts, not full HTML (Work Q proof archived); T03–T05 identity unresolved, 0 credits.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
