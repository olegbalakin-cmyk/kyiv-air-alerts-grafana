# Project State — coordination snapshot

**Date:** 2026-11-12. **NO-GO; GLOBAL_CUTOVER=NO; C6/C3=PARTIAL.**
Latest accepted: **C6-POSTPR93-REGULAR-C2-CONTINUITY-23-01** (first post-PR93 C2 23/23 same-run source checkpoints; no cutover).

## Rules

Read this file and CHANGELOG first. Check immutable SHA/Actions/artifacts. Keep production, WIP, historical, backfill, casualties and Neon distinct. No force-push, secrets or inferred deployment from research. Keep current gates outside history; archive old checkpoint text. Maintain 5–10 CHANGELOG entries; size ≤12 KiB (≤16 KiB warning). Read bounded evidence.

## Current tracks and blockers

- **Production:** C2 published verified Git JSON to `site-prod@d0a7d22d` (after PR #93 Sevastopol and PR #91 casualty). Netlify `6adb629bc3ebc570117d82e1` unchanged; Git remains source.
- **C2:** post-#93 scheduled #43262387718 SUCCESS, 33,267 episodes (+57/0 updated), **23/23 source checkpoints** incl. Sevastopol; ZIP/manifest SHA and artifact #13967335571. Independent new-run Neon→JSON readback OPEN. Sevastopol open `25100`, historical `25006→25008` unresolved.
- **Neon parity:** physical #43187464328 PASS, 6 JSON/18 SHA/23 historical receipts from C2 #43055353190. #74 exact 33,135, 262 old preserved. Current provenance OPEN.
- **Publication:** PR #94 gate [offline #43237670242](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43237670242) 17/17 PASS; `publication_allowed=false`. [Draft PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) exact-head [offline #43254618233](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43254618233) 14/14 PASS: default-OFF generator→six-JSON detached local Git candidate, NO PUSH. Live same-run activation & publication authority OPEN.
- **C3/frontend:** Draft PR #100 HEAD `b04e23a7`, exact-head #43278423559 offline PASS: static KPI generation guard, 184/184, CSV 23, Git rollback preview 23; base `68629fda` predates new C2 data; Git remains production source. **C3/rollback:** PR #101 exact-head #43260803310 6/6 offline PASS found unsafe stale Netlify static KPI fallback without dashboard generation match (Oct 23 vs Nov 12); operational rollback BLOCKED. #92 immutable Netlify HTTP/SHA PASS. Netlify preview `6af5aecd8901ea2a40de09ad` remains isolated.
- **Current API/Kyiv/DST:** 9/21 mapped AIR, 12 UNKNOWN. Kyiv provenance OPEN. DST four-case offline PASS but raw rolling gate OPEN; DST OFF.
- **Other tracks:** WIP, backfill, history, casualties remain separate.

## Concrete next tasks

1. Reuse post-PR93 C2 #43262387718 exact ZIP/receipts for **independent read-only same-run Neon→six-JSON** proof, plus source freshness checks; no manual C2/writer or production publication.
2. Keep PR #95 prepare job default OFF; verify exact current C2 integration and publication gate separately. No source switch without owner release permission.
3. PR #100 static KPI guard offline PASS but not merged; before any approved merge, preserve new `site-prod@d0a7d22d` C2 data. Pin compatible Git-only Netlify/static + moving Git runtime baseline and prove operational restore/auto-publish sequencing. Rollback BLOCKED. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-POSTPR93-REGULAR-C2-CONTINUITY-23-01 — first post-PR93 regular C2 23/23 source checkpoints PASS (2026-11-12)

- [Scheduled C2 #43262387718](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43262387718) SUCCESS, attempt 1, 16:46–17:15 UTC; code `main@375e6935`, input `site-prod@68629fda`, Git publish `site-prod@d0a7d22de2828c93236562cccc9d2e68c6a66e3d`. Direct persisted `c2_history_capture_checkpoints.json` has **23/23**, including Sevastopol, with identical run/attempt/input/workflow and per-city source SHA-256. Canonical Neon `NEON_SUCCEEDED`: 33,267 episodes, 57 inserted, zero updated; Git 23-city QA and publication PASS. Exact C2 bundle ZIP **SHA-256 `927343c620c1d55438823ad9203a16e986f540a816b35790d496200fe861944f`**, manifest **`5c3e2326eeb98ae6e90234183764525483e64fbc6a203b20dda8deb685d9b501`**; [artifact #13967335571](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43262387718/artifacts/13967335571), GitHub artifact-container digest `9f4168c12795977505f5a6cbbf836c1bb7c9a632286bb62de19d532612e2841e`.
- **Boundary:** source checkpoint 22/23 blocker CLEARED; independent live same-run Neon→six-JSON readback/current publication permission still OPEN. Sevastopol historical `25006→25008` and open `25100` are not presumed resolved; DST OFF; Netlify production unchanged. `GLOBAL_CUTOVER=NO`.

## C3-STATIC-KPI-GENERATION-GUARD-OFFLINE-01 — same-generation static KPI fallback offline PASS (2026-11-12)

- [Draft PR #100](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/100) updated to HEAD `b04e23a739973f67a94b7e3af3be323c88643641`; exact-head [Actions #43278423559](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43278423559) SUCCESS, [artifact #13971078119](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43278423559/artifacts/13971078119), GitHub SHA-256 `294d0820b493850dcdd49f3501263987a9277be1524dcf43abab0b12ef390181`. Exact `app.js` diff adds static fallback timestamp non-empty/parseable/exact-generation guard, preserves embedded Git index and pinned Neon preview rules. Offline 184/184 charts, CSV 23/23, Git rollback preview 23/23, negative stale/missing timestamp tests PASS. **`STATIC_KPI_FALLBACK_FIX_READY` is research/offline only**, no merge; PR remains based on pre-C2 `site-prod@68629fda` and must preserve newer C2 data when staged for merge. Operational two-plane rollback BLOCKED. No deploy/cutover.

## C3-STATIC-KPI-FALLBACK-GENERATION-RISK-01 — old static KPI fallback unsafe, rollback remains BLOCKED (2026-11-12)

- [Draft PR #101](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/101) exact HEAD `76d474fb72acdbab19752c0d9f1bcb686a89bcec`; [Actions #43260803310](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43260803310) SUCCESS 6/6 offline recovery-policy scenarios; artifact **#13963023002**, GitHub ZIP digest `298d43510bff61ae746e99c6cd9de76c1c663594ca9ecb1178d801b8967efb2c` (metadata). Existing static Netlify KPI generated 2026-10-23 differs from Git dashboard generated 2026-11-12. Direct read of `site-prod@68629fda:pages-preview/app.js` confirms embedded index enforces generation parity but static fallback does not; PR #100's minimal Neon predicate still has this fallback. Negative proof: `STALE_STATIC_INDEX_FALLBACK=ACCEPTED_UNSAFE_BY_OLD_APP`. 184/184 historical preview QA reused, not new operational rollback.
- **Decision:** accept reproducible vulnerability finding, **not** operational restore readiness. Keep current Git-only production behavior. Narrow next task: add static fallback generation-equality guard in current C3 frontend with a negative test and existing offline QA (no rewrite); prepare a **fresh compatible Git-only static+runtime JSON rollback baseline** at future cutover time instead of depending on October deploy. Preserve newer C2/casualty/aux and verify deploy/revert path plus auto-publish sequencing before GO. PR #101 remains Draft, no merge/deploy. `COMPATIBLE_ROLLBACK_READY=BLOCKED; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C3-FRONTEND-SITEPROD-PR100-OFFLINE-PASS-01 — current site-prod frontend fix compatible, offline PASS (2026-11-12)

- [Draft PR #100](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/100), base `site-prod@68629fdae5534ec3a136e666bcb7d5c84dcd05aa` (after #93 Sevastopol and #91 casualty), exact HEAD `88ace2016768771b0b250bff1e08f4088761c86d`. [Actions #43260329916](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43260329916) SUCCESS exact-head, artifact **#13964062068**, GitHub ZIP digest `b83595de5ecb665765c10d73de10c4f4520065a9997fa922e1002175a55e079e` (metadata digest, not separately re-hashed). Exactly four C3-only paths; minimal `pages-preview/app.js` predicate reused from PR #90; protected production/C2/casualty/aux paths unchanged.
- Offline immutable input SHA 18/18 PASS; Neon isolated historical preview 23 cities x 8 modes = **184/184**, CSV **23/23**, Git preview rollback **23/23**, 0 JS/HTTP>=400/external-request errors. Production `RAW_DATA_BASE` still Git `site-prod`; Neon KPI requires exact preview scope, schema, 23-city verification, pinned branch and dashboard generation. **`FRONTEND_COMPATIBILITY_READY` applies to code/offline preview only**; PR #100 remains Draft, no merge/deploy. C2 post-#93 23/23, production publication authority and two-plane rollback remain BLOCKED/PENDING. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-NEON-GIT-DEFAULT-OFF-INTEGRATION-PREPARED-01 — six-JSON local Git candidate PASS; production OFF (2026-11-12)

- [Draft PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) exact HEAD `c66cf00884e28b0d04d6eccd3bc5875a45c2e2b5`; [offline Actions #43254618233](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43254618233) SUCCESS **14/14**, artifact **#13961690528**. Replayed frozen physical #43187464328/C2 #43055353190; pinned PR #93 Sevastopol parser blob; six files SHA-checked and assembled as one isolated detached Git commit with **no remote/push**. Candidate = five `kyiv-air-alerts-grafana/data/` JSON plus root `historical-daily-kpi.json`; Kyiv intervals, casualty metadata and auxiliary bytes preserved.
- Default-OFF `c6-neon-six-json-prepare` waits for C2 success and requires exact run/attempt, read-only Neon proof, same-run receipts and freshness gate; `contents:read`. **Proof limit:** offline frozen-fixture staging ONLY, not a current live C2 23/23 readback, two-plane Netlify/Git activation or rollback. PR #94 still `publication_allowed=false`; production frontend PR #90, approved release authority, post-#93 C2 and rollback OPEN. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-NEON-PUBLICATION-GATE-OFFLINE-01 — staged read-only publication gate PASS (2026-11-12)

- [Draft PR #94](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/94) HEAD `e61a43f104a92d564105a853a3cdabf3c08a93b6`; [Actions #43237670242](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43237670242) SUCCESS 17/17 using physical #43187464328. Checks six JSON/18 SHA, 23 receipts, history freshness, KPI index and auxiliaries; rejects stale/incomplete/forged permissions. Explicit NO-PUBLISH: `publication_allowed=false`; no Git/Netlify writes. Live C2 23/23 and generator→Git integration pending. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
