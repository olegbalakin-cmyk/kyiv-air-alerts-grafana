# C4-E2 — H1/H2 historical parity closeout

**Recommendation: `C4_PARTIAL`, 2026-10-28.** C4 PASS or PASS_CANDIDATE is not established. Neither the 25 binding-only exceptions nor any database repair is accepted by the owner. Current `site-prod` JSON remains the production publication source.

## Preflight and scope

Read current `main:PROJECT_STATE.md`, `main:CHANGELOG.md`, and C4 closure criterion in immutable `4cc20029466795f16b0c648d84acbf6d50e75c66:research/neon_migration_closure_audit_2026-10-10.json`. C4 requires exact historical canonical IDs and decisions, source memberships and event/current-tip semantics by ID/hash, or **explicitly accepted bounded exclusions**. The accepted 2026-10-28 coordinator checkpoint `2a11a637` governs older chat and research proposals. The binding-only proposal `a653f030` is **not accepted**.

Historical denominators are **H1 = 6,863** and **H2 = 19,542** classifications. They must not be relabeled a count of unique physical alerts. Unit A and live remain separate. We did **not** rerun A5, historical classification or existing accepted exhaustive verdict/QA proofs.

Existing accepted exact evidence: H1 `3d10cb3c` (6,863/6,863 identities, verdicts and QA, zero frozen-vs-Neon missing/extra for these identity checks); `b4b0764d` (6,863 classification key-input authority, 2,340 source-link key-input authority and 119 modeled event key/relationship authority). H2 `c2338794`, `5a640d69` (18/18 city chronology; independent **offline** key calculations for 19,542 classifications, 1,429 source links and 961 events); `7ed2e426` (source membership authority 286 original, 1,067 derivable, 76 replay-only). These accepted historical/producer proofs are not automatically full persisted-row parity.

## Read-only Neon observations

Pinned `green-cake-44216048 / br-bold-mode-b5rub8pq / neondb / ep-calm-rice-b5073ypp`, with `transaction_read_only=on` and `pg_is_in_recovery()=true`. Queries were **SELECT only**; they are independent reads, not a single certified frozen multi-query snapshot.

| Cohort | Checked Neon classifications / unique keys | BOUND / UNBOUND | Unique source-link keys | Unique event keys | Confirmed violations in these bounded checks |
|---|---:|---:|---:|---:|---:|
| H1 | 6,863 / 6,863 | 6,858 / 5 | 2,340 | 119 | 0 |
| H2 | 19,542 / 19,542 | 19,522 / 20 | 1,429 | 961 | 0 |

Each cohort also has unique classification UIDs and historical city/target episode identities, no historical superseding revisions, zero orphan BOUND parents and zero observed broken ACTIVE modeled-event to current-classification/binding links. These are **structural count, identity-uniqueness and internal-Neon relationship checks**. They **do not** prove every historical expected key/value, source-link membership/field, event field or semantic decision is equal to its frozen Git counterpart.

## Historical parity status: four requested indicators

| Cohort | Verified (bounded) | Matches | Differs | Still unproven |
|---|---|---|---|---|
| H1 | All 6,863 exact identity/verdict/QA comparisons already accepted; 6,863 current Neon rows/unique keys, 2,340 links, 119 events structurally examined | 6,863/6,863 frozen identity/verdict/QA; current uniqueness/relational constraints PASS | 0 confirmed in accepted identity/verdict/QA and new structural checks | Exhaustive expected-to-Neon classification **remaining required fields**, source-link exact keys and required nonkey values, event key/current-tip/required-field values |
| H2 | 18/18 accepted city chronology hashes, 19,542/19,542 offline classification key calculations, 1,429/1,429 source, 961/961 event; current Neon count/uniqueness/links structurally checked | All accepted **offline** producer computations; current internal-Neon invariants PASS | 0 confirmed in the new structural checks | Complete frozen-to-Neon exact 19,542 target episode identities, classification keys, per-row verdict/QA/required fields, 1,429 exact source-link memberships and fields, 961 modeled event keys/tips/fields |

**Do not equate “verified” with fully semantically certified:** H2's 19,542 original key computations were proven against independent Git producer inputs, **not** matched one-for-one against current Neon. Prior H1 verdict/QA proof need not be repeated.

## Exactly 25 proposed exceptions — parent matching ONLY

The accompanying `c4_historical_parity_residuals.json` enumerates precisely **25 unique classification UIDs**, each tagged `PENDING_OWNER_ACCEPTANCE` (H1 5; H2 20; Kyiv 18, Lviv 3, Kharkiv 2, Sumy 1, Zaporizhzhia 1). New UID-directed Neon SELECTs show **25/25 exact frozen classification key matches**, **25/25 expected verdict matches**, **25/25 `UNBOUND` with NULL parent**, **25/25 matching expected active-event UID sets**, **14 current source-link records** and **2 ACTIVE modeled events**. A complete original-frozen-to-Neon required-field comparison for those 14 source links has **not** been demonstrated.

Verdicts in the 25: **16 NO_CONFIRMED_EVENT**, **7 NEEDS_REVIEW**, **1 STRICT_EVENT_POSITIVE**, **1 SENSITIVITY_EVENT_POSITIVE**. Preserve two ACTIVE event UIDs: Zaporizhzhia `ef34834b-0513-4351-8839-d866a0e76e99`, Kharkiv `dc3a63ec-d9f8-412c-b0a1-09dd9398b27b`.

The 18 Kyiv original municipal `historical_episode_id` strings differ by design from the Neon deterministic target episode IDs. The accepted frozen exact-interval dual-ID crosswalk governs this; direct string inequality is **not 18 new anomalies**. All 25 current temporal canonical candidates are **research-only**, never accepted foreign keys or proof of exact original historical parent survival. Exact original parent admission remains **0/25**, without authorizing duplicates, fuzzy matching or boundary retimestamping. Kharkiv case #6 retains the distinct 7h15m50s source-end conflict; do not silently select a source. Owner acceptance of any proposed exception remains **0/25**.

The proposed exceptions would waive **only exact canonical-parent matching**, not verdict, QA, source evidence, event association, tip, denominator inclusion or unchanged publication metrics. Future Neon-backed readers must not silently drop these 25 through an `INNER JOIN` on NULL parent IDs.

## Residual accounting — do not manufacture zero

**Confirmed non-parent missing = 0, extra = 0, duplicate key = 0, semantic mismatch = 0 in the checks actually performed and accepted.** The exact **global** non-exception missing/extra/mismatch count remains **`NOT_CERTIFIED`**, not zero: missing complete frozen-to-Neon row-level anti-joins prevent an accurate global number. Specifically, H1's accepted field-input authority and H2's accepted exporter calculations do not independently certify all persisted source-link/event required fields. The 76 H2 replay-only memberships are an **authority/provenance uncertainty**, **not** 76 observed Neon discrepancies. There is **no affirmative evidence** justifying mass backfill.

The bounded minimum outstanding comparison, without repeating accepted full checks:

1. H1: exact classification UID/key to frozen expected remaining *required classification fields*; exact 2,340 source link key/member/field tuples and 119 modeled-event key/tip/field tuples.
2. H2: exact deterministic target episode ID, classification key, verdict/QA and required fields for 19,542; exact 1,429 source membership/key/field tuples and 961 event key/tip/field tuples; preserve 18 Kyiv municipal-to-target crosswalk domain and 76 replay-only provenance labels.
3. Independently confirm full relevant source → frozen producer → Neon tuple equality and current `site-prod` publication metric non-loss, especially both ACTIVE events tied to UNBOUND classifications. Report every discovered mismatch with exact UID, key, field, frozen blob and action. Apply only minimal **separately authorized** record-level fixes if contradictions exist.
4. If all these requirements become proved and global unexpected missing/extra/mismatch reaches certified zero, present exactly the 25 pending parent-only exceptions for explicit owner consent. The executor may then recommend `C4_PASS_CANDIDATE`; it cannot approve exceptions or declare C4 PASS.

## Separate Unit A and live dependencies

**Unit A:** previously accepted full-manifest snapshot PASS: 1,713 classifications + 1,559 links + 10 events = 3,282, zero snapshot semantic mismatches; A5 was committed and **must not rerun**. Concurrency proof ceiling remains separate.

**Live/C3:** normal due-work completion/live queue integration and safe reader/export flow remain separate migration gates, not solved by historical 25-case adjudication. No Neon authority activation, live workflow restart, production deployment, backfill, `main` documentation change, or `site-prod` JSON rewrite is authorized here.

## Decision

`C4_PARTIAL`. There is accepted, substantial historical evidence, including **all 6,863 H1 identity/verdict/QA outcomes**, accepted independent deterministic key-input authority for H1/H2, and a clean current **26,405 historical classification structural inventory** (cohort counts combined *as classification records only*). However **full C4 semantic persisted parity of those 26,405 is not yet proven**, nor are the 25 parent-only exceptions accepted. Zero globally unexplained differences cannot honestly be certified from these observations. No confirmed defect warrants broad remediation. Read-only research checkpoint only.
