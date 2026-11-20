# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

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


### UI-WEEKDAY-LIVE-LOCKED-2026-11-19-01 — weekday UI production READY + locked
- Owner GO, PR #201 site-prod@`ae650feadef8e8d028ffadc2c5dc5a8e3f0f041b`; proof-tested preview #44591705771, release QA #44602597715 PASS. Production one-shot [#44602714671](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/44602714671) SUCCESS; artifact #14567973014; Netlify `6aff5392a3a6d0497a6f5d1d` READY + locked, served JS and 23-city KPI PASS. Weekday counts/time filters, 4-part and day(09–18)/evening-night switch, bilingual tutorial LIVE. Same-run 4h derived-data generator updated; first scheduled refresh not yet proven; no C2/Neon modifications. Legacy prod workflow #44602714524 failed predeploy (tour steps test).


### SEO-ARCHIVE-23C-LIVE-LOCKED-2026-11-16-01 — 23-city historical archive production LIVE, monthly OFF
- Owner approved first production SEO archive only. PR #194 → site-prod@`6d0879c`, release CI #43874588605 PASS. Netlify `6afb034ee4ead33599681226` READY and locked; production Actions #43874825782 deploy/KPI/relock PASS, **overall FAILURE** at prior strict bilingual HTML post-smoke. Independent read-only [Actions #43875088810](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43875088810) SUCCESS: 50 HTML pages/61 HTTP checks, 936 sitemap URLs, 23/23 exact deployed KPI blob parity; artifact #14229611799. No C2/Neon/four-hour updates affected. Monthly schedule in Draft #193 remains OFF, separate owner GO required.

### UI-TREND-HATCH-LIVE-LOCKED-2026-11-16-01 — trend live, Netlify locked, HTML QA still red
- Approved PR #191 site-prod@7c1adc43; 4-file UI release on latest C2; CI #43854043494 PASS. Actions #43854098357 deployed 6afae2d20fa2229b8c0c2bc0 READY+locked (independent Netlify proof); JS/KPI HTTP/relock PASS, overall FAILURE due to last bilingual HTML smoke. #187 test-only; no Neon/C2/JSON/schedule changes. Investigate smoke harness without redeployment.

### C6-DST-CANONICAL-DISPLAY-VERIFIED-2026-11-15-01 — same-run 23-city Git projection already excludes stale DST parents

- Live physical readback proof [#43706909819](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43706909819), artifact #14159523883: 33,911 raw closed AIR rows, 33,646 exact C2 canonical lineages/23 cities, eight correct Oct 25 DST witnesses in the four city calculations, three wrong merged physical parent UIDs absent from lineage. Published at site-prod@048af474, six data blobs unchanged through site-prod@901dab2f; frontend reads Git JSON. No second correction required: leave `DST_CORRECTION=OFF`, preserve three physical legacy records; PR #182 selector would block if enabled on already clean current canonical input. Scheduled stabilization still OPEN; no data, workflow, Neon, C2, source HTTP or Netlify changes.

### UI-BILINGUAL-LIVE-LOCKED-2026-11-15-01 — published EN and Ukrainian, Netlify locked; post-smoke CI remains red

- Owner-approved bilingual PR #164–166 code already merged. PR #178/#179 use **current same-generation Git-stored Neon historical 23/23 KPI**, not independent stale source re-derivation. PR #180/#181 refine HTTP RUM and guarded one-shot Netlify unlock→deploy→relock. `site-prod@901dab2f`, production deploy **6af9a134186a8e5d83bb3cdf** live, `locked=true` via read-only Netlify, independent Actions #43712522543 served `/` + `/en/` with correct locale metadata and RUM-only difference PASS. Production Actions #43712415014 had 23-city KPI HTTP PASS, but overall **FAIL** on overly strict post-deploy HTML check. Next: reconcile QA harness, not live availability; no C2/Neon writes.

<!-- coordination:history:end -->
