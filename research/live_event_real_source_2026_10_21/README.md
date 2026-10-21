# Bounded real-source research replay (2026-10-21)

## Scope

Non-authoritative frozen-news processing for a bounded Kyiv cohort. This proof does **not** activate an operational monitor, publish attack events, access Neon, change the 23-city WIP state, modify historical frozen verdicts, or poll UkraineAlarm.

Inputs are the two exact earlier GitHub Actions evidence archives (IDs `11608819645` and `11609004684`), including 67 historical Kyiv alert episodes and 105 source candidates. The actual repaired development classifier is pinned by Git object `4019b8374dcc44846df04ed0cc41356652214bff`, proof source `65c32480c88c0e72824764b04515576b46a3e158` at commit `906b9e18aa9e0a2056bcb798b9870ae35d8dee3d`.

The replay selects at most three cases: a candidate-backed strict/sensitivity case, a source-backed needs-review case, and a frozen search with zero retained candidates. It does not create candidates. The full classifier is rerun twice, and source and classifier identities are checked before any local acknowledgement. The `NO_CONFIRMED_EVENT` label is **bounded to the archived search coverage**; it is never used as proof of no physical attack or of complete live discovery.

## Durability and tests

Local disposable JSON stores result and ACK together in one atomic replace, with explicit nonterminal error states. Retried failures remain eligible; least-recently-attempted ordering avoids cap-induced starvation. The synthetic failure-injection fixtures do not enter any historical or canonical results. Each CI execution starts with fresh local disposable storage: repeated separate CI runs establish reproducibility only, not cross-run state handoff.

Two machine-readable classifier traces, a JSON report, an HTML report and an isolated local ledger are uploaded as research-only artifacts. A green CI job alone is insufficient for an accepted event claim; inspect the report plus job log, exact tested source and artifact digest.

## Preliminary proof

First working real-source CI: [39590006641](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/39590006641) on `acd6b74256bbde53c701b36f3c48557a283705d9`. Three selected episodes, three actual candidates, three local ACKs, full classifier fingerprint `57fa5e402a79ab852b48d540de6a56581c3dd27fde4e986d3cce28ea3b611af8`; all six isolated ledger fault/fairness controls PASS. Initial run `39589777392` failed on archival artifact redirect HTTP 401, addressed by using the verified requests redirect behavior; the original failure remains visible.

## Remaining acceptance boundary

This evidence is not proof of current publisher fetch availability, continuous coverage, 23-city scheduling, complete source provenance in the present day, safe cross-run durable handoff, a canonical PostgreSQL transaction, or any production WIP activation. Main H2 and R6 controls remain separate.
