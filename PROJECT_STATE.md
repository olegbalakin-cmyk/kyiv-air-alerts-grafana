# Project State — current coordination snapshot

**Date:** 2026-11-19. **Weekday dashboard LIVE, Netlify READY + locked.** Historical Neon cutover `GLOBAL_CUTOVER=YES`; four-hour Git-only updates unchanged. `DST_CORRECTION=OFF`; live active-alert status uncertified. English/trend/SEO LIVE. C6 stabilization tracked separately.
Latest accepted transition: **UI-WEEKDAY-LIVE-LOCKED-2026-11-19-01**; latest prior C6 code pin **C6-DST-READER-PIN-MERGED-2026-11-15-01**.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Historical production cutover/C3:** PR #78 accepted `C6-C3-WORKS-NEON-CUTOVER-PASS-01`; owner-gated [Netlify #43496568449](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43496568449) and [Git #43497605769](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43497605769) SUCCESS, 23-city historical KPI/CSV/browser QA PASS. `GLOBAL_CUTOVER=YES` applies to historical JSON only.
- **Scheduled C2/C6:** first four-hour Neon→Git #43625014243 PASS. Next two #43655729191/#43686460909: writer PASS, reader hash blocked. PR #167 fixed pin on main. Owner-approved one-shot [#43706909819](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43706909819) SUCCESS, C2 Neon receipt, 23/23 readback, [Git-only `site-prod@048af474`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/048af474d98c953bbac351936092ee2bd08c6fad), zero Netlify. Temporary one-shot trigger removed via PR #176 (`main@63a614ca`). **Still no successful scheduled post-pin cycle; C6_STABILIZATION=OPEN**.
- **Netlify/UI + SEO archive (2026-11-16):** Trend hatch PR #191 site-prod@7c1adc43 and bilingual site LIVE. Owner-approved SEO release PR #194 merged `site-prod@6d0879c`; Netlify `6afb034ee4ead33599681226` READY and locked. 23 city/raion series, 392 verified completed months, 784 bilingual monthly pages, 936 sitemap URLs, `robots.txt`, footer link. Same-generation KPI sourced from embedded verified dashboard (deployed blob `a64a93e3`; standalone Git index older). Release CI #43874588605 PASS. Production workflow #43874825782 deploy/relock/KPI PASS, overall **FAIL** at known HTML post-smoke. Independent live HTTP #43875088810 PASS (50 pages/61 requests, artifact #14229611799). Monthly cron OFF (Draft #193); future activation needs separate GO. Four-hour C6 unchanged.

- **Weekday UI LIVE (Nov 19):** PR #201 site-prod@`ae650fea`; Netlify `6aff5392a3a6d0497a6f5d1d` READY + locked; Actions #44602714671 SUCCESS. UK/EN tutorial, 4-band/day-night switch. Next scheduled dayparts refresh awaits proof; C2/Neon unchanged.
- **DST VERIFIED; correction OFF:** one-shot #43706909819 artifact #14159523883 proves all eight correct Kharkiv/Poltava/Zhytomyr/Cherkasy DST witnesses selected, all three obsolete parent UIDs excluded by canonical C2; no overlay/Neon writes. Other backfill/casualty/live-status gates independent.


## Concrete next tasks

1. Check 1–2 **scheduled** post-pin C2→Neon→Git cycles: 21/21 continuity, writer, 23/23 readback, Git-only publication, no Netlify. Do not mistake manual #43706909819 for scheduled proof.
2. DST: no further activation/promotion. Preserve the source UTC fix and exact C2 canonical selector; in the next **scheduled** 23-city proof, verify the same eight witnesses and that three stale UIDs remain absent from calculations. Do not delete physical Neon evidence or enable the superseded research selector in PR #182.
3. UI/SEO: archive and trend LIVE, Netlify locked. Investigate strict HTML post-smoke #43874825782 without unnecessary deploy. Monthly automation requires separate owner GO; preserve four-hour Git updates.
4. Verify scheduled same-generation weekday dayparts refresh; old Netlify UI test #44602714524 failed *before deploy* (tour 8 vs 6). Keep regular Netlify publishing locked.
5. Mark C6 stabilization CLOSED only after repeat-cycle proof; keep casualty/backfill separate.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## UI-WEEKDAY-LIVE-LOCKED-2026-11-19-01 — production LIVE
- Owner GO; PR #200 preview Actions #44591705771 PASS, artifact #14564845428; release PR #201 exact QA #44602597715 PASS. site-prod@`ae650feadef8e8d028ffadc2c5dc5a8e3f0f041b`. One-shot Actions #44602714671 SUCCESS, proof #14567973014. Netlify `6aff5392a3a6d0497a6f5d1d` READY+locked; live asset parity/KPI PASS. 4h derived update code ready, scheduled proof pending. No Neon writes or C2 changes. Old workflow #44602714524 failed before publish.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
