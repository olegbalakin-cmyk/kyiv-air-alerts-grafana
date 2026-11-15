# Project State — current coordination snapshot

**Date:** 2026-11-14. **Casualty scope: PROMOTE=OFF.** C6 current historical status follows newer accepted `main:C6-AUTO-GIT-RESTORED-2026-11-14-01` (`GLOBAL_CUTOVER=YES`, stabilization open); old C6 checkpoints here are historical.
Latest C6 state: governed by newer `main:PROJECT_STATE.md`, not this casualty coordination draft.
Latest casualty: **CASUALTY-WORKAC-BOUNDED-CAPTURE-OFFLINE-PASS-LIVE-BLOCKED-01**: PR #169 `1cd3e85f`, Actions #43696226023 17/17 offline PASS. Live shadow BLOCKED.

## Working instructions

1. Read both root documents first; newer accepted checkpoints govern old memory.
2. Verify exact commits, Actions and artifacts; research PASS does not imply production.
3. Separate production, WIP, history, backfill, casualty and Neon; no overwritten commits, force pushes or leaked credentials.
4. Keep live blockers/status/next tasks outside history markers; accepted checkpoints inside, newest first, full evidence in archives.
5. Aim for 5–8 KiB state and 5–10 changelog entries; ≤12,288 B PASS, ≤16,384 WARNING, above FAIL. Before oversize, use [maintenance CLI](docs/coordination-maintenance.md) dry-run then archive on a separate branch.
6. Search checkpoint IDs and read bounded lines; avoid bulk JSON/SQL, archives and full logs. Preserve reproducible work; recover interrupted commits first.

## Current tracks and open release gates

- **Other tracks:** production/C6, Neon, C3, API, DST and historical completeness follow newer accepted `main:PROJECT_STATE.md`; this casualty draft does not authorize changes to them.
- **Operational WIP / casualty:** Work Y merged to main (PROMOTE hard-OFF); Work AB/AC RSS→article→evidence PASS on mocked input. Direct Google News publisher links and counted claims unresolved; 0 credits. Active WIP workflow unchanged.

## Concrete next tasks

1. C6 production/stabilization/DST tasks: see newer `main:PROJECT_STATE.md` and PR #78; do not use old C6 tasks in this casualty draft.
2. Casualty H/I: PRs #114/#115 PASS offline, no release.
3. Casualty next: Work AD narrow source-URL resolution and Work J count/scope integration, plus exact-head offline E2E. Check current WIP HEAD before transfer. No live HTTP or WIP writes before owner GO; T03–T05 NEEDS_REVIEW.
4. Separately verify actual Netlify frontend asset and its GitHub Raw JSON fetch read-only; until then live casualty parity is UNVERIFIED.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-WORKAC-BOUNDED-CAPTURE-OFFLINE-PASS-LIVE-BLOCKED-01 (2026-11-15)

- [PR #169](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/169) `1cd3e85f72f8c80dadd2b53d2b9ce2bb0b0984cf`; [Actions #43696226023](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43696226023) SUCCESS 7 Work AB + 10 Work AC offline tests; proof #14154303167 (uploader ZIP digest in CHANGELOG), 3/3 inner SHA PASS. 23 RSS/10 publisher GET budgets, secure article capture and three mocked cycles PASS. 0 real HTTP, WIP writes or death credits. Opaque Google News URLs remain unresolved and `claim_deaths=null` without Work J counts. No active workflow changes, PROMOTE OFF; `READY_FOR_SHADOW_GO=BLOCKED`.

## CASUALTY-WORKAB-SHADOW-OFFLINE-PASS-LIVE-BLOCKED-01 — three-cycle scratch proof PASS; live GO blocked (2026-11-15)

- [PR #163](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/163) exact `4604004bd7399975c7b4d4cc87c0a43fcb4cd403`; [Actions #43646987342](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43646987342) SUCCESS 7/7 offline; artifact #14133897958 (ZIP digest in CHANGELOG). Three mocked four-hour scans 23/23→22/23→23/23, cursor recovery, 48h overlap, replay 0; scratch queue 1707→1708 synthetic, 3 saved T03–T05 cards NEEDS_REVIEW, 0 publisher GET or credits. No live page capture, network budgets not enforced; WIP/main/site-prod unchanged.

## CASUALTY-WORKAA-CONTEXT-OFFLINE-PASS-EVIDENCE-PARTIAL-01 (2026-11-14)

- [PR #160](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/160) `38b444dff0e9f1e363593aaa42dec4dc278743e0`, [Actions #43643850083](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43643850083) SUCCESS, proof #14132887476 (SHA in log). 183 executed/1 SKIP; Work Z-derived index 1,683→3, broken T04 flagged incomplete. All 3 incident pairs INSUFFICIENT_EVIDENCE, no HTTP or credits. PR #160 research-only, no merge. Work Y PR #147 already merged to main, PROMOTE hard-OFF.

## CASUALTY-WORKZ-HTTP200-EVIDENCE-PARTIAL-01 (2026-11-14)

- [PR #145](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/145), [run #43609731091](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43609731091): 3 GET/HTTP200, three unproven pairs, 0 credits. GET grant spent. Saved excerpts only; absent text cannot be recovered offline.

## CASUALTY-WORKW-INTEGRATION-OFFLINE-PASS-01 (2026-11-14)

- [PR #141](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/141) `4e083db7` / CI #43589692637 PASS. Protected write OFF; research only, zero production changes.

## CASUALTY-WORKX-INDEPENDENT-SCAN-EVIDENCE-OFFLINE-PASS-01 — offline PASS (2026-11-14)

- [PR #142](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/142) `b07a5957`, Actions #43589727392 169 PASS/1 SKIP, artifact #14111089895 (SHA in CHANGELOG). 23-city independent RSS plan and retained cards tested; 3/3 T03–T05 NEEDS_REVIEW. No live HTTP, credits, merge or deployment.

## CASUALTY-WORKV-REVIEWER-OPERATOR-OFFLINE-E2E-PASS-01 — physical offline chain PASS (2026-11-14)

- [PR #140](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/140) exact `663f3eeb`, [Actions #43587369075](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43587369075) SUCCESS; artifact #14110980955 (uploader SHA in CHANGELOG; independent ZIP hash pending). Scratch reviewer/operator→generator 18→20→23 = 23, replay +0, unknown proofs BLOCKED, Sumy +1/22 cities unchanged. T03–T05 NEEDS_REVIEW; 0 live HTTP, PROMOTE or publication.

## CASUALTY-WORKTU-CONTRACT-AND-LIVE-JSON-GATES-01 — Work T code mismatch verified; Work U live parity unresolved (2026-11-14)

- Exact Git blobs: `main@413d34ac` reviewer `cf65d85c`, operator `740b985b`, workflow `3771a501`; `site-prod@2fa9044a` generator `f5840c20`. The reviewer does not emit generator's incident/proof fields; operator preview calculates a raw delta sum, not the cumulative effective credit. PR #105 [shadow Actions #43290975899](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43290975899) SUCCESS does not prove scheduled operation. No new code deployed.
- Work U: Zaporizhzhia Git JSON compared against PR #139, 316 deaths, September last validated month, October absent. Current Netlify deploy `6af76b2d` is READY/locked, but the actual served frontend/data fetch was not captured; `LIVE_PARITY=UNVERIFIED`. Live site may fetch GitHub Raw directly; do not equate locked deploy with frozen JSON. T03–T05 remains blocked, death credits 0.

## CASUALTY-WORKR-OWNER-ONE-SHOT-HTTP200-CONTEXT-CAPTURE-PASS-IDENTITY-REVIEW-01 — one physical Work R source capture PASS, event identity reviewer-only (2026-11-14)

- Owner-authorized one-shot [PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137) launch `b9d8d6183f882fbe5108f0641f80b16e3821d4a4`, exact prelaunch `f2f3a922bfe193a66680d8bf64f29a80be17dc9a`, launch.json-only diff; [Actions #43574791160](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43574791160) first-attempt SUCCESS, owner/ancestry and 68 safety checks PASS, 3/3 T03/T04/T05 HTTP200, 3 GET, 0 redirects/retries. [Artifact #14105343291](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43574791160/artifacts/14105343291) ZIP SHA256 `8248b426baa23d822b0ba92332137ab59c63146b648b22271c41af7ff0a3177b` independently MATCH and 4/4 manifest hashes PASS, five JSON files only, full bodies absent. New bounded clues: T03 strike on Zaporizhzhia private house + local 2; T04 earlier 2 then count rose, later deceased aged 69; T05 evening missile near private sector and 3 dead aged 37/38/69. Supports same-incident 2→3 hypothesis but attack date/location identity NOT independently verified; article-wide T03/T04 totals NULL, T05 3 unbound. All NEEDS_REVIEW, 0 automatic links/credits, no PROMOTE/production publication. Authorization `CASUALTY-T03-T05-OWNER-20261114081321838-WORKR-ONCE` CONSUMED; next offline human review, no repeat GET.

## CASUALTY-WORKR-IDENTITY-REVIEW-PREFLIGHT-SOURCE-REVIEW-REQUIRED-01 — source identity research PASS offline, full event link pending (2026-11-14)

- [PR #137](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/137) `f2f3a922bfe193a66680d8bf64f29a80be17dc9a`, [CI #43573408615](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43573408615) exact SUCCESS 153 PASS/0 FAIL/1 SKIP, physical 18→20→23 PASS, 5 source-empty clusters BLOCKED. [Artifact #14104883690](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43573408615/artifacts/14104883690) independent ZIP SHA256 `6ab3d7ec12d6973f8ea3f63bc6fe572364dba0c48eb514ff39b7e3ecfba8d76b`, 11/11 manifest PASS. T03 couple 37/38; T04 additional deceased age 69; T05 police 37/38/69: corroborating ages, no independently verified shared attack date/place/object. All 3 pairs INSUFFICIENT_EVIDENCE, SOURCE_REVIEW_REQUIRED. Existing one-shot runner added bounded deidentified review clues (≤8 snippets/source, ≤170 chars/each; total ≤650 chars and 25% body). 0 GET, 0 credits/PROMOTE/deploy. Fresh owner grant required for future source verification; no launch.json or authorization ID.

## CASUALTY-WORKQ-REAL-EXCERPTS-AUXCI-OFFLINE-PARTIAL-01 — Work Q local parser + CI PASS; incident totals PARTIAL (2026-11-14)

- [Draft PR #135](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/135) exact `858e255ebea543383a9ca95d07847a40e22742e6`, [CI #43571952329](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43571952329): 145 PASS/0 FAIL/1 SKIP, 18→20→23 PASS, 5 source-empty clusters blocked. [Artifact #14104761484](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43571952329/artifacts/14104761484) ZIP SHA256 `90ec4ef12c967facc743914316da41e99b6d9d0237350b16437cd820bad451d5` independently MATCH; 10/10 manifest hashes PASS. T03 «двоє»→local 2; T04 additional death ≠ total, 69 age; T05 3 unbound; no automatic 2→3 or credits. Work O auxiliary CI launch.json-only push guard corrected offline, live guards unchanged; 0 source GET, no production/PROMOTE. Full-article T03/T04 totals UNKNOWN (**PARTIAL**).

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
