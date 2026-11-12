# CASUALTY-ZAPORIZHZHIA-ADDITIONAL-EVENTS-WORKB-01

**Decision: `BLOCKED_MISSING_EVIDENCE`.** Research-only, 2026-11-12. The five specified candidate groups (11 WIP messages) were checked against the frozen Work B crosswalk and the previously recorded publisher-capture scope. **No additional independently verifiable deaths can be admitted on the retained article-body evidence identified so far.** This is **not** a finding of zero actual deaths. October 2026 remains **`COVERAGE_INCOMPLETE`** with a separately accepted **minimum of 23 deaths for the single 10 October city attack**. No publication or revisions are authorized.

## Exact recovery and verification boundary

- Read `main:PROJECT_STATE.md` and `main:CHANGELOG.md` at `375e69351e6a5aee1be16892821f7cdde2a8f21a`. Main's newest general accepted coordination checkpoint is `C6-POSTMERGE-C2-EXPORT-23-01` (not a casualty approval). [Draft coordination PR #71](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/71) adds the newer casualty-specific review checkpoint: `NO-GO`, and Work A preview is independently `PREVIEW_BLOCKED` on duplicate-event accounting. Nothing from PR #71 was merged.
- Reused **exactly** the frozen `candidate_inventory.json` from [Draft PR #85](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/85) / `19fad28885ab0cac2b331c06be7c0b6001bddadc`, Git blob `f40b740f89845f8fade219b3448834a8bd0ea226`, SHA-256 `1875194070511272469b1884a6ace0a6e50cdbe217244e2da3d20b1c70ab1876`.
- Frozen original WIP is `multicity-wip-2026-09-16@c66c242a852d7647b6183425228cb3db2d1d088b`; `multicity_review_queue.json` Git blob `e0845574e40d3c7ad56ccf7fff0cf83553924665`, source SHA-256 `3d9133d178d229d5356e1939db827411f8b2af21a4b72766c16c214933da0d8d` (previously verified in PR #85).
- The inventory contains 208 city-tagged WIP **messages**, all `needs_review`; 197 were published Sep 19–Oct 31. This task did **not** rescreen these 208. It selected the 11 specific candidate IDs below, each present **once** in the frozen inventory, with `stored_article_body_in_this_wip_row=false`.
- The retained WIP `source_state.json` at `c66c242a` (Git blob `c78f4e2c0ec5e8ae34ed32d71ca757c1aa80fdcb`) contains Kyiv source URLs, **no Zaporizhzhia publisher-article bodies**. WIP RSS titles and snippets are not primary-article body evidence.
- Checked old physical-capture scopes: [five-candidate run #42998441793](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998441793), [artifact #13844887603](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998441793/artifacts/13844887603) (Dnipro, Kharkiv, Lutsk, Odesa, Kharkiv, **none of these 11 IDs**); and [three-candidate run #43053796144](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144), [artifact #13870872313](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144/artifacts/13870872313) (Zaporizhzhia **10 Oct**, Ivano-Frankivsk, Kharkiv, **none of these 11 IDs**). Their source captures are documented in [PR #66](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/66) and [PR #67](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/67); no new capture is authorized. The previously accepted Oct 10 Suspilne original is preserved independently.
- An explicit target-ID intersection with both old selected capture sets is empty. This verifies only that the **previously indexed capture scope does not supply matched original article evidence**. It does not rule out additional, currently unidentified caches or articles.
- The [machine-readable `verification_matrix.json`](verification_matrix.json) preserves all 11 exact IDs, publications, original RSS URLs, WIP line links, evidence gaps, and uncertainty fields. A Google News RSS URL is **not** a resolved direct publisher URL: the actual article URL must be determined from the approved capture/archived redirect metadata or provided by the source before any new HTTP.

## Priority incident table

**Dates below are publication dates / proposed clusters, not independently verified dates of attack.** Every candidate has `BLOCKED_MISSING_SOURCE` until a saved full original publisher/official body becomes available and the incident attributes can be evaluated.

| Proposed publication cluster | Candidate IDs, source | Evidence result | Additional deaths accepted |
| --- | --- | --- | --- |
| **18 Oct** female death / drones | `43a268ae2e19123554d6d476` — ZPRZ.CITY ([WIP source](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L39122)) | **`BLOCKED_MISSING_SOURCE`**: original dated report/official city location, civilian status and event identity absent; title mentions one female victim and drone attack but is not admissible death evidence | Not established |
| **22–23 Oct** 2 versus 3 | `7c3ac3280ba7ad4b9c10f3b1` — Ukrinform.ua ([WIP](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L22992)); `dcdd2fe28fd1464e7fbabdc1` — Газета МИГ ([WIP](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L24301)); `24654383bd30cc0f4e29c95f` — ZPRZ.CITY ([WIP](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L24107)) | **`BLOCKED_MISSING_SOURCE`**: 2→3 could be cumulative same-attack updates, or separate events; next-day headline is not proof of 23 Oct attack. No basis for adding 2+3 | Not established |
| **26 Oct** apartment-strike victim | `103256b72707ad66d91f6aae` ([WIP](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L19225)); `cb222eea2a20aa1db2d67d5d` ([WIP](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L20537)) — Ukr.net | **`BLOCKED_MISSING_SOURCE`**: exact repeated headline suggests possible duplicate RSS accounts; actual occurrence date, impact location, military/civilian status and total still lack article-body confirmation | Not established |
| **25–26 Sep** reported two fatalities | `89a03da642500bf4def8ec9c` — shelter.in.ua ([WIP](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L107240)); `05affefbcbb9f27a322ff5d3` — Радіо Свобода ([WIP](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L87632)); `db8ada77be0650fbf7c686cd` — Інтерфакс-Україна ([WIP](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L102430)) | **`BLOCKED_MISSING_SOURCE`**: 25 Sep headline may precede 26 Sep official confirmation or concern a separate event; incident time, exact place, civilian status and source text missing | Not established |
| **27 Sep** Shahed reported fatality | `7f57e0e0e4743e98c8a88186` — Перший Запорізький ([WIP](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L83998)); `a3e25aad501f5f76e30ae65e` — Справжнє ([WIP](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/c66c242a852d7647b6183425228cb3db2d1d088b/kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json#L102494)) | **`BLOCKED_MISSING_SOURCE`**: two 27 Sep drone reports potentially describe the same strike; precise strike date/location and independent death count not proved from original article body | Not established |

### Source retrieval queue (no HTTP performed)

For **each of the 11 rows**, the retained precise `candidate_id`, `publisher`, `original_wip_rss_url`, `published_at`, original WIP line and its permanent hyperlink are stored in the [verification matrix](verification_matrix.json). Obtain original archived text or officially dated report for these sources, in this order:

1. **Ukrinform.ua / Газета МИГ / ZPRZ.CITY, 22–23 Oct**: establish whether the reported `2` and `3` are successive totals of one attack or independently sourced different events.
2. **ZPRZ.CITY, 18 Oct; Ukr.net, 26 Oct**: confirm the distinct attack, actual city impact, victim status and later corrections. Check whether both Ukr.net URLs are copies of one article.
3. **Радіо Свобода / Інтерфакс-Україна / shelter.in.ua, 25–26 Sep; Перший Запорізький / Справжнє, 27 Sep**: establish two separate attack dates (if supported) and whether official follow-up totals overlap.

Do not resolve RSS redirects, fetch media articles, or issue additional capture jobs without a **separate owner authorization**. Where no retained original exists, all rows stay blocked and must not be turned into an assumed zero.

## Research-only totals

| Measure | Result |
| --- | --- |
| Priority groups checked | **5** (11 candidate message IDs) |
| Additional independent fatal attacks confirmed | **0 established in this examination** |
| Additional confirmed October deaths | **0 newly established** (not zero actual deaths) |
| Confirmed October minimum | **23** from 10 Oct, unchanged; cannot be advertised as a complete month |
| Confirmed deaths from new Sep 19–30 groups | **0 newly established**; actual total **unknown** |
| Groups with insufficient original-body evidence | **5/5** |
| Possible duplication | 22–23 Oct cumulative 2/3; 26 Oct same-title pair; 25–26 Sep overlap; 27 Sep same-date pair |
| Sources still requiring original article/official text | **11 candidate-specific article receipts**, potentially fewer independent articles after dedup |
| October completeness | **`COVERAGE_INCOMPLETE`** |
| Final decision | **`BLOCKED_MISSING_EVIDENCE`** |

**Recalculation rule:** confirmed baseline **23** + independently verified additional October events **0 established in this research** = retained **research minimum 23**. The arithmetic is a *minimum preservation*, not an assertion that only 23 people died or that the last observed aggregate is complete. Do not credit a person twice for multiple article snapshots; exclude attacks outside the city's administrative limits and expressly military casualties. Attribute any delayed death to the original attack date.

## Evidence fingerprints and execution integrity

| Material | Exact immutable reference / SHA-256 |
| --- | --- |
| PR #85 frozen candidate inventory | `19fad28885ab0cac2b331c06be7c0b6001bddadc`; SHA-256 `1875194070511272469b1884a6ace0a6e50cdbe217244e2da3d20b1c70ab1876` (recomputed on fetched full UTF-8 content) |
| Original WIP queue | `c66c242a852d7647b6183425228cb3db2d1d088b`; SHA-256 `3d9133d178d229d5356e1939db827411f8b2af21a4b72766c16c214933da0d8d` (prior Work B receipt; not recomputed here) |
| Five-URL previous physical capture artifact | `13844887603`; ZIP SHA-256 `81f29dcfb29db64a98466febf5fd3abb77816b827e01d29dad9b19ab7d78c2ba` (previous accepted proof) |
| Three-URL physical capture artifact | `13870872313`; ZIP SHA-256 `f7255cba58faea1ecb7defbe2cdbed40db2ddf05a5b92f5fe3530cead32f2148`; evidence JSON SHA-256 `84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df` (previous proof) |
| Frozen independently assessed October 10 original | [`INDEPENDENT_GOLD.json`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/4174d3bbb8e3d34e640c9d2c0677f3fa02d98a6a/research/casualty_three_new_http_2026_11_11/INDEPENDENT_GOLD.json); SHA-256 `6da41b2bcd2650d0f24c19d4f1320624189a995b388202601eac9dbe21340db0` (recomputed fetched full content) |
| This research's new audit | `verification_matrix.json`, created solely on separate research branch; Git blob SHA and content SHA-256 recoverable independently via GitHub |

**Execution scope:** Remote GitHub file reads and code-mode data crosschecks only. Prior artifact indexes, reports and source membership were inspected; original ZIP files were **not** independently downloaded and rehashed in this task. No new media HTTP, no CI run, and no proof ZIP claimed. No WIP, `revisions.csv`, generator/reviewer, frontend, production, Neon, main, PR #85 or PR #71 changed. This branch contains only the two new research files. **Do not merge/deploy/publish.**

Coordinator handoff: compare this `BLOCKED_MISSING_EVIDENCE` outcome separately against Work A's incident-level duplicate fix. Any later source-body capture needs explicit new owner permission, and any publication still needs separate complete-month and idempotency clearance.
