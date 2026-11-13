# Work O — casualty parser and evidence retention

**Scope:** research only; clean Work N parent 236d3d3af785ea89f44504995498bcd0915d2e10. No launch.json, new publisher HTTP, merge, deploy, PROMOTE, casualty JSON, WIP, C2, Neon or production writes.

**Evidence-limited verdict:** PARTIAL_REAL_HTML_REQUIRED. Code-level defects were corrected and physically tested offline, including immutable archival evidence and generator replay. Real T03–T05 HTML was never retained, so the exact real-world failure cannot be reproduced on genuine source text.

## Physically verified pilot evidence

- GitHub Actions #43510162714 SUCCESS, three GET, zero redirects, all HTTP 200.
- ZIP artifact #14076819100 independently downloaded and verified: SHA256 dc7d1ba10d66e6b3e39f7f3a85fffbb7522e8930390117b139185e5eb6627da6. Four files independently match their hashes inside manifest.json.
- Work A: articles_seen=2; source_text_present=2; unique_fatal_scope=0; structured_reports=0; NO_PARSEABLE_FATAL_TOTAL=2.
- Three retained source cards, all NEEDS_REVIEW; all excerpts empty; no structured report, no credits.

| Source | Receipt proves | Code explains | Synthetic offline case | Still unproven |
|---|---|---|---|---|
| T03 Ukrinform | HTTP 200; 25896 bytes; claim_deaths=null; empty excerpts | Word numerals already supported by Work A, but Work J excerpts required digits. A short unrelated article teaser could suppress main text | Word numeral 2 and short teaser vs. substantive main | Whether these exact failure mechanisms occurred in the real page |
| T04 MIG | HTTP 200; 110518 bytes; claim_deaths=null; empty excerpts | Cumulative "кількість загиблих зросла до трьох" is already recognized by Work A; Work J digit-only excerpt gate omitted word-number evidence | Word numeral 3, cumulative 3, non-additive 2 to 3 | Whether real page contains an unparsable grammatical variant, multiple attacks, or unrelated content |
| T05 Police | HTTP 200; 132694 bytes; claim_deaths=3; empty excerpts; attack date absent | Official content is deliberately separate from candidate-bound Work A publisher records and cannot infer date or incident identity | Undated police 3 stays NEEDS_REVIEW; safe quote retained, identifying proper name withheld | Which attack T05 describes, city vs region, and whether its real sentence is safely quotable |

Verified document SHA256: T03 b611e1a53f130bbed55883751adcebe18f95aea91f9543a1f4e4b1f37afae45d; T04 443ddadd46d5f3df01149bfdbd4e27ba17f03688c660ec87c417bf6b065dd32e; T05 1e993caa928ade1689a69676411736b669db9918dee851fa50ef71107d7f7b98.

Verified extracted text SHA256: T03 7453f3a0cb8066b97f49ea3d00f46d519e454d73bf63db98190b2650a214dad6; T04 7e045a964ea85846dc9462568dc0cb7992fa83ac3e0afbce208cc4f466e32bdf; T05 1857286a32e1b75e94e8c46231106298c9d12c2ba458009eb2e64b8fe21e50c4.

The hashes do not allow reconstruction or inspection of the original ephemeral text. They establish integrity of the captured bytes and normalized text, not that any desired sentence survived cleaning.

## Narrow changes

1. HTML extractor previously took any article element over main, including an unrelated short preview; it now prefers an article with at least 180 characters, otherwise the main region. Skips additional non-content tags and records only a non-sensitive extraction-scope label in the receipt. This is a controlled counterexample fix, not a generic site parser.
2. Short evidence selection previously required the count's digit characters and returned nothing if total was None. It now checks full fatality sentences with the existing Work A count recognizer, including word numerals, and can preserve a relevant quote with claim_number=null. Full 170-character limit remains. It no longer cuts the sentence at 23 words or 170 chars, which could erase negation/uncertainty.
3. Work J distinguishes unknown fatality totals and no relevant complete sentence. Work A now records numeric counts for fatality mentions, parseable and rejected scopes without source text.
4. Runner separates privacy-withheld quote from absent quote, while preserving the existing strict privacy filter, NEEDS_REVIEW and zero-publication decisions.
5. Work A fatality count recognizer already supports "двоє", "троє" and "зросла до трьох"; no speculative change to number or incident-confirmation logic.
6. Existing owner authorization is consumed. The runner pins original Work A / Work J Git blobs and is intentionally NOT repointed at the updated research code.

## Safeguards and test boundaries

New synthetic tests cover wording, 2 -> 3 never 5, separate incidents, missing attack date and police association, HTML menu/ad/main extraction, complete short excerpt retention, name withholding, no inferred facts and no publication. Frozen pre-launch Work N 68 offline tests and existing Work A tests are executed separately: frozen safety tests must not be made to run against altered immutable authorization pins. The original 18 -> 20 -> 23 physical evidence/generator regression remains an earlier validated checkpoint, not a new physical regression proof unless the exact retained artifact and generator are rerun.

**Observed physical evidence on code-and-tests HEAD 90f708bdff9f04f84ca5d709f76789647ee52537:** [GitHub Actions #43513639931](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43513639931) SUCCESS. Frozen E/G/I/J/K/L baseline: 68 PASS, 0 FAIL, 0 SKIP. New Work O / Work J/E: 31 PASS, 0 FAIL, 0 SKIP. Work A: 34 PASS, 0 FAIL, 1 SKIP (missing untracked historical cached_evidence.json; not reported as passed). Total 133 PASS, 0 FAIL, 1 SKIP. Separate pinned original-evidence ingestion and exact existing generator verification succeeded: 18→20→23, +23, five source-empty clusters blocked. Zero new publisher/police GET; no production publish or automatic casualty credits.

[Proof artifact #14080260918](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43513639931/artifacts/14080260918), ZIP SHA256 **731f2d94e0844513e804bc83aac40ef8ca3fb1fa5ec854f604788448314c0f39**, independently downloaded and hashed byte-for-byte. All **7/7** manifest file SHA256 hashes independently rehashed and PASS. Proof manifest SHA256 values: baseline.log 83542845e09caf50e5f7a93f485e0e00a17fa19666fab7d0d763d44186485e76; new.log ce31b18d989d896fb1dcf9eb0ccbe9bb13697709d2dbac5c790851d45113e89d; work-a.log f3184879d2e3b192fa7be2274c977b5e5fd6b4dade04ef03bebe50ae23644edb; proof.json d4906e12b4f4a308eb0ae68a1e6afa5a9dad9605111e783a7510c102d2c4940e.

**Exact-HEAD caveat:** This report update creates a documentation-only successor commit. Verify the successor's GitHub Actions SUCCESS separately before reporting it as exact-final-HEAD PASS. The successful code-and-tests HEAD above is immutable and remains validated, including all affected implementation files.

## Why the live pilot failed, and what must wait

T03 and T04 text reached Work A, but no unique parseable fatality scope was detected. The real reason is unknown: HTML extraction may have lost the relevant sentence, an unsupported variation may have occurred, or the text could describe conflicting scopes. The Work J excerpt implementation demonstrably could not retain word-number evidence, and could not retain any relevant fatality quote when no numeric total was parsed. T05 number 3 did not establish an attack date, city boundary or event match; the absence of excerpts could also reflect privacy withholding. Never infer an event from source URLs, titles, or expected counts.

A new controlled HTTP replay is required to verify the fixed processing on real T03/T04/T05 pages, not to validate the already-proven synthetic code paths. This report is a proposal for NEW owner consent only, NOT authority to run.

### New owner approval package (NOT EXECUTED)

Sources: same three exact T03/T04/T05 URLs as the Work N capture plan (Ukrinform AMP, MIG article, Zaporizhzhia police report). Purpose: establish whether the actual article body contains a fatality sentence, where it appears in HTML, whether the current parser selects it, why short quote is rejected/withheld, and whether police report describes the same attack. No other URLs or redirects by default. Limits: one authorization, one execution, max 3 initial GET; up to 6 aggregate only for exact redirects separately allowed by owner; max 1 MB each, 15 seconds, 0 retries, at least 1 second between requests, 24-hour maximum consent window. Distinct new grant, branch and exact prelaunch SHA required; consumed Work N consent cannot be reused.

Safe output only: response SHA256, extracted text SHA256, extraction region and character count, count of fatality-containing candidate sentences, aggregated rejection-stage counts, privacy withholding reason and at most 170-character de-identified COMPLETE relevant excerpts. Never persist full HTML/text, names, addresses, phones or unapproved quotations; never automatically associate T05 or record a casualty credit. Any expanded raw capture requires separate privacy authorization not included here. No publisher HTTP executed under Work O.

**Checkpoint for casualty coordinator:** CASUALTY-WORKO-PARSER-EVIDENCE-PARTIAL-REAL-HTML-REQUIRED-01. PR #71 and PR #117 must remain unmodified.
