# C3 production rollback operational preflight — 2026-11-12

**Scope:** documentation-only, read-only operational inspection. **Verdict: BLOCKED (operator Publish deploy control and compatible data-generation restore not yet demonstrated)**; read-only immutable production HTTP/SHA evidence PASS, but Netlify **Publish deploy** privilege and a production rollback have not been exercised. **GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF.** This report does not certify cutover.

## Pinned state and evidence

- Netlify site **`b5aafc46-7468-4070-baf1-db80a4d30501`** (`ukraine-air-alerts`). Read-only Netlify project query returns *current* published deploy **`6adb629bc3ebc570117d82e1`**, with deploy state `ready`, context `production`; published at `2026-10-23T13:35:27.742Z`. Immutable deploy URL: https://6adb629bc3ebc570117d82e1--ukraine-air-alerts.netlify.app/ . API reports `commit_ref=null`, `has_source_zip=false`. Do **not** infer an associated Git commit from this deploy ID.
- Isolated candidate **`6af5aecd8901ea2a40de09ad`**: `ready`, `branch-deploy`, alias https://c3-neon-83f14e27--ukraine-air-alerts.netlify.app/ ; **not published to production**.
- Git `site-prod` HEAD on inspection: **`fc7261660bdee75ee59296ee94cc1189be6b1a22`**. `main` HEAD: `375e69351e6a5aee1be16892821f7cdde2a8f21a`. Snapshot is time-dependent; re-read immediately before any change.
- [Draft PR #90](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/90) HEAD `83f14e27bf4675f64aff72fa20010630f0305d52`, base `site-prod` at the pinned SHA, no merge. Scoped frontend compatibility PASS per [#43205095573](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43205095573).
- C3 live preview [#43218752830](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43218752830) job SUCCESS, artifact [#13945375693](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43218752830/artifacts/13945375693) **present, not expired**, expires **2026-12-12**. Accepted evidence in [coordination PR #78](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/78): 184 city/mode views, 23 CSV exports, Git source UI rollback, no JS/HTTP errors. This is **not** a production rollback test. PR #78 remains unmerged; its newer proposed checkpoint governs this preflight's evidence interpretation, not the old `main` summary alone.
- Prepared 29-file preview bundle from [#43208800105](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43208800105), artifact #13940887007; 6 Neon JSON plus 6 same-run Git JSON. This is a *preview* recovery artifact, **not** the older production deploy archive.

## Critical two-plane rollback

**Netlify publish rollback restores only the deployed static asset snapshot. It does not revert the Git JSON that this production frontend fetches at runtime.** Verified source in `site-prod:kyiv-air-alerts-grafana/pages-preview/app.js`, line 11:

```js
const RAW_DATA_BASE = "https://raw.githubusercontent.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/site-prod/kyiv-air-alerts-grafana/data/";
```

The immutable Netlify deploy also contains `historical-daily-kpi.json` built when the original production deploy ran, while runtime dashboard/derived/aux JSON can continue changing on Git. A rollback to an older immutable build can therefore create **mixed-generation data**. Treat Netlify-only restore as emergency containment of broken frontend, NOT as certified full data rollback. An exact old production data snapshot must be pinned at the future cutover, or an explicitly approved last-known-good Git data commit must be chosen with timestamp and generation compatibility evidence.

**Git assets to inventory before cutover:** the deployed `app.js`, `index.html`, `styles.css`, `kpi-range.js`, `chart-share.js`, `features.json`, branding/favicon files and `netlify.toml`; runtime JSON `kyiv-air-alerts-grafana/data/dashboard_data.json`, `site_derived.json`, `alerts_combined.json`, `kyiv_threat_mix.json`, `sevastopol_events.json` (plus any casualty, CSV or auxiliary files changed by the proposed cutover). The sixth preview JSON, `historical-daily-kpi.json`, is a build artifact, *not* tracked as a regular Git data file. Record the built file SHA-256 and its `meta.source_ref`, `source_dashboard_generated_at`, `verified_count` and `expected_cities` at cutover. Record file SHA-256, Git blob IDs and generation metadata for both pre-cutover and candidate. Never assume that reverting all of `site-prod` is safe: live C2/casualty updates may have landed since the snapshot.

## Operator runbook (NOT executed)

### A. Immediately BEFORE the authorized cutover

1. Freeze the release decision: owner approves a controlled window separately; confirm no parallel publication or pending C2/frontend deploy that would overwrite a recovery; `GLOBAL_CUTOVER=NO` until separate decision; `DST_CORRECTION=OFF`.
2. In Netlify site **Deploys**, pin `site_id`, *currently published* deploy ID, immutable deploy permalink, publication time, `ready` status; capture screenshot/receipt; confirm **Publish deploy** is available to the authorized operator for the exact old production deploy, and that it remains available after the planned new deploy. Do not click it during preflight.
3. Pin exact `site-prod` Git HEAD and all runtime file hashes + blob SHA, original frontend source, index and embedded generations; snapshot the entire *proposed-to-change file set* as an immutable Git artifact or commit reference. Recheck HEAD before making a restore commit. Note the production Netlify deployment currently has `commit_ref=null`: Git `site-prod@fc726...` is the observed HEAD, **not an authenticated attribution of the 2026-10-23 Netlify artifact**.
4. Read-only confirm the old deploy's immutable URL serves `index.html`, `app.js`, `kpi-range.js`, `historical-daily-kpi.json`, `features.json` with HTTP 200 and expected content. Compare stable hashes of deploy-specific static assets. Compare current main-domain deploy with pinned deploy after any future publishing event; record URL, HTTP status, digest and timestamp. Avoid confusing the old immutable deploy with the C3 branch alias.
5. Before promoting a cutover, verify 23/23 city keys and historical KPI verified count (23) in the old/pinned data and planned candidate, chart/CSV/share/Kyiv reasons/casualty assets present, no console or request failures. Reuse existing acceptance evidence; do **not** rerun the complete generic browser QA or Neon physical readback for this runbook.

### B. Stop/rollback conditions

Initiate rollback on a verified wrong deploy, blank/broken chart, missing city, misleading zeros/corrupt historical data, KPI index/source mismatch, broken CSV/share/aux, material 4xx/5xx/JS errors, unexpectedly enabled current-alert indicator, or inability to demonstrate 23/23. Block cutover if old deploy is missing, operator cannot see **Publish deploy**, Git baseline isn't pinned, automatic re-publication risk is unresolved, or data generations are incompatible.

A **failed candidate deployment that never became published** requires STOP + inspection, **not** a rollback of the still-serving old deploy.

### C. Emergency restore after a bad *published* candidate

1. STOP the candidate pipeline and coordinate with Work A/C2. Prevent a queued workflow or auto-publish event from immediately overwriting recovery; if needed the authorized operator uses Netlify **Lock publishing to this deploy** after the old deploy is restored. Record the lock and explicitly plan to unlock it later; do not silently modify site settings.
2. In https://app.netlify.com/projects/ukraine-air-alerts/deploys open old successful production deploy **`6adb629bc3ebc570117d82e1`** (or the newly pinned actual pre-cutover production ID, if it changed). Confirm the displayed exact ID, production context and working preview permalink. Click **Publish deploy**, confirm the production-domain publication and re-read the project's *current published deploy ID*. This re-publishes retained immutable files without creating a new build; it is an operator action **NOT PERFORMED HERE**. Official UI instructions: https://docs.netlify.com/deploy/manage-deploys/manage-deploys-overview/#rollbacks .
3. If cutover changed **runtime data in Git**, restore ONLY cutover-owned data files using exact pinned Git SHA or approved pre-cutover snapshot, *without reverting newer unrelated C2/casualty checkpoints*. Prepare a normal reviewable Git PR; follow the existing protection/release process. Example commands below are **templates, not commands executed**. Beware that a `site-prod` push touching frontend/test/workflow paths can automatically trigger `.github/workflows/netlify-production.yml` and overwrite the Netlify rollback: coordinate the sequencing / lock publishing. Git JSON-only changes are not among that workflow's path triggers, but other workflows may still publish data.
4. If a previous Git tree no longer safely represents current data, do **not** blindly run `git reset --hard` or `git revert` across the entire branch; choose the last accepted compatible dataset and make an explicit partial restore PR. Keep the C2 producer and casualty tracks untouched.
5. If old Netlify deployment is unavailable or Publish deploy is disabled: **BLOCKED**, keep the production publish lock/stop in place and seek owner/operator assistance; a rebuild from source is a *new deployment*, not an atomic rollback, and needs its own authorization.

```bash
# TEMPLATE ONLY; run in a separate clean checkout AFTER authorization.
git fetch origin site-prod
git switch -c restore-c3-runtime-data origin/site-prod
git rev-parse HEAD                 # compare to pinned pre-cutover and current HEAD
# Populate EXACT_RESTORE_PATHS with ONLY cutover-owned runtime JSON files.
git restore --source=<PINNED_PRE_CUTOVER_GIT_SHA> --staged --worktree -- \
  kyiv-air-alerts-grafana/data/dashboard_data.json \
  kyiv-air-alerts-grafana/data/site_derived.json
git diff --cached --stat
git diff --cached --check
# REVIEW diffs and verify hashes/generation; then commit, push, and open reviewable PR.
# Do not run: git reset --hard <old sha>; do not force-push site-prod.
```

The two paths in this template are **illustrations**, not a declaration that a future cutover touches only two files. Expand to the manifest of files actually changed, or exclude files not changed.

### D. Verification after restore

- Netlify project `currentDeploy.id` equals exact pinned old deploy ID, `state=ready`, context production; main URL `https://ukraine-air-alerts.netlify.app/` serves old static assets and does not redirect to branch preview. Check with cache-busted requests.
- HTTP 200 for `/`, `/app.js`, `/kpi-range.js`, `/historical-daily-kpi.json`, `/features.json`. Compare static digests and index metadata to pinned baseline. Do not claim bytes of Netlify-hosted `index.html` match repository exactly when host injects scripts (seen in C3 preview).
- Verify the actual runtime Git data URLs and hashes for the approved rollback data generation (including `dashboard_data.json`, `site_derived.json`, `kyiv_threat_mix.json`); confirm **23 distinct cities, 23 verified historical KPI entries, source_ref expected, no data-generation mismatch**. Validate data content, not only 200 HTTP.
- Smoke check city selection across all 23; KPI time modes, CSV download, sharing, comparisons, Kyiv reasons, casualty data, derived charts and no critical browser/network errors; preserve screenshots/HTTP log and exact verification time. For full browser coverage reuse accepted QA as a reference, not as proof of this new production restoration.
- Monitor the next C2/Git publication and Netlify deploy event; make sure automatic deployment or writer updates did not reintroduce the broken source. Re-enable normal publishing only after owner sign-off.

## Execution ledger / evidence boundary

| Item | Status |
|---|---|
| Read main PROJECT_STATE.md and CHANGELOG.md | PASS |
| Read newer PR #78 coordination comments/diff | PASS; pending merge |
| Netlify site current published ID | PASS read-only |
| Old immutable production deploy `ready` and retained | PASS read-only |
| C3 branch deploy isolated and `ready` | PASS read-only |
| Git `site-prod` head and static build workflow | PASS read-only |
| Live C3 QA job and artifact availability | PASS metadata; not repeated |
| HTTP retrieval of immutable production deployment assets | **PASS** [read-only CI #43224744877](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43224744877), artifact #13946647755: seven old static assets HTTP 200 and SHA-256 pinned |
| Authorized operator can click Netlify **Publish deploy** | **UNVERIFIED**; action not exercised |
| Original Netlify deployed static SHA inventory | **PARTIAL PASS** for seven served static files; full original deployment source ZIP unavailable, `commit_ref=null` |
| Production rollback/re-publish | **NOT EXECUTED** |
| Production data rollback | **NOT EXECUTED** |
| Production 23-city post-rollback QA | **NOT EXECUTED** |

**Smallest unblock:** an authorized Netlify Developer/Owner must visually verify **Publish deploy** exists for the exact retained old deploy **without clicking**; pin a compatible Git JSON restore generation just before cutover and prove it matches the restored frontend/index (current generation differs from the old embedded KPI index). The independent read-only HTTP/SHA snapshot is already PASS. This is a preparatory gate, not permission to deploy or to rollback. After these are recorded, the existing Netlify UI supports controlled restoration; production rollback itself will remain untested until explicitly authorized and performed. No new rollback infrastructure is needed.

## Accepted narrow evidence — immutable HTTP/SHA baseline (2026-11-12)

- Isolated read-only [Actions #43224744877](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43224744877) **SUCCESS**, artifact [#13946647755](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43224744877/artifacts/13946647755), research proof SHA `21b59965b12168d473461ff6eb83aaeec4282107`. This proof reads only immutable public Netlify URLs and pinned Git JSON URLs; it neither touches Netlify publishing nor Git writes. Production `site-prod` SHA pinned before and rechecked after: `fc7261660bdee75ee59296ee94cc1189be6b1a22`.
- Captured HTTP 200, SHA-256, byte lengths and headers for **seven** old immutable Netlify files: `index.html`, `app.js`, `kpi-range.js`, `chart-share.js`, `styles.css`, `features.json`, `historical-daily-kpi.json`; and **five** pinned Git runtime files: `dashboard_data.json`, `site_derived.json`, `alerts_combined.json`, `kyiv_threat_mix.json`, `sevastopol_events.json`. Main production URL returns the same bytes as the old immutable Netlify URL for `app.js`, `historical-daily-kpi.json`, and `features.json`. The report contains all full digests; old Netlify build `commit_ref` remains unknown.
- Old Netlify `historical-daily-kpi.json` meta: `source_ref=site-prod`, `verified_count=23`, `expected_cities=23`, `source_dashboard_generated_at=2026-10-23T07:47:16.946235+03:00`. Pinned **current** Git dashboard: **23 cities**, `meta.generated_at=2026-11-12T09:08:13.340390+02:00`. Their generations **do not match**. A Netlify-only Publish deploy reversion is therefore not evidence of full historical-KPI or data rollback. Use a compatible Git JSON generation or separately proved fail-closed fallback; keep casualty and newer C2 data protected.
- **Gate remains BLOCKED:** owner/operator Publish deploy permission unverified, compatible two-plane restore baseline not yet approved, production rollback not performed. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
