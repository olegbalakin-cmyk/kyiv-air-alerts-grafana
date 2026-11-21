# Project State — current coordination snapshot

**Date:** 2026-11-21. **Active23 28-day URL rollover FIX LIVE and Netlify locked; 21 Nov row verified.** Historical Neon cutover `GLOBAL_CUTOVER=YES`; four-hour Git-only updates unchanged. `DST_CORRECTION=OFF`; live active-alert status uncertified. English/trend/SEO LIVE. C6 stabilization tracked separately.
Latest accepted transition: **UI-ACTIVE23-URL-ROLLOVER-FIX-LIVE-2026-11-21-01**; previous **UI-ACTIVE23-LIVE-LOCKED-2026-11-20-01**. Historical details below.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Historical production cutover/C3:** PR #78 accepted GLOBAL_CUTOVER=YES for historical JSON; owner-gated Netlify #43496568449 and Git #43497605769 SUCCESS, 23-city KPI/CSV/browser PASS. Not active-alert live status.
- **Scheduled C2/C6:** #44778822214 SUCCESS scheduled writer/readback/Git-only publish; 23-city source sidecar on site-prod@d8845e19, zero Netlify. Earlier reader pin PR #203 PASS. Repeat-cycle proof pending; `C6_STABILIZATION=OPEN`.
- **UI/SEO LIVE:** PR #194 bilingual archive & trends (784 monthly pages, sitemap 936), Netlify `6afb034ee4ead33599681226` locked; browser QA #43875088810 PASS. Monthly cron OFF.

- **Weekday UI LIVE:** PR #201 site-prod@ae650fea, Netlify `6aff5392a3a6d0497a6f5d1d` READY+locked; Actions #44602714671 PASS. UA/EN weekday graphs, time modes, tutorial; regular C2/Neon unchanged.
- **Active23 UI LIVE + daily28 URL rollover FIX:** scheduled #44850889425 PASS, 23-city 21 Nov partial-day source; PR #219 merged site-prod@fcef2eb9. One-shot #44905428716 SUCCESS, proof #14707134897; Netlify `6b01928589f62e08bb7e4793` READY+published+locked. Live UA/EN/stale-URL Chromium #44906316130 PASS (Nov21 shown; 20min/2 starts for Kyiv). Source-at-capture only; stale unclosed cap hidden, completed data retained. No Neon/C2 change.
- **Archived preview:** PR #208 frozen and NOT production; source-bound PR #214 tested, released via #217.
- **DST VERIFIED; correction OFF:** #43706909819 proves 8 correct witnesses for Kharkiv/Poltava/Zhytomyr/Cherkasy and 3 stale parent UIDs excluded; no Neon mutation.


## Concrete next tasks

1. Verify 1–2 more scheduled 23-city C2→Git cycles after #44778822214 (writer, 21/21 continuity, reader, zero Netlify); keep C6 stabilization OPEN until repeat proof.
2. Monitor Active23 current-day rows after subsequent Git-only cycles, including URL rollover, 23-city parity, stale unclosed cap, clear behavior and trend; no regular Netlify deploys.
3. DST: no further activation/promotion. Preserve the source UTC fix and exact C2 canonical selector; in the next **scheduled** 23-city proof, verify the same eight witnesses and that three stale UIDs remain absent from calculations. Do not delete physical Neon evidence or enable the superseded research selector in PR #182.
4. UI/SEO: archive and trend LIVE, Netlify locked. Investigate strict HTML post-smoke #43874825782 without unnecessary deploy. Monthly automation requires separate owner GO; preserve four-hour Git updates.
5. Verify weekday dayparts after the next scheduled cycle; keep Netlify locked and Git-only publication.
6. Mark C6 stabilization CLOSED only after repeat-cycle proof; keep casualty/backfill separate.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## UI-ACTIVE23-URL-ROLLOVER-FIX-LIVE-2026-11-21-01 — saved 28-day URLs follow new dates
- Scheduled C6 #44850889425 SUCCESS, 23-city 21 Nov source; Chromium #44905071873 proved clean link showed Nov21, while #44905182276 proved stale `cityto=2026-11-20` omitted it. PR #219 merged site-prod@fcef2eb9; owner one-shot #44905428716 SUCCESS, receipt #14707134897. Netlify `6b01928589f62e08bb7e4793` READY/published/locked. Post-release Chromium #44906316130 SUCCESS: UA/EN/stale-URL show Nov21, Kyiv 20min/2 starts, no JS errors; source remains 23-city Git-only, provisional expiry unchanged. Custom date intervals are not auto-shifted.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
