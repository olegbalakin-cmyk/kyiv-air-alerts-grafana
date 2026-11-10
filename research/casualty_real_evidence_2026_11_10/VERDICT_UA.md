# FIRST REAL EVIDENCE PROOF — bounded negative result (2026-11-10)

**Decision: NEEDS_REVIEW for both events; AUTO_READY=0, new proposals=0.** The four article URLs were accessible and their numbers match the control assumptions. This is **not** proof that no civilian deaths occurred; it is proof that these particular texts cannot clear the existing strict automatic evidence contract.

## Source retention and integrity

- `sources.json`: four specific source URLs, retrieval date, copied verbatim excerpts (maximum 25 words per article), line locations, SHA-256 of the **UTF-8 excerpts joined with LF**. **Hashes do not represent HTTP response bodies or full article text.** The complete body/headers could not be exported to this runner. The snippets are preserved with their provenance and are reproducible as the inputs to this bounded test.
- `pinned_revisions.csv`: unmodified research copy of the verified production `site-prod@1157c81b` ledger (Git blob `8d7a2e2540bf4bf0f8c6227023821390bf82ce13`): one confirmed Sumy entry, no Dnipro/Odesa November rows. The `main` version of this CSV is empty and **must not** be silently substituted.
- `reproduce.py`: builds a **temporary shadow queue of four article records** from URLs/titles, passes only excerpts via the original `auto-propose` `articles` input, checks baseline/ledger, hashes input snapshots and compares two offline runs. No supplied `facts=True`, proposed incident identity, hard-coded death total or auto-ready labels.
- The original 1,654-row WIP queue and the candidate fingerprints in the prior `cached_evidence.json` are **not** replaced or edited. This is an isolated four-article parsing probe, **not** a replay of the entire real queue. Existing diagnostic candidate IDs: DN-1103 `41bebb97f70d0fdd4a04b116`, `5d60e1c78026fdc494ea3c84`; OD-1109 `74e84d0dff4b77858aa82bb4`, `eccc1ff1fb2602b2782750f6`, `6b272933d06ebaabe2ee6e1a`, `5b66f06ed9aa6654861618be`, `93607059f26871023b56195f`.

## Case findings

| Incident | What source text establishes | Independent origin status | Reviewer outcome | Proposed delta / gate |
| --- | --- | --- | --- | --- |
| Dnipro, 2026-11-03, morning missile strike | 2 deaths; city and morning missile strike, damaged homes | АрміяInform attributes death count to DSNS; Суспільне has original eyewitness reporting from the site, but provides no independently named source for the **death total** | NEEDS_REVIEW | None. Civilian status never explicitly stated; the excerpts do not give an exact incident time and address, and death-count independence is not established |
| Odesa, 2026-11-09, morning drone/warehouse strike | 3 deaths, city; Suspilne attributes the total to prosecutor spokesperson Inna Verba; LB.ua attributes it to MVA head Serhii Lysak | Two differently named authorities appear; whether their casualty totals derive from an independent underlying source is not proved. Media domains alone are not proof | NEEDS_REVIEW | None. No explicit civilian status; no shared precise attack-time/address identity suitable for automatic joining |

Important event identity control: LB.ua also describes a **second** strike at approximately 16:25 on 9 November. It is not the morning lethal attack and must never be grouped solely by city/date. The separate 10 November Odesa day of mourning is a **reporting/commemoration date**, not another 9 November attack.

## Real-text vs auto-propose

The diagnostic lexical probe (not an eligibility gate) extracts the words `двоє` / `троє` as 2 and 3 from all four source snippets and detects the later Odesa attack. The existing `extract_cached_reports` refuses to construct an incident when the document does not explicitly supply a single ISO attack date, HH:MM and street address. The strict `prepare` step also requires explicit civilian status and two independent origin families for every essential fact; absent support is UNKNOWN. **Do not manufacture those fields from a headline, general residential/warehouse context or a synthetic annotation.**

Running `python research/casualty_real_evidence_2026_11_10/reproduce.py` with a local copy of this PR prints a bounded verdict and writes `results/` in this research directory; it does not change production data. The targeted test is `python -m unittest discover -s kyiv-air-alerts-grafana/tests -p 'test_casualty_real_evidence.py' -v`. Earlier 58/58 tests cover 2→3 = +1, repeat = +0, two attacks in one day and stable event identity; this change does not alter their logic, but those tests must be rerun in a runnable checkout for a new PASS claim.

**Next minimal step:** add one already-authoritative item per event that explicitly establishes the civilian status, and for Dnipro a genuinely separate origin for the fatality total; also seek a precise common event identifier (place and attack window) before enabling full-text positives. Do not publish, merge or promote.
