# Recovered parity verification — 2026-10-31

The saved replay was physically executed from the frozen Neon readback. Its four
saved reports are byte-identical to recovery commit `e1534955`. This is an offline
consumer projection, not a fresh database query or production deployment.

| Check | Result |
| --- | ---: |
| Physical closed AIR rows / cities | 31,935 / 23 |
| Rows after in-memory DST proposal | 31,939 |
| Direct 22-city differences without / with DST | 0 / 366 |
| Full differences with DST | 1,354 |
| Expected DST projection effects | 847 |
| Legacy derived omission of accepted C4-KH-06 | 457 |
| Cutoff timestamps / research marker | 49 / 1 |
| Unexplained differences | 0 |

The old grouping of all 1,304 substantive paths as DST was incorrect. A single
Kharkiv interval counterfactual exactly reproduces the published heatmap and
exploration fields: the legacy derived loader omits the owner-accepted March
5–6, 2025 correction. The Neon candidate already uses that accepted interval.
`derived_owner_correction.patch` adds the existing correction helper to the
legacy derived loader. Real loader tests verify correction, idempotency and
fail-closed handling of unexpected input. This patch is research-only.

All seven proposed DST intervals match the pinned UkraineAlarm bridge exactly.
Four physical DST cases remain unrepaired in Neon. Alerts-combined interval and
source semantics match the reference; timestamp formatting can differ.

## Reproduce

Use repository source including this directory, a separate checkout of
`site-prod@0ecbb291e8f443f7ab366bc4ac033d096f2c44f4`, Python 3.12+, and
`requests==2.34.2`, `beautifulsoup4==4.15.0` (recorded execution: Python 3.12.14).
From the repository root:

```bash
python research/neon_cutover_work_2026_10_30/verify_parity.py \
  --site /path/to/reference/kyiv-air-alerts-grafana \
  --work /path/to/separate/replay-output
```

No credentials are needed. The harness unpacks and hashes inputs, blocks socket
connections, executes both replay modes, independently walks every JSON path,
tests the minimal loader patch, and saves reports and hashes under `--work`.
`--reuse-replays` performs analysis on existing output and is not a new replay.

The candidate is suitable for a bounded research preview with the DST simulation
clearly identified. Production cutover remains NO. Complete upstream historical
CSV and original ingestion receipts are not supplied by this snapshot; full
source-to-database regeneration is not asserted. Browser/CSV, update freshness,
source switching and rollback remain outside this verification.
