# Independent real-article gold assessment (BEFORE reviewer run)

Date: 2026-11-11. Research-only. **This assessment was recorded before executing the frozen reviewer against the selected two articles.** It is based on retained article text and source metadata, not algorithm categories.

## Frozen scope and chain of custody

- Starting implementation commit: `f46753e4b85e56052639959beb1d96ee408e227e` on `research-casualty-attribution-2026-11-11`.
- Prior accepted 45/45 full offline regression: [Actions #43034383784](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43034383784). Not repeated.
- Original stored evidence: [replay artifact #13845600971](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998990269/artifacts/13845600971) from Actions #42998990269; ZIP SHA256 `3fa949194a80d70c23ea3d6f757878f770bff6e1345f7787e51ff9df67341503`; retained `evidence.json` SHA256 `68ceccdcca68a0c93d42a0c0173c32c9ab47b659415e9bd2b274df8d9cf0fdf9`.
- Independent local verification of ZIP and evidence JSON hashes PASS.
- Available usable article excerpts in this artifact: **4**; two excluded previous controls: Dnipro `5d60e1c78026fdc494ea3c84` and Odesa `f4719e871b92e7563c7150da`. Fifth Korrespondent candidate `81196e29c4a6ac2141a93617` has `HTML_NO_ARTICLE_PARAGRAPHS`, not an article text.
- Cross-checked previous `casualty-wip-gnews-5url-retest` artifact #13801289333: **0 retained articles** (five failed captures). Historical `casualty-exact-sha-offline-proof` artifact #13785572875 contains events/proof, but no new captured article text. Historical `sources.json` contains four short **Dnipro and Odesa** extracts only, already excluded. Original legacy `cached_evidence.json` is seven structured reports, not additional retained article text.
- Therefore only **two eligible new real article texts** found in this checked evidence inventory; insufficient for a three-case independent sample. No new media HTTP requested or performed.

## Independent judgment on the TWO eligible new texts

### 1. Kharkiv / LB.ua — `96dc8052cf48f4ce74df29f6`

- Retained URL: https://lb.ua/society/2026/10/28/776738_rosiyskiy_dron_atakuvav_harkiv.html
- Publisher: LB.ua. WIP `published_at=2026-10-28T12:35:00Z` (publication date, **not necessarily the fatal strike date**). Article `observed_at=2026-11-11`.
- Exact retained UTF-8 article excerpt SHA256 `cb4ed15646d44d6f0a5d95333f841597125885416d46dce92aa74fdc01913db9` (`receipts[].excerpt_sha256`).
- Fatal report: Russian drone struck Kharkiv, one person was killed (later specified as a 60-year-old man); claim attributed to Kharkiv Oblast Military Administration head Oleh Syniehubov. Presumption of civilian status permitted absent military markers.
- **Other material in the same text:** a clearly dated *evening 27 October* strike on a Kharkiv residential building, reporting **four injured** rather than dead; more drone hits in several city districts reported as occurring the previous day, including an injury.
- The fatality belongs to the **primary reported drone strike**, not automatically to the 27 October residential-building incident or the unrelated district impacts.
- **Fatal strike calendar date is not explicitly attached to its report in the saved text.** October 28 is the article's publication date; October 27 refers to a distinct strike. Do not use that October 27 date, evening slot or residential-building location to construct a confident fatal incident identity.
- **Independent expected status: `NEEDS_REVIEW`.** Evidence for city, air weapon, death and named official exists, but a uniquely dated fatal attack identity is not established. In particular a hypothetical `AUTO_READY` dated 27 October would be an unsafe cross-incident inference.

### 2. Lutsk / UNIAN — `6c946bfd46fffbe953d795bf`

- Retained URL: https://www.unian.ua/war/novini-lucka-dron-vluchiv-u-gurtivnyu-yevrogurt-ye-zagibli-13528494.html
- Publisher: UNIAN. WIP `published_at=2026-10-14T12:50:00Z` (publication timestamp, **not independent proof of attack date**). Article `observed_at=2026-11-11`.
- Exact retained UTF-8 article excerpt SHA256 `cc6d670436ff1190da1230b1cabb16630838f6da33ef055e712560890a33d9cd` (`receipts[].excerpt_sha256`).
- One reported Russian reactive-drone attack in **Lutsk city** with damage to the EuroGurt warehouse, plus debris damage to a residential apartment within that incident. Primary initial information attributed to Volyn Oblast Military Administration head Roman Romaniuk; later fatality updates explicitly attributed to **Lutsk City Council**, with clarification from the OVA.
- **Time-ordered cumulative fatality counts:** 14:42 update **4**, 15:13 update **5**, 15:50 update **6**. Final reported total is **6**, **not 4+5+6=15**; later clarification says five were found in rubble and one died in hospital, also totaling six. The warehouse and residential debris impact are not evidence of two different sets of fatalities.
- The preserved text provides no independently stated calendar date for this drone strike; the three clock times are publication updates, not verified strike time. No explicit military-victim evidence.
- **Independent expected status: `NEEDS_REVIEW`** under the existing requirement for a uniquely grounded dated incident. A future additional dated official record could justify `AUTO_READY` for a total of six (not fifteen); with only this frozen article text and its publication timestamp, the necessary event date is unproven. A putative `AUTO_READY` inferred from update timestamps alone would not be justified.

## Predetermined acceptance and safety checks

- Run unchanged frozen `kyiv-air-alerts-grafana/scripts/casualty_auto_review.py` against exactly these two retained article objects, corresponding two original WIP candidate objects, and frozen ledger/baseline files.
- Compare category for **each** to `NEEDS_REVIEW`, and inspect why. A mistaken `AUTO_READY` must be recorded as an unsafe false positive even if its delta is zero.
- Run first and second offline passes with the first proposals as reservations; assert zero *new* proposals in pass 2, no repeated death addition and byte-for-byte identity for all protected inputs.
- No source HTTP, no code modifications, no ledger/WIP/production writes, no cutover or publication. Keep `publication_allowed=false`.
- **Scope boundary:** two negative cases cannot measure general false-negative sensitivity or justify deployment. The third to fifth additional stored article texts are **missing**; recommend a separate explicitly approved 3-URL source capture focused on a complete single-attack official dated report, cumulative fatality updates, and a multi-attack retrospective text if a broader quality sample is desired.
