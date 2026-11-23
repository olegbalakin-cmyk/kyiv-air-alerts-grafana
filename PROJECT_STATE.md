# Project State — current coordination snapshot

**Date:** 2026-11-22. **Weekday split per-column percentages LIVE on locked Netlify; 23-city same-release PASS.** Historical Neon cutover `GLOBAL_CUTOVER=YES`; four-hour Git-only updates unchanged. `DST_EXTRA_CORRECTION=NOT_REQUIRED` (status label only; research selector remains disabled); live active-alert status uncertified. English/trend/SEO LIVE. C6 stabilization tracked separately.
Latest accepted transition: **DOC-DST-STATUS-CLARIFIED-2026-11-22-01**; previous **UI-WEEKDAY-SPLIT-LIVE-LOCKED-2026-11-22-01**. Historical details below.

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

- **Weekday UI LIVE:** PR #201 and correction PR #229 (based on PR #226), site-prod@49abd7a, Netlify `6b02d5edba0ff97b80b83052` READY/published/locked. Exact 5 JS/CSS and UA/EN markers, 23-city release parity independently PASS #45018970389. Per-weekday-bar hover/tap gives hours and its own percentages. C2/Neon unchanged; main release Actions #45018819545 published/relocked successfully but overall FAILED at byte-exact HTML smoke (Netlify-injected bytes); no redeploy required.
- **Active23 UI LIVE:** PR #219, source-bound current day and URL rollover verified #44906316130; present in newer locked Netlify `6b02d5edba0ff97b80b83052`. Source-at-capture only.
- **Archived preview:** PR #208 not production; #214 released via #217.
- **DST VERIFIED; extra correction NOT REQUIRED:** #43706909819 confirms eight correct witnesses and three stale UIDs already excluded from calculations; research selector stays disabled, no Neon mutation.


## Casualty track — first publication preparation (NO GO)

- **Priority:** safely publish partial September/October civilian fatality data for 23 cities, without treating incomplete values as exact totals. September has partial baseline in every city; October has 4 verified attacks/11 fatalities in 4 cities, remaining 19 unknown. First UI preview PR #237 passed only offline (#45073738532). Never interpret 11 as full October total.
- **Parallel prepared scopes:** September coverage/proof #238, Sep+Oct UI + real browser preview #239, Git-only sidecar/publisher contract #240. Their proof and release gates are independent; prevent cross-track writes.
- **Proof / next gate (Nov 23):** #238→PR #243 CI #45147864411 PASS: Sep 23 partial city rows, known minimum **56** incl. existing Sumy +1, **zero new** safe Sept credits. #239→PR #237 UA/EN browser #45151092355 PASS 28/28 but reads frozen fixture. #240→PR #244 corrected HEAD **1cf1fb29** (#45151954338 PASS): removed 19 unproven per-city cutoff dates; only Kyiv Sep15, Kherson Sep17, Odesa/Zaporizhzhia Sep18 proven; Sumy Sep20 an event, not ongoing coverage. **Integration #245** must connect live canonical Git sidecar and physically prove 23-city browser/CSV/rollback before separate owner GO. `PROMOTE=OFF`; production untouched.

## Concrete next tasks

1. Verify actual Netlify `c6-backup` scheduled invocation and, once both age gates permit, one owner-actor `c6_run_now` C2→Neon→Git-only publish. Production Netlify must remain locked; GitHub cron remains active but unreliable. Verify next physical 23-city C2→Git cycles after UI-race fix PR #221: writer, 21/21 continuity, reader, Git-only publication and zero Netlify. A change in data/non-UI files blocks stale publication; next scheduled cycle or separately owner-triggered `c6_run_now` collects anew. Keep stabilization OPEN.
2. Monitor Active23 current-day rows after subsequent Git-only cycles, including URL rollover, 23-city parity, stale unclosed cap, clear behavior and trend; no regular Netlify deploys.
3. DST: no further activation/promotion. Preserve the source UTC fix and exact C2 canonical selector; in the next **scheduled** 23-city proof, verify the same eight witnesses and that three stale UIDs remain absent from calculations. Do not delete physical Neon evidence or enable the superseded research selector in PR #182.
4. UI/SEO: archive and trend LIVE, Netlify locked. Investigate strict HTML post-smoke #43874825782 without unnecessary deploy. Monthly automation requires separate owner GO; preserve four-hour Git updates.
5. Verify weekday split after next scheduled 23-city Git-only refresh; preserve release-manifest binding, zero Netlify auto-deploy and percentage denominators per weekday bar. Investigate Netlify-injected HTML strict byte-comparison smoke without redeploy.
6. Mark C6 stabilization CLOSED only after repeat-cycle proof; keep casualty/backfill separate.

## Latest accepted checkpoint — full text

<!-- coordination:history:start -->
## CASUALTY-INDEPENDENT-PROOFS-CUTOFF-FIX-2026-11-23-01
- September PR #243 HEAD f8112362 CI #45147864411 PASS: 23-city partial, existing minimum 56, no new September credits. UI PR #237 HEAD c654a1ef, browser #45151092355 28/28 PASS, proof #14805749223; still frozen local fixture. Publisher PR #244 corrected HEAD 1cf1fb29, CI #45151954338 PASS after removing unsupported 19 Sep18 cutoffs; four known cutoffs only, Sumy Sep20 a single credited event. **Not integrated**: issue #245 canonical Git-only data + UI physical QA. No release GO; PROMOTE=OFF.


## CASUALTY-FIRST-PUBLICATION-TASKS-2026-11-23-01 — preparatory gates only
- Owner prioritizes first correct casualty publication; owner permits executor briefs, **not** production publication. Coordinator created September 23-city audit issue #238, UI partial Sep+Oct browser-preview issue #239, and Git-only sidecar/publisher contract issue #240. PR #237 (HEAD b8f29139, Actions #45073738532 SUCCESS) proves offline October UI only, not browser or production; source PR #236 (HEAD 270702cc, #45073045655 SUCCESS) contains 4 October events/11 deceased, 19 city-months unknown. All September baselines remain partial; existing Kyiv original Sep cutoff 2026-09-15, three independent validated-city cutoffs are Kherson Sep17 and Odesa/Zaporizhzhia Sep18. Freeze Sumy Sep20 confirmed revision. Collector #45070256716 used its one-shot 27 GET grant; no grant remains. Release is BLOCKED until source proofs, 23-city browser+CSV parity, and publish/rollback contract PASS, followed by separate owner GO. Keep PROMOTE=OFF, zero production/Neon/Netlify changes.

## DOC-DST-STATUS-CLARIFIED-2026-11-22-01 — documentation label only
- Clarified the current coordination status to `DST_EXTRA_CORRECTION=NOT_REQUIRED`: eight valid DST witnesses are already counted and three stale physical UIDs excluded, supported by readback Actions #43706909819 and proof artifact #14159523883. Superseded research selector PR #182 remains disabled/unmerged. No runtime flag rename, Neon mutation, C2 change, production publication, or Netlify deploy.

## UI-WEEKDAY-SPLIT-LIVE-LOCKED-2026-11-22-01 — release verified independently
- Owner GO; preview PR #226 exact HEAD `75662e5ec013a550d73620e54ca1beb0ede1020f`, Actions #45013730066 SUCCESS (14 Node, 374 23-city integration, 57 browser cases), artifact #14751022637. Production PR #229 squash `site-prod@84c62de09b7df2f6a17e3cb7231bb4d88cd951f6`, follow-up gate repair `49abd7a562ab3becd1df4827aa12d9505be6565d`; Actions #45018819545 built and published Netlify `6b02d5edba0ff97b80b83052` READY/locked but overall FAILURE only on byte-comparing HTML modified by Netlify. Independent read-only Actions #45018970389 SUCCESS: exact served five JS/CSS assets, UA/EN HTML markers, 23-city same-release data and production lock PASS. UI fix LIVE, no duplicate redeploy; C2/Neon and regular Git-only publisher unchanged.

## C6-WATCHDOG-RUNTIME-OBSERVED-2026-11-22-01 — hourly invocations proven, fallback unproven
- Audit #45018145331 SUCCESS: 7 Netlify checks 04:47–10:47 UTC Nov22. After activation 09:47/10:47 C6_ATTEMPT_RECENT/no redundant dispatch; before activation 04:47–06:47 DRY_RUN_ONLY. Native C6 #44995863969 SUCCESS. Backup-triggered C6 NOT observed; C6_SCHEDULE_RELIABILITY=OPEN.

<!-- coordination:history:end -->

## Evidence and documentation maintenance

- [Complete archive index and integrity](docs/coordination-archive/README.md): exact previous roots, original large historical blobs and dated snapshots; [machine manifest](docs/coordination-archive/manifest.json).
- [Maintenance contract and CLI](docs/coordination-maintenance.md). CI verifies byte limits, exact historical record coverage and immutable archives. Automatic archival proposes a PR only; no direct main push or auto-merge.
- **DOC-AUTO-MAINTENANCE-MERGE-02:** [PR #34](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/34) merged at `main@3735f359d2bfa3310cc7f9fd46f9c8f3a2af0e8f`; [Actions 41202336197](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/41202336197) SUCCESS on main (unit tests, byte gate, archive integrity and dry-run). Roots: PROJECT_STATE **7,990 B**, CHANGELOG **7,127 B** at merge; 10 records / 8 unique checkpoint IDs archived with hashes. Main-only PR-proposal job is now active but no over-threshold PR-creation attempt yet; bot permission remains unproven. No required status checks/rulesets; protection unchanged. CLI/patch fallback remains available. This documentation checkpoint is not a Neon release.
