# CASUALTY-THREE-REAL-ARTICLE-SAFETY-FINDINGS-01 — captured 3/3; real positive missed

Date: 2026-11-11. **Research only; no revision, release or merge authorization.**

## Frozen scope and provenance

- Owner approved **one** bounded source HTTP attempt for three new, unreviewed WIP candidates. [Physical Actions #43053796144](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144) at exact SHA `b68788b3fc2ce9bfc6418008c920149ad47c7d79`: original WIP 1,657-row queue Git blob `f3f7141aa6d7584c63ff42510b40239a18834d15`, three exact rows in saved selection blob `98f17abc05a4fdcb490d9e27faec189076314ac4`, 25/25 offline capture/policy tests PASS.
- Actual source fetch: **3/3 approved publisher articles captured with 12 HTTP requests**, 0 blocked, 0 operational writes; GitHub original [artifact #13870872313](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144/artifacts/13870872313), ZIP SHA-256 `f7255cba58faea1ecb7defbe2cdbed40db2ddf05a5b92f5fe3530cead32f2148`. Its `evidence.json` SHA-256 `84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df`. Original internal 2/2 manifest hashes and 3/3 excerpt receipt hashes independently verified.
- **Independent article gold was committed before any reviewer run** in [`4174d3bb`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/4174d3bbb8e3d34e640c9d2c0677f3fa02d98a6a) (`INDEPENDENT_GOLD.json`), using only frozen source text. No reviewer code changed: Git blob `0ce2cd1658ad8fa8e3d922c4ea5539e97b161301`.
- [Offline replay Actions #43056505565](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43056505565) at `dfe56bf6`: gold prior-commit check PASS, original artifact download PASS, **reviewer-vs-gold check FAILURE by design** (one missed real positive), no new source HTTP. Output [artifact #13872120318](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43056505565/artifacts/13872120318), ZIP SHA-256 `f9657caa98ba3a0d4736cbe06a9938c7ae7945aaefd2d4007516b0490bdfb58f`, root 7/7 manifest checks PASS. Prior CI #43056317426 failed on checkout *history depth* before reviewer ran; corrected to `fetch-depth: 0` without media HTTP.

## Three real cases, independent gold versus unchanged reviewer

| WIP candidate ID | Actual publisher facts | Independent gold (frozen first) | Reviewer result | Verdict |
| --- | --- | --- | --- | --- |
| `e0fba98b19473874e9a1d8f1` Zaporizhzhia, Suspilne | Morning **10 Oct 2026** KAB attack wave inside Zaporizhzhia city; **23 deaths** as latest official oblast DSNS total, updating earlier **18 → 20 → 23**, not a sum | **AUTO_READY**, a single dated citywide air-attack wave, +23 subject to no older ledger entry | NEEDS_REVIEW, `TOTAL_DEATHS_UNKNOWN_OR_CONFLICTING`; zero cached reports | **Missed real positive**; reviewer does not recognize cumulative chronological updates |
| `42f2a273f56c87e0bcd22af8` Ivano-Frankivsk, LB.ua | Drone strike **11 Oct 2026**, final total 3; the city mayor **expressly says all three deceased were servicemembers** | NEEDS_REVIEW, **0 civilian deaths eligible** for automatic addition | NEEDS_REVIEW, no proposals | **Surface status correct, internal safety bug** (see below) |
| `5e46ae290e43745fc4b827fa` Kharkiv, Suspilne | **4 deaths spread across Izyum, Malodanylivska hromada, Prykolotne and Derhachi–Kozacha Lopan road** on separate days; Kharkiv city paragraphs mention injuries only | NEEDS_REVIEW for **Kharkiv city**; no city death total may be inferred | NEEDS_REVIEW, `CITY_VS_REGION_REQUIRES_EVIDENCE` | Safe city/oblast negative; no cross-incident +4 |

**Totals:** 3 new usable real publisher texts; **2/3 statuses matched frozen gold**, **0 false AUTO_READY**, **1 missed justified AUTO_READY**, **0 new research proposals**, **0 replay duplicate proposals or deaths**, protected input SHA-256 unchanged. This is an observed *one-case* miss, not a population-level recall estimate.

## Additional safety finding: military-victim evidence ignored internally

For the Ivano-Frankivsk article, `first/events.json` in artifact `13872120318` contains a parsed report with `civilian_status="civilian_presumed"` and `facts.civilian=true`, **despite the explicit “Загиблі — військовослужбовці” statement in the retained article**. This violates the owner-approved civilian presumption exception when military status is explicit.

The actual reviewer still returned `NEEDS_REVIEW` because **`origin_id="unattributed"`**, but that independent provenance blocker is not proof that its civilian-status decision is safe. **Do not promote any research result** until the explicit military-status override is separately tested. The same event report has a spurious `place` parsed from the warning not to remain `на вулиці під час сигналу "повітряна тривога"`; that text is **not an attack location**. Keep this as a second narrow negative extraction regression.

## Decision and ordered next tasks

- **Capture/provenance PASS:** all three originally pinned publisher excerpts were downloaded once; original SHA, redirects and input immutability preserved.
- **Real reviewer generalization FAIL:** one dated official aggregate 23-death positive held incorrectly; two negatives held, but military victim marker was missed internally.
- **Priority 1 safety fix (separate offline task):** explicit service-member deaths must override `civilian_presumed` even if an article has otherwise valid date, weapon, origin and total. Include this real retained article and a controlled positive source-attribution variant, without fabricating deaths.
- **Priority 2 automation fix (separate task):** recognize chronological `18→20→23` same-incident **cumulative** updates, prioritizing the final dated/official 23, without summing counts and without borrowing totals from another strike.
- **Priority 3 small negative control:** warning text “на вулиці під час тривоги” must never become incident `place`.
- **Hard release boundary:** no `revisions.csv` writes, no WIP queue mutations, no Git/Neon/prod cutover, no publish, no merge. These findings do **not** authorize further media HTTP requests. Existing 45/45 offline regression remains a separate, earlier accepted checkpoint; no change to code has been proposed here.
