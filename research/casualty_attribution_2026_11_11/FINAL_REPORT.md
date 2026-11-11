# CASUALTY-ONE-ATTRIBUTION-FIX-RESEARCH-01 — offline proof, NOT safe to promote

Date: 2026-11-11. **Research-only. Publication OFF; code not approved for merge.**

## Inputs and scope

- Exact frozen source: [artifact 13845600971](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998990269/artifacts/13845600971), ZIP SHA256 `3fa949194a80d70c23ea3d6f757878f770bff6e1345f7787e51ff9df67341503`; `evidence.json` SHA256 `68ceccdcca68a0c93d42a0c0173c32c9ab47b659415e9bd2b274df8d9cf0fdf9`.
- Reviewer at base blob `1fe711626a48817ae16be55c875fdf7f93790d8c`. No source HTTP; no changes to transport, WIP, `revisions.csv`, production, C6/Neon or rules outside source attribution.
- Existing [PR #65](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/65) and [PR #66](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/66) remain open/draft/unmerged.

## Root cause and narrow edit

In retained Odesa/Suspilne article `f4719e871b92e7563c7150da`, sentence:
`Про це повідомив очільник Одеської міської військової адміністрації Сергій Лисак.`
The old `_origin_attribution` regex matched `повідомил`, not masculine singular `повідомив`. It also relied on a separate verb match somewhere else in the whole article. Added one direct, contiguous phrase pattern, restricted to `повідомив очільник … міської військової адміністрації`. Ordinary mentions of the police, prosecutor, city administration, or a reporter do not match the new pattern.

Dnipro/Suspilne `5d60e1c78026fdc494ea3c84`: excerpt asserts two deaths on November 3 but cites only eyewitnesses, not an official confirmation of those deaths. The correct source is still `unattributed`; NEEDS_REVIEW.

## Offline replay outcome and safety verdict

- Focused frozen-artifact test: **4/4 PASS** on [Actions #43007370603](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43007370603) (final exact test HEAD `b1e00eec`, SUCCESS; proof artifact [13849147170](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43007370603/artifacts/13849147170)), including actual Odesa and Dnipro excerpts, unrelated authority mention negative controls, unchanged inputs and two-pass idempotency.
- First-pass: **0 → 1 AUTO_READY**, **0 → 1 offline proposal**, specifically Odesa November 7 +1 death. Second identical pass: **0 new proposals, 0 duplicated deaths**. All outputs remain research-only.
- **Not accepted as a reliable revision:** The extracted Odesa incident has `place=residential-buildings`, `attack_slot=night`, `attack_type=drone`, although the fatal evening city attack is described as an infrastructure hit with no weapon specified in the fatality sentence. `residential-buildings` comes from the *earlier nonfatal city attack* and `drone` from the *separate attack on the north of Odesa oblast*; `night` is also likely inferred from `північ` (north), not a nighttime attack. Thus a real origin-verb defect has been fixed in isolation, but the one resulting `AUTO_READY` uses cross-incident context and is **NOT a justified correction**. Do not merge or publish without separate approval of an incident-locality/identity fix; that fix is expressly outside this task.

## Other excerpts — no change in this task

- Kharkiv/LB.ua: official reference to the Kharkiv regional administration appears, but no complete cached incident anchor matching the reviewer constraints; death count is singular without its required definite numeric total pattern and later 27 October strike plus earlier drone hits appear in the excerpt.
- Lutsk/UNIAN: article has updates of four, five and six dead and official references to OVA and Lutsk city council, but no unique extracted total; reviewer does not treat those changing numbers as a single safe total. No cached incident report.
- Kharkiv/Korrespondent was the fifth URL, not part of the four usable articles; HTML extraction stopped with `HTML_NO_ARTICLE_PARAGRAPHS`.

## Decision

**Code remains on an isolated research branch, not production-ready.** Genuine direct-attribution recognition regression fixed and tested. Correct automated casualty proposal still **BLOCKED** due to mixed-incident extraction. No security/provenance guard has been deliberately weakened. No WIP queue or casualty ledger changes.
