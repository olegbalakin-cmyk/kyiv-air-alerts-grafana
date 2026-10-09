# Changelog

Accepted project checkpoints, newest first. This is not the full Git history, a branch inventory, or a retry log. **PROVEN** describes bounded evidence; **FROZEN** additionally requires a durable exact manifest. Development checkpoints below do not change production unless explicitly stated.

## 2026-10-09

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
