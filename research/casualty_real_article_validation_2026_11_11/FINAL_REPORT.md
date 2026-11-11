# CASUALTY-NEW-REAL-ARTICLE-INDEPENDENT-VALIDATION-01

Date: 2026-11-11. **Research-only, 2/2 independent article classifications correct; no promotion or publication authorization.**

## Precise result

| Candidate ID | Source | Expected (independently frozen before execution) | Actual | Correct | Difference |
| --- | --- | --- | --- | --- | --- |
| `96dc8052cf48f4ce74df29f6` | [Kharkiv, LB.ua](https://lb.ua/society/2026/10/28/776738_rosiyskiy_dron_atakuvav_harkiv.html) | `NEEDS_REVIEW` | `NEEDS_REVIEW` | YES | None |
| `6c946bfd46fffbe953d795bf` | [Lutsk, UNIAN](https://www.unian.ua/war/novini-lucka-dron-vluchiv-u-gurtivnyu-yevrogurt-ye-zagibli-13528494.html) | `NEEDS_REVIEW` | `NEEDS_REVIEW` | YES | None |

- Additional new real articles **2** (minimum 3 requested, so **1 short**, preferred 5 so **3 short**).
- Correct reviewer statuses **2/2**. False `AUTO_READY` **0**. Missed justified `AUTO_READY` **0 observed, but no eligible positive case was available**, so this is *not* a false-negative-rate estimate.
- First run 2 messages / 2 potential events / 0 cached parsed reports / 0 `AUTO_READY` / 2 `NEEDS_REVIEW` / 0 new proposals.
- Second run with first proposals as reservations: **0 additional proposals, 0 duplicate deaths**. Protected inputs unchanged byte-for-byte. Publication OFF.
- In both cases reviewer reports `NO_CACHED_FACT_EVIDENCE_TITLE_IS_NOT_PROOF` and `TOTAL_DEATHS_UNKNOWN_OR_CONFLICTING`. This classification is appropriate for the **current frozen text-only evidence**, not an assertion that no civilians died.

## Independent manual grounds (frozen BEFORE algorithm execution)

- **Kharkiv:** one killed in an alleged drone strike; official report attributed to Kharkiv OVA head. A *separately narrated* 27 October evening residential hit caused injuries, but no deaths were stated for that hit. The saved text does not establish the exact date of the fatal strike, and does not license borrowing the residential-hit date/time/place. Presumed civilian unless contrary evidence, but unique dated incident identity unresolved: `NEEDS_REVIEW`.
- **Lutsk:** a single reactive-drone incident in Lutsk, warehouse and apartment impact; named Volyn OVA official plus municipal authority updates. Cumulative deaths were **4 then 5 then 6** by 14:42, 15:13, 15:50, not 15. Five bodies recovered at the warehouse plus one hospital death are one total of six. The article does not expressly anchor the strike to a calendar date; publication date and update clock times are not enough to prove the attack date: `NEEDS_REVIEW`. This remains a *missed automation opportunity* to investigate with better evidence, **not** a demonstrated false negative under current evidence rules.

## Exact provenance and repeatability

- Gold prepared **before** reviewer execution at [commit `1b0b6879`](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/1b0b6879894737b65ec8ff1af08e56365ec5c09d): [INDEPENDENT_GOLD.md](INDEPENDENT_GOLD.md).
- Implementation frozen at `f46753e4b85e56052639959beb1d96ee408e227e`. Reviewer Git blob `0ce2cd1658ad8fa8e3d922c4ea5539e97b161301`, unmodified.
- Existing accepted [45/45 CI #43034383784](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43034383784) NOT repeated.
- Immutable source: [GitHub artifact #13845600971](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998990269/artifacts/13845600971); ZIP SHA-256 `3fa949194a80d70c23ea3d6f757878f770bff6e1345f7787e51ff9df67341503`; contained `evidence.json` SHA-256 `68ceccdcca68a0c93d42a0c0173c32c9ab47b659415e9bd2b274df8d9cf0fdf9`. Both checked independently.
- Kharkiv `text` UTF-8 SHA-256 `cb4ed15646d44d6f0a5d95333f841597125885416d46dce92aa74fdc01913db9`; Lutsk `text` SHA-256 `cc6d670436ff1190da1230b1cabb16630838f6da33ef055e712560890a33d9cd`. Both match original receipt excerpt hashes.
- Successful exact-head [Actions #43049239644](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43049239644), head `5ea34f85d5327c7c3670b0437649943b16513f1a`. Reusable [verdict artifact #13869540015](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43049239644/artifacts/13869540015), ZIP digest `sha256:0c66327c1d1666d583deeb170e81fefaf172be47606243bdc8b50511725e3209`. Artifact contains `verdict.json` and input hash manifest.
- Reproduce from this research branch: check the exact reviewer blob and gold commit; use `actions/download-artifact` to fetch run `42998990269` / artifact name `casualty-five-source-artifact-offline-replay` into `research/casualty_real_article_validation_2026_11_11/input`, then run `python research/casualty_real_article_validation_2026_11_11/run_offline.py`. The workflow performs all of this automatically.
- Odesa `f4719e871b92e7563c7150da` and Dnipro `5d60e1c78026fdc494ea3c84` excluded from the new sample. Original fifth candidate had `HTML_NO_ARTICLE_PARAGRAPHS`, not usable saved text. Previous five-URL artifact #13801289333 contains zero article objects; previous real evidence `sources.json` includes only Dnipro/Odesa excerpts. No additional qualifying retained article was located in checked casualty research proofs.

## One remaining leading blocker

**Insufficient independent real-article coverage, especially zero qualifying positive `AUTO_READY` examples.** The two usable novel texts were both ambiguous date/identity negatives; this validates safe holds but not automatic recall.

Next **separately authorized** test: capture **three** additional real saved publisher texts from current approved WIP selections (one complete official single-attack report with explicit date, one late cumulative update case, one unrelated multi-strike retrospective case). Preserve URL, candidate ID, source body/excerpt SHA and dated official origin; manually freeze gold prior to replay. If strictly targeting the minimum three-item sample, only one extra suitable novel article is required. No HTTP permission is presumed by this report.

**Scope limits:** No source-media requests, reviewer code change, ledger or WIP mutation, production modification, Neon/C6 activity, merge, deployment or casualty publication. Do NOT infer broad production safety or a measured false-negative rate from 2 negative examples.
