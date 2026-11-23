# Issue #257 — primary official leads and 23-city September–October completeness

**Research only — 2026-11-23.** `PROMOTE=OFF`; `NO PUBLISH`; no collector GET, no WIP/Neon/C6/revision changes, no production or test Netlify deploy, no paid research job.

## What changed
- `official_primary_source_matrix.csv`: **26 explicitly held proposed victim/site aliases**, 15 September + 11 October. All match Issue #252's prior proposed **12 group IDs** and its 36-row independent acceptance matrix. The aliases are non-identifying research labels, not legal identities or independent primary attestations. Each row holds its official **direct URL**, publisher, attack date, comment-claimed original publication date/time, source vs cumulative semantics, precise source-body deficit, conflicting claim and earlier *short-excerpt* SHA fingerprints clearly distinguished from real publisher-body hashes.
- `revised_official_source_go_request.json`: **12 unique official URL leads**, from the [coordinator's PR #254 comment](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/254#issuecomment-7109371842). They replace the *suggested target list*, not its historical evidence. They are **not verified publisher-body archives**, not publisher snapshots and not approved for GET. Publisher dates and times are claims in that comment; one weekly summary has unknown exact original date. Nothing is backfilled with fabricated timestamps or hashes.
- `coverage_gap_priority_23cities.csv`: 23 separate city records for September and October. September **23 PARTIAL**, October **10 PARTIAL from bounded research** and **13 UNKNOWN**. Partial October does *not* mean fully validated even for the days with attacks. Four exact individual September cutoffs established from prior records (Kyiv Sep15, Kherson Sep17, Odesa/Zaporizhzhia Sep18); the remaining 19 individual cutoffs are unknown. OVA region-level monthly summaries cannot stand in for a city's administrative-boundary deaths.
- `coverage_metrics.json`: two intentionally independent metrics — **known incident-level minima** and **complete city-month proof**, not one misleading total. As of pinned `site-prod`, 23-city September *previously published partial lower bound* 56 includes Sumy +1 already credited; Kyiv's prior September baseline 18 through Sep15. **Additional 15 September and 11 October Kyiv proposals still HELD**; Sep25 other 2 unresolved and Sep27 possible second city victim unverified. Four previously vetted **other-city** October incidents total 11 but remain a separate owner-gated Release-1 candidate, not published. `NEW_INDEPENDENTLY_RELEASABLE=NOT_YET_VERIFIED`; **authorized additional credits 0**. **0/46 complete city-month proofs**, not 46 months with zero deaths.

## Crucial event/date/source distinctions
| Event | Site/statement reconciliation | STOP condition |
|---|---|---|
| Sep23 | Mayor 1→2 and later hospital death belong to *one* Sep23 wave | Two distinct city deaths, not 1+2; site/identity body unarchived |
| Sep24 | 57-year-old Podilskyi woman + 65-year-old Solomianskyi man | Two city victims, not two per police report |
| Sep25 | Solomianskyi office 4 + Pecherskyi child 1 are subsets of citywide final 7 | The other two are unallocated. **Never 4+1+7.** Journalist included in office four |
| Sep27 | One 56-year-old Solomianskyi guard vs q81 city 2 / q82 city+oblast | Don't import Sofiivska Borshchahivka market or invent second city victim |
| Sep28 | Academy two women from 1→2 rescue update | Weekly city two is not source-body proof of second Academy victim; obtain rescue source |
| Sep30 | Sviatoshynskyi two women plus Solomianskyi driver = city final 3 | Exclude Vyshhorod child, don't add interim 2 + final 3 |
| Oct7 pre-dawn | Darnytskyi ballistic garages two older guards | Separate from Oct7 **evening** UAV wave |
| Oct7 evening | Obolonskyi courtyard 2, Desnianskyi apartment 2 | Police article **published Oct8** describes Oct7 attack, not a second Oct8 event |
| Oct8 daytime | Solomianskyi shop 3 + claimed Holosiivskyi 1, city 3→4 | Police shop story supports 3, not independent full-body witness of fourth city location |
| Oct20 | City Department of Health reports one death; Holosiivskyi fuel-station location remains to be established | **Chabany three are Kyiv oblast, not Kyiv city** |

The comment/source hints do not prove a unique, civilian, non-duplicated slot. Site aliases also need inspection against *latest* `site-prod` revisions immediately before release. The new URL allowlist is a **bounded next capture proposal**, not a proof that this publisher said every inferred row. For Sep28/Oct8/Oct20 additional exact first-hand police or rescue evidence is needed beyond the 12 listed URLs.

## Full-month evidence gaps and priority
- **P0**: Kyiv full Sep after 15 and Oct 1–31, Kyiv source bodies and unallocated Sep25 two; Dnipro Oct20 hospital revision; Zaporizhzhia Oct22 2→3 city scope; Kropyvnytskyi oblast three vs city; Chernihiv city deaths vs oblast count; Kherson UAV fatality within city, not oblast/munition.
- **P1**: close known September cutoff gaps for Kherson/Odesa/Zaporizhzhia, and finish exact October monthly coverage for Lutsk/Poltava/Ivano-Frankivsk/Khmelnytskyi already-vetted incident records.
- **P2**: 19 city September cutoffs not individually supported, and remaining October city-months without comparable independent coverage.

A **genuine complete month** needs a dated official *city-only* daily register or monthly authority cumulative covering the entire attack-date interval, source corrections/later hospital deaths, civilian deaths caused by aerial attacks and overlap checks; mere availability of an OVA regional digest, no found article, or numeric 0 is not proof. No MVA/OVA city-only full-month summary has been independently verified from the pinned local research. The current package does not pretend to have completed a wider online survey of 23 city administrations.

## Evidence / hard boundaries
- `main@b35ca5c8d189a011c1b7158275f189a195192890`; inspected `PROJECT_STATE.md`, `CHANGELOG.md`.
- Prior #252 [Draft PR #254](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/254) @`ea6bef7b5963dfe34fd844737fd05b045526efaf`; [Actions #45190860163](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45190860163) successful 22 offline tests; [artifact #14826450630](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45190860163/artifacts/14826450630) archived (reported sha256 `d0c4dea95f8bff53e8292dafe558feb1bf99aa6f846e311e9b6f3aace5195f2c`; not independently downloaded again here).
- At readback, `site-prod@bfd68247954605fb8fb6c956153a11679bd83714`; this was an unrelated scheduled C6 publish; casualty Kyiv September source blob still `52238c1e72bdba3b06fc0c0469d699f018d8e353`, confirmed revisions blob `8d7a2e2540bf4bf0f8c6227023821390bf82ce13`, twenty-city monthly-wide blob `f3b7fdf6750e12d7b9af05ffd094bb47aa9ed801`. These were read only and cannot be mistaken for event-release proof.
- Earlier collector 27-GET grant **spent** (21 HTTP200, no full bodies saved). **Never reuse it**.
- Future, **only after a separate explicit owner GO** on exact HEAD and exact request-manifest digest: max **12** original official HTTPS GET, one each, 15s, 2MiB, public IP only, no redirects/retries, sequential, bounded SHA-256 body preservation, no automatic credits, no revisions, no Netlify production or previews.
- Offline unit command: `python -m unittest discover -s research/casualty_issue257_official_sources_2026_11_23 -p 'test_*.py' -v`. This command uses Python stdlib only; no workflows or deployments are included. Physical execution status should be reported separately, not presumed. Before any future credit, re-check latest canonical site-prod and baseline.

## Coordinator handoff
Primary body collection is the next evidence gate; it is *not* authority to publish or even to fetch now. The independently vetted four-other-city October 11 from Release-1 should proceed separately when the owner authorizes publication, unaffected by held Kyiv candidates. `PROMOTE=OFF` always.
