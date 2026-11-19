# Changelog — recent accepted transitions

Newest first; current coordination lives in [PROJECT_STATE.md](PROJECT_STATE.md). Full historical text, SHA/Actions/artifact references and exact previous roots are preserved in the [archive index](docs/coordination-archive/README.md), verified by its manifest. Maintain 5–10 brief transitions; use the [archival CLI](docs/coordination-maintenance.md) before growth exceeds 12 KiB.

<!-- coordination:history:start -->
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
