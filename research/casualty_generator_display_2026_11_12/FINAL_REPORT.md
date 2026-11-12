# WORK D — Real generator → incomplete-month display

**Scoped decision: `GENERATOR_DISPLAY_PASS` (isolated shadow only).** This is not approval to merge, publish or declare coverage complete.

## Physical result and exact evidence

- Draft [PR #109](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/109), branch `research-casualty-generator-display-2026-11-12` against pinned `site-prod@d0a7d22de2828c93236562cccc9d2e68c6a66e3d`.
- Final functional proof [Actions #43307927716](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43307927716), exact code HEAD `19bd73ff116116bd3f37469f4dcb21da725ded98`: **SUCCESS**, real-generator bridge PASS, bridge contract PASS, **42/42 Chromium PASS (0 FAIL)**.
- [Artifact #13985480143](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43307927716/artifacts/13985480143): ZIP SHA-256 `d5ba02d323c4a93c2bcb9433fd4ddbbe419043dd0afaf09f5b17610205090975`, independently downloaded and rehashed: **MATCH**. Full proof includes the original generator probe, shadow proposal, qualified dashboard, bridge receipt, desktop/mobile screenshots, desktop/mobile CSV, desktop/mobile PNG share output, embed screenshot and rollback screenshot.
- Actual generated ephemeral dashboard SHA-256: `8b12fd8909348b3d651bc69cbc1612fef159ec6176f08415ee82e894a3870b8f`; browser-proof concatenated sorted file contents SHA-256: `6c3d8eb0dca82bf969fdd7cdf94975a8aa2fca764823806ab223c9bc5ba720db`. Do not mistake this for the ZIP digest.
- Source: PR #105 `6a0100b0937218c62c5c079fd46e80e5071783cb`; PR #99 preview `384fb8b8e087701f42510f68f19817d9732f883e`; PR #106 reviewer-independent compatibility findings `5441bdaf60b96e8efbb5019182ac7cf6a3c76da1`. PR #71 coordination read-only.

## What really flows through

1. The pinned Work A `pipeline.py` processes 1,682 candidates from frozen WIP against previously retained original source evidence, the approved transport receipts, original revisions and source city CSV. **One** source-backed Zaporizhzhia 10 October candidate is AUTO_READY; 1,681 remain NEEDS_REVIEW. These are not inferred deaths.
2. Work A invokes the actual copied `site-prod/update_casualties.py` `reconcile_confirmed_revisions()` and `apply_city_revision_overlay()`. The actual `generator_probe.json` proves the deduplicated, cumulative **23**, increment **+23**, October original baseline **0** and original 22 other city objects hash-identical. Nothing is injected as an artificial prebuilt chart fixture.
3. `bridge.py` checks source candidate ID and retained text hash, single safe cumulative proposal, original production generator and ledger SHA-256, original 23 alert city records, original 22 non-Zaporizhzhia casualty cities, unchanged existing Zaporizhzhia month values and timestamps, and exclusive scope of the generator patch. It changes just the **temporary, generated** October row from raw numeric 23 into the explicit classification:
   ```json
   {"month":"2026-10","deaths":null,"coverage_status":"INCOMPLETE","confirmed_minimum":23,"complete_total":null}
   ```
   The original raw numeric generator result remains in the proof.
4. The local isolated frontend reads this actual generated dashboard file; `coverage-preview.js` reuses the PR #99 existing Chart.js overlay, which wraps the existing casualty charts and CSV export only. The only display adjustment is a small y-scale headroom and label positioning to keep `≥23` above hatching on 375px screens. **No separate chart, production frontend replacement, new review system, artificial `fixture.json`, or `local-fixture-loader.js`.**
5. The separate local rollback frontend reads the original pinned `site-prod` dashboard, without the overlay, and reproduces the legacy graph.

## Browser / export acceptance, physically checked

- Existing monthly chart: diagonal hatching, visible **`≥23`** label above the October column, source legend, chart-card note **«жовтень 2026 — щонайменше 23 загиблих. Дані неповні.»** without tooltip occlusion.
- Real Chart.js tooltip callback: **«щонайменше 23 ... дані неповні»** plus **«Це нижня межа, а не остаточний підсумок»**.
- Desktop and 375px responsive mobile: correct chart geometry; in both screenshots the onboarding overlay is suppressed at browser startup (test session only), chart cards are unobstructed, `≥23` is above the hatch. The exported mobile share PNG keeps the annotation and uncertainty legend.
- CSV files encode `INCOMPLETE`, `confirmed_lower_bound_not_final`, and `confirmed_minimum=23`; no export labels it exact.
- Actual ChartShare PNG and embed retain lower-bound annotation, monthly note on embedded card; annual 2026 classifier is **INCOMPLETE**, not final even when an arithmetic minimum is shown. `UNKNOWN` and absent data cannot become an asserted confirmed zero; old legacy values remain ungraded rather than auto-COMPLETE.
- Comparison does not leak status into other cities; 23 alert city records preserved; original raw counts unchanged for 22 other casualty cities; year/interval keyboard focus, city switch Zaporizhzhia→Kyiv→Zaporizhzhia and rollback all PASS. No JavaScript page errors in checked paths.

Tests are 42 browser assertions plus Work A's existing 10 safety tests (7 run, 3 intentionally skipped in the pinned runner) and generator/bridge integration checks. They are not evidence that the wider WIP reviewer or casualty monitoring covers all source articles.

## Rollback and publication boundary

Rollback is **remove the isolated overlay and qualified temporary dashboard**, serving the immutable `site-prod` frontend/data unchanged, as browser-tested. No true production rollback was invoked or needed.

The branch changes only `research/casualty_generator_display_2026_11_12/**` and one isolated `.github/workflows/research-casualty-generator-display.yml`. `main`, `site-prod`, reviewer, PR #71 documents, production casualty JSON, regular C2, WIP queue, Neon, Netlify and production Git publication are untouched. Every actual Work A output retains `publication_allowed:false`. No new publisher HTTP.

**Acceptance: `GENERATOR_DISPLAY_PASS` for generator→classified temporary dashboard→original chart/exports.** Wider unattended casualty accuracy and full October coverage remain **NOT PROVEN**. **No merge, deployment or live casualty JSON update.**
