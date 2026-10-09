# Project State

Last updated: 2026-10-09  
Last updated commit: PENDING_INITIAL_DOCUMENTATION_COMMIT

> This file records the **accepted coordination state** of the repository, not a new technical acceptance. Read it before proposing work in another ChatGPT chat. Detailed authority remains in the linked immutable commits, workflow runs and proof artifacts; if this summary conflicts with a more specific accepted artifact, that artifact governs. **Never infer production activation from a development-only proof.** Update this file only after an accepted checkpoint.

## 1. Project purpose

The original Kyiv Grafana air-alert dashboard has grown into a repository with distinct tracks: public air-alert collection and presentation; alert-to-attack classification and live multicity processing; historical attack-event reconstruction and a separate Kyiv historical-discovery development effort; human-reviewed civilian-casualty discovery and promotion; and bounded canonical persistence/Neon work. The original dashboard documentation is [`kyiv-air-alerts-grafana/README.md`](kyiv-air-alerts-grafana/README.md). It remains the dashboard manual, not the cross-track project status.

## 2. Read this first

- **Production-safe:** `main` drives scheduled data workflows; `site-prod` contains the published website dataset. A confirmed Sumy casualty revision is present in `site-prod`. Live 23-city attack-event persistence has **bounded** Neon canary proofs, not an unrestricted end-to-end guarantee for every attack type.
- **Development-only:** the accepted, repository-committed immutable Kyiv discovery source set remains **12 families**. Its result is **26/48** known positives candidate-covered and **3/48** final-positive; it is not production classifier data.
- **Newer Kyiv experiment:** 15-family EXPANSION-3 passed the authoritative **offline** 67-episode acceptance replay on 2026-10-09. Its manifest digest exists in the Actions proof artifact, but **no corresponding expanded single-file freeze is committed in the inspected proof branch**. Acceptance replay **PROVEN**; promotion to the repository's frozen development baseline **WAITING**.
- **Historical work:** the older, separate **five-city** historical backfill campaign is `COMPLETE` (6,863 frozen episodes). **No new Kyiv 67-episode historical-discovery backfill has been started by the immutable development tasks.** Do not conflate these campaigns.
- **Independent validation:** **NOT READY**. The earlier blind cohort was consumed and must not be reopened for tuning or passed off as a fresh holdout. Future independent validation needs a fresh cohort.
- **Neon:** live canaries document bounded canonical writes and read-back. The complete Neon migration state is **STATE NOT DURABLY ENCODED IN REPOSITORY**; the separate database migration must be checked in its own track. Documentation creates no Neon writes.
- **Active blockers:** Unit A historical shadow persistence is **BLOCKED** by six non-frozen classifier decision fields needed for a lossless evidence payload. Casualty scheduled-run idempotency is **WAITING** for a qualifying normal run after the first publication.

Status vocabulary: **PROVEN** = directly observed bounded behavior; **FROZEN** = exact version and provenance committed; **PRODUCTION** = authoritative production path; **BLOCKED** = acceptance gate failed; **WAITING** = future proof/event absent; **SUPERSEDED** = replaced by a later accepted state; **HISTORICAL REFERENCE** = preserved earlier authority. A successful GitHub Action does not by itself establish a repository freeze or general production readiness.

## 3. Track status table

| Track | Current status | Production? | Authoritative evidence | Next action |
| --- | --- | --- | --- | --- |
| Air-alert feeds and public 23-city dataset | PRODUCTION, routine updates | Yes, `main` / `site-prod` | [Production updater run 37930852302](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37930852302); `site-prod` revision ledger | Monitor regular scheduled publication; do not rewrite source-bridge semantics |
| A. Live 23-city attack-event processing | PROVEN bounded live canaries; earlier failed parent canary superseded | Production code path, narrowly evidenced | [Due-orchestration proof](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/8143f497081736b9b36baf1d1b9139575bdb1df7/research/attack_event_live_due_orchestration_repair_canary_2026-10-08.json); [raion proxy proof](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/8143f497081736b9b36baf1d1b9139575bdb1df7/research/attack_event_raion_proxy_logical_grouping_repair_canary_2026-10-08.json) | Observe normal live evidence/read-back; investigate only a demonstrated new failure |
| B. Kyiv historical classification reference | PROVEN / HISTORICAL REFERENCE | No new deployment from the proof | [V2 formalization proof](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/e460bc30524deb8abc37923276d78f6dab1450a4/research/historical_v2_formalization_kyiv_proof_2026-10-02.json); [continuity run 37529446549](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37529446549) | Preserve the 411-control continuity contract |
| C. Kyiv immutable historical discovery | 12-family **FROZEN**; 15-family acceptance **PROVEN**, freeze **WAITING** | **No; development-only** | [Freeze commit 2a7b17c](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/2a7b17c9514a43648e22eb795f0f2f7b65c3980f); [expansion acceptance run 37947654494](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37947654494) | Commit the single-file EXPANSION-3 development freeze from the already-successful replay, without a new replay |
| D. Hold safety | Exact frozen E56 clearance; F06 remains legacy/pre-existing | Development controls only | [12-family freeze artifact](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/2a7b17c9514a43648e22eb795f0f2f7b65c3980f/research/kyiv_immutable_development_source_set_freeze_2026-10-09.json) | Retain exact-evidence guard; do not infer broader adjudication |
| E. Independent validation and blind | BLOCKED / NOT READY; old blind cohort consumed | No | [Freeze artifact, blind procedure note](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/2a7b17c9514a43648e22eb795f0f2f7b65c3980f/research/kyiv_immutable_development_source_set_freeze_2026-10-09.json) | Fresh independent cohort only after development freeze gate |
| F. Historical backfill | Five-city v2 campaign COMPLETE; new Kyiv discovery backfill NOT STARTED | Separate historical campaign only | [Frozen acceleration state](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/71cb6f6fbe856cc7b96759310fe9cc9c71cc0453/research/historical_attack_event_backfill_acceleration_state.json); [scheduled read-back run 37931720136](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37931720136) | No new backfill from this documentation task |
| G. Casualty discovery/review/publication | PRODUCTION first real publication PROVEN; scheduled idempotency WAITING | Yes, published ledger on `site-prod` | [Cutover commit 0c59cca](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/0c59ccabc9e75896bc52b8c70142ece77c1f684b); [production run 37930852302](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37930852302) | Read-only audit of first qualifying *later* routine updater run |
| H. Unit A historical projection / Neon | A3 membership PROVEN; A4 persistence projection **BLOCKED**; no A5 write | No; shadow-only | [A4 artifact on isolated branch](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/510b9afcf48d1644cdd9af0c7a135d8f59afd486/research/attack_event_execution_unit_a_shadow_persistence_gap_audit_resume2_2026-10-09.json); [run 37936840809](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37936840809) | Establish lossless source-evidence decision payload provenance before A5 |
| Neon migration overall | PARTIALLY evidenced; complete migration **STATE NOT DURABLY ENCODED IN REPOSITORY** | Bounded live canaries only | [Shared live persistence canary](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/8143f497081736b9b36baf1d1b9139575bdb1df7/research/attack_event_shared_live_production_persistence_canary_2026-10-07.json); subsequent due/raion proofs above | Refer to separate database coordination track for full migration |

### A. Live processing: what actually passed

An early shared 23-city production persistence canary failed before classification writes because a canonical alert-episode parent was missing. Its [failure artifact](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/8143f497081736b9b36baf1d1b9139575bdb1df7/research/attack_event_shared_live_production_persistence_canary_2026-10-07.json) is historical diagnosis, **SUPERSEDED** by later targeted repairs, not evidence that later live processing is still entirely blocked.

The [due-orchestration canary](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/8143f497081736b9b36baf1d1b9139575bdb1df7/research/attack_event_live_due_orchestration_repair_canary_2026-10-08.json) wrote **9** canonical classifications with **9/9** Neon exact read-back and zero duplicate classifications. All nine were `NO_CONFIRMED_EVENT`; no positive-event publication is proven by that test. The [raion-proxy canary](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/8143f497081736b9b36baf1d1b9139575bdb1df7/research/attack_event_raion_proxy_logical_grouping_repair_canary_2026-10-08.json) later proved **55/55** identities matched across 19 proxy cities and **1/1** canonical classification read-back in its production canary. It corrected overlapping-fragment Sumy identity without changing the pinned classifier, discovery or durable-live eligibility rules. Do not reopen already-closed parent-ordering and due-scheduling failures without contradictory current evidence.

A separate **Unit A** track concerns historical shadow persistence, **not** the healthy live canary path. A3 established **1,559** exact source membership occurrences; [A4 resume2](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/510b9afcf48d1644cdd9af0c7a135d8f59afd486/research/attack_event_execution_unit_a_shadow_persistence_gap_audit_resume2_2026-10-09.json) stopped on `UNIT_A_SOURCE_ROW_PROJECTION_NOT_LOSSLESS`. Six required fields were absent from frozen A3 decisions: `air_defense_context`, `candidate_evidence`, `controlled_blast_event_segments`, `sensitivity_basis`, `single_episode_day_inference`, `strict_explosion_evidence`. **A5 did not run; no Neon transaction or production mutation occurred.** Do not synthesize these fields or borrow them from another classifier run. The cross-branch authority overlap audit was [SAFE](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/f51d74a9e0810a715720e6a61e1ec14291d6ad20/research/attack_event_unit_a_crossbranch_authority_overlap_audit_2026-10-09.json) for the then-current state; that does not authorize later Kyiv backfill overlap.

### B. Frozen Kyiv historical reference, separate from discovery optimization

The historical V2 formalization reports **2,456 canonical Kyiv alert episodes**, with **145 accepted event-positive** outcomes: **141 STRICT**, **4 SENSITIVITY**, **266 needs review**, and **2,045 no confirmed event**. It normalized **411** retained evidence observations. [Authoritative replay run 37529446549](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37529446549) reproduced all **141 STRICT** and all **4 SENSITIVITY** controls with no historical hold promotions. Its compact summary artifact is `kyiv-411-classification-continuity-summary-37529446549`; do **not** open the detailed blind ledger for source-set tuning. The pinned classifier identity used in frozen development is commit `71cb6f6fbe856cc7b96759310fe9cc9c71cc0453`, blob `778469b74c2aa807d851cf2c2ee35cf4aa785589`.

These **2,456 / 145** historical reference totals are **not** the denominator in the new development sample. Development uses a frozen **67-episode** cohort: **48 known positives** and **19 holds**. A 411-episode continuity replay is a regression check; it is neither a new validation cohort nor a production backfill.

### C. Immutable development discovery: accepted sequence

1. Earlier source-set and Variant A investigations used evidence snapshots that cannot be compared causally to the new immutable corpus. The [Variant A development freeze/diagnosis](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/2a7b17c9514a43648e22eb795f0f2f7b65c3980f/research/kyiv_historical_source_set_variant_a_freeze_2026-10-09.json) remains provenance, not the selected current freeze.
2. [Immutable runner 37916038826](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37916038826) completed successfully at implementation commit `51c0b8411b59714a33fc1b3e945d262cc2f2499b`. The immutable discovery/native/normalized hashes are in section 4.
3. Commit `2a7b17c9514a43648e22eb795f0f2f7b65c3980f` froze a safe **12-family** source set including Variant A additions and `war.telegraf.com.ua`. Selected manifest SHA-256: `bc77629b7936e02488cd611da1515dc9f9b52db945d5cf334aaa60245ca295ee`. Final: **26/48 candidate-covered**, **3/48 classified positive**, **zero newly uncleared hold promotions**.
4. The immutable remaining-failure diagnosis, cited in the [expansion pilot artifact](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/b749e0195c4ec1b2262c998e381a92277a89a5e9/research/kyiv_immutable_source_eligibility_expansion_pilot_2026-10-09.json), records **45** remaining known-positive failures. Largest first-failure class: `RELEVANT_FROZEN_RESULT_OUTSIDE_SELECTED_SOURCE_SET` (**12** cases). Demonstrated source-family eligibility lever ceiling: **11** unique positives. This is diagnosis, not a promise of 11 successful classifications.
5. [Pilot 37937223379](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37937223379), recorded at commit `b749e0195c4ec1b2262c998e381a92277a89a5e9`, found the **material** EXPANSION-3 combination: `5.ua`, `zaxid.net`, `kyiv.novyny.live`. **31/48** candidate-covered, **5/48** final-positive, **0** newly uncleared hold promotions. It was explicitly **provisional**.
6. **Latest checkpoint:** [authoritative offline acceptance run 37947654494](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37947654494) completed **SUCCESS**, reporting `ALL_ACCEPTANCE_GATES_PASS`, **67/67** episode-verdict, candidate-set and classifier-outcome equality, and expanded-manifest SHA-256 `58dbde111229d099413ad03e99be3839557431957c4ac72832b23be8a49bc08e`. Its Actions artifact `kyiv-expansion3-authoritative-acceptance-proof` (artifact ID `11624138372`) contains the bounded acceptance result. The workflow explicitly checked for **no repository-file changes**. As of this audit, proof branch `kyiv-expanded-development-freeze-acceptance-proof-2026-10-09` remained at `6f237628994c6d6ae1c6a1f50c73069473ce27e7`, without a committed new development manifest. **Do not label the 15-family source set FROZEN until that single-file freeze is durably persisted and verified.** Production unchanged.

The **next exact Kyiv discovery task** is now to **persist and verify the accepted EXPANSION-3 single-file development freeze from the successful run/artifact, without rerunning discovery or classification**. It replaces the earlier task “complete acceptance replay,” which is already proven.

### D. Hold safety and provenance

- `e56cdca45ed5b1cd7b0b9746`: candidate `daa340c00d22f5c8fc538510` was cleared **only for the exact frozen Suspilne National evidence**, extracted-text SHA-256 `fd41c256d699bc6eddb46b6f2a2725f8ecbf93df29265917c7ff27fa6242ea07`. The frozen proof states that this evidence supports the target episode; it is not an open-ended clearance for other URLs, text or classifiers. The original standalone forensic artifact was **not copied** into the examined freeze branch; the freeze embeds the accepted clearance reference.
- Procedural qualification: an earlier forensic session **incidentally displayed old blind-labelled rows**, though they **were not used** to reach the forensic decision. Do not repeat this exposure.
- `f06c52e0ed82b44792ec2ec7`: a **pre-existing baseline positive hold**, associated with candidate `7e17816122c34aed4440a768`; the earlier source-set pilot said new evidence supports *reopening historical review*. It is **not** a fresh forensic clearance and must not be silently adjudicated or newly promoted.

### E. Independent validation

The old blind cohort is **CONSUMED**. It cannot serve again as independent evidence or be inspected for tuning, threshold selection or retrospective “blind” confirmation. Existing continuity checks are regression evidence. A new independent cohort is required after the development configuration has been durably frozen; there is no accepted fresh validation in this repository.

### F. Historical backfill boundaries

[Campaign state](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/71cb6f6fbe856cc7b96759310fe9cc9c71cc0453/research/historical_attack_event_backfill_acceleration_state.json) records `historical-attack-events-v2-2026-09-27` as **COMPLETE**, covering **6,863 frozen episodes** across its older **five-city** scope. Last successful progress was recorded 2026-10-01; scheduled [run 37931720136](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37931720136) on 2026-10-09 inspected the COMPLETE phase and committed **zero** new batches. This work is separate from the current Kyiv 67-episode discovery source-set effort, for which **NO production backfill has been authorized or run by these proofs**. Avoid an unqualified “historical backfill = NO” statement: it would erase the completed separate campaign.

### G. Casualty pipeline

Multicity casualty candidate discovery and its human review queue are on `multicity-wip-2026-09-16`. The review/promotion path was tested in isolation and integrated at production cutover commit `0c59ccabc9e75896bc52b8c70142ece77c1f684b`; the [isolated cutover proof run 37839508214](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37839508214) passed without promoting candidates. A **single** human-reviewed real candidate `a25952a45587fdc555fbbb43` was then confirmed for **Sumy, attack date 2026-09-20, deaths_delta +1**. The canonical `site-prod` `kyiv-air-alerts-grafana/data/casualties/revisions.csv` has one confirmed row, record ID `casualty:sumy:2026-09-20:fpv-double-strike-zarichnyi-apartment-entrance`; production updater [37930852302](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/37930852302) succeeded and the `site-prod` publication exists. The `main` and WIP nested `revisions.csv` files are still header-only and must not be mistaken for the published `site-prod` ledger.

**Post-publication scheduled idempotency remains WAITING:** no *later qualifying normal scheduled production updater* was established at audit time. Its next bounded action is **read-only inspection of the first such run**, proving that this exact record stays single and totals do not increase again. No manual dispatch, second promotion, review-queue modification or repair is authorized by this document.

### H. Neon / canonical persistence

The inspected artifacts name Neon project `green-cake-44216048` and branch `br-bold-mode-b5rub8pq` for bounded live canonical read-back/shadow operations. Earlier shared canary wrote zero classification rows; later due/raion canaries proved exact bounded persisted read-back. The Unit A A4 branch did **not** connect to Neon and is blocked before A5. Nothing here proves full historical migration, all schemas, or final rollout across other tracks. **Neon migration is coordinated in a separate track; complete current migration state is not durably encoded in this repository.** All documentation work is repository-only and writes no database state.

## 4. Authoritative identities

| Item | Identity |
| --- | --- |
| Repository coordination base, inspected | `main` at `8143f497081736b9b36baf1d1b9139575bdb1df7`; `site-prod` at `e71412503f27c3301d30bff841e449c901138e33` |
| Shared authoritative classifier | Commit `71cb6f6fbe856cc7b96759310fe9cc9c71cc0453`; blob `778469b74c2aa807d851cf2c2ee35cf4aa785589` |
| Immutable development runner | Implementation `51c0b8411b59714a33fc1b3e945d262cc2f2499b`; run `37916038826` |
| Immutable corpus SHA-256 — discovery | `fc1e184741c8409ce634015771a9484de8cfd8230037be56e3d8970d0178e5cc` |
| Immutable corpus SHA-256 — native | `bcfdedba186b58671dab7c3c1bd33dc8ec0f2772c8b9f9c3bf053c7d64cff858` |
| Immutable corpus SHA-256 — normalized | `e5790301a8d17b9997a3dbdfb71651e486de8ba6a4c39a552043754805e7ce2d` |
| Selected committed 12-family development freeze | Commit `2a7b17c9514a43648e22eb795f0f2f7b65c3980f`; manifest SHA-256 `bc77629b7936e02488cd611da1515dc9f9b52db945d5cf334aaa60245ca295ee` |
| EXPANSION-3 pilot | Commit `b749e0195c4ec1b2262c998e381a92277a89a5e9`; run `37937223379` |
| EXPANSION-3 accepted offline replay, **not yet repo-frozen** | Proof branch head `6f237628994c6d6ae1c6a1f50c73069473ce27e7`; run `37947654494`; artifact `11624138372`; manifest SHA-256 `58dbde111229d099413ad03e99be3839557431957c4ac72832b23be8a49bc08e` |
| Casualty production review/promotion cutover | `0c59ccabc9e75896bc52b8c70142ece77c1f684b` |
| First real casualty publication | `site-prod` revisions row; updater `37930852302` |
| Unit A A4 blocked proof | Run `37936840809`; artifact on head `510b9afcf48d1644cdd9af0c7a135d8f59afd486` |

SHA-256 values labelled “corpus,” “manifest” or “evidence” are **content hashes**, not Git commit addresses. Production branch heads are point-in-time observations and can advance with scheduled updates.

## 5. Do not reopen without new accepted evidence

- Do not treat old blind labels as fresh validation, inspect them again for tuning, or silently change the positive/hold reference truth.
- Do not recreate missing old Variant A pages and present them as the original frozen native evidence; do not make causal claims from mutable cross-corpus differences.
- Do not turn search snippets into native-page proof where the retained full page governs; do not invent classifier decision fields missing from frozen Unit A outputs.
- Do not use the EXPANSION-3 pilot or successful offline acceptance as proof that production was changed. The committed 12-family freeze remains the reference until an expanded freeze is durably recorded.
- Do not reopen repaired live parent ordering, due-episode selection or raion grouping without a new failing production observation.
- Do not backfill Kyiv historical discovery or persist Unit A/A5 until their own independent safety gates pass. Do not mutate live/historical/casualty state from proof branches.
- Do not auto-confirm casualty candidates or replay the first confirmed death as a new +1 revision.

## 6. Active next tasks

- **Kyiv immutable discovery —** persist one authoritative EXPANSION-3 development source-set freeze using successful acceptance artifact `11624138372` and manifest SHA-256 `58dbde...`, verify exact provenance, hold safety, and repo-only mutation. **Do not rerun the already-proven 67-episode acceptance.**
- **Unit A historical persistence —** bounded, read-only provenance/representability repair for the **six missing frozen A3 decision fields**; prove the source-evidence payload lossless before attempting A5. No substitute fields, Neon writes, or classifier reruns under a documentation task.
- **Casualty production idempotency —** when the first qualifying normal updater run *after* production publication exists, audit its inputs, canonical ledger and output read-only for one-time effect. Until then status is `WAITING`.

The live path has no new authorized repair solely on the strength of earlier, superseded failures; monitor its ordinary runs. Independent Kyiv validation awaits a new cohort after freeze. Overall Neon migration decisions remain with the separate database track.

## 7. How another ChatGPT chat should use this file

1. Read `PROJECT_STATE.md` before proposing work, then `CHANGELOG.md` for accepted transitions.
2. Verify the exact referenced proof artifact, immutable identity and branch head for the **one track** being changed; this file is a pointer, not proof-by-itself.
3. Act on one bounded failure class and state permitted mutations and forbidden changes explicitly.
4. Separate **production**, **development**, **historical reference**, **backfill** and **human-reviewed casualty** evidence.
5. Update `PROJECT_STATE.md` only after an accepted, reproducible checkpoint.
6. Append to `CHANGELOG.md` only for an accepted state transition; omit routine workflow attempts and debugging retries.
