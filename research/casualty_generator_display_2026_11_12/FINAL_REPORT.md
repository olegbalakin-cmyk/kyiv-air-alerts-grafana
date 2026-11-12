# WORK D — Real generator → incomplete-month display

**Decision: PENDING EXACT-HEAD CI.** Do not treat staged changes as GENERATOR_DISPLAY_PASS.

## Pinned sources

- Original site-prod generator/frontend: `d0a7d22de2828c93236562cccc9d2e68c6a66e3d`.
- PR #105 source-backed WIP→generator pipeline: `6a0100b0937218c62c5c079fd46e80e5071783cb`.
- PR #99 existing Chart.js overlay: `384fb8b8e087701f42510f68f19817d9732f883e`; `coverage-preview.js` reused byte-identically.
- PR #106 independent audit: `5441bdaf60b96e8efbb5019182ac7cf6a3c76da1`.

## Actual integration

The pinned Work A program processes frozen WIP, retained source excerpts, immutable approved receipts, private copies of the real revisions ledger and *actual* production generator functions. Its `generator_probe.json` is an actual result of `reconcile_confirmed_revisions()` and `apply_city_revision_overlay()`; no prewritten `fixture.json` is used.

`bridge.py` rejects wrong source/ledger hash, unverified cumulative dedup fields, altered month, wrong +23 generator result, non-exclusive patch, mismatched 22 other casualty cities or altered 23 alert cities. It converts only the original generator-derived numeric October Zaporizhzhia row to `deaths:null, coverage_status:"INCOMPLETE",confirmed_minimum:23,complete_total:null`; the numeric proof remains in the generator JSON. Legacy months are not declared COMPLETE and unknown values are never rewritten as zero.

The isolated localhost frontend uses the generated dashboard and PR #99 overlay. A second, clean frontend uses original site-prod data and no overlay as the rollback comparison. Real browser QA covers chart/bar/label/note/tooltip/CSV/PNG/embed/annual state/375px/mobile/city switching/keyboard and rollback.

## Acceptance and scope

An exact-head GitHub Actions SUCCESS with archived real generator probe, qualified dashboard, CSV, PNG, desktop/mobile/embed/rollback screenshot and check logs is required for `GENERATOR_DISPLAY_PASS`. Until then the result remains `PARTIAL`.

This branch changes no production casualty JSON, reviewer, WIP, coordination files, main, site-prod, C2, Neon or Netlify; no merge or deployment authorized.
