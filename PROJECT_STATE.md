# Project State — current coordination snapshot

**Date:** 2026-11-11. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-FROZEN-B2-OWNER-READONLY-AUTH-01** (one read-only proof approved, not run). First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON physical PASS still OPEN.** `GLOBAL_CUTOVER=NO`.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Production:** Git JSON updated and remote publication confirmed in C2 #43055353190 (`site-prod@cf960d7c`); frontend/source still Git, no Neon cutover. Netlify deployment not independently verified.
- **Neon reader / historical parity:** [Work B #74](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/74) verified 33,135 exact C2 episodes across 23/23 cities, plus 262 historical superseded rows retained in Neon. One-hop receipts 23/23; full origin and 22-city episode-level provenance still OPEN.
- **Live writer / provenance:** C2 #43055353190 `NEON_SUCCEEDED`, 33,135 episodes (69 inserted), 23/23 checkpoints match run/attempt/workflow SHA. Sevastopol checkpoint advanced; its historical alert `25006→25008` remains unresolved.
- **23-city generator / publication:** C2 artifact #13873291895 SHA `ebcf2b6a...04c1d` PASS; physical [#43098776474 attempt 2](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43098776474) failed closed at historical receipt replay (no JSON PASS). Research [PR #77](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/77) integrates exact C2-only canonical selection (#75) and active AIR endDate replay fix (#76). [Offline #43102701988](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43102701988) SUCCESS on immutable `93899d5b`; physical proof OPEN.
- **UkraineAlarm current API (research):** [run 41219158954](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41219158954): 9/21 mapped IDs direct AIR, 12 UNKNOWN. Active/negative/cache semantics OPEN.
- **DST / Kyiv:** 4-case offline fix `14e1b0b9` passed tests; rolling guard BLOCKED pending private raw baseline. DST OFF; Kyiv provenance OPEN.
- **Preview / C3:** frozen browser/CSV/rollback [proof 66f87241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/66f872413f67668c9bd23b94cff17520fea705f9) research-only; operational cutover and rollback gates OPEN.
- **Operational WIP / historical reference / backfill / casualty:** separate tracks; no change or promotion is established by these research or documentation checkpoints. Consult the relevant pinned evidence through the archive index before acting on a track.

## Concrete next tasks

1. **One owner-approved read-only proof** on PR #79 HEAD `beb2ad4d1f37e88b0084e49306281f8d2650d568`, C2 #43055353190. In Environment `c6-neon-shadow-readonly`, allow only branch `research-c6-frozen-b2-evidence-2026-11-11` and pin `C6_SHADOW_APPROVED_RESEARCH_SHA` to this SHA; owner to dispatch once. Not run; no DB writes, HTTP or cutover.
2. Prove 23-city six-file JSON, receipts and freshness in that run; origin-complete history/episode provenance and Sevastopol `25006→25008` remain separately unresolved. Do not infer Netlify deployed from Git.
3. DST raw baseline/rolling 4-case correction and C3 rollback acceptance remain separately gated. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-FROZEN-B2-OWNER-READONLY-AUTH-01 — one read-only run authorized (2026-11-12)

- Owner approved one physical nonpublishing Neon→JSON proof on PR #79 `beb2ad4d1f37e88b0084e49306281f8d2650d568`, bound to C2 #43055353190. Protected branch/SHA approval and owner dispatch pending. No physical PASS, Neon writes or cutover. `GLOBAL_CUTOVER=NO`.

## C6-FROZEN-B2-EVIDENCE-OFFLINE-01 — frozen B2 provenance isolated; exact-run offline PASS (2026-11-11)

- Physical read-only [#43104972888](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43104972888), artifact #13893437446: `FRESHNESS_READY_FOR_INTEGRATION` **23/23**, then `FROZEN_PHYSICAL_PARENT_COUNT_CHANGED` at generator; no 6 JSON files.
- Read-only Neon: 382/382 frozen Kyiv B2 parent UIDs present, 184 outdated live provenance parents plus 198 current C2 members. Research [PR #79](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/79) `beb2ad4d1f37e88b0084e49306281f8d2650d568` lets B2 inspect all 382 solely as view evidence while statistics use only exact C2 canonical episodes. [Offline #43105919875](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43105919875) SUCCESS. Protected physical rerun requires separate owner exact-SHA approval. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-INTEGRATED-READONLY-PROOF-OWNER-AUTH-01 — approval consumed by blocked physical run (2026-11-11)

- Owner-authorized research PR #77 `93899d5b` physical [#43104972888](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43104972888) reached Neon readback and verified 23/23 historic receipts/freshness, then failed closed at frozen B2 generation. No six-file proof, writes or deployment.

## C6-EXACT-READBACK-INTEGRATED-OFFLINE-01 — exact C2 canonical reader + replay offline PASS (2026-11-11)

- Work A protected read-only physical #43098776474 attempt 2 failed closed at receipt replay (artifact #13892361332), no six-file PASS. [Work B #74](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/74) 23/23 exact C2 corpus 33,135, 262 retained older versions; 23/23 one-hop receipts and 39/39 pages, not full historical origin.
- Work C exact-run membership [#43100877453](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43100877453) PASS; UA active endDate replay [#43102017533](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43102017533) PASS. Integrated [PR #77](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/77) `93899d5b` [offline #43102701988](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43102701988) SUCCESS. New SHA requires separate owner approval; C6 PARTIAL, `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-POSTMERGE-C2-EXPORT-23-01 — physical same-run export and checkpoints PASS (2026-11-11)

- [Actions #43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) scheduled C2 SUCCESS (16:08:40–16:36:22 UTC), after Work A `main@fe4ab1c1` and Work B `site-prod@6de49e3b`. `NEON_SUCCEEDED`: 33,135 canonical episodes (+69), 23-city QA, Git JSON publication `site-prod@cf960d7c` PASS.
- Actual C2 ZIP artifact [#13873291895](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190/artifacts/13873291895) uploaded (`c2-shadow-inputs-43055353190-1`, 3,669,061 bytes), export ZIP SHA-256 `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`, manifest SHA-256 `f64620936677b3a329a5e7823d3f4d52e4bc60c5b6a29bb8da6ff943adf3e433`. `CAPTURE_NAIVE_TIMESTAMP` absent; 23/23 persistent source checkpoints share GitHub run ID `43055353190`; Sevastopol now updated, historical `25006→25008` remains unresolved.
- **Proof boundary:** successful export/capture does not establish independent Neon readback/parity, source freshness all-city PASS in readback, Netlify deployment, approved DST/rollback or permission for global source switch. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-REPLAY-SEVASTOPOL-MERGED-01 — two scoped fixes staged in production branches (2026-11-11)

- Owner-approved [PR #61](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/61) squash-merged to `main@fe4ab1c14bffa03ff58f1f9debc3cc510f1099b0`, exact-head [Actions #42981135850](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42981135850) **16/16 offline PASS** (UkraineAlarm event timestamp replay only).
- Owner-approved [PR #62](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/62) squash-merged to `site-prod@6de49e3b0cf9692c7bb242672e92f062e516af20`, exact-head [Actions #42982010821](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42982010821) **8/8 offline PASS** (Sevastopol checkpoint eligibility only). No synthetic event closure, no cutover.
- First post-merge C2 and exact ZIP/SHA, source receipt continuity across all 23 cities, independent Neon readback and any Netlify deployment **not yet verified**. Prior source checkpoint 22/23; `25006` still unresolved. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## C6-THREE-RUN-EXPORT-01 — exact blockers after activated cycles (2026-11-11)

- [42902124611](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42902124611) and [42908463331](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42908463331) SUCCESS; [42970870607](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42970870607) data/Neon/23-city QA/Git PASS (`site-prod@390e7635`, 33,066 episodes), overall FAIL at artifact upload.
- All three bundle exports BLOCKED `CAPTURE_NAIVE_TIMESTAMP`, no ZIP/SHA; 22/23 checkpoints refreshed, Sevastopol stuck since bootstrap. Cutover NO.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
