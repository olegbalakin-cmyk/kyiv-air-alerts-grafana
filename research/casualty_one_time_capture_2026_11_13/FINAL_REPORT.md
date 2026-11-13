# One-time owner-authorized casualty source capture — physical research receipt

**Date:** 2026-11-13 UTC. **Scope:** 10 exact PR #111 targets T01–T10; strict Work I PR #115 exact redirect policy, no whitelist extension. User consent in this chat on 2026-11-13; authorization `CASUALTY-T01-T10-OWNER-20261113-ONE-SHOT-01` used once.

## Physical execution

- Immutable live commit: `fbc721e79c3cec16bd584431dbcd6d9b18b6163f`.
- Physical [Actions #43405970445](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405970445) **SUCCESS**, attempt 1, source-only read-only GitHub job.
- [Proof artifact #14027391709](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405970445/artifacts/14027391709), GitHub ZIP and independent download SHA256 **MATCH**: `d43e81484c043d45a9ebee7435f041207303060590fb5ba0687bbaa1d9205bf3`.
- ZIP manifest SHA-256 checks independently MATCH for all three included JSON outputs. All 36 Work E/G/I offline safety tests PASS on live job before outbound requests; earlier [preflight #43405810266](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405810266) SUCCESS (36/36, zero source GET).

## Transport findings (exact research targets only)

| Target | Question | Source kind | HTTP | GETs | Result |
|---|---|---|---|---|---|
| T01 | Oct 18 | publisher | 200 | 1 | unverified text |
| T02 | Oct 18 | police | 200 | 1 | unverified text |
| T03 | Oct 22 early count | publisher | 200 | 1 | unverified text |
| T04 | Oct 22 later count | publisher | 200 | 1 | unverified text |
| T05 | Oct 22 | police | 200 | 1 | unverified text |
| T06 | Sep 26 | publisher | 200 | 1 | unverified text |
| T07 | Sep 26 | police | 200 | 1 | unverified text |
| T08 | Sep 27 | publisher | 200 | 1 | unverified text |
| T09 | Sep 27 | police | 200 | 1 | unverified text |
| T10 | Possible Oct 5 delayed death | publisher | 200 | 1 | unverified text |

**Transport verdict: PASS, bounded.** Ten of ten approved initial URLs returned status 200, HTML was extracted; all **10** actual requests used against the **20** request ceiling. There were **0 redirects**, **0 retries**, no cross-host or cross-path request, no rate/budget breach, no safety stop. Six publisher URLs generated seven in-memory candidate text bindings because T10 mapped to two candidates; four official originals were handled separately.

## Evidence extraction boundary and next blocker

**Fact extraction verdict: BLOCKED / zero new structured reports.** Work E/A existing `extract_cached_reports` returned **0** structured reports on these new real texts. That is not a claim of 0 deaths or a negative finding about the four attacks. All source bodies were ephemeral: the ZIP contains only HTTP audit receipts, response hashes, page titles and the unverified preview; no full raw article text was persisted, and **no extracted claim excerpts were persisted**. These hashes alone are insufficient to independently reconstruct or adjudicate death counts. This is an identified evidence-retention gap before any later live run.

The four police originals were captured as text in memory but **not independently incident-linked**. Reconcile Sep 26/27 to existing credited September entries; do not sum Oct 22 2+3 as five; require a separate dated official statement and prior-credit audit for any delayed Oct 5 death.

## Controls and final decision

- Actual casualty death credits: **0**; production/statistics/WIP/C2/Neon/frontend changes: **0**; publication `false`.
- No `REVIEW`, `PROMOTE`, scheduled ingestion or update of live `revisions.csv`.
- User's one-time authorization has been **consumed**. Do not retry or rerun under this authorization ID, even after a partial failure. New source HTTP requires a fresh explicit owner grant.
- Root cause of missing fact outputs must be diagnosed with **only saved receipts and code** (no new HTTP); any subsequent proposal to capture bounded factual excerpts and independently bind official claims must be separately reviewed before another authorization.

**Overall: `ONE_TIME_SOURCE_TRANSPORT_PASS_FACT_EXTRACTION_BLOCKED`.** Positive physical source reachability proof; **not** a casualty accuracy, completeness, reviewer or publication PASS. Keep draft research branch, no merge/deploy.

## Coordinator handoff

Accept this bounded transport checkpoint in casualty coordination only. Further priorities: (1) inspect Work E/A general-source parsing assumptions offline; (2) design small, auditable, privacy-safe factual excerpt retention **before any future re-capture**; (3) event-level official/source matching and Sept prior-credit reconciliation; (4) maintain October Zaporizhzhia **`COVERAGE_INCOMPLETE`**, including verified `≥23` only from prior original-source Work F.
