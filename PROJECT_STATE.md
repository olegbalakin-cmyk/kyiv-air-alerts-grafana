# Project State — coordination snapshot

**Date:** 2026-11-12. **NO-GO; GLOBAL_CUTOVER=NO; C6/C3=PARTIAL.**
Latest accepted: **C3-FRONTEND-SITEPROD-PR100-OFFLINE-PASS-01** (PR #100 exact-site-prod frontend offline PASS; production NO-GO).

## Rules

Read this file and CHANGELOG first. Check immutable SHA/Actions/artifacts. Keep production, WIP, historical, backfill, casualties and Neon distinct. No force-push, secrets or inferred deployment from research. Keep current gates outside history; archive old checkpoint text. Maintain 5–10 CHANGELOG entries; size ≤12 KiB (≤16 KiB warning). Read bounded evidence.

## Current tracks and blockers

- **Production:** Git `site-prod@68629fda` includes separate casualty PR #91 code-only after C2 parser fix #93 (`6704c483`); no runtime JSON/frontend change from casualty merge. Netlify `6adb629bc3ebc570117d82e1` unchanged. Git JSON remains source.
- **C2:** latest #43172960738 33,210 episodes, 22/23 receipts; post-#93 scheduled 23/23 PENDING. Sevastopol open `25100`, old `25006→25008` unresolved.
- **Neon parity:** physical #43187464328 PASS, 6 JSON/18 SHA/23 historical receipts from C2 #43055353190. #74 exact 33,135, 262 old preserved. Current provenance OPEN.
- **Publication:** PR #94 gate [offline #43237670242](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43237670242) 17/17 PASS; `publication_allowed=false`. [Draft PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) exact-head [offline #43254618233](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43254618233) 14/14 PASS: default-OFF generator→six-JSON detached local Git candidate, NO PUSH. Live same-run activation & publication authority OPEN.
- **C3/frontend:** Draft PR #100 (base `site-prod@68629fda`) exact-head #43260329916 offline PASS: 184/184, CSV 23/23, Git fallback 23/23; Git remains production source. **C3/rollback:** #92 immutable Netlify HTTP/SHA PASS; research PR #101 may add offline tests but operational non-current republish and two-plane rollback remain BLOCKED. Netlify preview `6af5aecd8901ea2a40de09ad` remains isolated.
- **Current API/Kyiv/DST:** 9/21 mapped AIR, 12 UNKNOWN. Kyiv provenance OPEN. DST four-case offline PASS but raw rolling gate OPEN; DST OFF.
- **Other tracks:** WIP, backfill, history, casualties remain separate.

## Concrete next tasks

1. Check next regular C2 23/23 and Sevastopol checkpoint, preserve open anomalies.
2. Review PR #95 default-OFF implementation against post-PR93 natural C2 exact run/attempt and frozen physical proof; do not activate preparation/publishing or manually dispatch C2.
3. Keep PR #100 frontend fix staged until separate release decision. Independently prove Netlify/static KPI and moving Git JSON rollback baseline, verify non-current deploy re-publish authority and handle newer C2/casualty/aux; request separately approved publication authority. No cutover. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
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
