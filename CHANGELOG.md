# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
### C6-C3-WORKN-PUBLISHER-ROLLBACK-OFFLINE-PASS-01 — code and Git-only recovery offline PASS (2026-11-13; accepted)

- [Draft PR #119](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/119) exact `bd2c7ec8`, [Actions #43407396191](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43407396191) SUCCESS: 20 publisher tests, physical C2/Work L/Work M source/final ZIP SHA PASS; original missing C2 prep not substituted, separate owner publication receipt still required. Fresh 23-city `site-prod@f0cfcbc8` Git-only rollback 18-file package and 8 no-loss cases PASS; artifact #14027727854 SHA `3817cb462904a37237cd6c48970bad576648c6c273093febe33b7ddfc55e4c43`. Physical Netlify production restoration authority unproven. `PUBLISHER_CODE_READY=YES; ROLLBACK_OFFLINE_READY=YES; ROLLBACK_OPERATIONAL_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.


### C6-WORKM-FINALZIP-INDEPENDENT-PASS-01 — physical prepare-only and independent eight-file ZIP PASS (2026-11-13; accepted)

- [Actions #43403595621](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43403595621) SUCCESS attempt 1 on PR #116 exact `9d846279`; only prepare job ran. [FINAL artifact #14025629654](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43403595621/artifacts/14025629654) independently SHA-256 `f2252da0014ce4ed28d5d52a7164e077b8fcd8c99380dd752ee0650412b051ed`; report #14025729121 SHA `f4f786b168d28f37bdf6a333d4e514b503e402e4fda25553d99ffa0a8d6a8648`; 8/8 final members, 6/6 JSON/sha, Work L 6/6 source sha, release binding/report PASS. No publication. Publisher original C2 prep contract and fresh rollback remain blocked: `FINAL_ZIP=PASS; ROLLBACK_READY=NO; CUTOVER_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-WORKM-OWNER-GRANT-NODISPATCH-01 — one prepare-only owner grant, not dispatched (2026-11-13; accepted)

- Owner approved **one** prepare-only on exact PR [#116](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/116) SHA `9d846279b91b44b324a722ca00276a99956b4fca`. GitHub connector cannot enable workflow, configure repo variables/secret/environment or dispatch; one-shot permission **unconsumed**. Require `C6_GIT_ONLY_PUBLISHER_PAUSED=true` before any shared-workflow enable. Work M-specific CI, owner receipt, final ZIP and fresh rollback remain OPEN; no C2/writer/Git publish/Netlify/merge/cutover. `GLOBAL_CUTOVER=NO`.

### C6-WORKL-PHYSICAL-SIXJSON-PASS-01 — six JSON physically proven (2026-11-13; accepted)

- [#43390770985](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43390770985) SUCCESS at PR #113 `325669a4`; [artifact #14020616892](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43390770985/artifacts/14020616892) independently checked SHA `79acb3017dccefdf19def7fe15bdaf2033b27d8c8a6d41f146d7b0e903bd3954`, 18/18, 6/6 JSON, historical 23/23. Same original C2 attempt 1; zero writer, source HTTP or publication. Final ZIP original C2 prep missing; rollback/current alert/DST open. GLOBAL_CUTOVER=NO.

### C6-WORKL-RECOVERY-OFFLINE-PASS-01 — immutable C2 reusable (2026-11-13; accepted)

- [Draft PR #113](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/113) `325669a4`, [CI #43389706624](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43389706624) SUCCESS: 20/20 tests plus real run/job/ZIP gate PASS. C2 #43321997695 attempt 1, inner ZIP SHA `3f53c7ca4a0bc1d0f25cd228dcde003cd45ac247ecab76747405f556f75e8030`, writer 33,315 (+48), 23/23 receipts. Root cause unknown. Physical proof and FINAL ZIP still gated; no new C2/cutover.

### C6-C2-ONESHOT-DATA-PASS-PREP-NOARTIFACT-01 — C2 data PASS; C6 preparation FAIL (2026-11-13; accepted)

- [#43321997695](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43321997695) attempt 1: update-site SUCCESS; C6 prep FAILURE without steps, overall FAILURE. C2 artifact #13991878472 outer SHA-256 2686f1c54e77e630fd7f8c920f4d88d05f6048b68be26f11f5e3fa03745bebde verified; site-prod@f0cfcbc8 23/23 capture checkpoints. No C6 prep artifact, new Work A, FINAL ZIP or rollback proof. Production unchanged; owner reset C6 flag false. GLOBAL_CUTOVER=NO.

### C6-C2-ONESHOT-DISPATCHED-REPAUSED-INFLIGHT-01 — one authorized C2 launched; C2 and Netlify automation re-disabled (2026-11-13; accepted)

- [Preflight #43321776471](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43321776471) PASS with `C6_NEON_JSON_PREPARE_ENABLED=true`; [one-shot controller #43321969919](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43321969919) SUCCESS dispatched exactly one [C2 #43321997695](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43321997695) attempt 1, observed `in_progress` at `main@712c9e35`; C2 `360885782` + Netlify `360885508` returned `disabled_manually`. No Netlify/Neon Git release; C2 results and same-run C6 prep pending. Owner one-run grant used; owner must reset C6 prepare flag after run. `CUTOVER_PREFLIGHT_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-C2-ONESHOT-PREFLIGHT-BLOCKED-PREP-VAR-403-01 — owner one-shot C2 preflight blocked by required C6 variable; no dispatch (2026-11-13; accepted)

- [#43320947067](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43320947067) SUCCESS: exact postmerge heads, C2+Netlify disabled, C2 bundle/capture true but **`C6_NEON_JSON_PREPARE_ENABLED` not true**; matching preparation job would skip. [#43321093676](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43321093676) SUCCESS: GitHub Actions `GITHUB_TOKEN` repository variable GET HTTP 403; connector no variable-write permission. Owner-approved one-shot C2 **not dispatched**, no production writes or deploy. Next: owner/admin set Actions repository variable true, then one exact C2 run and restore false, leave Netlify off. `MATCHING_C2_PREPARATION_ARTIFACT=NO; CUTOVER_PREFLIGHT_READY=NO; GLOBAL_CUTOVER=NO`.

### C6-C3-CODEONLY-MERGES-AUTOMATION-PAUSED-01 — owner-approved code-only merges PASS; both production workflows disabled (2026-11-13; accepted)

- [Actions #43319519354](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43319519354) SUCCESS: C2 workflow `360885782` + Netlify production `360885508` disabled after no-active-runs check. PR #95 `329eb5f6` → `main@712c9e35`; PR #104 `ea71a0e2` → `site-prod@3cdac85a`; PR #100 `19446ba9` → `site-prod@6648a112`. Read-only post-merge [#43319759972](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43319759972), [#43319913889](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43319913889), [#43320143898](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43320143898) all SUCCESS; both remain `disabled_manually`. `site-prod` changed code only, Git JSON unchanged; Netlify production `6adb629bc3ebc570117d82e1` unchanged. **`CODE_ONLY_MERGES=PASS; C2_AUTO_WRITER_PAUSED=YES; NETLIFY_AUTO_DEPLOY_PAUSED=YES; CUTOVER_PREFLIGHT_READY=NO; GLOBAL_CUTOVER=NO`**. Next: separately authorized matching fresh C2/Work A/final ZIP, fresh rollback, production deploy and Git cutover.

### C6-C3-WORKK2-55PASS-RELEASE-CODE-READY-01 — Work K2 exact-head 55/55 code integration PASS; physical artifact blocked (2026-11-12; accepted)

- [PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) `329eb5f60adc75ea52547f98530ef837d1a00cda`, [Actions #43309443728](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43309443728) SUCCESS 55/55, [artifact #13983919719](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43309443728/artifacts/13983919719) verified SHA-256 `4035c68db1ca97ce0ed4a55fb5186ff576b9c031b2a43280034074fae6e2dd01`. Exactly workflow+test changed: remove undefined `FINAL_RUN_ID` from prepare, fetch `final-run.json` after ID in publisher, regression test PASS. `RELEASE_CODE_INTEGRATION_READY=YES` offline only. C2 #43262387718 lacks required same-run C6 preparation artifact; no authorized final ZIP. Rollback production authority/fresh package outstanding. `CUTOVER_PREFLIGHT_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

### C6-C3-WORKK-54PASS-FINAL-WORKFLOW-NOGO-01 — Work K 54/54 offline PASS with workflow runtime NO-GO (2026-11-12; accepted)

- [PR #95](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/95) `d25f02f2`, [#43307825507](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43307825507) SUCCESS 54/54, artifact #13983708946 SHA `c44dfb4f552c2afbfafa751dcd79f150194dbbc7edfc5650d33bf5b9bb14b214`. Prepare-only uses undefined `FINAL_RUN_ID`; publisher does not download required `final-run.json`. Exact #43262387718 C2 bundle exists, same-run C6 preparation artifact absent. Work K2 narrow fix + future matching provenance needed. `RELEASE_CODE_INTEGRATION_READY=NO; CUTOVER_PREFLIGHT_READY=NO; GLOBAL_CUTOVER=NO`.

### C3-G2-WORKI2-NETLIFY-ALIAS-PHYSICAL-PASS-01 — physical Git-only Netlify alias PASS (2026-11-12; accepted)

- Owner-approved [Actions #43306339282](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43306339282) SUCCESS at `382ea915`, [artifact #13984106982](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43306339282/artifacts/13984106982) verified ZIP SHA `106673981e7233bcfc44522f0843227a1ee3a7efa1ea501e2bb71ab11b0301b0`; Netlify alias `6af629b311d9632a220e652a` ready/branch-deploy. 13/13 HTTP 200, 12/13 file SHA exact (index RUM inserted; sole HTML diff not proven), 23/23 cities, 184/184 graphs, 23 CSV, Kyiv/casualty PASS, zero JS errors. Production `6adb629bc3ebc570117d82e1` and site-prod `d0a7d22d` unchanged. `NETLIFY_NONPROD_REDEPLOY_PROVEN=YES`; production authority/fresh no-loss rollback OPEN, `ROLLBACK_OPERATIONAL_READY=NO; GLOBAL_CUTOVER=NO`.

### C3-C6-WORKJ-FINAL-RELEASE-PREFLIGHT-NOGO-01 — Work J confirms final artifact ordering and rollback NO-GO (2026-11-12; accepted)

- Proofs: physical #43299402658 23 cities/18 SHA/33,267 historical, #43302381173 PR95→104→100 12/12 offline, rollback #43297683167 32/32+8/8. PR #95 currently creates FINAL binding + six files only in Git-publishing job; #104 requires pre-existing pinned artifact for Netlify. Work K: one default-OFF prepare-only final artifact output, no release. PR #104/#100 merges may auto Netlify `--prod`; Netlify manual workflow absent on main. Pause C2/Netlify before merges and maintain sole writer afterward. Work I2 nonprod alias separately approved but unproven, fresh production rollback remains blocked. `RELEASE_CODE_INTEGRATION_READY=NO; CUTOVER_PREFLIGHT_READY=NO; GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

### C3-FINAL-AUTHORIZED-KPI-PR104-EXACT-HEAD-12PASS-01 — PR #104 final authorized KPI contract exact-HEAD offline PASS (2026-11-12; accepted)

- [PR #104](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/104) `ea71a0e2` exact [#43302381173](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43302381173) SUCCESS: 12/12 cases and real pinned PR #95→#104→#100 fixture E2E, six final SHA, immutable original proof and byte-identical static KPI, fail-closed negatives. Four code-only paths, Git-only default unchanged, Neon release OFF. Physical historical six-JSON #43299402658 already PASS; no real authorized final artifact, Netlify deployment or Git publication. `FINAL_NEON_KPI_RELEASE_CONTRACT_CODE_READY=YES` offline; `ROLLBACK_OPERATIONAL_READY=NO; GLOBAL_CUTOVER=NO`.

<!-- coordination:history:end -->
