# CASUALTY Release 1 — read-only owner-GO readiness, 23 Nov 2026

**READY_FOR_OWNER_GO=NO** · **PROMOTE=OFF** · **NO PRODUCTION PUBLICATION**

Coordination root at review: `main@b35ca5c8d189a011c1b7158275f189a195192890`. This is a **draft-only documentation checkpoint** and never implies accepted production deployment. Actual release must refresh this record against new `main` and `site-prod`.

## Scope and fact baseline

- Implementation: [Draft PR #253](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/253), immutable candidate `e5428063f37962cd95f8bdeb78ea4b09b8a8b7d9`, from `site-prod@f7e0681ca6aa98405638dae7a63c884f4ed55d20`.
- Previous integrated frozen UI: Draft #250, HEAD `71be304ec3fac649de0ee5c81b496f6259b48359`, Actions #45158190608, artifact #14809337693.
- September: 56 **already credited** historical partial baseline, including the existing Sumy +1. Exactly four independently supported city cutoff dates; 19 are unknown. No new September casualty credit.
- October: four reviewed incident minima = **11** (Lutsk 6, Poltava 1, Ivano-Frankivsk 1, Khmelnytskyi 3). All other 19 city-months unknown, not zero. No exact October aggregate. Do not integrate additional Kyiv +15/+11 from research PRs #249/#248 pending separate #252 signoff.
- Preserve already published monthly historical totals; both partial months excluded from reconstructed exact 2026 yearly totals. No new casualty revision.

## Immutable physical QA

[Actions #45190794160](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45190794160) **SUCCESS at exact candidate HEAD**, [proof artifact #14825787011](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45190794160/artifacts/14825787011): 27-file SHA-256 bundle manifest, 121 browser assertions `errors=[]`, 4 UA/EN desktop/mobile screenshots, real casualty CSV checks including known minimum and unknown blank field, 23-city selection and comparisons, Python sidecar tests, immutable real Git candidate transport with simulated canonical branch alias/HEAD, and fail-closed 404/tamper/changed-ref cases.

- Immutable dashboard SHA-256: `ce4e14e85054593c43854fabe014a678da0880eaeb12f9c4b17ee572c1e34007`.
- Immutable casualty sidecar SHA-256: `0cba878c49562742d8b0eda93372338bdc89cae71b64ecbde4bbc162ed378e13`.
- Original C6 release-manifest SHA-256: `ea335a2c2cd599ef19f9e56b16b7dbd90818299af3e8bdf1c08b18372675cad4`. Candidate's six original C6 Git files remain unchanged; dashboard + derived + active23 are release-bound; 23 cities.
- Repaired prior obsolete asset version contract without weakening checks. Read-only UI Actions #45190458814 SUCCESS. Read-only active23 one-shot preflight Actions #45190459139 SUCCESS; production release SKIPPED. Both on preceding HEAD; full candidate evidence on #45190794160.
- Isolated Netlify draft only; **live canonical Git sidecar absent (HTTP 404)**. Replayed canonical reader with real immutable Git bytes is *not* live canonical production proof.

## Exact blocker / next action

A scheduled C6 Git-only publication advanced `site-prod` by one commit after the candidate's base was frozen: `f7e0681ca6aa98405638dae7a63c884f4ed55d20` → `58634812155ddc6b4324c26d694cf3de6cfb9bbe`, changing 11 regular data/Grafana files. **Do not merge Draft #253 or move production backward.**

Before requesting owner GO, a release preparer must:
1. Re-pin **latest** main/site-prod HEAD, current C6 generation and **six JSON** Git blob hashes, release manifest, independent 23-city release/readback proof, and currently published locked Netlify deploy.
2. Re-scope a fresh candidate from latest site-prod containing only the sidecar and UI/code required for partial-month display, with corresponding Netlify build assets; no C6 workflows, data modifications, raw casualty revisions or unreviewed sources. Confirm regression and bilingual/browser CSV proof on the **new exact candidate**.
3. Verify canonical live-source contract using an owner-approved controlled staging read when possible, while explicitly marking `canonical_live_verified=false` until the production sidecar exists. Reject missing, corrupt, mismatched, changing Git HEAD, or stale September baselines.
4. Prepare **one exact separate owner-GO request**, spelling out newest base SHA, candidate code/data Git blob + SHA-256 hashes, successful Actions run IDs/artifact IDs, one safe Git-only sidecar commit, one controlled UI Netlify deploy and immediate lock reactivation, expected browser/CSV readback for 23 cities and UA/EN × mobile/desktop, historical parity and year cutoffs.
5. Roll back by **reverting only scoped casualty sidecar commit on top of newer C6 commits** plus restoring prior locked Netlify deploy. Never force-reset site-prod or undo legitimate C6 updates.

At this checkpoint, Netlify production deploy `6b02d5edba0ff97b80b83052` was observed READY, published and locked; **no Netlify prod deployment was performed**. No Neon, C6 writer, collector HTTP, revision, main/site-prod change or casualty promotion was authorized or executed by Issue #251.

### Track separation

- **Casualty Release 1:** validated isolated candidate, not publication-ready.
- **C6/Neon:** maintain regular four-hour Git-only six-JSON publisher independently. C6 schedule stabilization remains OPEN in main coordination.
- **UI/Netlify production:** existing published locked version unchanged; owner-controlled one-shot release still needs separate approval.
- **Historical/DST:** excluded from this candidate.
- **Development/WIP casualty monitoring:** remains `PROMOTE=OFF`; no activation of automatic credited totals.

This report is a **read-only release readiness assessment**, not a deployment instruction or authorizing GO.
