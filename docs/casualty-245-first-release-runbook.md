# CASUALTY Issue #245: integrated Git-only partial UI (NO PUBLISH)

Status: DRAFT; PROMOTE=OFF; publication_allowed=false. No site-prod/main merges, Netlify production deployment, data credits, new publisher GET or C6 writes.

## Pinned starting evidence

- Main: b35ca5c8d189a011c1b7158275f189a195192890.
- Site-prod: f7e0681ca6aa98405638dae7a63c884f4ed55d20 (re-pin before any future GO).
- UI PR #237 HEAD c654a1efcf3dc5d8393d427ec35b5f4ced8211b2; Actions #45151092355 SUCCESS, artifact #14805749223 (isolated browser 28/28).
- Corrected sidecar PR #244 HEAD 1cf1fb29e8883a62ef1b25976b9e7a5b367e19cf; Actions #45151954338 SUCCESS (supersedes erroneous Sep cutoff assertions in older #244).
- September audit PR #243 HEAD f8112362beaf6a9a8015c83c86dd8b131df5236c, Actions #45147864411 SUCCESS.
- Historic Netlify production deploy 6b02d5edba0ff97b80b83052 READY, locked per accepted checkpoint. Independently verified 23-city same-release #45018970389. Recheck live lock at release.

## Integration and source policy

Preserves UI from PR #237, replacing its October-only fixture with exactly the corrected schema and JSON from #244. No writer/collector workflow is introduced. Production source must be the canonical URL:
https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/casualty_partial_months.json

Production source mode reads site-prod HEAD, immutable dashboard_data.json at that SHA, canonical sidecar plus immutable sidecar at the same SHA, compares sidecar SHA-256, and re-reads HEAD. Missing, corrupt, old, mismatched or concurrently advanced source makes casualty charts and comparisons unavailable; never displays unverified values or silently falls back to a frozen casualty fixture. Other air-alert graphs may load.

Only the separate test deployment (Netlify site id 42159ba4-a142-4c7b-ad42-9b6ba4de4dcb) changes the bundled features.json into explicit frozen_test mode. It copies the exact frozen site-prod dashboard and corrected sidecar into an isolated bundle, computes SHA-256 file manifest and test binding, and checks both hashes at browser boot. Tracked features.json retains canonical_site_prod. The static preview MUST NOT be called canonical live data.

September 2026 is incomplete for 23/23 cities. Existing baseline 55 plus already-credited Sumy Sep20 +1 = 56 partial minimum, not a full-month total. Exactly four proven cutoff dates: Kyiv 09-15, Kherson 09-17, Odesa and Zaporizhzhia 09-18. Other 19 cutoff dates unknown, including Sumy. Unreviewed Kyiv 17 remain excluded.

October four reviewed incident minimums 6+1+1+3 = 11 (Lutsk, Poltava, Ivano-Frankivsk, Khmelnytskyi); other 19 city-months unknown, not zero. Both partial months excluded from 2026 January-August nonfinal annual comparisons. Prior historical months unchanged. No new revisions or source claims.

## Release gate / physical proof

Actions workflow casualty-245-integrated-qa.yml tests the corrected publisher, 23-city semantics, negative source cases (schema, tamper, missing, unknown cutoff, invalid counts, in-flight SHA changes), physical browser four form factors (UA/EN x desktop/mobile) with 23-city selection, yearly/monthly comparison, reloading, screenshots and an HTTP404 fail-closed test. Saved artifacts: bundle SHA-256 manifest, JSON browser results, PNGs, CI logs and isolated preview URL. Do not claim a PASS before actual Actions run and artifact verification.

## Future one-shot production runbook (NO GO YET)

1. Re-pin latest main, site-prod SHA, C6 six-JSON manifest, readback, 23-city parity and locked Netlify production deployment. Detect concurrent C6 updates, stop rather than using stale base.
2. Require physical integrated browser PASS, immutable Draft PR HEAD, artifact ID and bundle hashes. Verify frozen baseline parity and no new identity or credited proofs asserted. publication_allowed=false is a policy gate, not a source-accuracy signal.
3. Request explicit separate owner GO identifying exact protected base and proposed head, scope of one Git-only casualty sidecar commit and single locked one-time UI Netlify deploy, hashes, rollback.
4. Once approved, Git-only sidecar update readback; one-time UI deploy and re-lock Netlify; 23-city UA/EN browser and CSV parity. Keep Netlify auto publishing OFF; no routine Netlify deployment per casualty update.
5. Roll back only the approved data/UI changes while preserving newer C6 commits; revert scoped commits or restore pinned prior Netlify deploy. Do NOT reset site-prod or overwrite C6.

GO REQUEST STATUS: NOT YET ELIGIBLE until physical integrated PASS. PROMOTE=OFF; zero production writes.
