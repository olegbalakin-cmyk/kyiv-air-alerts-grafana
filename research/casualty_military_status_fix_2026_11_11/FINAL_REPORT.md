# CASUALTY-EXPLICIT-MILITARY-STATUS-FIX-01 — 54/54 OFFLINE PASS

**Date:** 2026-11-11. **Research-only**, no media HTTP, no operational writes, no merge, deployment, production or Neon/C6 changes.

## Frozen starting state and root cause

- Base of isolated branch: `8f39b8b8cc16c77c340249d1b050ea79727b6949` (PR #67 original, research only).
- Existing owner-approved presumption was implemented by `_civilian_status(low,total)` in `kyiv-air-alerts-grafana/scripts/casualty_auto_review.py`. Prior regular expression only recognized forms of `загинули ... військовослужбовці` and `серед загиблих ...`; **`Загиблі - військовослужбовці`** was missed and fell through to `civilian_presumed`, yielding `facts.civilian=true`. `origin_id=unattributed` accidentally stopped the final proposal but did not fix this underlying false presumption.
- Real retained LB.ua article, 2026-10-11, candidate `42f2a273f56c87e0bcd22af8`, reports three deceased servicemembers in the Ivano-Frankivsk strike. Source captured in the already completed one-shot [Actions #43053796144](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144), [original artifact #13870872313](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144/artifacts/13870872313). No further publisher requests.

## Scoped fix

- Only the existing `_civilian_status` classifier changed. Specific nearby phrases asserting that **deceased** people were servicemembers override presumption and return existing `civilian_ambiguous` state (not a new schema).
- Unchanged `extract_cached_reports` contract derives `facts.civilian=None` from ambiguous status; unchanged `prepare` attaches `CIVILIAN_AMBIGUOUS` and blocks `AUTO_READY`. Therefore **0 of these three military deaths are eligible to be automatically added as civilian fatalities**. The source still accurately records the original three deaths as an unverified total, not a civilian proposal.
- Explicit military deaths, possible mixed civilian/military victims and military-object ambiguity fail closed. Mentions of injured servicemembers, military administrative offices, denied service-member status and separately introduced attacks must not falsely classify first-event deceased as military.
- If there is no military-death/risk marker, the owner-approved civilian presumption and the normal `AUTO_READY` path remain unchanged.
- No modifications to source attribution, incident-date/geography/dedup, allowlist, WIP queue, `revisions.csv`, C6 or production.
- Intentionally unresolved separate findings: Zaporizhzhia cumulative update 18→20→23 and false `place` from "на вулиці під час тривоги".

## Immutable sources and offline checks

- Original source ZIP SHA-256: `f7255cba58faea1ecb7defbe2cdbed40db2ddf05a5b92f5fe3530cead32f2148`.
- Original three-source `evidence.json` SHA-256: `84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df`.
- LB.ua preserved excerpt SHA-256: `ce5dde16ff43e43f03a53ae0b39e637f068daa0bef31bb924a2f3f43a60d646d`.
- Historic five-article `evidence.json`: `68ceccdcca68a0c93d42a0c0173c32c9ab47b659415e9bd2b274df8d9cf0fdf9` from previous artifact #13845600971.
- Historic fixture restored **only** from commit `05ce47b1a92374af6c44c662f2d31f041a8f8afc` with original cached evidence `4dad9a007db2e396b8d2f03e9db49b5eaa98707fe7f390341399a5b0966a51b3` and original events `c82ac990755bc2015fc01cb5c52881edd7b3d9f72af7e49230b5c14838d39339` SHA-256.
- [Final exact-code run #43069234925](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43069234925) on code/test commit [`60c742a7`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/60c742a7d58f69b36cc472b93c66cef9b1cf83b4): **54/54 PASS** = original full 45 + nine additional real/synthetic safety tests.
- [Final offline proof artifact #13877985246](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43069234925/artifacts/13877985246), ZIP digest `sha256:9a83fbf42bc552fef1d9e0006269f7b94d5a5ab5c257377a5de657da578e1986`: `test_log.txt`, complete before/after SHA checks and `integrity_verdict.txt`.
- Initial CI #43068968488 failed from a *new test assumption*: `_fatal_total` intentionally fails closed and yields no parsed report when narrative includes `не загинули`. The test was corrected without changing the existing total-extraction behavior; next run #43069103719 and final run #43069234925 both succeeded.

## Per-condition verdict

| Required outcome | Verified |
| --- | --- |
| Ivano-Frankivsk real LB.ua: explicit military status recognized | PASS; `civilian_ambiguous`, not `civilian_presumed`; `facts.civilian=None` |
| Ivano-Frankivsk status | `NEEDS_REVIEW`; no three-civilian-death proposal |
| Fully dated, attributed, in-city synthetic military fatalities | PASS; `CIVILIAN_AMBIGUOUS` blocks `AUTO_READY` even with DSNS provenance |
| No military markers: positive civilian presumption | PASS; `civilian_presumed` and `AUTO_READY`, +2 only in synthetic shadow |
| Injured servicemembers, separate attack, explicit denial | PASS; no inappropriate military-victim inference |
| Mixed/uncertain casualty status | PASS; `NEEDS_REVIEW` |
| Previous full offline regression | **45/45 PASS**, original frozen legacy fixture, Odesa/Dnipro/Kharkiv protections |
| All targeted + regression | **54/54 PASS** |
| Full original three-article replay | First/repeat **0 proposals**, **0 duplicate proposals**, **0 duplicate added deaths** |
| SHA-256 invariance of original captured and historical inputs | PASS; all before/after hashes equal |
| Publishing, operational WIP/revisions, Neon/C6, merge/deploy | None |

**Release status: RESEARCH PASS ONLY.** This task does not authorize a merge or a casualty publication.
