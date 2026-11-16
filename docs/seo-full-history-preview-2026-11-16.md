# Full-history machine-readable statistics archive — preview proof

**Status:** `TEST_PREVIEW_READY`; production OFF; Draft PR #193 against `site-prod`. No owner GO for production publication has been issued.

**Exact tested HEAD:** `7e41b732ea720c48badf8a64e0c029311a1cc0f2` (2026-11-16). Subsequent documentation commits are not included in the exact-head physical code proof.

**Physical Actions:** [#43857943300](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43857943300) **SUCCESS**. The earlier runs #43857731870 and #43857818187 failed on test-only boundary/HTML integration issues that have been corrected; they are not release proofs.

**Immutable source:** `site-prod:historical-daily-kpi.json` Git blob `5a88388445f0bb6c6ed58cb3972ca1b6bc577bc0`, source generated `2026-11-13T10:08:11.334497+02:00`. This is a frozen historical snapshot; the archive does not claim to contain new alerts observed since this source snapshot.

## Produced output

- **23/23** verified city/district series; 392 verified complete calendar months, through October 2026.
- **784** city-month pages (392 × Ukrainian/English), each with daily numeric rows and a month summary.
- **102** city-year pages; years with fewer than 12 verified months explicitly say `Частковий рік` / `Partial year`, so partial years are not misrepresented as full annual totals.
- **46** city overview pages; **2** archive index pages; **2** existing bilingual dashboard roots.
- **936 canonical URLs** recorded in `sitemap.xml`. `robots.txt` generated with a sitemap reference. Geography states city vs raion and describes district proxy limitations.
- All new pages use static text/table HTML, no JavaScript needed to read their values, unique canonical+hreflang, source attribution and snapshot date, optional per-dataset JSON-LD. Principal dashboard links remain in the footer and survive existing app.js language initialization.
- Historical archive generation occurs during an explicitly initiated Netlify frontend build; this **does not** add Netlify deployments to the four-hour Git JSON refresh cycle. To publish a new month or historical correction, rebuild the archive after input parity verification and owner approval.

The generator fails closed on unknown/missing cities, unverified or incomplete months, irregular daily array lengths, impossible numerical values, geographic scope inconsistencies and differences between daily sums and the original verified monthly data.

## Physical verification

- **4/4 Python unit tests PASS**, including full 23-city/392-month parity, every archive URL and both hreflang entries, partial/full-year labels and an intentional corrupted-month negative test.
- **936/936** sitemap entries resolve to generated files in the full build (dashboard roots are separately built by the pre-existing bilingual builder).
- **36/36 Playwright checks PASS** on desktop 1440×900/mobile 390×844; Ukrainian/English; dashboard with JavaScript ON and OFF; footer survival, direct navigation to 23-row index, years and representative month pages.
- **17/17 remote draft HTTP checks PASS**, including both dashboards, both archive indexes, sitemap, robots.txt and representative city/month/year URLs.
- GitHub [offline proof artifact #14221049306](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43857943300/artifacts/14221049306): screenshot set, JSON browser checks, source manifest, and sitemap.
- GitHub [deploy proof artifact #14222485973](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43857943300/artifacts/14222485973): draft URL and deployment receipt.

## Exact Netlify preview

- Draft deploy ID: `6afae8f84e35bde27c4f60e4`, Netlify context `deploy-preview`, state **READY**, no production publication.
- [Dashboard](https://6afae8f84e35bde27c4f60e4--ukraine-air-alerts.netlify.app/)
- [Ukrainian archive](https://6afae8f84e35bde27c4f60e4--ukraine-air-alerts.netlify.app/stats/)
- [English archive](https://6afae8f84e35bde27c4f60e4--ukraine-air-alerts.netlify.app/en/stats/)
- [Generated sitemap](https://6afae8f84e35bde27c4f60e4--ukraine-air-alerts.netlify.app/sitemap.xml)

**Production remains** Netlify `6afae2d20fa2229b8c0c2bc0` READY, `locked=true`, published 2026-11-16 11:02:43 UTC under accepted separate trend-hatch checkpoint. The production Actions HTML post-smoke issue remains OPEN and was not addressed by this SEO preview.

## Next gate

Owner review of the full archive UX, text, and naming; then an explicit release decision. Before production publication, reconfirm current site-prod HEAD, historical Git blob, Netlify lock, preview parity and the production HTML QA harness. Update `PROJECT_STATE.md` and `CHANGELOG.md` only after an accepted checkpoint alters coordination state; neither is changed by this draft proof.
