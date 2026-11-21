# C6 schedule reliability audit — 21 November 2026

**Scope:** read-only diagnosis, not a production release, scheduling change, Neon write or Netlify deployment. Times below are UTC. Source of truth: `main:PROJECT_STATE.md` and `main:CHANGELOG.md`.

## Verified observation

- The main C6 workflow `.github/workflows/update-netlify-site.yml` has `schedule: 15 */4 * * *` (six UTC slots/day). The exact schedule is present in the main commit variants used on November 18–21; default branch is `main`.
- Actual scheduled C6 runs visible via GitHub Actions API by UTC calendar day:
  - Nov 18: 07:34, 17:17 — **2** created;
  - Nov 19: 01:53, 13:16, 23:04 — **3** created;
  - Nov 20: 07:22, 16:59 — **2** created;
  - Nov 21 (checked after 21:25 UTC): 01:33 and 12:42 — **2** created.
  **Nine runs vs 24 nominal four-hour ticks.** This is an observed count, *not* proof that 15 exact events were permanently discarded: scheduled events may arrive many hours late.
- Parallel, separately gated workflows also lagged on Nov 21:
  - `casualty-monitor-wip.yml`, `45 */4 * * *`: 01:45 and 13:01 UTC (2 of 6 nominal slots);
  - `historical-attack-event-backfill-scheduler.yml`, `17 */3 * * *`: 02:26, 11:20, 19:25 UTC (3 of 8 nominal slots);
  - `telegram-vs-rss-temporal-attribution-panel.yml`, 08:45 and 20:45 UTC: runs at 01:43 and 16:22 UTC. These can be reconciled with delayed preceding cron slots, rather than any corresponding on-time ticks.
- C6 `#44850889425` **SUCCESS**, ended 2026-11-21 02:02 UTC, last verified data Git-only publication. C6 `#44905215404` **FAILURE** at Git publication after Neon writer/reader succeeded: independent UI PR #219 moved `site-prod` during the run. The UI-only race protection merged as PR #221 (`main@8eba3cd7`), with isolated tests `#44950124198` SUCCESS; a physical scheduled confirmation is still pending.
- The workflow is not globally disabled: scheduled events do get created and execute. There are no recorded `cancelled` C6 runs accounting for the missing slots. The 4-hour cron did not change in the exact sampled workflow commits. Job-level skip/if conditions cannot explain the absence of a *workflow-run entry*.

## Diagnosis and limits

This is **GitHub Actions cron dispatch unreliability / severe delay**, broader than the C6 writer or publisher. GitHub documents that `schedule` events may be delayed or dropped under high Actions load: https://docs.github.com/en/actions/how-tos/troubleshoot-workflows

This repository cannot see GitHub's internal cron queue, so the exact upstream failure mechanism or a specific November 21 service incident is **NOT VERIFIED**. Neither changing the cron minute nor adding more GitHub cron expressions guarantees four-hour delivery.

## Safe response

1. **Immediate catch-up:** the existing owner-only `workflow_dispatch` input `c6_run_now=true` on `main` executes the ordinary guarded C2→Neon→Git-only pipeline. Check no ongoing C6 run first. Do not rerun the stale failed publication job.
2. **Reliable scheduling:** use an independently hosted scheduler, authenticated to an explicitly owner-approved narrow trigger, and add read-only freshness and last-attempt checks before any C2 network/write work. Preserve the normal >=4h interval, same-run 23-city evidence, no-force-push protections, zero regular Netlify deployment, and owner-only manual gates. Require separate security review/owner GO for new credentials, machine actor and schedule changes.
3. **Optional mitigation, not a guarantee:** an hourly GitHub schedule can retry *checking* the last data publication, but must fail-closed and enforce a four-hour **attempt** budget; a success-only freshness check would repeat writer HTTP/Neon attempts hourly after a failure and is **not safe**.
4. **Proof gate:** obtain at least two actual C6 Git-only publications across independent scheduled cycles, verify 23-city freshness, Neon receipts, branch SHA advance, zero Netlify, and age of last delivery. Keep `C6_STABILIZATION=OPEN` and `C6_SCHEDULE_RELIABILITY=OPEN` until then.

No production, C2 writer, backfill, casualty, source HTTP, Neon, Netlify or workflow schedule was changed by this diagnostic.
