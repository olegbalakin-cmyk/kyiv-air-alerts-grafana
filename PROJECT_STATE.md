# Project State — current coordination snapshot

**Date:** 2026-11-21. **Active23 28-day URL rollover FIX LIVE and Netlify locked; 21 Nov row verified.** Historical Neon cutover `GLOBAL_CUTOVER=YES`; four-hour Git-only updates unchanged. `DST_CORRECTION=OFF`; live active-alert status uncertified. English/trend/SEO LIVE. C6 stabilization tracked separately.
Latest accepted transition: **C6-WATCHDOG-RUNTIME-OBSERVED-2026-11-22-01**; previous **C6-WATCHDOG-ENABLED-DEPLOYED-PROOF-PENDING-2026-11-22-01**. Historical details below.

## Working instructions

1. Read this root file and [CHANGELOG.md](CHANGELOG.md) before repository work. This file governs current coordination; newer accepted repository checkpoints govern older chat memory.
2. Verify the relevant immutable commits, actual Actions runs and proof artifacts before technical action. A successful research job does not prove production deployment or a release PASS.
3. Keep production, development/WIP, historical reference, backfill, casualty and Neon/persistence tracks separate. Do not overwrite another worker's commits, force-push shared branches, expose credentials or infer a production change from research.
4. Keep unresolved blockers, track status and next tasks **outside** the history markers below. Put detailed accepted checkpoints inside them, newest first; retain the latest checkpoint. Prepend brief accepted transitions inside CHANGELOG's markers. Full evidence belongs in immutable archives or proof files.
5. Aim for **5–8 KiB** here and **5–10 recent transitions** in CHANGELOG. UTF-8 byte gate: ≤12,288 PASS; 12,289–16,384 WARNING; >16,384 FAIL. Before an oversized update, run `python scripts/coordination_docs.py archive --dry-run`, then `archive` on a separate branch. See [maintenance instructions](docs/coordination-maintenance.md).
6. Never load entire historical archives, large JSON/SQL dumps or full Actions logs into Work context. Search an exact checkpoint ID and read bounded lines. Save reproducible work promptly; recover interrupted commits before new research.

## Current tracks and open release gates

- **Historical production cutover/C3:** PR #78 accepted GLOBAL_CUTOVER=YES for historical JSON; owner-gated Netlify #43496568449 and Git #43497605769 SUCCESS, 23-city KPI/CSV/browser PASS. Not active-alert live status.
- **Scheduled C2/C6:** backup scheduler PR #224 merged; owner PAT saved as Netlify secret, backup enabled in isolated deploy `6b02b299b68451c6ef022581` READY (cron :47 UTC hourly). Seven actual checks verified; fallback dispatch pending. #44850889425 last confirmed data publish; #44905215404 writer/readback PASS but Git-only publish blocked after concurrent UI PR #219. PR #221 merged `main@8eba3cd7`, UI-only race recovery offline 8+12 tests PASS (#44950124198), no Netlify. Physical repeat-cycle proof pending; `C6_STABILIZATION=OPEN`; 4h cron delivery unreliable (`C6_SCHEDULE_RELIABILITY=OPEN`).
- **UI/SEO LIVE:** PR #194 bilingual archive/trends (936 sitemap URLs); Netlify locked, #43875088810 PASS. Monthly cron OFF.

- **Weekday UI LIVE:** PR #201, Netlify READY+locked, Actions #44602714671 PASS; weekday charts, modes, tutorial LIVE. C2 unchanged.
- **Active23 UI LIVE:** PR #219, Netlify 6b01928589f62e08bb7e4793 READY+locked, browser #44906316130 PASS; source-at-capture only.
- **Archived preview:** PR #208 not production; #214 released via #217.
- **DST VERIFIED; correction OFF:** #43706909819 proves eight correct witnesses and three stale UIDs excluded; no Neon mutation.


## Concrete next tasks

1. Verify actual Netlify `c6-backup` scheduled invocation and, once both age gates permit, one owner-actor `c6_run_now` C2→Neon→Git-only publish. Production Netlify must remain locked; GitHub cron remains active but unreliable. Verify next physical 23-city C2→Git cycles after UI-race fix PR #221: writer, 21/21 continuity, reader, Git-only publication and zero Netlify. A change in data/non-UI files blocks stale publication; next scheduled cycle or separately owner-triggered `c6_run_now` collects anew. Keep stabilization OPEN.
2. Monitor Active23 current-day rows after subsequent Git-only cycles, including URL rollover, 23-city parity, stale unclosed cap, clear behavior and trend; no regular Netlify deploys.
3. DST: no further activation/promotion. Preserve the source UTC fix and exact C2 canonical selector; in the next **scheduled** 23-city proof, verify the same eight witnesses and that three stale UIDs remain absent from calculations. Do not delete physical Neon evidence or enable the superseded research selector in PR #182.
4. UI/SEO: archive and trend LIVE, Netlify locked. Investigate strict HTML post-smoke #43874825782 without unnecessary deploy. Monthly automation requires separate owner GO; preserve four-hour Git updates.
5. Verify weekday dayparts after the next scheduled cycle; keep Netlify locked and Git-only publication.
6. Mark C6 stabilization CLOSED only after repeat-cycle proof; keep casualty/backfill separate.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## C6-WATCHDOG-RUNTIME-OBSERVED-2026-11-22-01 — hourly invocations proven, fallback unproven
- Audit #45018145331 SUCCESS: 7 Netlify checks 04:47–10:47 UTC Nov22. After activation 09:47/10:47 C6_ATTEMPT_RECENT/no redundant dispatch; before activation 04:47–06:47 DRY_RUN_ONLY. Native C6 #44995863969 SUCCESS. Backup-triggered C6 NOT observed; C6_SCHEDULE_RELIABILITY=OPEN.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
