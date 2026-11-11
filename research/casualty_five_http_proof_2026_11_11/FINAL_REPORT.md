# CASUALTY-FIVE-WIP-HTTP-SHADOW-PARTIAL-01 (2026-11-11)

**Research-only accepted transport proof. Publication: OFF.** The user approved one live shadow test of exactly five previously selected WIP candidate IDs. It ran once, with no repeat publisher HTTP.

## Immutable inputs and code

- Selected sample: `research/casualty_five_candidate_selection_2026_11_11/selected_queue.json` blob `050d85606f6742306d28651a410baa23947557bd`.
- Separate WIP queue snapshot: `multicity-wip-2026-09-16@c5ad6548`, blob `f3f7141aa6d7584c63ff42510b40239a18834d15`, **1,657** records. All five unique IDs and metadata fields match and remain `needs_review`.
- Unchanged code Git blobs: monitor `a6c09d7a`, reviewer `1fe71162`, capture adapter `40273785`, transport policy `74450ca9`.
- Previous known live WIP failures: [#42899975187](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42899975187) (three denied target hosts, two publisher 403). This test uses **different, fixed** candidates and the same safe allowlist.

## Actual five-URL physical run and independent offline replay

- [Physical Actions #42998441793](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998441793), exact SHA `5e50f004da34d0dc45e9ee5220ce29debd58cc55`, 25/25 offline tests PASS and five-ID preflight PASS. **Five selected URL attempts, 20 bounded HTTP requests, five publisher HTML documents downloaded, four usable excerpt/evidence packages, one `HTML_NO_ARTICLE_PARAGRAPHS`.**
- Original run job `FAILURE` due to the **research harness assertion** mistakenly comparing `articles_downloaded=5` with the four stored usable article objects. The capture engine and reviewer had already completed. No evidence is lost. This harness assertion was corrected on the research branch **without triggering another source-HTTP run**.
- Initial reviewer: five messages/five potential events; **0 AUTO_READY, 5 NEEDS_REVIEW, 0 proposed revisions**. Two reports parsed count/date/city signals (Dnipro/Suspilne and Odesa/Suspilne), but their retained source attribution is `origin_id=unattributed`; the unchanged reviewer correctly blocks all six fact supports. LB.ua/Kharkiv and UNIAN/Lutsk yielded excerpts but no complete cached incident report. This is an extraction/attribution limitation, **not** evidence of zero deaths.
- [Independent offline replay #42998990269](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998990269) **SUCCESS**, reused the immutable original HTTP artifact, did no publisher HTTP, and confirmed **0 new proposals, 0 duplicate deaths, protected input SHA-256 unchanged**.
- Original [artifact 13844887603](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998441793/artifacts/13844887603): original ZIP SHA-256 `81f29dcfb29db64a98466febf5fd3abb77816b827e01d29dad9b19ab7d78c2ba`; 5/5 manifest hashes PASS.
- Complete [replay artifact 13845600971](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998990269/artifacts/13845600971): ZIP SHA-256 `3fa949194a80d70c23ea3d6f757878f770bff6e1345f7787e51ff9df67341503`; 12/12 replay manifest hashes PASS, plus original 5/5.

## Per-candidate physical result

| Candidate ID | City / publisher | Physical result | Evidence-review outcome |
| --- | --- | --- | --- |
| `5d60e1c78026fdc494ea3c84` | Dnipro / Suspilne | HTML + retained excerpt PASS | Parsed report, official origin unattributed; NEEDS_REVIEW |
| `96dc8052cf48f4ce74df29f6` | Kharkiv / LB.ua | HTML + retained excerpt PASS | No complete cached incident report; NEEDS_REVIEW |
| `6c946bfd46fffbe953d795bf` | Lutsk / UNIAN | HTML + retained excerpt PASS | No complete cached incident report; NEEDS_REVIEW |
| `f4719e871b92e7563c7150da` | Odesa / Suspilne | HTML + retained excerpt PASS | Parsed report, official origin unattributed; NEEDS_REVIEW |
| `81196e29c4a6ac2141a93617` | Kharkiv / Korrespondent.net | HTTP HTML PASS, article paragraph selection FAIL | `HTML_NO_ARTICLE_PARAGRAPHS`; NEEDS_REVIEW |

## Exact acceptance boundary

**PASS:** real WIP candidate → signed Google RSS routing → publisher HTML → safe excerpt for 4/5, unchanged reviewer execution, standalone offline replay, zero duplicate proposals, no data mutation.

**STILL BLOCKED:** automatic casualty revision for these five; 0 AUTO_READY because fact provenance and incident parsing remain insufficient. No 23-city end-to-end auto-publication claim.

**Next recommended separate task:** investigate retained-excerpt parsing and official source attribution using *these four captured documents offline*, then adjust only confirmed narrow extraction/attribution defects with mock tests. In particular, verify the report's `origin_id=unattributed` against the text and reviewer parsing contract. Do not weaken provenance, city/date, civilian-status, or deduplication safeguards. No further publisher HTTP, merge, operational WIP writes, `revisions.csv` changes, C6/Neon interaction, deployment, or publication authorized.
