# CASUALTY-CUMULATIVE-OFFICIAL-UPDATE-63-01 — real Zaporizhzhia + 63/63 offline PASS

**Date:** 2026-11-11. **Scope:** research-only, no publisher HTTP, no WIP/revisions writes, no merge, deploy, publication, allowlist or Neon/C6 changes.

## Starting state / evidence boundary

- Starting exact accepted military-fix PR #69 head: `03cfaecb71111bfd3b896e4a19ca6f027118963f`, [54/54 successful Actions #43069489502](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43069489502). Explicit deceased servicemembers remain `civilian_ambiguous` and cannot create a civilian proposal.
- Original 3-source one-shot publisher capture: [Actions #43053796144](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144), [artifact #13870872313](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144/artifacts/13870872313), ZIP SHA-256 `f7255cba58faea1ecb7defbe2cdbed40db2ddf05a5b92f5fe3530cead32f2148`, `evidence.json` SHA-256 `84ffea1315d41b8ec67b55a07273d6bbd7d6e8e14191801402168f7fddf4e5df`. No new publisher requests.
- Frozen independent gold (recorded **before** reviewer validation): commit `4174d3bbb8e3d34e640c9d2c0677f3fa02d98a6a`; Zaporizhzhia candidate `e0fba98b19473874e9a1d8f1`, original Suspilne excerpt SHA-256 `011894b7c4bd906dcfd0c5d2f7cef07a932976ca313220fa9089999264feb259`. Reviewer baseline [Actions #43056505565](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43056505565), artifact #13872120318: Zaporizhzhia held `TOTAL_DEATHS_UNKNOWN_OR_CONFLICTING`, no proposal.

## Root cause and narrowly scoped change

- `_fatal_total()` previously collected all fatality figures as a set and accepted only one distinct value. The real same-wave 18 → 20 → 23 cumulative revisions therefore returned `None`, causing no cached report and `NEEDS_REVIEW`.
- Added `_cumulative_total_update()` as a **conditional** fallback for conflicting numbers: collect source-adjacent death-count statements, require each nonfinal alternative to have explicit update context, no different incident/attack slot/weapon, a uniquely attributable competent official corrected total, and fail closed when official alternatives remain ambiguous. The article order is **not** interpreted as chronological, and the maximum is **not** selected. The chosen figure is traceable to the competent official sentence SHA and original immutable article SHA.
- Recognize directly stated `КАБ` / guided aviation bombs as `guided-bomb` so the existing air-attack evidence condition can evaluate the real KAB event. Keep all other date, city, civilian, attribution, event-identity, baseline/revision and duplicate protections intact.
- Existing military-status historical replay assertion changed narrowly: the one **unrelated** Zaporizhzhia research-only positive is now expected, but Ivano-Frankivsk military deaths still yield no civilian proposal.
- Intentionally **not** changed: known false `place` extraction from `на вулиці під час тривоги`, transport allowlist, source HTTP policy, production/WIP, Neon/C6.

## Physical proof

[Exact-head GitHub Actions #43080101616](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43080101616) at `9009a6a83388a939bdeeac7e1795bfec3aa8054d` **SUCCESS, 63/63 PASS** = previous 54 tests (45 historical + 9 military) plus **9 new** cumulative cases. [Proof artifact #13883418211](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43080101616/artifacts/13883418211) ZIP SHA-256 `7a8a77d592921346d73082260fbcc55ac84b3c06a35f828caaaad9ed4a2332af` (independently downloaded and verified). Its `first_events.json`, `shadow_proposals.json`, `repeat_summary.json`, `test_log.txt`, `sha256_verification.txt` and verdict are retained.

### Real 3-article shadow replay result

| Article / guard | Outcome |
| --- | --- |
| Zaporizhzhia, 10 Oct 2026, one morning KAB wave | `AUTO_READY`; single **total 23** with confirmed DSNS provenance and the three extracted cumulative figures **18, 20, 23** |
| Zaporizhzhia attribution/date/city | `origin_id=dsns`; incident city `zaporizhzhia`, date `2026-10-10`, `attack_slot=morning`, `attack_type=guided-bomb`; `place=unlocated` (no invented location) |
| New shadow-only proposal | One: `casualty-event:15926922be20f6beb1bc7049:total-23`, `deaths_delta=23`, `already_accounted=0` under **pinned research ledger only**; `publication_allowed=false` |
| Replay of same inputs with previous proposal reserved | **0 new proposals**, `prior_proposals_suppressed=1` |
| Ledger update safety | Actual-event scenario with **18 already counted** proposes only **+5**; after accounting 23, proposes **0** |
| Ivano-Frankivsk real explicit deceased servicemembers | `NEEDS_REVIEW`, `CIVILIAN_AMBIGUOUS`, no civilian proposal; earlier source-`place` bug remains out of scope |
| Kharkiv real weekly oblast multi-strike article | `NEEDS_REVIEW`; no borrowing of oblast deaths to Kharkiv city |
| Separate second strike, additional/incremental deaths, unexplained figures | Fail closed; no cumulative `AUTO_READY` |
| Official downward 23→20 correction | Selects **20**, not maximum |
| Multiple incompatible official corrections | Remains unresolved; no automatic total |
| Previous Odesa, Dnipro, old attribution and military regression | All prior **54/54 PASS** |
| Input SHA-256 frozen | **PASS**, original three-source, historical five-source, two legacy fixture files and other protected evidence inputs unchanged |
| Operational writes | **None** |

**Interpretation:** `+23` is a **research-only proposal** against the pinned ledger/baseline snapshot, not a claim that production has never counted those deaths. Production reconciliation is a separate gated decision.

**Release decision:** **RESEARCH PASS ONLY. NO MERGE / NO PUBLISH.**
