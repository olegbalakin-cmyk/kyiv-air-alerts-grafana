# WORK J — casualty parser diagnostic and evidence retention

**Scope:** Research-only; isolated branch `research-casualty-workj-fact-retention-2026-11-13` based on strict Work I `da49571a9e22e2e1e62a2842f902f984cbd0ab10`. No merge, site deployment, WIP, C2, Neon, casualty JSON, or source HTTP.

## Real transport evidence (immutable prior run)

- [PR #118](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/118), live launch `fbc721e79c3cec16bd584431dbcd6d9b18b6163f`.
- [Actions #43405970445](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405970445) SUCCESS: 10/10 status 200, 10 GET, no redirects; six publisher originals / seven candidate bindings and four police originals; zero structured reports and credits.
- [Artifact #14027391709](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43405970445/artifacts/14027391709), independently verified ZIP SHA-256 `d43e81484c043d45a9ebee7435f041207303060590fb5ba0687bbaa1d9205bf3`.
- **Article bodies were not retained.** Per-article parser rejection cannot be reconstructed from the receipts, titles, snippets or SHA.

## Proven code-level defects

1. Work E's HTTP capture allowed seven PR #111 source hosts; Work A's `ALLOWED_HOSTS` was narrower. Previously any returned report from an unapproved host would fail `validate_reports`. Work J adds **only** the relevant PR #111 original domains.
2. Work E's `build` raised `PR102_CLUSTER_HAS_UNEXPECTED_FACT_REPORT` when one previously blocked cluster finally acquired a report. New facts should be evaluated and blocked for incident/credit review rather than crashing all ingestion.
3. `extract_cached_reports` silently discarded missing texts, zero/multiple fatal scopes, missing anchor, uncertain boundary, origin, or identity; Work J adds optional `diagnostics` with candidate-linked reasons and stage counts, leaving the default return API unchanged.
4. Narrow Ukrainian forms for a single cumulative death total and explicit Zaporizhzhia spelling were absent; Work J adds guarded count wording. It does **not** infer a unique attack from a title, publication date, matching count alone, or co-occurring police document.

**Not proven:** none of these defects can be assigned to a particular one of the ten articles without its original captured body. They are code review findings and offline regression targets, not retrospective source judgments.

## Changes and boundaries

- `kyiv-air-alerts-grafana/scripts/casualty_auto_review.py`: optional per-article diagnostics; fail-closed reasons including `SOURCE_TEXT_NOT_RETAINED`, `NO_FATAL_CLAIM`, `NO_PARSEABLE_FATAL_TOTAL`, `MULTIPLE_POSSIBLE_INCIDENTS`, `CITY_BOUNDARY_UNCERTAIN`, `ATTACK_DATE_MISSING`, `ATTACK_IDENTITY_AMBIGUOUS`, `WEAPON_ORIGIN_UNCONFIRMED`. The existing reviewer / dedup retains authority.
- Work E `ingest.py`: parser stage/reason accounting in offline handoff; pre-existing PR #102 blocked cluster no longer aborts extraction; proposed fact report remains `NEEDS_REVIEW` until source/incident/prior-credit reconciliation.
- `minimal_capture_facts` keeps limited separate cards for **future, separately approved** source captures. Each card has its own source URL, role (publisher/official), optional candidate ID, publication/attack date when established, explicitly extracted count, count semantics, origin attribution, short de-identified excerpt (max 170 characters), raw-document SHA-256 when receipt provides it, extracted-text SHA-256, parser version, and reasons. Does **not** store full source bodies, publish, promote or automatically match police material to a publisher incident.
- Evidence excerpts remain publisher-attributed if the publisher quotes an institution; attribution alone is not independent retained police text. The audit card's `locality_verified` stays null if not proven.
- SHA-256 is a **consistency receipt**, not proof that an interpretation is correct. Minimal cards do not establish all facts required for AUTO_READY.

## Offline test scope

The branch's GitHub workflow `.github/workflows/research-casualty-workj-fact-retention.yml` runs Work E/G/I safety suites and Work J tests plus the previously retained Zaporizhzhia 10 October Work A→generator proof. It downloads only immutable GitHub artifacts previously allowed, makes **zero source publisher/police HTTP GET**, and writes solely to temporary runner paths.

- **Real retained-original fixture:** 10 October Zaporizhzhia count 18 → 20 → 23 must remain a single +23 event; 22 other cities, prior credits, and repeated proposals cannot be affected.
- **Synthetic safeguards:** two/three and revised counts, injury-only and late death, multiple attacks, unattributed official claims, source-text absence, separate police versus publisher cards. Synthetic examples are NOT source proof.
- **Not verified yet:** any of the ten November pilot texts; the HTTP receipts alone cannot supply parsed body facts.

## Next bounded pilot — NOT AUTHORIZED

Only after offline proof is checked and the owner separately grants a new authorization, use three exact original PR #111 URLs:

- T03 publisher, early 2: `https://www.ukrinform.ua/amp/rubric-regions/4177207-armia-rf-zavdala-udaru-po-zaporizzu-zaginuli-dvoe-ludej.html`
- T04 publisher, later 3: `https://mig.com.ua/vorozhyy-udar-po-pryvatnomu-budynku-v-zaporizhzhi-zahynuly-troye-lyudey/`
- T05 police, possible official corroboration: `https://zp.npu.gov.ua/news/na-zaporizhzhi-cherez-rosiiski-ataky-zahynulo-troie-liudei-shche-odna-otrymala-poranennia-politsiia-dokumentuie-naslidky-voiennykh-zlochyniv`

Fresh consent must specify exact three URLs, whether any exact redirect path is allowed (default none), max three initial GET and no more than six total including approved redirects, >=1-second delay, max 1MB each, 15-second timeout, no retries, <=24h time window, single execution only. Read and summarize at most short evidence extracts; shadow-only; require independently linked police body, a unique attack, source-specific cumulative 2→3 rather than sum 5, and prior-credit proof. No HTTP permission is carried over from PR #118.

## CI and verdict

**Pending exact-head physical Actions verification at report creation.** A successful workflow and independently verified artifact digest are required for `PARSER_DIAGNOSTIC_OFFLINE_PASS`; no early PASS is implied. Otherwise report `PARTIAL` or `BLOCKED_RECAPTURE_REQUIRED` with the failing checks.

Publication false; October coverage incomplete, confirmed minimum >=23 from earlier independent proof only. No authorization for recapture or promotion.
