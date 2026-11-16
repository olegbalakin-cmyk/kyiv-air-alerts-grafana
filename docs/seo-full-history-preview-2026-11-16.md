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

## Monthly automation, experimental / NOT ACTIVATED

**Owner request on 2026-11-16:** prepare monthly autonomous archive refresh on **test only**. Current code does not enable scheduled publishing, production deployment or persistent changes to the live four-hour data pipeline. The new readiness workflow is `.github/workflows/seo-monthly-readonly-preview.yml`.

**Planned calendar:** the third day of every month at **08:23 UTC** (GitHub cron). This is intended as a checkpoint after month-end, not a guarantee that every city is up to date by then. GitHub scheduled workflows run **only from the repository default branch (`main`)**. The workflow exists on the isolated `seo-full-history-preview-2026-11-16` branch and therefore **its monthly schedule is dormant** until a separately authorized main integration. The feature branch permits test push/manual-run checks. No claim is made that a production monthly automation is already active.

### Input and verification

The source selection script reads both **live `site-prod` Git files**, without writing them:

- `historical-daily-kpi.json`, the existing static 23-city index. This file is **not** in the automatic four-hour C6 Git-only publisher's `DELIVERED` allowlist, so it can stay older than the current dashboard data.
- `kyiv-air-alerts-grafana/data/dashboard_data.json`, possibly containing a more recent `historical_daily_kpi` index. If a newer embedded index exists, its generation timestamp MUST agree with the enclosing dashboard's generation; the selector rejects unbound/conflicting inputs. Its normalized extracted Git blob is **derived**, not falsely presented as an independently committed `historical-daily-kpi.json` file. The receipt records both original source Git blobs.

Read the **actual published** archive manifest, not the unapproved test preview receipt. Before a first owner-approved production archive release, this baseline is absent and the gate returns `NO_VERIFIED_PUBLISHED_BASELINE`.

The gate uses local **Europe/Kyiv** dates. It requires a fresh snapshot in the month of the check, and the **previous full calendar month verified for all 23 cities**. The underlying existing archive validator checks all asserted months, daily-array coverage, day counts, geography/scope and exact parity of daily and verified monthly totals.

Outcomes:

| Decision | Meaning | Allowed action |
| --- | --- | --- |
| `BLOCKED` | Missing verified month, stale source, unverified or partial city coverage, no published baseline, historical revision without new months, data regression, or failed provenance | **Nothing published**; read-only receipt |
| `NO_CHANGE` | The previously published archive already covers all verified months with identical source blob | No deployment |
| `READY_FOR_DRAFT` | All 23 city series advanced and complete source checks passed | **Draft preview only**, never `--prod` |

Every outcome explicitly sets `production_deploy_allowed=false`, `git_publish_allowed=false` and `neon_access_allowed=false`. GitHub workflow permissions are `contents: read`. An optional Netlify draft deploy happens **only** after `READY_FOR_DRAFT`; no token is used on blocked/no-change runs. The existing Netlify production lock remains unchanged. The four-hour C2/Neon/Git updates are independent and untouched.

### Open operational gates

1. Confirm that automatic C6 current `dashboard_data.json` really generates a fresh, same-generation `historical_daily_kpi` for every completed month. If it does not, **an upstream verified-index refresh is required**; the monthly SEO checker must not synthesize the missing month or misrepresent the static file as fresh.
2. After a first explicitly authorized archive production release, confirm that `/static-archive-manifest.json` is served and its source blob matches the shipped data. Until then, the monthly job remains blocked by design.
3. To activate true scheduled shadow checks, owner approval is required for a minimal **main** integration. To permit recurring production publication, a **separate explicit production GO** and guarded unlock/deploy/relock workflow must be reviewed; that behavior does not exist in this test.
4. Once a new month genuinely passes, validate the generated draft against current `site-prod`, not a stale UI commit; owner decides on production release. A future production automation must enforce a separate release-authorization contract.

This is intentionally conservative, particularly because the site already has a known unrelated production HTML post-smoke failure and ongoing C6 scheduled stabilization.

### Physical monthly-shadow test (2026-11-16)

- Test code exact HEAD: `96e73810a71b0e6a7453accb35be70f38a4c2433`. Physical [Actions #43872244555](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43872244555) **SUCCESS**. Adding this documentation afterwards does not create a new code proof.
- **17/17 monthly source/gate tests PASS**; full static archive 4/4 unit tests PASS; 936 URLs built; 36/36 UA/EN desktop/mobile browser checks PASS; 17/17 remote draft HTTP probes PASS.
- Actual real Git-only site-prod source selection picked **embedded** `dashboard_data.json:historical_daily_kpi`, generated at `2026-11-16T09:03:30.995243+02:00`, derived normalized Git blob `a64a93e38fe8d7b3ceb6f27b009161efd1ca5b02`. The standalone `historical-daily-kpi.json` is older (last `2026-11-13T10:08:11.334497+02:00`); prefer the verified, correctly bound embedded index and retain original physical-file provenance in the source selector receipt.
- Physical monthly preflight result: **`BLOCKED / NO_VERIFIED_PUBLISHED_BASELINE`**, expected month `2026-10`. This is correct: the full archive has **not** been owner-approved or shipped on the production Netlify URL, so there is no legitimate *published* baseline manifest. No monthly draft release is warranted by this gate. Production deployment flags remain false.
- A separate repeat UI-test draft deploy was produced by the full-history preview workflow: [Netlify preview `6afaffa17a7ff3726b01be9e`](https://6afaffa17a7ff3726b01be9e--ukraine-air-alerts.netlify.app/), **READY**, no `--prod`. Latest production remains Netlify `6afae2d20fa2229b8c0c2bc0` READY and locked. Proof artifact [#14228462576](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43872244555/artifacts/14228462576) includes source-selection and monthly-gate receipts; [#14228163149](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43872244555/artifacts/14228163149) contains the draft URL.
- New isolated `seo-monthly-readonly-preview.yml` defines a test `push`/manual gate and a **dormant** `cron: 23 8 3 * *` schedule. GitHub executes scheduled workflows only from default branch `main`; no monthly recurring schedule is active while the workflow remains on this test branch. This job has `contents: read`; when ready it can build an isolated Netlify draft preview **only**, never production.
- The physical test demonstrates the gate works against actual C6 live Git files. It does **not** demonstrate that a later month will be fully verified by the third day or that monthly production deployments run automatically. A separately authorized main integration, an accepted initial archive production release, and a production promotion policy are still required.
