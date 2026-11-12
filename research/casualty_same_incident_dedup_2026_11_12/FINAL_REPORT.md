# CASUALTY-SAME-INCIDENT-DEDUP — clean `site-prod` patch (2026-11-12)

**Scope:** Draft research patch; no merge, deploy, data correction or publication. October 2026 coverage remains `COVERAGE_INCOMPLETE`.

- Target: `site-prod` at `fc7261660bdee75ee59296ee94cc1189be6b1a22`.
- Isolated branch: `research-casualty-dedup-clean-site-prod-2026-11-12`; branched directly from the target SHA.
- Verified implementation source: PR #89 at `d406875cd5ccbd382fc736fcbb9a3cdc3a448289`.
- Accepted research checkpoint: `CASUALTY-SAME-INCIDENT-DEDUP-25-01`.
- Immutable source proof: [Actions #43201016241](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43201016241), 25/25 subject PASS; [artifact #13936055275](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43201016241/artifacts/13936055275), SHA-256 `4a7aefc61f4d47683b72d0b33ec81deb57104eff6933873a2b2923d2ada4179f`.

## Exact patch boundaries

The production implementation `kyiv-air-alerts-grafana/scripts/update_casualties.py`, the isolated physical harness `test_dedup.py` and `frontend_probe.js` are copied byte-for-byte from the verified research commit. This report is rewritten for the clean branch. The research GitHub Actions workflow retains the strict offline harness but restricts push triggers to this branch and grants only `contents: read`.

Only these five paths differ from `site-prod`:

1. `.github/workflows/research-casualty-same-incident-dedup.yml`
2. `kyiv-air-alerts-grafana/scripts/update_casualties.py`
3. `research/casualty_same_incident_dedup_2026_11_12/FINAL_REPORT.md`
4. `research/casualty_same_incident_dedup_2026_11_12/frontend_probe.js`
5. `research/casualty_same_incident_dedup_2026_11_12/test_dedup.py`

No `revisions.csv`, original casualty data/manifest, JSON, frontend, WIP, C2, Neon, Netlify or production workflow is changed. The final HEAD, diff stats, strict CI run and artifact digest must be checked in the clean Draft PR, not inferred from the source run.

## Algorithm and evidence boundary

Optional inbound fields `incident_id`, `count_kind`, `baseline_credited`, `identity_proof` and `credited_proof` distinguish verified cumulative incident totals from increments and known already-credited deaths. The generator groups reports for the same proven incident, rejects decreasing or ambiguous totals, inconsistent proof, reused candidates/sources across incidents, and unverifiable previous credit. Missing identity or credit fails closed; the exact existing Sumy +1 revision remains compatible. No outbound JSON schema change.

Proof handles are traceability references, **not automatic validation** that a source proves incident identity or the amount already counted. Human review remains mandatory for any new confirmed correction. The generator must not infer historical event-level credit from monthly aggregates.

## Offline acceptance

The original physical suite ran 25/25 PASS on the frozen `site-prod` corpus, including Zaporizhzhia 0→23, 18→23, 23→23 and 18→20→23; independent same-day incidents, Sumy +1, idempotence, rollback, 22 other cities, historical months, frontend function, protected input hashes and October 316→339. The clean-branch workflow repeats the same test file on its own exact commit. The final GitHub run, artifact and test count are documented in the Draft PR after execution.

**NO MERGE / NO DEPLOY / NO PUBLISH.** Separate owner approval, fresh `site-prod` validation, source-identity evidence, partial-month decision and controlled rollback plan are still required.
