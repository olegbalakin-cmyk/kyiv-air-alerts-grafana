# Project State — current coordination snapshot

**Date:** 2026-11-15. **Casualty PROMOTE=OFF.** C6 is governed by newer accepted `main:PROJECT_STATE.md`; this casualty draft does not change production.
Latest C6 state: governed by newer `main:PROJECT_STATE.md`, not this casualty coordination draft.
Latest casualty: **CASUALTY-WORKAI-PR198-MANUAL-REGISTRATION-MERGED-2026-11-18-01**: owner GO merged PR #198, `main@ddb58809`, manual-only registration; OFF dispatch and separate article GO pending.

## Working instructions

1. Read both root documents first; newer accepted checkpoints govern old memory.
2. Verify exact commits, Actions and artifacts; research PASS does not imply production.
3. Separate production, WIP, history, backfill, casualty and Neon; no overwritten commits, force pushes or leaked credentials.
4. Keep live blockers/status/next tasks outside history markers; accepted checkpoints inside, newest first, full evidence in archives.
5. Aim for 5–8 KiB state and 5–10 changelog entries; ≤12,288 B PASS, ≤16,384 WARNING, above FAIL. Before oversize, use [maintenance CLI](docs/coordination-maintenance.md) dry-run then archive on a separate branch.
6. Search checkpoint IDs and read bounded lines; avoid bulk JSON/SQL, archives and full logs. Preserve reproducible work; recover interrupted commits first.

## Current tracks and open release gates

- **Other tracks:** production/C6, Neon, C3, API, DST and historical completeness follow newer accepted `main:PROJECT_STATE.md`; this casualty draft does not authorize changes to them.
- **Operational WIP / casualty:** Work AH 29/29 offline PASS, research-only; PR #198 registered manual-only workflow on main. Research dispatch not yet tested. No publisher GET/credits; PROMOTE OFF.

## Concrete next tasks

1. C6 production/stabilization/DST tasks: see newer `main:PROJECT_STATE.md` and PR #78; do not use old C6 tasks in this casualty draft.
2. Casualty H/I: PRs #114/#115 PASS offline, no release.
3. Casualty next: separate owner-approved manual `article_go=OFF` dispatch on exact Work AH branch, then fresh GO manifest/expiry and distinct owner GO for 3 T03–T05 article GET. No RSS, WIP/production writes or PROMOTE.
4. Separately verify actual Netlify frontend asset and its GitHub Raw JSON fetch read-only; until then live casualty parity is UNVERIFIED.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-WORKAI-PR198-MANUAL-REGISTRATION-MERGED-2026-11-18-01 (2026-11-18)

- [PR #198](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/198) `afdd4e7b` merged `main@ddb5880938f3dfac95f63e34a26839c18589bcd5`: 1 new 55-line manual-only workflow. No push/schedule, parser, live job on main, data/WIP changes or publisher HTTP. Research OFF-dispatch pending, old GO expired. No credits; PROMOTE OFF.

## CASUALTY-WORKAH-OFFLINE-PASS-EXPIRED-GO-DISPATCH-UNVERIFIED-2026-11-17-01 (2026-11-17)

- [PR #177](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/177) `2b3b5799`, [CI #43709216154](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43709216154) 29/29 offline PASS, proof #14159263098 (SHA in log), 3/3 inner PASS. Network job skipped, GO expired; no HTTP/credits/PROMOTE.

## CASUALTY-WORKAG-ARTICLE-FIRST-OFFLINE-PASS-LIVE-BLOCKED-01 (2026-11-15)

- [PR #174](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/174) `4d20b5f0`, [CI #43706844061](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43706844061) 20/20 offline PASS, artifact #14159030801 (ZIP SHA in changelog); 4 synthetic HTML layouts, no saved full real HTML. Work X T03–T05 URL known, no article GET/credits; live GO unready.

## CASUALTY-WORKAF-FILTER-ALLOWLIST-GO-OFFLINE-PASS-LIVE-BLOCKED-01 (2026-11-15)

- [PR #173](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/173) `37cf0b19`, [CI #43702948168](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43702948168) 12/12 PASS, artifact #14157426485. Synthetic atomic GO tag PASS; old network jobs unguarded. Four article hosts staged; no media GET or credits.

## CASUALTY-WORKAE-DUAL-RSS-PILOTS-RECONCILED-BUDGET-EXCEEDED-2026-11-15-01 (2026-11-15)

- Owner six-GET GO was used twice: [A #43700780104](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43700780104) and [B #43700806130](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43700806130): **12 vs 6 approved**. Both 5/6 RSS200 and 115 direct publisher links, Espreso 403. A city-filter hit 1 vs B broad filter 6 (non-comparable). [PR #172](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/172) 30/115 hosts allowlisted. No article GET/credits; shared spent-GO required.

## CASUALTY-WORKAE-SIX-DIRECT-RSS-ONESHOT-5OF6-2026-11-15-01 (2026-11-15)

- [PR #171](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/171) `53c48f0b` offline 40/40 PASS, [Actions #43700806130](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43700806130) six GET, five RSS200/115 direct links, six broad keyword hits; artifact #14156048863 SHA in changelog. Also run A above; no article GET, credits or live shadow.

## CASUALTY-WORKAD-URL-WORKJ-FACTS-OFFLINE-PASS-SHADOW-PARTIAL-01 (2026-11-15)

- [PR #170](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/170) `a502616d`, [CI #43697942529](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43697942529) 34/34 PASS; artifact #14155356566 SHA in changelog, 4/4 inner PASS. Work J count/delta/scope synthetic PASS; opaque GN links unresolved, T03–T05 NEEDS_REVIEW; 0 live HTTP/credits.

## CASUALTY-WORKAC-BOUNDED-CAPTURE-OFFLINE-PASS-LIVE-BLOCKED-01 (archived evidence)

- [PR #169](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/169) `1cd3e85f`, [CI #43696226023](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43696226023) 17/17 offline, artifact #14154303167 SHA256 `c45ae98be3dd0ab4e5bd0ffc9b23d31777032d2bb9b39e150c635bbd531695d9`, 3/3 inner PASS. Network safeguards mocked; live URL/claims unproven, credits OFF.

## CASUALTY-WORKAB-SHADOW-OFFLINE-PASS-LIVE-BLOCKED-01 (archived evidence)

- [PR #163](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/163) `4604004b`, [CI #43646987342](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43646987342) 7/7 offline; artifact #14133897958 SHA256 `7e7e1474f1dfd6c40ae336fead3045fd818413b0eaff8109f11fa52a5349c818`. 23→22→23 mock cursor/replay, 0 real HTTP/credits.

## CASUALTY-WORKAA-CONTEXT-OFFLINE-PASS-EVIDENCE-PARTIAL-01 (2026-11-14)

- [PR #160](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/160) `38b444df`, [CI #43643850083](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43643850083) 183 PASS/1 SKIP, artifact #14132887476 (SHA in changelog). T03–T05 evidence partial/unlinked, 0 HTTP/credits; PROMOTE OFF.

## CASUALTY-WORKZ-HTTP200-EVIDENCE-PARTIAL-01 (2026-11-14)

- [PR #145](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/145), [run #43609731091](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43609731091): 3 GET/HTTP200, three unproven pairs, 0 credits. GET grant spent. Saved excerpts only; absent text cannot be recovered offline.

## CASUALTY-WORKW-INTEGRATION-OFFLINE-PASS-01 (2026-11-14)

- [PR #141](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/141) `4e083db7` / CI #43589692637 PASS. Protected write OFF; research only, zero production changes.

## CASUALTY-WORKX-INDEPENDENT-SCAN-EVIDENCE-OFFLINE-PASS-01 — offline PASS (2026-11-14)

- [PR #142](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/142) `b07a5957`, Actions #43589727392 169 PASS/1 SKIP, artifact #14111089895 (SHA in CHANGELOG). 23-city independent RSS plan and retained cards tested; 3/3 T03–T05 NEEDS_REVIEW. No live HTTP, credits, merge or deployment.

## CASUALTY-WORKV-REVIEWER-OPERATOR-OFFLINE-E2E-PASS-01 — physical offline chain PASS (2026-11-14)

- [PR #140](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/140) `663f3eeb`, [CI #43587369075](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43587369075) PASS, artifact #14110980955. Offline reviewer→generator 18→20→23 with no summed credit, T03–T05 NEEDS_REVIEW; 0 live HTTP/PROMOTE.

## CASUALTY-WORKTU-CONTRACT-AND-LIVE-JSON-GATES-01 — Work T code mismatch verified; Work U live parity unresolved (2026-11-14)

- Exact Git blobs: `main@413d34ac` reviewer `cf65d85c`, operator `740b985b`, workflow `3771a501`; `site-prod@2fa9044a` generator `f5840c20`. The reviewer does not emit generator's incident/proof fields; operator preview calculates a raw delta sum, not the cumulative effective credit. PR #105 [shadow Actions #43290975899](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43290975899) SUCCESS does not prove scheduled operation. No new code deployed.
- Work U: Zaporizhzhia Git JSON compared against PR #139, 316 deaths, September last validated month, October absent. Current Netlify deploy `6af76b2d` is READY/locked, but the actual served frontend/data fetch was not captured; `LIVE_PARITY=UNVERIFIED`. Live site may fetch GitHub Raw directly; do not equate locked deploy with frozen JSON. T03–T05 remains blocked, death credits 0.

## CASUALTY-WORKR-OWNER-ONE-SHOT-HTTP200-CONTEXT-CAPTURE-PASS-IDENTITY-REVIEW-01 (archived evidence)

- [PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137) / [CI #43574791160](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43574791160) three GET/HTTP200, ZIP #14105343291 SHA256 `8248b426baa23d822b0ba92332137ab59c63146b648b22271c41af7ff0a3177b`. T03–T05 age matches; attack identity unproven, zero credits; one-shot spent.

## CASUALTY-WORKR-IDENTITY-REVIEW-PREFLIGHT-SOURCE-REVIEW-REQUIRED-01 (2026-11-14)

- [PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137) `f2f3a922`, CI #43573408615 153 PASS/1 SKIP, ZIP #14104883690 SHA256 `6ab3d7ec12d6973f8ea3f63bc6fe572364dba0c48eb514ff39b7e3ecfba8d76b`, independent/11 inner PASS. T03–T05 ages overlap, attack identity INSUFFICIENT_EVIDENCE. 0 credits/GET.

## CASUALTY-WORKQ-REAL-EXCERPTS-AUXCI-OFFLINE-PARTIAL-01 (archived evidence)

- [PR #135](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/135) `858e255e`, [CI #43571952329](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43571952329) 145 PASS/1 SKIP, ZIP #14104761484 SHA256 `90ec4ef12c967facc743914316da41e99b6d9d0237350b16437cd820bad451d5` independent/10 inner PASS. T03 2, T04 +1 not total, T05 3 unbound; 0 credits, totals PARTIAL.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
