# WORK G2 — minimal Git-only rollback offline proof (NO DEPLOY)

**No merge, production deploy, C2 writer, Neon access, source HTTP, Git publisher or DST correction.** 
`GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.

## Exact inputs (all independently checked by CI)

- C2/Git baseline: `site-prod@d0a7d22de2828c93236562cccc9d2e68c6a66e3d`
- Compatible Git frontend and static timestamp fallback guard: Draft PR #100 HEAD `19446ba9b9513ec962be08a128b4132de3f1912c`
- Git-only Netlify builder: Draft PR #104 HEAD `a18e20295a7aa148c57fce4c5913ad68c3bd4c34`
- Accepted latest C2 (not necessarily current at future cutover): [#43262387718](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43262387718), attempt 1. Exact `site-prod` checkpoint file must assert 23/23 matching source capture receipts.
- The historical deploy `6adb629bc3ebc570117d82e1` is **not** a usable G2 rollback baseline.

## Proof contract

On a successful exact-HEAD Actions run, artifact `c3-g2-minimal-git-only-rollback-offline` contains:

- `REPORT.json` — PASS/blocked boundary, exact source commits, independent package and manifest hashes
- `manifest.json` — 23-city keys, dashboard and static KPI generation, five Git runtime JSON Git blob SHA-1 + SHA-256, Kyiv city SHA, all tracked casualty file hashes, C2 checkpoints/QA, and every package member SHA-256
- `git-only-rollback-package.zip` — five Git-only runtime JSON under `git-json/` and twelve static root files plus `data.json` under `netlify/_site/`. **No casualty queue files are bundled for reversion.**
- `package.sha256`, `checks.json`, `no_loss_cases.json`

The static index is copied from the **same-generation verified Git-only dashboard embedded index**, not October Netlify and not a cached Neon index; this avoids a new HTTP source fetch in this proof. The Netlify 12 root files are sourced from exact PR #100 frontend with PR #104's Git-only delivery contract. The consumer must verify generation and city identity; `source_ref=site-prod` and 23/23 verified. The C2 data is a frozen input, never a promise of cutover-time freshness.

The eight independent synthetic no-loss scenarios reject stale/Neon data, allow *recapture* of newer C2/casualty/aux, and never overwrite any prior bytes. These are policy checks, not a live future-C2 recovery. CI is `contents:read`, `persist-credentials:false` and does **not** execute Netlify, C2 or Neon.

## Minimal operator runbook — NOT EXECUTED

1. **Before any approved cutover:** freeze conflicting release writers and get the *latest* successful C2 `site-prod` SHA, run/attempt and 23/23 full receipts; fetch the then-current Git-only dataset, Kyiv intervals, all casualty files and auxiliary files. Regenerate this manifest/package from the **then-current compatible Git-only** frontend and Netlify workflow. Compare byte SHA-256 + Git blob SHA, source generation, 23 exact cities, verified Git historical index and Netlify static KPI generation. If any field differs, discard the old G2 package; **do not deploy it as current**.
2. Capture an immutable Git-only Netlify deploy ID and all twelve static SHA. Verify the operator has authorization to re-publish a **non-current** deploy, or has separately approved rights to deploy the exact pinned static package; today's *current* October deployment offers no meaningful republish test.
3. On a future failed Neon release, stop Neon Git publisher and concurrent Netlify auto-deploy first. Reconstruct **fresh** Git-only JSON through the existing authorized C2/Git path and reconcile later casualty, Kyiv and auxiliary changes. **No `git reset`, no force-push and no blind overwrite of five old JSON.** If latest C2 and casualty/aux cannot be retained, STOP.
4. Confirm the five Git runtime JSON, Git-only `source_ref`, 23/23 city set, embedded KPI, matching generation, Kyiv intervals, casualty and auxiliary checksums. Only then republish the pinned compatible Git-only static package. After publication validate real HTTPS files, all five Git JSON, 23-city/8-mode browser smoke, CSV/share, Kyiv intervals/reasons and casualties. Observe the next regular C2 to ensure the correct one-writer path continues.
5. Return to normal operations only after explicit operator acceptance; keep `GLOBAL_CUTOVER=NO` until separately authorized.

### Exact optional non-production alias rehearsal (DO NOT RUN without owner authorization)

On an operator machine with an independently verified `NETLIFY_AUTH_TOKEN`, download the **successful exact-head** G2 Actions artifact and check its GitHub-reported archive SHA-256, then extract it and run:

```bash
sha256sum -c package.sha256
mkdir -p /tmp/g2-rollback-preview
unzip -q git-only-rollback-package.zip 'netlify/_site/*' -d /tmp/g2-rollback-preview
npx -y netlify-cli@latest deploy \
  --dir=/tmp/g2-rollback-preview/netlify/_site \
  --site=b5aafc46-7468-4070-baf1-db80a4d30501 \
  --alias=g2-git-only-d0a7d22d \
  --auth="$NETLIFY_AUTH_TOKEN" \
  --json
```

Target: **non-production** alias `g2-git-only-d0a7d22d--ukraine-air-alerts.netlify.app`, only if the deploy succeeds. **No `--prod`**. Confirm actual Netlify deploy ID and `context=branch-deploy`, HTTP 200 for twelve static files + `data.json`, SHA against manifest (allow Netlify's documented injected `index.html` script only if independently proven), then run 23 city views and CSV/browser smoke with Git still pinned. Confirm production deploy ID remains unchanged.

This would test the exact package and *ability to create a draft alias*. It does **not**, by itself, prove access to re-publish an inactive deploy in production. Also, the production frontend still loads moving `site-prod` runtime JSON, so the alias is valid only while the Git generation remains identical; any later C2/casualty/aux update requires renewed verification.

## Hard readiness boundary

- `ROLLBACK_OFFLINE_READY=YES` **only after exact-head Actions PASS and immutable artifact digest verified.**
- `ROLLBACK_OPERATIONAL_READY=NO` until (a) current compatible cutover-time bundle and no-loss recovery are proven and (b) Netlify redeploy authority is proven, with an explicit owner gate.
- Neither an offline QA PASS nor a branch alias proves a completed real rollback.
