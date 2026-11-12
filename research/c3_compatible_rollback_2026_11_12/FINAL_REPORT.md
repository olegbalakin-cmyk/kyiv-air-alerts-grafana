# C3 compatible two-plane rollback — read-only research handoff (2026-11-12)

**Operational verdict: BLOCKED. GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF.**

This independent Work B proof reuses PR #92 (original immutable HTTP/SHA Actions #43224744877, artifact #13946647755), Netlify read-only deployment metadata, frozen C3 preview Actions #43208800105, and current production Git `site-prod@68629fdae5534ec3a136e666bcb7d5c84dcd05aa`. No production Git, casualty, Neon, deployment, or coordination changes.

## Pinned baseline, two independent channels

Netlify site `b5aafc46-7468-4070-baf1-db80a4d30501`: old production deploy `6adb629bc3ebc570117d82e1`, ready/current, published 2026-10-23, `commit_ref=null`; separate nonproduction Neon preview `6af5aecd8901ea2a40de09ad`, ready/branch-deploy. Netlify restore replaces only the immutable static files, **not** the Git-hosted runtime JSON.

**Old Netlify static SHA-256** (immutable HTTP proof):

| File | SHA-256 |
|---|---|
| `index.html` | `a3eeb42acd74559be0ac10bcfeb49e23fd46cdfaff2374aa34220898459c2f03` |
| `app.js` | `b39f1190ce50e403f24f81414fd0f9defe1269122e5aa4683afeca14e20e0d04` |
| `kpi-range.js` | `08835ec81cb5c6147b06a66ff085dae07d1af4c76cc07f4c8fe671f8905709c6` |
| `chart-share.js` | `bb60f92dc07e4e06358ba4fc5c055e8fddede18dfa458e57da6906e8fad25672` |
| `styles.css` | `24125beb75bc655df8e122726d695310c86e9713be6861c6faf1e6320767b554` |
| `features.json` | `861b488bbf3668914e4d82235b30bf15ea841f4a54b545bbe378c0f77886898b` |
| `historical-daily-kpi.json` | `eda9b43eb4b4207fb7e6e0619bfe082f0f47599f8b8edc9c5742ff71d4239d0f` |

Old static KPI: `schema=verified-historical-daily-start-counts-v1`, `source_ref=site-prod`, `verified_count=23`, `expected_cities=23`, `source_dashboard_generated_at=2026-10-23T07:47:16.946235+03:00`.

**Five Git runtime JSON** (immutable `fc726166…` proof, current `site-prod@68629fdae5534ec3a136e666bcb7d5c84dcd05aa` checked directly by this Actions job):

| File under `kyiv-air-alerts-grafana/data/` | SHA-256 |
|---|---|
| `dashboard_data.json` | `ea01943609fb4e8adc64450181cc1a94d7438507db7898fc78f99ab177d188fe` |
| `site_derived.json` | `72e3c8c1dfece827f3549113fc1d18b65303f7a9ddd1c98b744dcb424995caaf` |
| `alerts_combined.json` | `8a8fa73e8440a12833b0f3a2a37fc2e3eeffd12a669951df43127904eb121846` |
| `kyiv_threat_mix.json` | `5b1f65dd90b5a2bcf09cf892ff091c4de532d6b202bb9838bb86c5ae2a79a95e` |
| `sevastopol_events.json` | `9978c4cbaab313bf731f6e420c769219c585747117e4ecf4ef1652dc9439176d` |

Pinned Git dashboard `meta.generated_at=2026-11-12T09:08:13.340390+02:00`. Git `site-prod@68629fdae5534ec3a136e666bcb7d5c84dcd05aa` includes unrelated C2 and casualty code-only commits since the older immutable HTTP proof. Do not attribute the October Netlify static to any Git commit; the deploy has `commit_ref=null`.

## Safety-critical finding

The current production `app.js` checks generation parity for `dashboard_data.json.historical_daily_kpi`, but its **static KPI fallback** checks source, schema, 23 expected cities and positive verified count **without checking generation parity**. Therefore restoring October static while Git remains a newer or Neon generation can accept stale historical KPI if the fresh embedded index is not usable. Netlify-only rollback is **NOT a proven compatible data rollback**.

## Reproducible offline tests

`check_recovery.py` runs six cases: (1) old frontend with currently pinned Git data and 23 cities; (2) mismatched KPI generation, rejection required by recovery policy; (3) synthetic newer C2 changes; (4) synthetic independently updated casualty, Kyiv intervals and auxiliary changes; (5) old Netlify static against fixed Neon Git candidate; (6) auto-republish workflow triggers. It evaluates the **real production validIndex() JavaScript**, compares exact runtime SHA-256/Git blob IDs, and uses the prior 184/184 preview QA report as **previous candidate evidence**, not new production rollback QA. Synthetic records never leave the isolated test process.

GitHub workflow is branch-scoped, `contents:read`, `actions:read`; downloads immutable existing GitHub Actions artifacts only. It does not dispatch regular C2, access Neon, change source, publish Git JSON, merge PRs, or deploy Netlify. A successful CI result means *unsafe cases detected and blocked*, not operational READY.

## Operational rollback runbook (NOT EXECUTED)

1. Before future authorized cutover, capture fresh main/deploy ID, complete Netlify seven-file SHA-256 manifest, current five-file Git blob/SHA-256 manifest, `source_ref`, `generated_at` and 23 city keys. Freeze conflicting releases. Do not use old static and new Git as an assumed pair.
2. Confirm authorized operator can re-publish an **inactive former production deploy** without actually clicking in preflight; current deploy has no `Publish deploy` by design. This access is currently unverified and cannot be proven from today's UI state.
3. Separately authorize and verify a Netlify publishing lock or equally effective deploy quiescence before changing production. The existing `site-prod` frontend workflow can execute `netlify deploy --prod` after qualifying commits and overwrite a recovered static version.
4. If a published candidate is defective, hold C3 release jobs, reconcile current runtime JSON against a pinned compatible Git generation **without reverting post-baseline C2/casualty/auxiliary updates**, then re-publish the retained old static via the authorized operator. If no compatible data can be restored without loss, STOP/BLOCK rather than reset `site-prod`.
5. Confirm production current deploy ID, seven static hashes, five live Git hashes, historical KPI generation, 23/23 cities and smoke QA including eight periods, CSV/share, Kyiv causes and casualties. Monitor next C2 and deploy event; unlock only after owner approval.

**Unresolved:** republish authorization on non-current old Netlify deployment; complete compatible 2-plane last-good checkpoint at actual cutover time; fail-closed static KPI fallback in any accepted production frontend; no-loss reconciliation for real later C2/casualty updates; enforced auto-publish pause/lock and operational restore test. The historic C3 preview (#43218752830) is not a production rollback.

No changes to Work C, PR #90, PR #95, PR #78, main or site-prod.
