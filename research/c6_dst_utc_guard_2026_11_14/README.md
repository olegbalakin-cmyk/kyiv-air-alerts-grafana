# C6 DST UTC union prevention: review-only preparation, 2026-11-14

## Status
`RESEARCH_ONLY=YES; DST_CORRECTION=OFF; PRODUCTION_UNCHANGED=YES; GLOBAL_CUTOVER=YES`.

This branch is based on exact `site-prod@c980c3f70ed894d2583fc83ecdedd1f82c04afb1`. It changes only the autumn-DST-safe sort and boundary comparison in the existing `union_alerts()`, adds the four source-witness regression tests, and a research-only offline CI. This is not the historical Neon or published-site repair. Merge would change the live collector; **separate owner GO and follow-up validation are required**.

## Independent read-only Neon check (2026-11-14)

- Read-only role `c6_shared_reader_v2`, transaction_read_only `on`, existing branch `br-bold-mode-b5rub8pq`; only SELECT statements used.
- Three previously confirmed wrongly merged physical rows remain in Neon.
- Seven source-witness legacy IDs are absent; seven exact (city,start,end) candidates are also absent.
- The protected earlier Cherkasy physical row remains present.
- Source evidence and expected +4 episodes / -9,059,359,958 microseconds on the frozen old corpus: `C6-DST-UTC-01`, accepted `7265e40a` and research `14e1b0b9`, `research/c6_dst_projection_2026_11_09/README.md`.
- This current Neon check confirms the **persistence of the known anomaly**, but does not re-certify source witness bytes, whole-corpus parity, or a current 23-city after-correction output.

## Historical correction integration is independently gated

The accepted research `c6-dst-projection-v1` is default-OFF and pins old `LINEAGE_SHA` / `BINDING_SHA` from the 2026-11-09 frozen corpus. Regular C2 changes the corpus. Activating that old correction unchanged would block generation on drift and could interrupt the four-hour publisher. Do **not** merge the frozen calculation-layer patch or enable `DST_CORRECTION` in the scheduled workflow.

Next:
1. Validate the preventive patch in exact-head offline CI and review deployment to `site-prod` (separate GO).
2. Rebind the four-case evidence to the latest **same-run C2/Neon** readback and ensure repeatable compatibility with future scheduled corpora while preserving exact old-row identity and all unaffected cities.
3. Dry-run historical correction on a current six-JSON candidate; verify 23/23, the four-city arithmetic, Kyiv/casualty/aux/CSV parity and byte-exact OFF rollback.
4. Get separate owner GO for any production code/data change. No SQL writes/deletes, DDL, source HTTP, C2 dispatch, automatic flag edit, or Netlify deployment here.
