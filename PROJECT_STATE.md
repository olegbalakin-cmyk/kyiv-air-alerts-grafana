# Project State — current coordination snapshot

**Date:** 2026-11-21. **Active23 28-day URL rollover FIX LIVE and Netlify locked; 21 Nov row verified.** Historical Neon cutover `GLOBAL_CUTOVER=YES`; four-hour Git-only updates unchanged. `DST_CORRECTION=OFF`; live active-alert status uncertified. English/trend/SEO LIVE. C6 stabilization tracked separately.
Latest accepted transition: **C6-CRON-RELIABILITY-AUDIT-2026-11-21-01**; previous **C6-UI-RACE-RECOVERY-MAIN-OFFLINE-PASS-2026-11-21-01**. Historical details below.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Historical production cutover/C3:** PR #78 accepted GLOBAL_CUTOVER=YES for historical JSON; owner-gated Netlify #43496568449 and Git #43497605769 SUCCESS, 23-city KPI/CSV/browser PASS. Not active-alert live status.
- **Scheduled C2/C6:** #44850889425 last confirmed data publish; #44905215404 writer/readback PASS but Git-only publish blocked after concurrent UI PR #219. PR #221 merged `main@8eba3cd7`, UI-only race recovery offline 8+12 tests PASS (#44950124198), no Netlify. Physical repeat-cycle proof pending; `C6_STABILIZATION=OPEN`; 4h cron delivery unreliable (`C6_SCHEDULE_RELIABILITY=OPEN`).
- **UI/SEO LIVE:** PR #194 bilingual archive & trends (784 monthly pages, sitemap 936), Netlify `6afb034ee4ead33599681226` locked; browser QA #43875088810 PASS. Monthly cron OFF.

- **Weekday UI LIVE:** PR #201 site-prod@ae650fea, Netlify `6aff5392a3a6d0497a6f5d1d` READY+locked; Actions #44602714671 PASS. UA/EN weekday graphs, time modes, tutorial; regular C2/Neon unchanged.
- **Active23 UI LIVE + daily28 URL rollover FIX:** scheduled #44850889425 PASS, 23-city 21 Nov partial-day source; PR #219 merged site-prod@fcef2eb9. One-shot #44905428716 SUCCESS, proof #14707134897; Netlify `6b01928589f62e08bb7e4793` READY+published+locked. Live UA/EN/stale-URL Chromium #44906316130 PASS (Nov21 shown; 20min/2 starts for Kyiv). Source-at-capture only; stale unclosed cap hidden, completed data retained. No Neon/C2 change.
- **Archived preview:** PR #208 frozen and NOT production; source-bound PR #214 tested, released via #217.
- **DST VERIFIED; correction OFF:** #43706909819 proves 8 correct witnesses for Kharkiv/Poltava/Zhytomyr/Cherkasy and 3 stale parent UIDs excluded; no Neon mutation.


## Concrete next tasks

1. Investigate a separately approved independently scheduled, freshness-and-attempt-gated catch-up; GitHub cron is not reliably delivering all six nominal C6 runs/day. Verify next physical 23-city C2→Git cycles after UI-race fix PR #221: writer, 21/21 continuity, reader, Git-only publication and zero Netlify. A change in data/non-UI files blocks stale publication; next scheduled cycle or separately owner-triggered `c6_run_now` collects anew. Keep stabilization OPEN.
2. Monitor Active23 current-day rows after subsequent Git-only cycles, including URL rollover, 23-city parity, stale unclosed cap, clear behavior and trend; no regular Netlify deploys.
3. DST: no further activation/promotion. Preserve the source UTC fix and exact C2 canonical selector; in the next **scheduled** 23-city proof, verify the same eight witnesses and that three stale UIDs remain absent from calculations. Do not delete physical Neon evidence or enable the superseded research selector in PR #182.
4. UI/SEO: archive and trend LIVE, Netlify locked. Investigate strict HTML post-smoke #43874825782 without unnecessary deploy. Monthly automation requires separate owner GO; preserve four-hour Git updates.
5. Verify weekday dayparts after the next scheduled cycle; keep Netlify locked and Git-only publication.
6. Mark C6 stabilization CLOSED only after repeat-cycle proof; keep casualty/backfill separate.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-CRON-RELIABILITY-AUDIT-2026-11-21-01 — read-only schedule audit, recovery not deployed
- C6 cron unchanged `15 */4 * * *` on main, but Nov18–21 only 9 scheduled run entries vs 24 expected slots; unrelated casualty and backfill cron workflows also severely delayed/absent. GitHub documents delayed/dropped scheduled runs; no verified Nov21 GitHub Actions incident or repository-level disablement. See `docs/c6-scheduled-reliability-2026-11-21.md`. No schedule or site-prod changes. Independently scheduled catch-up needs separate owner GO, last-attempt/freshness safety and zero Netlify; `C6_SCHEDULE_RELIABILITY=OPEN`.

## C6-UI-RACE-RECOVERY-MAIN-OFFLINE-PASS-2026-11-21-01 — UI-only Git race recovery merged, live proof pending
- Scheduled #44905215404 Neon writer/reader PASS, but Git-only publication BLOCKED after UI-only site-prod PR #219 merged during run; no Git data publish. PR #221 merged `main@8eba3cd7d4a50568b1ee399d155e6656b8a4c039`: bounded one-retry fast-forward across allowlisted UI changes, otherwise fail closed for data/non-UI drift; no Netlify or Neon change. Isolated Git Actions #44950124198 SUCCESS (8 race and 12 existing C6 tests); coordination CI #44950124236 SUCCESS. `site-prod` not changed by this code merge; real scheduled pass NOT YET PROVEN, `C6_STABILIZATION=OPEN`.

## UI-ACTIVE23-URL-ROLLOVER-FIX-LIVE-2026-11-21-01 — saved 28-day URLs follow new dates
- Scheduled C6 #44850889425 SUCCESS, 23-city 21 Nov source; Chromium #44905071873 proved clean link showed Nov21, while #44905182276 proved stale `cityto=2026-11-20` omitted it. PR #219 merged site-prod@fcef2eb9; owner one-shot #44905428716 SUCCESS, receipt #14707134897. Netlify `6b01928589f62e08bb7e4793` READY/published/locked. Post-release Chromium #44906316130 SUCCESS: UA/EN/stale-URL show Nov21, Kyiv 20min/2 starts, no JS errors; source remains 23-city Git-only, provisional expiry unchanged. Custom date intervals are not auto-shifted.

## UI-ACTIVE23-LIVE-LOCKED-2026-11-20-01 — scheduled sidecar and UI production PASS
- Scheduled Actions #44778822214 SUCCESS: C2→Neon readback, 23-city `active23_source_capture.json` (6 open at capture), Git-only site-prod@d8845e19; not authoritative live status. PR #217 released tested source-bound UI after Chromium #44722499442 PASS, PR preflight #44812470553 SUCCESS; site-prod@60cb8bb, follow-up one-shot build fix@096504ba. Owner-gated Actions #44812658726 SUCCESS, receipt #14667572246, Netlify deploy `6b00af31d1f034384896af23` READY, published and locked. Legacy automatic Netlify push trigger disabled; C6 updates remain Git-only. `C6_STABILIZATION=OPEN` pending repeat scheduled cycle.

## C6-ACTIVE23-SOURCE-REGISTERED-UI-PREVIEW-PASS-2026-11-20-01 — producer main, UI still OFF
- Producer PR #213 merged `main@615e91244b9750cd9a1584ec3027537ad2255734`; physical 6-JSON release binding offline #44721997889 PASS. UI PR #214 browser #44722499442 SUCCESS (27 scenarios, 23 cities, UA/EN/mobile, trend), artifact #14623105687, Netlify draft `6b00260ce91522afa4647a72` READY not published. **Scheduled C6 source sidecar NOT YET PROVEN**, site-prod/Netlify unchanged. UI release separately gated.

## UI-ACTIVE23-LIVE-SOURCE-OFFLINE-PASS-2026-11-20-01 — integration drafts only
- PR #213 C6 verified 23-city source receipts, expiry, all-clear and real six-file release-binding offline Actions #44721997889 PASS; PR #214 UI 23-city current-day overlay/count source/locale static #44721447216 PASS, Chromium pending. C2 derived vs later physical dashboard timestamps legitimately differ; bind by C6 release manifest and C2 SHA. No production change; C6 stabilization OPEN.

## UI-ACTIVE23-BROWSER-RENDER-PASS-2026-11-20-01 — rendered 20 Nov verified, draft only
- Initial Chromium #44702699636 and #44703124322 FAIL proved actual Nov19 final bar, source snapshot missing and `site-derived.json` HTTP 404. Isolated Netlify preview bundle repaired implicit root-build asset omission, tested immutable deploy `6b0007017cdb6d8c97bdbc05`: Actions #44703989283 SUCCESS, 27 real-browser cases across 23 cities, UA desktop/EN mobile, trend toggles and axis labels; screenshot/JSON proof artifact #14614097420. Draft PR #208 HEAD `3101a4682e13108cad75c14c4ab050856d0b3cad`; production untouched, active-status publisher not created.

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
