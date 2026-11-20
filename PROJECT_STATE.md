# Project State — current coordination snapshot

**Date:** 2026-11-20. **23-city current-day in-chart DRAFT READY; manual C6 SUCCESS; scheduled C6 OPEN.** Historical Neon cutover `GLOBAL_CUTOVER=YES`; four-hour Git-only updates unchanged. `DST_CORRECTION=OFF`; live active-alert status uncertified. English/trend/SEO LIVE. C6 stabilization tracked separately.
Latest accepted transition: **UI-ACTIVE23-CURRENT-DAY-DRAFT-2026-11-20-01**; prior **UI-ACTIVE23-LASTBAR-DRAFT-2026-11-20-01**; prior **UI-ACTIVE23-PROVISIONAL-TEST-READY-2026-11-20-01**; prior **C6-OWNER-MANUAL-CATCHUP-READY-2026-11-20-01**; prior C6 checkpoint **C6-WEEKDAY-READER-PIN-MERGED-2026-11-20-01**; prior UI checkpoint **UI-WEEKDAY-LIVE-LOCKED-2026-11-19-01**.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Historical production cutover/C3:** PR #78 accepted `C6-C3-WORKS-NEON-CUTOVER-PASS-01`; owner-gated [Netlify #43496568449](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43496568449) and [Git #43497605769](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43497605769) SUCCESS, 23-city historical KPI/CSV/browser QA PASS. `GLOBAL_CUTOVER=YES` applies to historical JSON only.
- **Scheduled C2/C6:** owner-only manual catch-up input `c6_run_now` registered on main through PR #205 (`main@7abdaf02`), default OFF, requires owner/main/auto ON, preserves C2→23-city Neon readback→Git-only release and zero Netlify. Manual #44680696823 SUCCESS, site-prod@8c8ee93 Git-only. This is manual proof, not a successful scheduled post-pin cycle. 2026-11-20 scheduled #44634410260 C2 writer NEON_SUCCEEDED (34,271 episodes, +53), but six-JSON reader BLOCKED on exact weekday `build_time_of_day_heatmap.py` blob drift. PR #203 squash merged `main@cf8d5db4`, offline C6 pin #44679502629 PASS; production `site-prod@ae650fea` unchanged, scheduled reader/Git-only proof **PENDING**. Earlier first four-hour Neon→Git #43625014243 PASS. Next two #43655729191/#43686460909: writer PASS, reader hash blocked. PR #167 fixed pin on main. Owner-approved one-shot [#43706909819](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43706909819) SUCCESS, C2 Neon receipt, 23/23 readback, [Git-only `site-prod@048af474`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/048af474d98c953bbac351936092ee2bd08c6fad), zero Netlify. Temporary one-shot trigger removed via PR #176 (`main@63a614ca`). **Still no successful scheduled post-pin cycle; C6_STABILIZATION=OPEN**.
- **Netlify/UI + SEO LIVE:** Trends and bilingual archive released PR #194; Netlify `6afb034ee4ead33599681226` READY+locked, 23 cities, 784 monthly pages and 936 sitemap URLs. Live independent read-only QA #43875088810 PASS. Monthly cron OFF; Git-only four-hour updates unaffected.

- **Weekday UI LIVE:** PR #201 site-prod@ae650fea, Netlify `6aff5392a3a6d0497a6f5d1d` READY+locked; Actions #44602714671 PASS. UA/EN weekday graphs, time modes, tutorial; regular C2/Neon unchanged.
- **23-city provisional TEST:** Draft PR #208, verified C2 capture #44680696823, 22 source-open + Sevastopol no-open; frozen snapshot only.
- **23-city latest-day chart FIX:** Draft PR #208 HEAD `31b68ac1`, verified 20 Nov final bar + mobile last-date tick, completed hours + unclosed hatch, uncluttered trend. Actions #44698962480 PASS (23/23 C2, 8+6+10 JS, DST); draft Netlify `6afffe14b64ca786aa56288d` READY/unpublished. Not live.
- **DST VERIFIED; correction OFF:** one-shot #43706909819 artifact #14159523883 proves all eight correct Kharkiv/Poltava/Zhytomyr/Cherkasy DST witnesses selected, all three obsolete parent UIDs excluded by canonical C2; no overlay/Neon writes. Other backfill/casualty/live-status gates independent.


## Concrete next tasks

1. Manual C6 #44680696823 SUCCESS. Check next 1–2 **scheduled** post-PR203 C2→Neon→Git cycles: exact weekday builder readback, 21/21 continuity, writer, 23/23 readback, Git-only publication, no Netlify. Do not mistake manual #43706909819 for scheduled proof.
2. UI active23: owner to review [corrected current-day in-chart draft PR #208](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/208), 20 Nov visible (no separate block). If approved, implement same-run live-sidecar producer with stale-source fail-closed and verified-all-clear replacement before separate owner-gated production release. Do not merge frozen snapshot into site-prod.
3. DST: no further activation/promotion. Preserve the source UTC fix and exact C2 canonical selector; in the next **scheduled** 23-city proof, verify the same eight witnesses and that three stale UIDs remain absent from calculations. Do not delete physical Neon evidence or enable the superseded research selector in PR #182.
4. UI/SEO: archive and trend LIVE, Netlify locked. Investigate strict HTML post-smoke #43874825782 without unnecessary deploy. Monthly automation requires separate owner GO; preserve four-hour Git updates.
5. Verify scheduled same-generation weekday dayparts refresh after PR #203; old Netlify UI test #44602714524 failed *before deploy* (tour 8 vs 6). Keep regular Netlify publishing locked.
6. Mark C6 stabilization CLOSED only after repeat-cycle proof; keep casualty/backfill separate.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## UI-ACTIVE23-CURRENT-DAY-DRAFT-2026-11-20-01 — 23-city final-day fix, draft PASS
- Owner flagged missing 20 Nov on intensity chart: same-run C2 dashboard has daily28 through Nov19, but exact C2 site_derived has Nov20 partial day for 23/23. Draft PR #208 HEAD `31b68ac10cc6a6ba1bd4f30b9255eeab5aeb0bad` now reconciles same-generation partial day without inventing completed hours, and forces final date tick on mobile. Actions #44698962480 SUCCESS (8+6+10 JS, DST/midnight), artifact #14611712593. Netlify draft `6afffe14b64ca786aa56288d` READY unpublished, primary production unchanged. Frozen snapshot, no automatic live status publisher.

## UI-ACTIVE23-LASTBAR-DRAFT-2026-11-20-01 — owner-feedback in-chart draft PASS; production unchanged
- Draft PR #208 HEAD 9c11f385f5755430b9067f17279de3e5e2c211f7. Replace standalone card with confirmed-blue + hatched provisional cap on the LAST intensity bar (23 source series), short dashed forecast-only tick when trend enabled, no competing forecast hatch; source-time tooltip and separate CSV provisional columns. Actions #44693191591 SUCCESS (23/23 frozen C2/Neon, 6+4+10 JS, DST/midnight) and #44693198945 SUCCESS, artifact #14609895891. Netlify draft `6afff30b288eb0e2e4f4e5e7` READY, unpublished; production `site-prod@8c8ee93` and published Netlify deploy unchanged. This is an archived static visual test, NOT a live status feed or automatic update.

## UI-ACTIVE23-PROVISIONAL-TEST-READY-2026-11-20-01 — archived 23-city draft PASS
- Draft PR #208 HEAD ec688164; C2 run #44680696823 NEON_SUCCEEDED, same-run source capture 23/23; Actions #44690082427 SUCCESS 6/6+10/10 JS, midnight/DST; proof #14607928356; 22 open source observations + Sevastopol no open at snapshot. Netlify draft 6affecda8c37c62e303f8b86 READY and unpublished; prod current deploy untouched. No automatic status publisher; NOT current live status, no canonical changes.

## C6-OWNER-MANUAL-CATCHUP-READY-2026-11-20-01 — workflow ready, not dispatched
- Owner asked immediate manual catch-up. Existing manual pilot blocked when auto mode ON. PR #205 merged `main@7abdaf02d8ee5ae965a7f90aa9fcfcb84259caf2`; new default-OFF `c6_run_now` requires owner `olegbalakin-cmyk`, `main`, auto enabled and all other one-shot toggles OFF. Reuses scheduled writer/read-only Neon 23-city reader/Git-only publisher and zero Netlify; guarded offline #44680250526 PASS, C6 pins #44680250420 PASS, timestamp #44680250542 PASS, docs #44680250456 PASS. No manually dispatched run or site-prod advance yet; do not claim data refresh or scheduled stabilization.

## C6-WEEKDAY-READER-PIN-MERGED-2026-11-20-01 — fix merged; scheduled proof pending
- Scheduled #44634410260: C2 writer NEON_SUCCEEDED, +53 / 34,271 canonical episodes, but isolated six-JSON reader fail-closed `BUILDER_CODE_DRIFT:scripts/build_time_of_day_heatmap.py`; no Git publish. Owner-authorized exact guard repair PR #203 squash merged `main@cf8d5db40eaa5ac94934035870e43d26af471b23`, fixed PR201 new Git blob while retaining original and rejecting arbitrary drift. Offline pin #44679502629 PASS, capture timestamp #44679502645 PASS, coordination CI #44679502639 PASS. No Netlify, production JSON, Neon or C2 mutation from repair. Need future scheduled 23/23 readback + Git commit proof; C6_STABILIZATION=OPEN.

## UI-WEEKDAY-LIVE-LOCKED-2026-11-19-01 — production LIVE
- Owner GO; PR #200 preview Actions #44591705771 PASS, artifact #14564845428; release PR #201 exact QA #44602597715 PASS. site-prod@`ae650feadef8e8d028ffadc2c5dc5a8e3f0f041b`. One-shot Actions #44602714671 SUCCESS, proof #14567973014. Netlify `6aff5392a3a6d0497a6f5d1d` READY+locked; live asset parity/KPI PASS. 4h derived update code ready, scheduled proof pending. No Neon writes or C2 changes. Old workflow #44602714524 failed before publish.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
