# CASUALTY-CROSS-INCIDENT-FACT-ISOLATION-01 — narrow offline fix

Date: 2026-11-11. **Research-only; not approved to merge or publish.**

## Exact inputs and source constraints

- Base research HEAD: `6d3c35d452a034034a17bb671bf62400cb2eab55`.
- Previously frozen evidence: [Actions artifact #13845600971](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998990269/artifacts/13845600971), ZIP SHA-256 `3fa949194a80d70c23ea3d6f757878f770bff6e1345f7787e51ff9df67341503`.
- Frozen `evidence.json` SHA-256 `68ceccdcca68a0c93d42a0c0173c32c9ab47b659415e9bd2b274df8d9cf0fdf9`. Verified unchanged by frozen evidence test. Existing queue, pinned revisions, and baseline inputs also unchanged.
- No new publisher HTTP, source capture, WIP queue updates, `revisions.csv` changes, production, Neon/C6, deployment or merge.

## Root cause and minimal remedy

`extract_cached_reports()` previously searched a complete publisher article independently for city/date, fatal count, place, weapon, time and attribution. The article describes multiple strikes, but the implementation assembled the first occurrence of each field into one fictitious incident.

The change introduces a conservative `_incident_scopes` helper to split a text at explicit, separately introduced attack sections such as `Раніше ... атакували` and `Також ... атакували`. Evidence parsing is limited to the **single section that contains a definite fatality total**. With no such unique section, extraction produces no report; the existing publication-only event stays `NEEDS_REVIEW`. Place, date, city, weapon, time, civilian markers and official attribution are consequently all evaluated within the same section; nothing is borrowed from another section. The separate `_attack_slot` boundary fix requires a complete time expression: `півночі` (north) is no longer recognized as `вночі` (at night).

The earlier direct `повідомив очільник ... міської військової адміністрації` rule is unchanged; none of the existing confirmation, identity, ledger, source or geographic gates were loosened. This deliberately limited heuristic is **not a universal Ukrainian incident segmenter**; an unmarked or linguistically different transition can still need review.

## Frozen Odesa incident facts

Candidate `f4719e871b92e7563c7150da`, Suspіlne Odesa, 7 November 2026:

| Field | Evidence in *fatal* section | Safe conclusion |
|---|---|---|
| City | `Увечері 7 листопада ... атакували Одесу` | Odesa city |
| Date | `7 листопада` tied to attacking Odesa | 2026-11-07 |
| Time | `Увечері` in fatal section | Evening (not night) |
| Deaths | `Унаслідок удару загинула одна людина` | One reported dead |
| Official attribution | `Про це повідомив очільник Одеської міської військової адміністрації Сергій Лисак` | `city-mva` recognized |
| Damage | `пошкоджень зазнала інфраструктура`; exact object not specified | Infrastructure mentioned, no proven exact location |
| Weapon | No missile/drone evidence in fatal section | Unknown, cannot uniquely anchor air-attack identity |

Previous nonfatal Odesa strike mentions a residential building. A separate strike to the north of Odesa **oblast** mentions a drone. Neither is evidence for the fatal Odesa strike. This is precisely why the resulting `NEEDS_REVIEW` and zero proposals are correct.

## Exact-head test results

- Implementation commit: [`c19e0c0`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/c19e0c057001e9b21867261250e5b4fc74b1d980).
- Final test-head at execution: `e96d521702c8538ecf3a49ef753cf8c8fd4f63c2`; [Actions #43024613349](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43024613349) **SUCCESS, 10/10 focused tests PASS**; [verdict artifact #13856616913](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43024613349/artifacts/13856616913).
- Odesa: `NEEDS_REVIEW`, zero cached incident reports, **no `AUTO_READY`, zero `+1` proposals**.
- Dnipro: `NEEDS_REVIEW`, origin remains `unattributed`.
- A single clearly identified fatal attack remains `AUTO_READY` in its controlled one-incident test, with `+2` proposal; second identical calculation yields zero additional proposals. Separate multi-incident examples and unrelated official statement are held for review.
- Frozen replay verdict: `after_auto_ready=0`, `after_new_proposals=0`, `replay_new_proposals=0`, `protected_inputs_unchanged=true`, `publication_allowed=false`.
- Initial broader attempt [Actions #43024467127](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43024467127) ran 45 tests: **44 passed**, one errored exclusively because the older `test_real_controls_and_existing_noop` fixture `research/casualty_automated_review_2026_11_10/cached_evidence.json` is not present on this research branch. This was not an assertion failure in the changed parser. The workflow was reverted to focused frozen-artifact cases, without modifying that older test or fabricating its fixture.

## Decision

**PASS for the precisely observed unsafe Odesa cross-incident example and focused regression set; NOT a general production-safety certification.** The original `+1` is rejected. Continue `NEEDS_REVIEW` when identity is insufficient. The legacy fixture-dependent test still lacks a runnable input on this branch; coverage of unknown narrative forms remains an explicit limitation. No merge or publication authorized.
