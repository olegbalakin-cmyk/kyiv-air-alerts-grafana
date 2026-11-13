# Project State — current coordination snapshot

**Date:** 2026-11-12. **Release decision: NO-GO. GLOBAL_CUTOVER=NO; C6=PARTIAL; C3=PARTIAL.**
Latest accepted: **C6-POSTMERGE-C2-EXPORT-23-01**. First post-merge regular C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) SUCCESS: `NEON_SUCCEEDED` 33,135 episodes, QA 23/23, Git JSON published `site-prod@cf960d7c`; real C2 ZIP `ebcf2b6a...04c1d` and 23/23 source checkpoints at this run. **Independent same-run Neon→JSON readback not yet performed.** `GLOBAL_CUTOVER=NO`.
Latest casualty: **CASUALTY-INTEGRATED-E2E-SHADOW-WORKF-01** + **CASUALTY-CONTROLLED-CAPTURE-PREFLIGHT-OFFLINE-01**. [F #112](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/112) joined saved-source C+D+E PASS: +23/replay 0, 11+42 tests; current frontend QA OPEN. [G #111](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/111) 10-URL preflight PASS, **HTTP NOT_AUTHORIZED**; same-host redirect-path guard OPEN. Oct Zaporizhzhia **≥23 INCOMPLETE**, publication OFF.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Production:** Git JSON updated and remote publication confirmed in C2 #43055353190 (`site-prod@cf960d7c`); frontend/source still Git, no Neon cutover. Netlify deployment not independently verified.
- **Neon reader / historical parity:** frozen 23-city [proof 741f277f](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/741f277f73d1dde1325069d25fa00b44a42d6f03), 0 unexplained diffs; no current full continuity PASS.
- **Live writer / provenance:** C2 #43055353190 `NEON_SUCCEEDED`, 33,135 episodes (69 inserted), 23/23 checkpoints match run/attempt/workflow SHA. Sevastopol checkpoint advanced; its historical alert `25006→25008` remains unresolved.
- **23-city generator / publication:** first real post-merge same-run export PASS (`C2 ZIP SHA-256=ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`, artifact `13873291895`, manifest SHA `f6462093...3e433`); no `CAPTURE_NAIVE_TIMESTAMP`. Independent Neon→JSON readback still OPEN.
- **UkraineAlarm current API (research):** [run 41219158954](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41219158954): 9/21 mapped IDs direct AIR, 12 UNKNOWN. Active/negative/cache semantics OPEN.
- **DST / Kyiv:** 4-case offline fix `14e1b0b9` passed tests; rolling guard BLOCKED pending private raw baseline. DST OFF; Kyiv provenance OPEN.
- **Preview / C3:** frozen browser/CSV/rollback [proof 66f87241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/66f872413f67668c9bd23b94cff17520fea705f9) research-only; operational cutover and rollback gates OPEN.
- **Operational WIP / historical reference / backfill:** separate. **Casualty:** WIP discovery and site-prod dedup operate; research #108/109/110 isolated PASS, #112 joined saved-source PASS, #111 capture preflight PASS (OFF). Automatic evidence capture/publication not activated.

## Concrete next tasks

1. From immutable C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190) and ZIP/SHA, run an **independent, read-only exact-run Neon→JSON proof** for all 23 cities, with same-run corpus and provenance. Requires separate owner approval for PR #48/exact head; no source HTTP/writer/cutover.
2. Verify 23/23 full historical capture receipts and freshness in the independent proof. Keep `25006` unresolved. Compare live output and rollback gate; do not infer Netlify deployed merely from Git publication.
3. DST raw baseline/rolling 4-case correction and C3 rollback acceptance remain separately gated. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
4. Casualty: check PR #112 with current site-prod frontend in isolated browser, not just frozen one; no merge or live writes.
5. Before HTTP pilot: exact-path redirect guard + offline regression, then separate owner approval for ten URL, max 20 requests/≤24h; Sep credit reconciliation still BLOCKED. Default OFF.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-INTEGRATED-E2E-SHADOW-WORKF-01 — joined historical-source shadow PASS (2026-11-13)

- [PR #112](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/112) `2274276`, [CI #43387209190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43387209190) SUCCESS; E/A → scratch REVIEW/PROMOTE → generator +23/replay 0 → chart `≥23 INCOMPLETE`. Work C 11/11, D 42/42; Sumy +1 preserved. Proof ZIP #14018663260 SHA256 MATCH. Current frontend not browser-tested; no publication.

## CASUALTY-CONTROLLED-CAPTURE-PREFLIGHT-OFFLINE-01 — controlled capture preflight PASS, HTTP OFF (2026-11-13)

- [PR #111](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/111) `630c996`, [CI #43387015696](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43387015696) 12/12 PASS. Ten exact URLs/seven hosts/max 20 requests proposed; 0 HTTP, consent absent. Proof ZIP #14019520132 SHA256 MATCH. Same-host redirect path still unguarded: must fix before pilot.

## CASUALTY-EVIDENCE-INGESTION-WORKE-01 — archived-source ingestion PASS, autonomous capture OFF (2026-11-13)

- [Draft PR #110](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/110) exact `6b44b976`, [Actions #43320351570](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43320351570) SUCCESS 10/10, [artifact #13990550763](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43320351570/artifacts/13990550763) ZIP SHA256 `5d313e372e53f4afd9c2d9f412e0b30c9b9f41880fae94e6f404fd4a1126b7e5` independently verified. Frozen 1682 candidates: 3 saved-source texts, 2 parsed reports, 1 +23 shadow AUTO_READY; five PR102 clusters missing texts blocked. `CONTROLLED_CAPTURE` default-OFF, 0 new publisher HTTP, no scheduled hook, merge or publication. Work C/D isolated PASS; joined E2E and authorized controlled live-capture proof remain OPEN.

## CASUALTY-GENERATOR-DISPLAY-WORKD-01 — real generator to qualified chart PASS, isolated (2026-11-12)

- [PR #109](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/109) exact `62aef364`, [Actions #43308531075](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43308531075) SUCCESS, 42/42 browser PASS. Actual source-backed Work A generator +23 to Oct `INCOMPLETE/≥23` chart, CSV, PNG and embed; other 22 casualty cities, 23 alert cities unchanged, rollback PASS. [Artifact #13985535590](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43308531075/artifacts/13985535590) ZIP SHA256 independently verified `86dff044fbe148fa4fe1d05eb24c3540f07e29d50a8d16f581527a59d2e7ca5a`. **Research only; no main/site-prod adoption or publication.** Work E and joined E2E pending.

## CASUALTY-REVIEWER-DEDUP-CONTRACT-WORKC-01 — 11/11 protected reviewer contract PASS, isolated (2026-11-12)

- [PR #108](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/108) `fb3dcb7a`: genuine Work A source-backed +23 through patched REVIEW → protected PROMOTE → scratch CSV → unchanged pinned site-prod generator, 0 duplicate replay; Sumy +1 and all five provenance fields preserved. [Actions #43305347207](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43305347207) SUCCESS, 11/11; [artifact #13982783250](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43305347207/artifacts/13982783250) SHA256 `27e0f18fe97d0c150a6d9753784c53f483219ab85e2f1c59dc3cf3237c8c54e4` independently rehashed. **No site-prod adoption/production writes.** PR #106 UI and source blocks remain; publication NO.

## CASUALTY-INDEPENDENT-E2E-PARTIAL-01 — independent evidence and two integration FAILs (2026-11-12)

- [PR #105](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/105) head `6a0100b0`, [CI #43290975899](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43290975899) PASS; one source-backed +23 Zaporizhzhia shadow, 0 replay, 1681 unverified candidates. Independent [PR #106](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/106) head `5441bdaf`, [CI #43295488092](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43295488092) SUCCESS, [artifact #13979427285](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43295488092/artifacts/13979427285) ZIP SHA256 `15e160bee3bdafad80aef1dc5299296deec1d7ff53fc034433f1388279b45aab` independently verified. Verdict **PARTIAL**: old reviewer drops 5 proof fields; real generator does not emit PR99 lower-bound status; 4 other confirmed selected attacks not advanced due to missing original text/September credit. No live changes; **SHADOW_E2E_PASS=NO, PUBLICATION=NO**.

## CASUALTY-MAIN-ADOPTION-READY-01 — live site-prod dedup; dormant main parity ready (2026-11-12)

- `main:update-netlify-site.yml` cron `15 */4 * * *` checks out `site-prod`, runs `update_casualties.py`; [#43262387718](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43262387718) SUCCESS including casualty step. Supersedes prior claim of dormant site-prod dedup. `main:update.yml` job is manual-only. [PR #98](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/98) exact `39c395cf`, four scoped paths, [CI #43259380544](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43259380544) 37/37 + 25/25 PASS, [artifact #13963896363](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43259380544/artifacts/13963896363) ZIP SHA256 `5f12c4ef784ba2f3226eed5c4b58df1161bd2ef31a7d7dd90aac3a85ed654bff` independently verified. Optional main-only merge awaits separate owner approval. No casualty publication.

## CASUALTY-DEDUP-CODE-SITEPROD-MERGED-01 — owner-approved code merge only (2026-11-12)

- [Clean PR #91](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/91) squash-merged to `site-prod@68629fdae5534ec3a136e666bcb7d5c84dcd05aa`, parent `6704c48306289bbc40b6e12da4fc8cac163ec428` retained for rollback. Compared parent→merge: **exactly five approved paths**, and all five blobs equal proven PR head `50446b24`. Earlier strict [CI #43204809570](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43204809570) **25/25 PASS**. `revisions.csv` and `dashboard_data.json` blobs unchanged; site-prod Netlify path filters not hit, no deployment. **`main` still runs old script**, so live scheduled casualty update has NOT adopted fix. Work B remains blocked on 11 original article bodies; October `COVERAGE_INCOMPLETE`; data publication NO-GO.

## CASUALTY-DEDUP-CLEAN-SITEPROD-25-01 — correct-base code readiness, no publication (2026-11-12)

- [Draft PR #91](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/91) exact head `50446b24d33e0fdb4af0414b224c4aab6bbf5598`, base/merge-base `site-prod@fc7261660bdee75ee59296ee94cc1189be6b1a22`, **5 intended files, +637/−3, zero others**. [Actions #43204809570](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43204809570) exact-head STRICT **25/25 PASS**, 0 FAIL, offline; [artifact #13936737623](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43204809570/artifacts/13936737623) ZIP SHA256 `35da0f733505c4ae3227051e3c2a52ac100220fb5aad913f4d813cf46354a210` independently checked; inner checksums 5/5 and 14 input SHA entries. Duplicates/ambiguous corrections fail closed; frozen Sumy +1 and rollback PASS. **CLEAN_PR_READY** is code review readiness only, **no merge/production change**; Work B source completeness separately blocked.

## CASUALTY-SAME-INCIDENT-DEDUP-25-01 — read-only exact-head research PASS (2026-11-12)

- [Draft PR #89](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/89) exact `d406875cd5ccbd382fc736fcbb9a3cdc3a448289`, [Actions #43201016241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43201016241) SUCCESS **25 domain PASS, 0 FAIL**, independently downloaded artifact `13936055275` SHA256 `4a7aefc61f4d47683b72d0b33ec81deb57104eff6933873a2b2923d2ada4179f`. Frozen `site-prod@fc726166`; explicit incident identity, cumulative/delta classification and evidence-backed prior credit fix 18→23 to +5, 23→23 +0, 18→20→23 total 23. Reject ambiguous records; preserve pinned Sumy+1, other cities, October row and rollback. Proof handles require human review. **Research PASS only**: PR's `main` comparison contains 166 changed files (vs five actual research files from frozen production); do not merge. Work B source evidence and October completeness still NO-GO.

## CASUALTY-ZAPORIZHZHIA-ADDITIONAL-EVENTS-WORKB-01 — source evidence unavailable (2026-11-12)

- [PR #88](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/88) final `34bc539d`: 11 WIP candidates / 5 priority Sep–Oct Zaporizhzhia groups, all `BLOCKED_MISSING_SOURCE` (no original publisher body). Retained earlier captures do not match target IDs. **0 additional deaths established by this review** is NOT a finding of zero actual deaths. October remains **≥23 minimum / COVERAGE_INCOMPLETE**. No new HTTP, CI or source ZIP verification claimed; production and WIP unchanged.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
