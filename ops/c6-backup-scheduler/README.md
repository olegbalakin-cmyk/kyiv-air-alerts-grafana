# C6 backup scheduler — separate Netlify site (default OFF)

This is a separately hosted watchdog for the existing C2→Neon→Git-only site data publisher. It does not read Neon, commit to Git, deploy the public website, or modify Netlify production settings.

**Status:** code and offline CI only until the independent Netlify project is deployed and an owner-created GitHub fine-grained personal token is configured. Do not assert production activation without a recorded successful actual scheduled function invocation and corresponding owner-authorized C6 dispatch.

## Separate Netlify project

Created project: https://app.netlify.com/projects/ukraine-air-alerts-c6-watchdog (project ID: 4370af81-4ccf-485c-8e43-5a9184ee7565). **Never link or redeploy the production website project** to install this scheduler.

1. In this new project, connect ONLY repository olegbalakin-cmyk/kyiv-air-alerts-grafana and select the approved main commit containing this directory. Set Netlify base directory ops/c6-backup-scheduler and publish directory public. The local netlify.toml configures the function directory. Deploy the independent project once (not production).
2. Keep C6_BACKUP_ENABLED unset or false until initial scheduled invocations show C6_BACKUP_CHECK C6_CATCHUP_REQUIRED DRY_RUN_ONLY when stale.
3. Create one fine-grained GitHub PAT in owner account olegbalakin-cmyk, restricted to ONLY this repository with Actions: Read and write, Metadata: Read. Set a short expiry and rotate it on expiration. Do not paste it into chat, GitHub code, CI or Netlify build files.
4. Save token ONLY in the separate Netlify scheduler project's secret environment variable C6_BACKUP_GITHUB_TOKEN, production context, Functions scope. It needs neither Neon nor site-prod write nor Netlify deploy permissions. Environment changes require a new deployment of the scheduler project.
5. After confirming existing owner-only C6 input c6_run_now, change C6_BACKUP_ENABLED to true and redeploy THIS independent scheduler project. Verify one scheduled check has DISPATCH_ACCEPTED, an owner-triggered C6 run publishes new Git-only data correctly, and the production Netlify deployment ID and lock remain unchanged.
6. If dispatch receives 401/403/422 or the function is not active, set C6_BACKUP_ENABLED false and redeploy only the scheduler. Never relax the owner gate.

## Operational behavior

- Netlify scheduled function checks every hour at :47 UTC.
- GitHub Actions history workflow ID 360885782 and last actual data-file commit on site-prod (a UI merge is NOT data freshness).
- No dispatch when any C6 workflow run is queued or active.
- No dispatch unless the most recent C6 attempt started at least 4h20m ago and the latest data commit is at least 5h old.
- Maximum six attempts in a rolling 24-hour window, counting scheduled and manual attempts, including failed attempts.
- Exact owner-token workflow_dispatch on main, c6_run_now=true, old pilot and release toggles OFF; no new Netlify deployments.
- Fail closed on missing run history or data commit, clock skew, GitHub errors, token missing, and ambiguous responses. Never retry POST.
- Existing GitHub cron stays on. GitHub concurrency serializes any overlapping C6 jobs, but the external scheduler and GitHub may still race; conservative attempts budget and Neon idempotency protect the writer.
- Logs contain enumerated reason labels only. No token or raw API body.

## Offline tests

Run: node --test ops/c6-backup-scheduler/tests/c6-backup.test.mjs. CI also runs the existing Python owner-gate test. These use no network, Neon, production Git push or Netlify deployment.

## Deployment separation

Do not remove owner-only input gates to make a GitHub App dispatch work. The fine-grained token deliberately authenticates as owner. The independent scheduler project must never be connected to the website's production Netlify publishing. Do not increase C2 write frequency beyond attempt guard.
