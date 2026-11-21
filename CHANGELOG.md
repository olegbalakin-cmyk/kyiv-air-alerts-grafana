# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

**C6-UI-RACE-RECOVERY-MAIN-OFFLINE-PASS-2026-11-21-01 — UI-only race recovery merged; real production cycle pending**
- Scheduled #44905215404 wrote to Neon but Git-only publish blocked after UI PR #219 advanced `site-prod` mid-run. PR #221 merged `main@8eba3cd7d4a50568b1ee399d155e6656b8a4c039`: revalidate and retry once across allowlisted UI-only changes; data/non-UI drift fail-closed (fresh C2 on next schedule or owner manual). Offline Actions #44950124198 PASS (8 new + 12 existing C6 tests), docs CI #44950124236 PASS. Zero Netlify, no immediate `site-prod`/Neon release; scheduled proof pending, stabilization OPEN.

**UI-ACTIVE23-URL-ROLLOVER-FIX-LIVE-2026-11-21-01 — saved full 28-day range follows scheduled refresh**
- C6 #44850889425 PASS; actual browser #44905182276 exposed old URL capped at Nov20, while #44905071873 showed Nov21 on clean URL. PR #219 site-prod@fcef2eb9, one-shot #44905428716 SUCCESS, proof #14707134897, Netlify `6b01928589f62e08bb7e4793` READY+locked. Live browser #44906316130 PASS for UK/EN/stale-URL Nov21. No C2/Neon/data changes; custom date filters unaffected.

**UI-ACTIVE23-LIVE-LOCKED-2026-11-20-01 — source-bound last-bar UI production READY+locked**
- Scheduled C6 #44778822214 SUCCESS, 23-city source sidecar on site-prod (6 open at capture), zero Netlify; UI PR #217 site-prod@60cb8bb, one-shot build fix@096504ba, Actions #44812658726 SUCCESS, proof #14667572246; Netlify `6b00af31d1f034384896af23` published READY+locked. 8h/local-midnight expiry, not a live status feed. Legacy automatic Netlify push disabled; C6 repeat-cycle stabilization OPEN.

**C6-ACTIVE23-SOURCE-REGISTERED-UI-PREVIEW-PASS-2026-11-20-01 — producer main, UI still gated**
- PR #213 merged main@`615e91244b9750cd9a1584ec3027537ad2255734`, physical 6-file release binding offline #44721997889 PASS. UI PR #214 still draft; Chromium [#44722499442](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/44722499442) SUCCESS 27/27 cases, screenshot/JSON proof #14623105687, archived Netlify preview only. First actual scheduled C6 source-sidecar publication still UNVERIFIED; production Netlify and site-prod unchanged. No claim of live rollout.

**UI-ACTIVE23-LIVE-SOURCE-OFFLINE-PASS-2026-11-20-01 — source-bound release preparation, DRAFT ONLY**
- Producer C6 PR #213 and UI PR #214 UNMERGED. C2 source→physical 6-JSON release SHA/clock binding offline Actions #44721997889 PASS; 23-city UI expiry/clear/count regression #44721447216 PASS. Browser QA and real scheduled Git-only proof remain release gates. Prod Netlify site locked; no data, C2 or Netlify publication.

**UI-ACTIVE23-BROWSER-RENDER-PASS-2026-11-20-01 — Nov20 actual Chart.js rendering PASS on unpublished draft**
- Chromium regression #44702699636 FAIL showed Nov19, missing snapshot and `site-derived.json` 404 despite static source PASS. PR #208 HEAD `3101a468` isolates complete Netlify draft bundle, Actions [#44703989283](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/44703989283) SUCCESS: 27 browser cases, 23 cities, UA desktop/EN mobile, actual Nov20 axis tick/bar, trend on/off; proof artifact #14614097420 (screenshots/JSON), Netlify draft `6b0007017cdb6d8c97bdbc05` READY/unpublished. Production unchanged; frozen source is not live publisher.

<!-- coordination:history:start -->
### UI-ACTIVE23-CURRENT-DAY-DRAFT-2026-11-20-01 — Nov 20 chart row restored in 23-city draft
- Owner reported no current date. Confirmed same-run C2 dashboard `daily28` ends Nov19; SHA-verified C2 `site_derived.daily28_current` supplies partial Nov20 for all 23 (including closed durations). Draft PR #208 HEAD `31b68ac1` now reconciles exact same-run partial row before range/chart and explicitly labels final day on mobile, preserving source-bound unclosed hatch, trend tick, and no independent panel. Actions [#44698962480](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/44698962480) SUCCESS: 8 overlay + 6 source + 10 weekday tests, DST/midnight; artifact #14611712593. Netlify draft `6afffe14b64ca786aa56288d` READY unpublished, existing published deploy unchanged. Frozen test only; no Neon/C2/production UI change.


### UI-ACTIVE23-LASTBAR-DRAFT-2026-11-20-01 — source-bound last-bar preview, no live release
- Owner requested no separate card: Draft PR #208 HEAD 9c11f385 now renders Neon-completed blue base + hatched unclosed source cap within last intensity bar; trend uses a short dashed marker (not a second fill). UA/EN, source-time tooltip, provisional CSV. Actions #44693191591 PASS 23/23 + 6/4/10 JS + DST; regression #44693198945 PASS; artifact #14609895891. Netlify draft `6afff30b288eb0e2e4f4e5e7` READY unpublished, production unchanged. Static archived test, not an automated live sidecar.


### UI-ACTIVE23-PROVISIONAL-TEST-READY-2026-11-20-01 — 23-city archived draft, production unchanged
- Draft PR #208 HEAD ec688164, Actions #44690082427 SUCCESS (same-run 23/23 C2/Neon source capture, 22 open + Sevastopol no open at source time, 6/6 active and 10/10 weekday JS, midnight/DST). Artifact #14607928356; Netlify draft 6affecda8c37c62e303f8b86 READY but unpublished. Manual C6 #44680696823 SUCCESS, Git-only site-prod@8c8ee93; scheduled stabilization OPEN. No live active-status sidecar and zero production changes.


### C6-OWNER-MANUAL-CATCHUP-READY-2026-11-20-01 — manual path registered, not executed
- PR #205 merged `main@7abdaf02`; exact scheduled C2→Neon→Git-only pipeline now accepts default-OFF `c6_run_now` for owner on main with AUTO enabled, other one-shot inputs OFF. CI [#44680250526](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/44680250526) PASS and existing guards PASS. No dispatch, new `site-prod` commit, or Netlify deploy from this change. Physical manual cycle pending; separate scheduled stabilization still open.


### C6-WEEKDAY-READER-PIN-MERGED-2026-11-20-01 — exact approved reader fix, scheduled validation pending
- Scheduled Actions #44634410260 writer PASS (+53, 34,271), six-JSON reader BLOCKED on new PR201 heatmap Git blob. Owner-approved PR #203 merged main@cf8d5db4; exact old/new allowlist plus negative drift CI [#44679502629](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/44679502629) PASS, regression #44679502645 PASS, docs #44679502639 PASS. No site-prod or Netlify changes, next four-hour scheduled cycle must demonstrate 23/23 readback and Git-only publication; C6 stabilization remains open.


<!-- coordination:history:end -->
