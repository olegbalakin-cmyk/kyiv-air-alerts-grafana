# Practical evidence rules — implementation review (2026-11-10)

**Status: IMPLEMENTED ON DRAFT BRANCH; EXECUTABLE PROOF NOT YET VERIFIED.**
**Publication: NEVER ENABLED.** This is not an accepted checkpoint or a production decision.

## Scope
The existing `casualty_auto_review.py` is modified in place; no new service or workflow.
The owner-approved, **offline/shadow only** presumption considers a death civilian
when a definite Russian air-attack death is reported and no marker of military
victims, military target/equipment or mixed casualties is present.
The three retained states are `civilian_explicit`, `civilian_presumed`,
`civilian_ambiguous`. The ambiguous state remains NEEDS_REVIEW.
Status basis, underlying source attribution and article excerpt SHA-256 are saved.

The new extractor accepts Ukrainian cardinal words, attack dates phrased in
ordinary news language, time of day rather than mandatory HH:MM, and a
meaningful place/target instead of a street address. It can corroborate
an undated article against a unique dated article, never against a city/date
alone when multiple anchors remain. The provenance explicitly records when
the date came from a different article. `trigger_episode_ids` are not used
as event identity evidence. Media that share a primary attribution are not
independent.

A single attributed competent official origin (DSNS, prosecutor, police or city
military administration) can support a death total for shadow eligibility;
a media assertion with no traceable primary attribution remains conservative.
The original strict rule and human-confirmed Sumy no-op remain compatible
with the new branch's methods. Existing `revisions.csv` is not written.

## Real saved excerpts: evidence-supported expectations, NOT a PASS claim

| Event | Old verdict | New test expectation | Delta expected | Qualification |
|---|---|---|---|---|
| Dnipro 2026-11-03 | NEEDS_REVIEW | AUTO_READY, civilian_presumed | +2 | Suspilne gives dated morning missile attack; ArmyInform attributes two deaths to DSNS |
| Odesa 2026-11-09 morning | NEEDS_REVIEW | AUTO_READY, civilian_presumed | +3 | Suspilne gives dated morning drone attack and attributes three deaths to prosecutor; LB's separate late attack must not add three more |

**IMPORTANT:** These values are targets of executable assertions, not validated
offline results. No local checkout of the exact branch was available in the
execution environment, and existing repository CI for this PR only checks
coordination documents. The new casualty tests and 4-excerpt `reproduce.py`
have **not** returned a verified PASS. Neither AUTO_READY nor any number of
proposals is claimed as an observed output from the new code.

The preserved production ledger copy at `pinned_revisions.csv` has one
Sumy entry and no Dnipro/Odesa November rows. Baseline coverage in
`baseline_coverage.json` ends 2026-09-18 for both, so these events are after
the historical snapshot. The original snippets are **excerpt SHA-256s**, not
full HTTP captures, and cannot certify that full articles had no contrary
facts. Full-article capture remains the most significant evidence limitation.

## Whole offline queue
The last **actually executed** offline run predates these rule changes:
1,654 messages, 1,505 potential event/publication groups, 1 already-accounted
AUTO_READY Sumy event (+0), 1,504 NEEDS_REVIEW, 0 new proposals.
The pinned prior diagnostic reports are summary-derived and not extracted
from article bodies; they cannot be silently treated as new qualified evidence.
**No after-change 1,654-message replay was executed**; any numerical before/
after comparison would be fabricated. New `sources.json` holds four snippets,
not full-text evidence for the other 1,650 messages.

## Required narrow verification before acceptance
Run from the PR checkout with Python 3.12+:

```bash
python -m unittest discover -s kyiv-air-alerts-grafana/tests -p 'test_casualty_auto_review.py' -v
python -m unittest discover -s kyiv-air-alerts-grafana/tests -p 'test_casualty_real_evidence.py' -v
python research/casualty_real_evidence_2026_11_10/reproduce.py
```

Then run existing operator tests and a clean replay of the pinned WIP queue,
compare before/after reason counts, inspect `results/verdict.json`,
`first/proposals.csv` and `replay/proposals.csv` and confirm second-run
`unique_proposals=0`. Until then: **NOT ACCEPTED; NO MERGE**.

Residual NEEDS_REVIEW reasons: no retained fact-bearing text for most queue
items, no reliably bounded city, mixed/military indicators, multiple same-day
strikes without a unique identity, unknown primary source, contradictory total,
late death without total, or baseline/ledger overlap.

**Single next step:** run the narrow test commands and actual read-only
offline queue replay in a runnable exact-SHA checkout; fix only demonstrated
failures and preserve logs and output hashes on this draft PR.
