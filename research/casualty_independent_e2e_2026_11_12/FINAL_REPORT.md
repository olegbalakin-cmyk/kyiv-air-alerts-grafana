# Independent casualty end-to-end audit — 2026-11-12

**Verdict: PARTIAL. SHADOW ONLY. NO MERGE / DEPLOY / DATA PUBLICATION.**

## Evidence scope and independence

This test evaluates **unchanged Work A** [Draft PR #105](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/105) exact HEAD `6a0100b0937218c62c5c079fd46e80e5071783cb`, not a rewritten or merged variant. `main:PROJECT_STATE.md` and `main:CHANGELOG.md` were read first; newer casualty coordination was checked in [PR #71](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/71). Separate source checks are based on [PR #85](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/85), [PR #102](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/102), and controlled cumulative generator evidence in [PR #91](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/91). [PR #99](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/99) provides a **separate, unpublished** lower-bound visualization contract.

Work A frozen WIP: `43b580491d54d1df3bd84a0ae59a6987f8ea4d03`. Generator / Git-only baseline: `d0a7d22de2828c93236562cccc9d2e68c6a66e3d`. Five-event case inventory: `34bc539d0c7abb8af4f699b2e2c9ecec4b668397`. PR99 visual proof: `384fb8b8e087701f42510f68f19817d9732f883e`. Retained original article and PR102 receipts come from already-authorized GitHub Actions archives; their **inner JSON SHA-256** is checked before executing the audit. A source transport receipt alone is not a retained factual article and therefore cannot authorize a casualty record.

**No fresh publisher HTTP is performed.** CI uses only existing GitHub checkouts/artifact retrieval, standard dependency provisioning and temporary runner files. No C2, Neon, Netlify, source collector, production revisions, production dashboards or review queue mutations.

## Independent case-control set

The six attack clusters below come from prior independent evidence rather than Work A decision labels. Synthetic tests are separate software-behavior probes, **not fictional attacks**.

| Real attack / event question | Independent evidence assessment | Work A on frozen inputs | Audit interpretation |
| --- | --- | --- | --- |
| Zaporizhzhia 10 Oct, KAB, successive 18→20→23 | 23 cumulative deaths, one incident; retained original Suspilne/DSNS text; no Oct prior credit in pinned city ledger | AUTO_READY, +23 | Correct source-backed selected positive, *not* a full-month total |
| Zaporizhzhia 18 Oct, drone | PR102 publisher+police source assessment: one death | NEEDS_REVIEW, no delta | Confirmed in prior research, but not automatically adjudicated from retained factual text |
| Zaporizhzhia 22 Oct evening, missile | PR102: one incident, **3 final**, not 2+3 | NEEDS_REVIEW, no delta | Correctly refuses guessed increment; confirmed incident not advanced |
| Zaporizhzhia 26 Sep, drone | PR102: two deaths, three candidate articles same event | NEEDS_REVIEW | Source-body and September prior-credit allocation missing |
| Zaporizhzhia 27 Sep, drone | PR102: one death, two reports same event | NEEDS_REVIEW | Source-body and September prior-credit allocation missing |
| Published 26 Oct, possible death after 5 Oct strike | No independent official late-death confirmation or prior-credit proof | NEEDS_REVIEW | Correctly blocked ambiguity; no asserted death |

PR102's article assessment is treated as independent **prior research**, not equivalent to complete retained text in this frozen replay. Confirmed cases withheld because source content is unavailable must not be mislabeled as false negatives of a classifier operating on full articles. They *are* operational gaps in end-to-end automation.

## Independent quality metrics and denominator

| Requested metric | Result / interpretation |
| --- | --- |
| Correct automatic confirmations | **1 real incident** in selected six-case set |
| False automatic confirmations | **0 observed** in the selected cases; no population false-positive bound |
| Independently confirmed attacks not automatically advanced | **4 selected incidents** (source/credit blockers; not proven classifier errors) |
| Correctly blocked ambiguous real attacks | **1** (possible later death after 5 Oct) |
| Automatic handling among selected six real-case questions | **1/6 = 16.7%** |
| Automatic readiness among all 1,682 queued WIP *messages* | **1/1,682 = 0.059%** (not incident-level detection recall) |
| Advancement among five independently confirmed selected incidents | **1/5 = 20%**, selected-case operational advancement only |
| Generator for known positive | **+23** in isolated October 2026 Zaporizhzhia |
| Repeat with explicit reservation | **0** additional proposals |
| Real-world overall detection completeness / recall | **UNKNOWN**; no exhaustive independent population gold |
| Overall precision, false-positive rate, false-negative rate | **NOT ESTIMABLE** from these biased small selected cases |

The WIP records are messages, **not 1,682 proven death incidents**. Two monitored cities with no WIP messages are not evidence of no attacks or fatalities. October 2026 remains **COVERAGE_INCOMPLETE**; the independently credible `≥23` minimum must not become a final integer.

## Production-compatibility diagnosis

**Two distinct paths must not be conflated:**

1. **Work A's direct adapter path — works in isolation.** It prepares `incident_id`, `count_kind=cumulative`, `baseline_credited=0`, `identity_proof`, `credited_proof` and injects its private proposed revision into a temporary copy of `revisions.csv`. The actual frozen site-prod `reconcile_confirmed_revisions` and `apply_city_revision_overlay` create an October +23 row with other 22 casualty-city objects unchanged. Rerun with the previous proposal reservation produces 0 new rows. This does not include live review/promotion or publication.

2. **Legacy review/promote path — incompatible.** `review_casualty_candidates.py` has only the original 10 `REVISION_FIELDS`. Its `promote_reviewed` constructs only those fields and `atomic_write_csv` writes only those fields. Thus even a manually confirmed candidate that includes all five new fields in its disposition loses them on promotion. The strict production generator rejects the resulting new confirmed revision with missing documented incident identity/credit provenance. The pinned pre-contract Sumy exception does not generalize. The independent test explicitly sends a genuine-shaped Work A proposal through the **real legacy `promote_reviewed` on a private queue/CSV** and then `load_revisions` plus `reconcile_confirmed_revisions` from the exact frozen generator. A safe fix would extend the existing reviewer CSV contract and validation to preserve/prove the five fields; **do not relax generator fail-closed checks**.

**Display end-to-end — not connected.** Work A's isolated generator emits a plain October row with `deaths: 23` and **without `coverage_status` or `confirmed_minimum`**. When passed to PR99's real `coverage-preview.js` normalization, it remains `LEGACY_UNVERIFIED`, not `INCOMPLETE`. PR99 separately proves a fixture `{deaths:null,coverage_status:"INCOMPLETE",confirmed_minimum:23}` can render `≥23` with hatching/CSV/PNG/embed. It is not automatically obtained from Work A's generator. Real Work A → classified JSON → graph → CSV/PNG/embed is **NOT PROVEN**, even though PR99 isolated fixture browser tests passed 40 offline + 36 Chromium. Never infer the production chart is safe to publish unqualified 23.

## Defensive regression and data isolation

The audit invokes the unchanged Work A bridge twice on the **same pinned** WIP/source/ledger/generator snapshot, re-evaluates six independent real attack questions, and runs seven synthetic safety probes against the actual generator:

- Sequential 18→20→23 cumulative observations yield 23, not 61.
- Repeating cumulative 23 does not produce 46.
- Already-credited 18 and new cumulative 23 yield an increment of 5.
- Two genuinely distinct attack identities on the same day remain separate.
- Reusing one candidate across different incidents is rejected.
- A contradictory 23→18 downward revision is rejected.
- Missing required immutable identity/credit proof is rejected.

Other-city and other-dashboard-key hashes, immutable input manifests and exact JSON restoration provide **offline rollback/isolation proof**. This does not prove a live deployment rollback, live end-user PNG/CSV/embed, or coverage after the pinned capture date. No published statistic is touched.

## Narrowest remediation, in order

1. Extend **existing** `review_casualty_candidates.py` `REVISION_FIELDS`, CSV load/promotion and explicit proof validation to safely preserve the five dedup fields. Retest exact reviewer → revision → production generator, including old Sumy row, duplicate candidates, contradictory cumulative updates and prior credited deaths. Keep the direct Work A adapter unchanged.
2. Reuse PR99's current `INCOMPLETE` schema and chart overlay in a **separate gated preview**: write lower-bound status explicitly for incomplete October, validate `≥23`, hatching, CSV, PNG and embed on the actual generated patch. Do not mark a month `COMPLETE` without independent full coverage.
3. Make approved retained original publisher/official content available for PR102's five blocked clusters, with provenance and event-level linkage. This requires separate authorization for any **new publisher HTTP**. Reconcile Sep incident credits and the possible later death before proposing additional deltas.
4. Only after the above, connect the **existing** WIP source, reviewer and generator to a separately tested **default-OFF** scheduled shadow run. Track incident-level confirmation coverage from an independently reviewed sample; retain manual escalation on ambiguous cases, immutable audit proofs and a reversible switch. No C2/Neon coupling, new architecture or automatic publication.

**Release gate remains CLOSED.** `PARTIAL` means the isolated positive generator and replay work, but the actual legacy promotion contract and real lower-bound graph handoff are missing, and incident discovery/source completeness is unmeasured. `SHADOW_E2E_PASS` is not justified. This report does **not** authorize any production action.
