# Changelog

Accepted project checkpoints, newest first. This is not the full Git history, a branch inventory, or a retry log. **PROVEN** describes bounded evidence; **FROZEN** additionally requires a durable exact manifest. Development checkpoints below do not change production unless explicitly stated.

## 2026-10-10

### Kyiv 42-case harness remains blocked after first aggregation repair
- **Status:** `KYIV REPAIRED 42-FAILURE FIRST-FAILURE REDIAGNOSIS = BLOCKED`. Proof commit `aa07ccaef848ca348860e7997a8dda4089af6ec2` changes only `.github/proof/kyiv_repaired_42_first_failure_diagnosis.py`; classifier blob remains `4019b8374dcc44846df04ed0cc41356652214bff`.
- [Run 38033720781](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/38033720781) again passed frozen classifier/source checks, `48 / 6 / 42`, exact 42-ID SHA and hold precheck, then failed in Diagnosis A with `VERIFIED_FORENSIC_CANDIDATE_NOT_EPISODE_PRIMARY:c475d1dca5c22956189e88e3`. Diagnosis B, determinism and final artifact were not executed.
- The added semantic-priority helper and fail-closed forensic identity controls are insufficient for the real episode. The next task must first identify the exact competing candidate/category/stage that outranks the verified forensic candidate, then apply the narrowest generic proof-harness aggregation correction. No classifier, source, production, Neon or backfill mutation is authorized.
### Kyiv 42-case diagnostic harness blocked on accepted semantic-disposition conflict
- **Status:** `KYIV REPAIRED 42-FAILURE FIRST-FAILURE REDIAGNOSIS = BLOCKED`. **Evidence:** proof commit `86413d069b9403a6c442d383e51867b9d788ad4d`, [run 38032645986](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/38032645986), artifact `11663131301`.
- Precheck passed the frozen repaired classifier/source identity, reproduced **48 known positives / 6 final positives / 42 failures**, matched 42-ID SHA-256 `fcf85d81ccfa59501fe3a3a51f1c11cab48f5ff36a79b20454309db23b2913ab`, and preserved **19 holds**, STRICT **2**, SENSITIVITY **0**, new uncleared promotions **0**.
- Diagnosis A stopped on `c475d1dca5c22956189e88e3`: harness primary category `EVENT_TIME_TRULY_ABSENT` contradicted accepted forensic category `NON_EVENT_CLOCK`. Accepted frozen identity remains candidate `bbb04ce34aba2a895fbc2ca3`, `suspilne.media/kyiv`, normalized text SHA-256 `29ecfb7410c69dd13b27d3b77d4bcd52ad01268d36015396321762fb60b9a591`, wording `О пʼятій ранку я завжди відкриваю ворота`, semantic role `NARRATIVE_ANCHOR_CLOCK`.
- Root cause is bounded to the **proof harness**: accepted forensic semantics are attached to the correct candidate, but episode-level strongest-candidate ranking can select another candidate and discard that semantic role. No classifier, source, frozen corpus, production, Neon or backfill mutation occurred.
- Diagnosis B, deterministic fingerprints, category/repairability totals, transition table and final one-file diagnosis artifact were not produced. **Next:** fix only this diagnostic aggregation/priority behavior without hardcoding a category, then rerun the full A/B diagnosis.
### Kyiv repaired development classifier identity frozen; 42-case re-diagnosis still incomplete
- **Stage A accepted:** `KYIV REPAIRED DEVELOPMENT CLASSIFIER IDENTITY = FROZEN`. Freeze commit [`9784473e`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/9784473e64c3ddfe3474bacdc30a12458923ff87) is exactly one JSON-only commit ahead of semantic repair `c5dd5fec6fe8f9a3fa0bbdefdd2cf71cee2ff801`; artifact `research/kyiv_repaired_development_classifier_freeze_2026-10-09.json`, Git blob `52f7179fe3dd58d82ba1f479824c6076deab25d3`.
- The freeze records the already-proven repaired classifier blob `4019b8374dcc44846df04ed0cc41356652214bff`, unchanged 15-family corpus, repair run `37974699629`, **6/48** final positives, **19/19** holds unchanged, and zero new uncleared hold promotions. No classifier code changed in the freeze.
- **Stage B not accepted:** repaired replay A/B identify exactly **42** known-positive non-final episodes and exclude `cfd8acaf2ae96fb3ab6508d6`; sorted compact-JSON-with-LF 42-ID SHA-256 `fcf85d81ccfa59501fe3a3a51f1c11cab48f5ff36a79b20454309db23b2913ab`. No complete deterministic per-case first-failure taxonomy, category counts, repair ceilings, priority ranking or re-diagnosis artifact exists yet.
- **Next:** replay only those 42 frozen episodes under the frozen repaired classifier and produce deterministic per-case first-failure diagnosis. No repair or source change.
## 2026-10-09

### Real production casualty INSPECT canary accepted; full operator activation remains PARTIAL
- **Verdicts:** `PRODUCTION CASUALTY INSPECT CANARY = PROVEN`; `HUMAN CASUALTY REVIEW OPERATOR PRODUCTION ACTIVATION = PARTIAL`. This accepts read-only behavior only; it does not authorize a real `REVIEW` or `PROMOTE`.
- **Actions evidence:** preliminary [run 37971168998](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37971168998) was successful `INSPECT` with blank candidate ID (supporting execution only). Target [run 37971497179](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37971497179), commit `1fad23d3b1f169fa7b60f8f343876b0a0ca924ce`, used `INSPECT` on actual Sumy candidate `7093d860648b497986e7ecb7` with decision `NONE` and empty payload; preflight **SUCCESS**, protected mutation job **SKIPPED**.
- **Immutable preview verified:** downloaded [artifact ID `11634799962`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37971497179/artifacts/11634799962) (`casualty-review-immutable-preview`, ZIP SHA-256 `0e32f289fdc575fb9d3dc1d63baa2cbb62eb81dd32513dab225f51affb39f85a`, inner JSON SHA-256 `5fadfd55cba87a64bdb687dab414de359590b98b0af89bb206266767a4a5e76c`). Candidate is `sumy`, `needs_review`, with Google News RSS / shelter.in.ua evidence and actual immutable source references. Preview has `decision=""`, `payload={}`, `effect=null`; warns `Possible media duplicate candidate: 19f0ab0f9136ec7aa7214e11`, without treating a warning as a review decision.
- **Zero operator mutation:** WIP HEAD `b4219a896193602fd93ef92fc231cd9bdb2fe2c0` and queue blob `c6c073cb632c1b61d534b6d96ca17ce8bc86e637` match run-time snapshots; the inspected candidate and possible duplicate are still `needs_review` without dispositions. `site-prod` HEAD `e71412503f27c3301d30bff841e449c901138e33`, `revisions.csv` blob `8d7a2e2540bf4bf0f8c6227023821390bf82ce13` and dashboard blob `420b2a736270fc9b46a9ca536698f4343935293c` are unchanged. Reviewer semantic blob `57c67af1ce108222c9a8dc0fefe34d67f9d0e23e` matches the production pin. Previously confirmed Sumy `+1` remains a single ledger revision; published September **4**, total **159** (baseline **3 / 158**) without a second increment.
- **Remaining restriction and next task:** Workflow code defines `casualty-review-approval` and `CASUALTY_OPERATOR_APPROVAL_VERIFIED`, but account-side reviewer/self-review/admin-bypass configuration and effective rollout variable could not be independently retrieved; no protected real `REVIEW`/`PROMOTE` mutation was exercised. Separately verify those settings **read-only**. The next independent casualty research priority is a 23-city live discovery coverage audit with a reproducible evidence archive. No repeat `INSPECT`, real `REVIEW`/`PROMOTE`, casualty-data mutation or historical backfill is authorized.

### Kyiv 08:25 evidence-segment selection repair proven
- **Status:** `KYIV EVIDENCE-SEGMENT SELECTION REPAIR = PROVEN` for the bounded immutable development cohort. **Evidence:** semantic repair commit [`c5dd5fec`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/c5dd5fec6fe8f9a3fa0bbdefdd2cf71cee2ff801), repaired classifier blob `4019b8374dcc44846df04ed0cc41356652214bff`, proof head `906b9e18aa9e0a2056bcb798b9870ae35d8dee3d`, [run 37974699629](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37974699629), artifact `11638425268`, proof JSON SHA-256 `d09bb068d7e23d2afd345e5e23f6aacd5e49c5871bf410f40b37ea3e7214308f`.
- The semantic diff is one commit from classifier base `71cb6f6f...` and changes only `exact_city_classification_evidence(...)`. Proof passed **12/12** generic selection tests, one exact baseline replay and two independent repaired replays over **67/67 episodes and 105/105 candidate rows**. Candidate universe remained identical.
- Exactly one candidate changed: `f0882d6580bb10476195589f`, selection `[1,4,5,7] -> [1,4,7,8]`, `needs_review -> approved_strict`, temporal code `TEMPORAL_EXPLICIT_EVENT_TIME_INSIDE_EPISODE`, bound to `cfd8acaf2ae96fb3ab6508d6`. Exactly one episode changed: `cfd8acaf2ae96fb3ab6508d6`, `NEEDS_REVIEW -> STRICT_EVENT_POSITIVE`.
- Known-positive metrics: candidate-covered **31/48 -> 31/48**, STRICT **3 -> 4**, SENSITIVITY **2 -> 2**, final positives **5 -> 6**. All five prior final-positive controls were preserved. Holds: **19/19 unchanged**, hold STRICT **2 -> 2**, hold SENSITIVITY **0 -> 0**, new uncleared hold promotions **0**.
- Repaired replay fingerprints A/B are identical: `57fa5e402a79ab852b48d540de6a56581c3dd27fde4e986d3cce28ea3b611af8`. Frozen corpus hashes and 15-family source set were unchanged. Network evidence fetches `0`; blind inspected `NO`; historical backfill `NO`; Neon queries/writes `0/0`; production mutations `0`. The 411 historical regression was not executed because it would require prohibited blind-detail exposure.
- **Boundary:** the repair is development-only and not yet a frozen classifier identity or production deployment. **Next:** `FREEZE THE REPAIRED DEVELOPMENT CLASSIFIER IDENTITY AND RE-DIAGNOSE REMAINING KYIV FAILURES`.
### Kyiv 08:25 evidence-segment selection contract accepted as design checkpoint
- **Status:** `SAFE CONTRACT IDENTIFIED`, **not yet an implemented or reproven classifier repair**. **Evidence:** commit [`ba3cc8b0`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/ba3cc8b04a4c689c17b223b9c1a989928c0b397a), artifact `research/kyiv_immutable_0825_evidence_segment_selection_contract_diagnosis_2026-10-09.json`.
- Recommended contract: `UNIQUE_LATE_CLOCK_AND_FREE_SLOT`. It retains the first four exact-city segments unless exactly one later segment satisfies the existing strict attack-event predicate and has exactly one existing parsed event clock, no retained strict segment already has a parsed event clock, and a non-strict slot is available; it then replaces the last retained non-strict segment and preserves original source order.
- Frozen-cohort selection effect: **67** episodes, **105** candidates, **1** changed candidate, **1** affected known-positive episode, **0/19** affected holds, **1** newly visible strict-event segment and **1** newly visible explicit-clock segment. Target selection becomes `[1,4,7,8]` instead of `[1,4,5,7]`.
- The full pinned classifier was **not executed** under this contract. The target `NEEDS_REVIEW -> STRICT_EVENT_POSITIVE` and aggregate **5 -> 6** final positives are projections only. Historical 411 counterfactual regression was not run because doing so would require prohibited blind-detail exposure.
- **Next:** implement and reprove only this contract on the frozen 67-episode cohort, with exact classifier execution, deterministic outcome equality outside the intended target, and zero new uncleared hold promotions.
### Human casualty review operator production integration accepted; INSPECT pending
- **Status:** `HUMAN CASUALTY REVIEW OPERATOR PRODUCTION ACTIVATION = PARTIAL`. [Activation commit `6f62bda841d33512e2c8bd69b9e766509e2461e2`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/6f62bda841d33512e2c8bd69b9e766509e2461e2) is in `main` ancestry and integrated exactly four production files: `.github/workflows/casualty-review-operator.yml`, `kyiv-air-alerts-grafana/scripts/casualty_review_operator.py`, `kyiv-air-alerts-grafana/scripts/review_casualty_candidates.py`, and `kyiv-air-alerts-grafana/tests/test_casualty_review_operator.py`. The proof-only workflow was **not** transferred.
- Isolated synthetic acceptance remains **29/29 PASS** at proof head `81ef49a8af79123986ac48b5cb0d7e4e2fff4937`, [run 37963256291](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37963256291). This does not constitute a production `INSPECT`, `REVIEW` or `PROMOTE` proof.
- Production workflow is manual-only (`workflow_dispatch`). Its read-only `INSPECT` preflight is separate from the protected mutation job; the latter requires a non-`INSPECT` mode, GitHub Environment `casualty-review-approval`, and `vars.CASUALTY_OPERATOR_APPROVAL_VERIFIED == 'true'`. The flag value and current account-side environment protections were **not independently verified** in this checkpoint; repository-defined controls alone do not establish them.
- GitHub Actions history checked 2026-10-09: **no production operator `workflow_dispatch` / accepted real INSPECT canary**. Production preflight success, correct real-candidate evidence preview, mutation-job skip and zero operator-attributable changes have not yet been accepted. The earlier first real Sumy casualty publication and subsequent scheduled idempotency remain separately **PROVEN**.
- **Next authorized action:** exactly one real candidate read-only `INSPECT` canary plus zero-mutation audit of review dispositions, WIP, canonical revisions, `site-prod`, dashboard data and published casualty totals. No real `REVIEW` decision or `PROMOTE` is authorized by this documentation update. Longer-term objective: live casualty coverage measurement across all 23 cities.

### Kyiv five-case temporal forensic audit accepted
- **Status:** `PROVEN`. **Evidence:** commit [`cf451a61`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/cf451a61c0f590ca1745f66744ce9c99561c9d13), artifact `research/kyiv_immutable_temporal_parser_five_case_forensic_audit_2026-10-09.json`.
- Corrected the preliminary temporal-parser ceiling **5 -> 0 safe parser-syntax misses**. Final five-case taxonomy: **1** `EVIDENCE_SEGMENT_SELECTION_LIMIT`, **2** `TEMPORAL_REPRESENTATION_LIMIT`, **2** `NON_EVENT_CLOCK`.
- For the sole safe direct-event clock, `event_clock_mentions(...)` already recognizes `(8,25)` and `strict_attack_event_signal(...)` is true; the sentence is classification segment **8/16**, exact-Kyiv segment **5/5**, and is removed by the existing `segments[:4]` selection before temporal evaluation. No classifier, source, backfill, Neon or production mutation occurred.
- **Next:** diagnose only this `08:25` evidence-segment selection limit and define a safe selection contract. No repair is authorized yet.

### Kyiv 08:25 full-history uniqueness accepted
- **Status:** `PROVEN`. **Evidence:** [run 37963714123](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37963714123), final proof commit `9355e17f4d2cacba90401e98b79fa15b7867fd95`.
- The accepted historical loader returned **2,456** canonical Kyiv episodes with **2,456** unique IDs. `2024-08-26 08:25 Europe/Kyiv` matched exactly one episode, `cfd8acaf2ae96fb3ab6508d6`, with canonical/raw interval equality. This proved episode specificity only, not a parser repair.

### Kyiv residual source-eligibility pilot accepted
- **Status:** `SMALL GAIN`. **Evidence:** [run 37955711497](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37955711497), final proof head `26eb3e560481115fb1c9f09f9c984af10c802733`.
- Best tested addition `Kyiv24 + bigkyiv.com.ua` raised candidate-covered positives **31/48 -> 36/48** but left final positives at **5/48**. New uncleared hold promotions: **0**.
- No new source-set freeze was accepted; the frozen **15-family** development baseline remains authoritative.

### Expanded-baseline 43-failure diagnosis accepted
- **Status:** `MIXED — ACCEPTED`. **Evidence:** commit `cb46d7b8232bc3af75c29f40592b731001aed8ea`, artifact `research/kyiv_immutable_expanded_baseline_remaining_failure_diagnosis_2026-10-09.json`.
- On the frozen 15-family baseline, **43/48** known positives remained non-final. Largest first-failure class was relevant frozen evidence outside the source set (**11**). The reported temporal-parser ceiling of **5** was a preliminary potential-repair ceiling and is now superseded by the accepted five-case forensic audit above.
### Human casualty review operator isolated proof accepted
- **Status:** `PROVEN` in isolated GitHub Actions only; **NOT production-activated**. **Evidence:** repair commit `81ef49a8af79123986ac48b5cb0d7e4e2fff4937`, [run 37963256291](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37963256291).
- Synthetic acceptance passed **29/29**, including exact equality with the authoritative **23-city** casualty scope, stale-SHA/concurrency guards, duplicate/idempotency behavior, no scheduled auto-confirm path, and no dashboard/historical mutation.
- GitHub environment `casualty-review-approval` is configured for required human approval by the single repository operator, self-review permitted, administrator bypass disabled. This account-side setting is not repository-versioned.
- The production-intended operator remains `workflow_dispatch`-only and outside `main`; no real candidate has been reviewed by it and no operator production canary has run. Next step is bounded production activation followed by a read-only/INSPECT canary.

### Casualty scheduled publication idempotency accepted
- **Status:** `PROVEN`. **Evidence:** manual publication [run 37916019429](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37916019429), first qualifying later scheduled [run 37930852302](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37930852302).
- The first real Sumy revision published exactly once: September 2026 **3 -> 4**, Sumy total **158 -> 159**. The subsequent scheduled run consumed the published state, observed one confirmed revision, passed casualty aggregation / 23-city QA / production verification, and preserved **4 / 159** with no repeated +1.
- Later scheduled run `37959553608` failed upstream at the UkraineAlarm checkpoint before casualty aggregation; it does not supersede or invalidate the accepted idempotency proof.


### Unit A persistence-payload replay proven
- **Status:** `PROVEN` for the bounded six-field replay and lossless canonical payload construction; A4 **READY TO RESUME**, not yet `PROVEN`. **Evidence:** [run 37957051537](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37957051537), artifact commit `013c2a7593af950fc00178790db668a7d8bfbf9b`, [frozen replay artifact on final proof HEAD `41bec58604420333dc71910ec38f4a785f6b108e`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/41bec58604420333dc71910ec38f4a785f6b108e/research/attack_event_unit_a_bounded_persistence_payload_replay_schema_repair_2026-10-09.json); Git blob `cb0192e6776cce44b056bb88bf5618541f1c9339`, artifact SHA-256 `d28d80e15251fed8aad7367748cda7ea3a75b37f45dcb9cd3b656a11db619317`.
- Twice replayed **1,418** exact frozen decisions: **17,016** existing-A3 field comparisons, **0** semantic mismatches. Recovered all six omitted fields for **1,418/1,418** decisions and **1,559/1,559** repaired memberships; frozen recovered map has **1,418** entries. **1,559/1,559** canonical evidence payloads constructable, with zero construction, canonical-key or formatter mapping failures.
- Original frozen A3 remains authoritative for every field already present; the new map governs only the six previously omitted persistence-payload fields. The former `UNIT_A_SOURCE_ROW_PROJECTION_NOT_LOSSLESS` blocker is resolved offline; the original blocked A4 entry remains below as historical evidence.
- **A4 not resumed; Neon not contacted; A5 not run; production unchanged.** Next: bounded A4 resume with full canonical projection and offline determinism gates; only after PASS run the bounded **READ-ONLY** Neon shadow gap audit and freeze the exact A5 delta if clean. **A5 remains unauthorized.**

### Expanded Kyiv immutable development source set frozen
- **Status:** `FROZEN`. **Evidence:** [freeze commit 7fdcc290](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/7fdcc2903205e8fc489b2eff588332a45cfaca09), [single-file freeze artifact](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/7fdcc2903205e8fc489b2eff588332a45cfaca09/research/kyiv_immutable_development_source_set_expanded_freeze_2026-10-09.json), [acceptance run 37947654494](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37947654494).
- Expanded development manifest SHA-256 `58dbde111229d099413ad03e99be3839557431957c4ac72832b23be8a49bc08e`; **15** source families. **31/48** known positives candidate-covered and **5/48** final-positive, with **43/48** known positives remaining non-final and **zero** new uncleared hold promotions.
- Previous **12-family freeze SUPERSEDED FOR FUTURE DEVELOPMENT EXPERIMENTS** and preserved as historical provenance. The 15-family configuration is now the authoritative **development-only** reference. Production source strategy unchanged; no historical backfill or Neon writes from this freeze.

### EXPANSION-3 authoritative offline acceptance
- **Status:** `PROVEN`. **Evidence:** [run 37947654494](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37947654494), artifact `11624138372`, proof-branch commit `6f237628994c6d6ae1c6a1f50c73069473ce27e7`.
- 67/67 verdict/candidate/outcome equality; **31/48** candidate-covered, **5/48** final-positive, zero new uncleared holds. Expanded manifest SHA-256 `58dbde111229d099413ad03e99be3839557431957c4ac72832b23be8a49bc08e` was emitted to an Actions artifact; **at that acceptance checkpoint**, the expanded repository freeze had not yet been committed. Production unchanged.

### Source-eligibility expansion selected in development
- **Status:** `ACCEPTED` as a **material pilot only**. **Evidence:** [pilot commit b749e019](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/b749e0195c4ec1b2262c998e381a92277a89a5e9), [run 37937223379](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37937223379).
- EXPANSION-3 added `5.ua`, `zaxid.net` and `kyiv.novyny.live` on the same immutable 67-episode corpus. The later acceptance replay supersedes pilot-only performance uncertainty; production unchanged.

### First durable Kyiv immutable development source-set freeze
- **Status:** `FROZEN`. **Evidence:** [commit 2a7b17c](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/2a7b17c9514a43648e22eb795f0f2f7b65c3980f), `research/kyiv_immutable_development_source_set_freeze_2026-10-09.json`.
- Selected **12** safe families, including `war.telegraf.com.ua`; **26/48** candidate-covered and **3/48** final-positive. Manifest SHA-256 `bc77629b7936e02488cd611da1515dc9f9b52db945d5cf334aaa60245ca295ee`. At that checkpoint it was the latest **repository-committed** Kyiv discovery source-set freeze; subsequently superseded by the accepted 15-family freeze.

### Source-dominant failure diagnosis
- **Status:** `PROVEN` for the frozen 12-family corpus. **Evidence:** diagnosis provenance in [expansion pilot proof](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/b749e0195c4ec1b2262c998e381a92277a89a5e9/research/kyiv_immutable_source_eligibility_expansion_pilot_2026-10-09.json).
- **45** known-positive failures remained; `RELEVANT_FROZEN_RESULT_OUTSIDE_SELECTED_SOURCE_SET` was the largest first-failure group (**12**); additional source eligibility had an **11-unique-positive ceiling**, not 11 proven final positives. Production unchanged.

### Immutable development runner established
- **Status:** `PROVEN`. **Evidence:** [run 37916038826](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37916038826), implementation `51c0b8411b59714a33fc1b3e945d262cc2f2499b`.
- Established the repeatable offline classifier proof against frozen discovery/native/normalized evidence. Production unchanged.

### Unit A: membership repair accepted; A4 persistence blocked
- **Status:** `PROVEN` for A3 membership; `BLOCKED` for A4. **Evidence:** [A3 run 37917554992](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37917554992), [A4 run 37936840809](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37936840809), `research/attack_event_execution_unit_a_shadow_persistence_gap_audit_resume2_2026-10-09.json` on proof branch `510b9afc...`.
- A3 matched **1,559** source memberships; A4 could not reconstruct six required classifier decision fields from frozen evidence (`UNIT_A_SOURCE_ROW_PROJECTION_NOT_LOSSLESS`). **A5 never executed**; no database or production writes.

### First human-confirmed casualty production publication
- **Status:** `PROVEN` on production path. **Evidence:** [production updater 37930852302](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37930852302), `site-prod:kyiv-air-alerts-grafana/data/casualties/revisions.csv`.
- Published one human-reviewed **Sumy 2026-09-20** casualty revision (**+1 death**) with stable canonical record identity. The later **normal scheduled-run idempotency** acceptance is still `WAITING`; no second publication is claimed.

### Exact frozen E56 hold clearance
- **Status:** `ACCEPTED` for one exact frozen evidence identity. **Evidence:** [immutable freeze commit 2a7b17c](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/2a7b17c9514a43648e22eb795f0f2f7b65c3980f), embedded forensic reference and text SHA-256 `fd41c256d699bc6eddb46b6f2a2725f8ecbf93df29265917c7ff27fa6242ea07`.
- `e56cdca45ed5b1cd7b0b9746` supports its target episode under the frozen Suspilne text only. Earlier incidental old-blind-row exposure was explicitly disclosed but not used; no clearance was inferred for `f06c52e0ed82b44792ec2ec7`.

## 2026-10-08

### Live raion-proxy canonical identity repair
- **Status:** `PROVEN` in bounded production canary. **Evidence:** [raion grouping artifact](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/8143f497081736b9b36baf1d1b9139575bdb1df7/research/attack_event_raion_proxy_logical_grouping_repair_canary_2026-10-08.json); production run `37798870617`.
- 55/55 logical identities matched across 19 proxy cities; one canonical classification persisted with exact read-back. Prior fragment identity divergence superseded for the tested scope.

### Casualty review/promotion production cutover
- **Status:** `PROVEN`. **Evidence:** [cutover 0c59ccabc](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/0c59ccabc9e75896bc52b8c70142ece77c1f684b), [zero-mutation proof run 37839508214](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37839508214).
- Integrated the human-reviewed candidate-to-confirmed-delta path without automatically confirming a real candidate; actual first real publication followed on October 9.

### Live due-episode scheduling and canonical write
- **Status:** `PROVEN`. **Evidence:** [due-orchestration proof](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/8143f497081736b9b36baf1d1b9139575bdb1df7/research/attack_event_live_due_orchestration_repair_canary_2026-10-08.json); canary run `37690103224`.
- Nine canonical **NO_CONFIRMED_EVENT** classifications were written and read back 9/9 with no duplicate rows; no positive-event publication claimed.

## 2026-10-06

### Kyiv historical 411-control classifier continuity
- **Status:** `PROVEN`. **Evidence:** [run 37529446549](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37529446549), compact continuity summary artifact `11443926832`.
- Preserved **141 STRICT** and **4 SENSITIVITY** accepted reference controls with zero historical hold promotion. Regression continuity does not supply fresh blind validation.

## 2026-10-02

### Kyiv historical V2 evidence formalization
- **Status:** `PROVEN`. **Evidence:** [historical V2 proof](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/e460bc30524deb8abc37923276d78f6dab1450a4/research/historical_v2_formalization_kyiv_proof_2026-10-02.json).
- Normalized 411 retained evidence observations over **2,456** canonical Kyiv episodes; reference outcomes **141 STRICT**, **4 SENSITIVITY**, **266 needs review**, **2,045 no confirmed event**. No incorporation or Neon writes.

## 2026-10-01

### Five-city historical attack-event backfill campaign completed
- **Status:** `PROVEN` campaign completion. **Evidence:** [acceleration state](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/71cb6f6fbe856cc7b96759310fe9cc9c71cc0453/research/historical_attack_event_backfill_acceleration_state.json).
- Historical v2 campaign phase `COMPLETE`, frozen universe **6,863 episodes**; this is separate from the later Kyiv 67-episode discovery-development work.
