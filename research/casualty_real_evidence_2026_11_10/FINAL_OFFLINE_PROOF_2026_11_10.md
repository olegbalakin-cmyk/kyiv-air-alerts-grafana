# CASUALTY FINAL OFFLINE PROOF — 2026-11-10

**Verdict: PASS for bounded offline reviewer proof; NOT a production/publication approval.**

- Exact code under test: `719c93c6239999bc430abc95bc8694205c103bbc` (draft PR #52, unchanged).
- Isolated CI workflow commit: `d7ee900bf89a420d888e10301ba637aac7f0dc67`.
- GitHub Actions run: https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42863730878 — **completed/success**.
- Uploaded proof artifact ID: **13785572875**, `casualty-exact-sha-offline-proof`, includes original test logs, result JSON/CSVs, hashes.
- No production, site, live queue, actual revisions.csv, Neon or schedules changed.

## Executed suite totals (from runner stdout)

| Execution | Actual result |
|---|---|
| `test_casualty_auto_review.py` | 35 tests, OK |
| `test_casualty_real_evidence.py` | 6 tests, OK |
| `test_casualty_review_operator.py` | 29 tests, OK |
| Real excerpt `reproduce.py` | exit 0 |
| Whole queue `reproduce.py` | exit 0 |
| SHA-256 preserved inputs | four checks OK |

**70 Python unittest cases PASS, zero FAIL.** This is a real GitHub runner execution of exact SHA, not a coordination-docs check.

## Four retained real-news excerpts

- 4 article records, 3 event groups; 3 eligible extracted reports; 2 AUTO_READY, 1 NEEDS_REVIEW.
- Dnipro 2026-11-03: **AUTO_READY**, `civilian_presumed`, **+2**. Event ID `casualty-event:802ed277833ed4bbd3771a0c`, DSNS-attributed count through retained ArmyInform excerpt.
- Odesa 2026-11-09: **AUTO_READY**, `civilian_presumed`, **+3**. Event ID `casualty-event:e53dc7cabe9362a8bd705160`, prosecutor-attributed count through retained Suspilne excerpt.
- The later Odesa attack mentioned in the LB extract was not added as another three deaths.
- `results/first/proposals.csv`: two proposed rows, +5 total; `results/replay/proposals.csv`: headers only, **0** newly proposed rows. Replay summary: 2 previously proposed rows suppressed.
- Inputs unchanged: sources.json, pinned_revisions.csv, baseline_coverage.json, cached_evidence.json all passed SHA-256 comparison.

**Scope limitation:** This proves behavior on *four preserved excerpts*, not on full HTTP article bodies; no independently verified full-body hashes or live source recapture. The CSV status field `confirmed` is a revision-format shadow proposal only, not a human confirmation or actual ledger entry.

## Full historical queue — actual rerun

| Metric | Before rule change | After rule change |
|---|---:|---:|
| Messages | 1654 | 1654 |
| Potential groups | 1505 | 1505 |
| AUTO_READY | 1 | 1 |
| NEEDS_REVIEW | 1504 | 1504 |
| New proposals | 0 | 0 |

Previously accounted Sumy event remained the only AUTO_READY (+0), while the new article excerpts are separate shadow inputs and were *not* injected into the 1654 queue. New flexible extraction, civilian presumption and single officially attributed casualty source do not invent missing retained body evidence. The pinned diagnostic reports are summary-based and cannot be upgraded to factual full-text reports.

## Remaining operational gate

The bounded code proof is PASS. **Operational automation/publication is not approved.** The next separately authorized implementation should capture article text and provenance in the existing casualty-monitor and reuse the current reviewer; no new pipeline. Validate on a fresh queue snapshot before any publication decision.

### Pointers to immutable evidence

- [GitHub Actions run #42863730878](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42863730878)
- Artifact `casualty-exact-sha-offline-proof` (ID 13785572875) retains `results/verdict.json`, `results/first/proposals.csv`, `results/replay/proposals.csv`, original suite logs, full-queue summaries and input hashes.
