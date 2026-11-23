# September 2026 casualties — 23-city offline audit (Issue #238)

**Decision: NO NEW SEPTEMBER VALUE IS PUBLICATION-READY.** This is an evidence review, not a revision/publisher approval. `PROMOTE=OFF`; zero new publisher/article GET; zero changes to `main`, `site-prod`, casualty revisions, WIP, Neon, Netlify, or deployed `deaths`.

## Pinned proof / immutable reference

- Latest verified production data branch before research: `site-prod@f7e0681ca6aa98405638dae7a63c884f4ed55d20` (Nov 23 07:16 UTC). This is **not** the target of the research PR.
- Source pinning and exact Git blob IDs in [september_2026_source_witness.json](september_2026_source_witness.json): September 20-city row, Kyiv explicit cutoff row, Kherson/Odesa/Zaporizhzhia monthly rows and manifests, Sumy confirmed revision, review queue.
- Baseline source: 20-city September master `f3b7fdf6750e12d7b9af05ffd094bb47aa9ed801`; Kyiv baseline `52238c1e72bdba3b06fc0c0469d699f018d8e353`. Published Sumy revision ledger `8d7a2e2540bf4bf0f8c6227023821390bf82ce13`. Current 132-card Kyiv review queue `8ae078bc60f2c27838b61e9aebf90b7286e0dd55`.
- Previous one-shot [Actions #45070256716](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45070256716) SUCCESS: **27 GET attempts**, 21 HTTP200, 5 HTTP403, 1 blocked HTTP301, [proof artifact #14773425588](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45070256716/artifacts/14773425588), report SHA256 `be053f77ade09db833eb976a67a6bcb036fb42cff1c98f81bfd90dde1fbe7ed8`. One-shot GO was consumed; not reusable. [Offline #45073045655](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45073045655) SUCCESS at PR #236 HEAD `270702ccc4a76d81ee8cc5b9cf73059fd19df025`; network job SKIPPED.
- Related drafts: [#235](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/235) is October reconciliation; [#236](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/236) is four October events (6+1+1+3=11 incident fatalities, not monthly totals); [#237](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/237) is October partial UI. These are NOT September source credits.

## What is already safely published

The **September 2026 baseline is PARTIAL for all 23 cities**; the published source has 55 deaths across its partial September monthly rows (20-city master 36; Kherson 12, Odesa 3, Zaporizhzhia 4). The separate, already-confirmed **Sumy 2026-09-20 +1** revision is in production revisions, resulting in a known published September minimum of **56** across 23 cities as of the pinned source. This is **not** a complete September monthly total and must never be labelled as such.

The 23-row [coverage CSV](september_2026_23city_coverage.csv) records original baseline, last proven cutoff or `coverage_unknown`, verification class, confirmed known minimum, review count and the appropriate geographical scope. Values of `0` in the original PARTIAL baseline do **not** mean zero deaths for the full month; the `confirmed_known_minimum` field is therefore BLANK in those cities (UNKNOWN). For nonzero rows, the minimum is the recorded partial source value, **not** a full-month certification.

**Only four independently supported cutoff dates:**
- Kyiv **2026-09-15**, from `baseline_monthly.csv`; its root 20-city manifest's generic import date is NOT proof of every other city's individual cutoff.
- Kherson **2026-09-17**, city manifest.
- Odesa and Zaporizhzhia **2026-09-18**, city manifests.
- For the other 19 cities, `validated_through` remains blank and `coverage_unknown=true`. Never infer individual city coverage from the 20-city spreadsheet filename or its imported date.

`needs_review_count` is **not** a comparable September incident count across cities: Kyiv has **53 September-date-tagged review queue source cards** (48 discovered after Kyiv's Sept 15 cutoff), not 53 deaths or 53 distinct attacks. Kherson 13, Odesa 8, Zaporizhzhia 2 are **all-date unresolved counts** from their manifests, not September-specific. For the remaining 19 cities, comparable September review counts are unknown. Regional monthly totals cannot fill these gaps.

## New candidate review — Kyiv post-cutoff, still NO CREDIT

The saved Kyiv queue supports six **date-level provisional groups** for attacks after Sept 15. These are NOT six proven independent attack IDs or complete city totals; the numbers below are **cumulative reported counts held for review**, not automatic addends.

| Attack date | Candidate cumulative deaths | Dedup / scope constraint |
| --- | ---: | --- |
| Sep 23 | 2 | One earlier hospital fatality became part of cumulative 2; don't add 1+2 |
| Sep 24 | 2 | Same ballistic-wave deaths reported by several publishers; not 2 per source |
| Sep 25 | 7 | Citywide 3→4→7 updates; 14-year-old in Pecherskyi and journalist in Solomianskyi may already be within seven |
| Sep 27 | 1 | Solomianskyi city death distinct from suburban-market deaths; don't import the latter |
| Sep 28 | 2 | Academy building: first 1, then 2; not three |
| Sep 30 | 3 | Overnight city two, later city driver one; cumulative three, not 2+3. Vyshhorod death excluded |

**Arithmetic review subtotal: 17 reported city fatalities across six provisional date-level groups. It is HELD, not a new September revision.** No new eligible death has a fully reconciled event/victim identity and immutable baseline-credited proof. Source URLs and captured source SHA256 values are in [september_2026_incident_candidates.json](september_2026_incident_candidates.json). Source queue material can include citywide multi-strike counts; one date-group is not necessarily a single physical attack. Hence the placeholder `candidate:...` IDs are **not production-grade** incident IDs.

### Specific anti-dedup exclusions

1. **Sumy Sep 20** `casualty:sumy:2026-09-20:fpv-double-strike-zarichnyi-apartment-entrance` already credited +1. A fresh source for this same person/incident is +0, even if independent journalism reports it.
2. **Glevakha/Fastiv Sep 19**, **Vyshhorod Sep 30**, and suburban market near Kyiv Sep 27 are not within Kyiv city. A Kyiv-branded source section or death in a Kyiv hospital does not change the location of attack.
3. Sep 25 named victims and districts are cross-references to the larger citywide cumulative series, not automatic extra fatalities.
4. Sep 15 Kyiv source cards overlap the day included in the baseline and cannot be added as post-cutoff deaths without individual credit proof.
5. Late deaths count in the **month of the attack**, not the month of source update or hospital death.

## What may be published now

**No new September revisions.** The only safe published September data remains the 23 partial baseline rows plus the **already credited** Sumy +1, displayed with explicit `PARTIAL / щонайменше` semantics and unknown-not-zero for unverified September remainder. If the existing production chart portrays full exact September monthly totals, that is a **presentation gap** to resolve under a separate UI/publisher contract; this research PR deliberately does not modify it.

To promote any of the 17 held Kyiv counts later, require exact incident identity, non-overlapping victim-level accounting, source proofs, civilian/weapon/city checks, baseline credited proof against the latest site-prod (not just the Sept 15 cutoff), date attribution and independent owner-approved release. Other 22 cities still need their own post-cutoff systematic coverage; the 27-GET October-oriented prior pilot did not establish it.

## Tests / proof

Run `python research/casualty_monthly_sources_2026_11_22/check_september_reconciliation.py` offline. It validates 23 unique cities, 23 PARTIAL flags, unknown cutoffs, four proven cutoffs, frozen baseline and Sumy credit, 53 cards versus six groups, cumulative-not-delta, verified URLs/hashes and zero publication readiness. Negative tests reject a complete-month flag, double-crediting Sumy, promoting candidates, treating cumulative as delta and unknown as zero. No credentials, HTTP calls, generator writes or deployment workflow are used.

Research checkpoint: `CASUALTY-SEPT2026-23CITY-PARTIAL-AUDIT-NO-PUBLISH-2026-11-23-01`. **Owner GO for publication: NOT GIVEN.**
