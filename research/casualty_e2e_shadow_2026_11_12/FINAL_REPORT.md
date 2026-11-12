# CASUALTY-E2E-SHADOW-2026-11-12 — final research report

**Decision: PARTIAL_SHADOW_PASS. NOT END_TO_END_PASS.** No casualty publication is authorized.

## Physical execution and immutable provenance

- Research Draft PR: [#105](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/105), stacked on the unmerged research reviewer branch `research-casualty-cumulative-total-2026-11-11`; **not a production merge candidate**.
- First successful physical [Actions #43290541402](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43290541402) at commit `28f4a580fd359d84df7de4f27ecfd5dd0f98e0db`: workflow SUCCESS, generator source-to-output proof PASS, idempotent replay PASS.
- [Artifact #13976997483](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43290541402/artifacts/13976997483): ZIP SHA-256 `7d0c4ede362288096ec4f31fecf33e817e177fa94717da5f47ee46cd2053ca52`, independently downloaded and rehashed **MATCH**. Includes JSON per candidate, per targeted attack, rejected/blocked ledger, generator overlay probe, input/output SHA manifest, first and replay runs and verdict.
- Frozen WIP branch SHA `43b580491d54d1df3bd84a0ae59a6987f8ea4d03`; frozen production `site-prod@d0a7d22de2828c93236562cccc9d2e68c6a66e3d`; frozen [PR #88](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/88) source-group matrix `34bc539d0c7abb8af4f699b2e2c9ecec4b668397`.
- Previously authorized original-article [artifact #13870872313](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144/artifacts/13870872313): evidence JSON SHA-256 `84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df`; retained 10 October Suspilne article text SHA-256 `011894b7c4bd906dcfd0c5d2f7cef07a932976ca313220fa9089999264feb259`.
- PR #102 previously approved HTTP [artifact #13963708531](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43261676781/artifacts/13963708531): `capture_receipts.json` SHA-256 `4c21321b8a75d57f60efc97f581e89604eaa03289bb64bfba26e491ac83a203b`; 14 source responses recorded, **no original response body retained**. Original HTTP 200 and original article URL are not evidence of the described casualties.

## Results: actual retained evidence, not invented event facts

| Measure | Verified result |
|---|---:|
| Monitored city configuration | 23 |
| Cities with WIP candidates in frozen queue | 21 |
| WIP candidates processed | 1,682 |
| Candidates AUTO_READY | **1** |
| Candidates NEEDS_REVIEW | **1,681** |
| Candidates REJECTED | **0** (no definitive independent exclusion evidence) |
| Distinct specifically targeted attack/publication clusters | 6 |
| Clusters AUTO_READY | 1 |
| Clusters blocked by missing original source text | 5 |
| New proposal records | **1**, Zaporizhzhia 2026-10-10 |
| First-run shadow increment for the proven event | **+23** |
| Second-run new proposals with prior reservation | **0** |
| Production generator dedup and city overlay | **PASS in isolated copy** |
| Production or live WIP writes / new publisher HTTP | **0** |

The 1,681 NEEDS_REVIEW candidates are **not** 1,681 independently established attacks. Of 1,682 queued candidates, 1,680 have no retained original article factual text in this bounded replay; one source-backed explicit military/ambiguous case and one separate source-backed region/multistrike case also remain unconfirmed. The five PR #102 clusters cover 11 candidate IDs and all remain `BLOCKED_SOURCE_CONTENT`. The unobserved 2 of 23 monitored cities have no candidates in this snapshot, which is **not** evidence of zero deaths.

### Attack-by-attack evidence decisions

| Event/cluster | Evidence-backed result | Decision |
|---|---|---|
| Zaporizhzhia **10 October** 2026, morning KAB guided-bomb attack | Preserved Suspilne source; DSNS attribution; definite **cumulative** updates 18 → 20 → **23**; attack city/date/air status; existing site-prod Zaporizhzhia October monthly row absent, and zero confirmed Zaporizhzhia revision rows; **baseline_credited=0** | **AUTO_READY**, exactly one +23 shadow proposal |
| Zaporizhzhia **18 October**, drone, 1 death in PR #102 source lookup | Publisher and police HTTP transport receipts only, full text not retained for this run | NEEDS_REVIEW / BLOCKED_SOURCE_CONTENT |
| Zaporizhzhia **22 October**, 2 → 3 later update | Three original article URLs, police receipt, no archived original text to verify 2 vs 3 and same-event identity; 2+3 is never applied | NEEDS_REVIEW / BLOCKED_SOURCE_CONTENT |
| Zaporizhzhia **5 October** possible hospital death, published 26 October | Two matching candidates point to a shared source, no preserved text/late-death official confirmation and earlier credit assessment | NEEDS_REVIEW / BLOCKED_SOURCE_CONTENT |
| Zaporizhzhia **26 September**, 2 deaths in source lookup | Three candidate receipts; September monthly baseline already contains 4 deaths with coverage only through Sep 18: per-incident allocation remains unproven | NEEDS_REVIEW / BLOCKED_SOURCE_CONTENT + baseline credit uncertainty |
| Zaporizhzhia **27 September**, 1 death in source lookup | Two candidate receipts; retained source text absent and attack-level September credited allocation unknown | NEEDS_REVIEW / BLOCKED_SOURCE_CONTENT + baseline credit uncertainty |

These facts about September/October 18/22/5 are **independent PR #102 research findings**, **not facts extracted by the new pipeline**. The pipeline therefore leaves `attack_date`, `confirmed_total` and `new_increment` null for all five blocked clusters in its machine-produced attack-decision JSON.

### Positive adapter proof and exact generator

The single generated Zaporizhzhia 10 October candidate row contains the real production keys `incident_id`, `count_kind=cumulative`, `baseline_credited=0`, `identity_proof=sha256:...`, `credited_proof=sha256:...`, `candidate_ids`, `source_url`, date and timezone-stamped observation. The contract uses **total 23**, not 18+20+23; the generator computes effective +23 once. Identity and prior credited proofs are immutable hashes of retained source/incident and frozen manifest, monthly CSV and revision ledger, respectively.

The exact pinned site-prod `update_casualties.py` was copied to a private runner temporary folder; the actual `reconcile_confirmed_revisions()` and `apply_city_revision_overlay()` were run against **private copied `revisions.csv`**, not against live data. The isolated October Zaporizhzhia month went **0 → 23**; other 22 city objects hash-identical, and the original dashboard/queue/ledger/source inputs unchanged. This is a generator contract validation, **not** permission to show 23 as a full October month: October remains **COVERAGE_INCOMPLETE**.

Replay passes the prior proposal as an explicit reservation rather than pretending to have credited production. Exactly **0** new rows are generated on replay, with unchanged original ledger and no remote write.

### Defensive tests

Unit tests use explicitly artificial **negative-only safety inputs**, never as casualty factual evidence: absent original body despite HTTP 200; missing response SHA; same-event cumulative 2 → 3 **not 5**; distinct attacks in the same city/date; cross-incident reuse of one candidate; injuries not deaths; attempt to credit an attack inside unallocated monthly baseline; unsafe output path. These are code-guard tests, not new positive attestations.

## Blockers and next steps

**Last material E2E blocker:** PR #102 receipts do not preserve the **original text** of the 11 target items or four official confirmations. An HTTP checksum is not a factual excerpt. No new unlimited publisher HTTP is authorized. New retained, attributable factual text with proof hashes is needed for the five clusters, including date, exact city-vs-oblast, weapon, specific incident, death-count semantics, civilian status and independently linked official corroboration. A source ingestion policy limited to approved/previously retained evidence is required before this can operate unattended.

**Additional distinct blocker:** September's 4 pre-existing monthly deaths are not mapped to individual 26/27 September incidents. Even if original texts become available, baseline allocation must first be independently proved to avoid double credit. For the 5 October late-death scenario, independently verified later official confirmation and original event credits are mandatory.

**Operational limitation:** This draft is a bounded, pinned offline **shadow proof**, not a live autonomous evidence fetcher or an integrated recurring unattended 23-city review stage. It reuses the old research reviewer, production generator and a frozen WIP queue but still requires an authorized input acquisition process and a separate future decision to integrate into a regular workflow. No new architecture, production data writes, CI secret access for publisher capture, frontend changes, or publication gate activation were added.

## Reproduce

The research-only workflow `.github/workflows/research-casualty-e2e-shadow.yml` runs on push to `research-casualty-e2e-shadow-2026-11-12`. It checks out three immutable Git refs, restores two previously approved **GitHub Actions** archives (not publisher HTTP), verifies SHA-256, executes `test_pipeline.py`, runs `pipeline.py` twice with isolated snapshots and a reserved-proposal JSON, verifies strict results using `verify_proof.py`, and uploads the 15-file shadow-only proof bundle. Workflow has only `contents: read`, `actions: read`; it does not invoke C2, Neon or Netlify.

**Release decision:** maintain `SHADOW_ONLY`. **Do not merge, deploy, publish a monthly total or record deaths.** `END_TO_END_PASS=false` is enforced even for the successful partial case.
