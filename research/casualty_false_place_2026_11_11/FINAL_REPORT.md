# CASUALTY-FALSE-ATTACK-PLACE-76-01 — isolated research-only location extraction fix

**Date:** 2026-11-12. **Status:** RESEARCH PASS (offline only), pending immutable report-head CI verification.
**Base:** PR #73 exact `6bfdf35a15bac0447bdfc3e975a9c5e3b70a15d5`. New branch: `research-casualty-false-place-2026-11-11`.
**Verified implementation:** [commit 9a9fd7ea](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/commit/9a9fd7ea7935e09ece4555ac680ec695a4d64f4e).
**Physical CI:** [Actions #43180248842](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43180248842), **SUCCESS, 76/76 offline tests**, comprising the previously accepted 63 and 13 new tests.
**Proof artifact:** [#13925259351](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43180248842/artifacts/13925259351), GitHub-reported ZIP digest SHA-256 `f8299ac9b9159d228f078189830775cab01cab34c42c37b5df93f126d338f3c9`.

## Root cause

The old `extract_cached_reports()` selected any substring after `на вулиці` or `за адресою`, regardless of whether it described an impact. In the original LB.ua 11 Oct 2026 Ivano-Frankivsk evidence, a general safety warning about remaining `на вулиці під час сигналу "повітряна тривога"` was incorrectly promoted to an incident location. This false location also acted as the only incident anchor for a correctly parsed fatal report. Simply removing that value caused a regression: the report disappeared, thereby hiding its explicit military-deceased classification.

## Narrow fix

- `_attack_place()` now requires an impact/direct damage or casualty predicate **in the same sentence**, rejects safety/advisory contexts, non-street generic terms after `на вулиці`, and explicit descriptions of another strike.
- It continues to recognize concrete named streets/addresses and impact-linked residential buildings, food warehouses and infrastructure objects. No new geographic model.
- A uniquely dated, single-narrative-scope, city-bound, Russian air attack with a fatal count may retain its **own** parsed report when `place` and `attack_slot` are unknown. It does **not** authorize an undated second report to join based only on city/day/death count. Existing multi-incident narrative boundaries remain in force.
- Existing `incident.place` contract remains `unlocated` when no direct place evidence exists. No changes to the death total, civilian-status classification, official attribution, deduplication, source transport allowlist or publication logic.

## Physical regression results

| Requirement | Result |
| --- | --- |
| False `place` root cause | Unconditional `на вулиці` / `за адресою` match; also an accidental report anchor |
| Fix | Sentence-local direct-impact extraction + safe unlocated own-report anchor |
| Ivano-Frankivsk place before / after | Safety-warning suffix after `на вулиці` → `unlocated` |
| Ivano-Frankivsk civilian classification / status | `civilian_ambiguous`, `facts.civilian != true`, `NEEDS_REVIEW`; no +3 civilian proposal |
| True impact street/address/building/object | Positive tests PASS |
| Multiple attacks and location borrowing | Both directions and explicit second-strike control PASS |
| Zaporizhzhia | `AUTO_READY` for one cumulative official total **23**, shadow-only +23 versus pinned research ledger |
| New targeted tests | 13/13 PASS |
| Previous accepted regression | 63/63 PASS |
| All tests | 76/76 PASS, CI #43180248842 |
| Replay duplicates | 0 new proposals on repeat |
| Protected original evidence | SHA-256 verification step PASS for frozen three-article, five-article, historic two-file fixtures and pinned inputs |
| Publication | `publication_allowed=false`; no merge or operational writes |

Original three-publisher retained artifact [#13870872313](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144/artifacts/13870872313) ZIP SHA-256 `f7255cba58faea1ecb7defbe2cdbed40db2ddf05a5b92f5fe3530cead32f2148`, original `evidence.json` SHA-256 `84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df`. Gold LB.ua excerpt `ce5dde16ff43e43f03a53ae0b39e637f068daa0bef31bb924a2f3f43a60d646d`. No new publisher/media HTTP: evidence restored only from prior immutable GitHub artifacts.

Offline replay covers preserved Odesa/Dnipro historical negatives, Ivano-Frankivsk military negative, Kharkiv city-vs-oblast negative, and Zaporizhzhia official positive. Baseline and original evidence remain unchanged. The published death ledger was **not** examined, modified, or reconciled.

**Boundary:** This is an isolated **RESEARCH PASS** and not approval for merge, production, deployment, WIP modification, changes to `revisions.csv`, casualty publication, or Neon/C6. The Zaporizhzhia `+23` remains research-only against the pinned baseline; production reconciliation is a separate later decision.
