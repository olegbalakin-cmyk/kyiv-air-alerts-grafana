# C6-OCT184-B1: freshness-aware Kyiv Neon display reader

Research-only. This code DOES NOT activate publication, change any parent, modify
Neon, certify physical identity for October 184, or rebind classifications.

The reader requires immutable source-row provenance (Git commit + blob), and a
separate bounded OWNER-approved **view-only** override for each of 184 frozen
minute/precise source candidates. No inferred `alert_episodes.source` column and
no minute-floor identity merge. All 55 classifications and 223 sources are raw
relationships; 28 minute-parent classifications remain unresolved for enriched
view consumers. Fresh verified completed Kyiv Digital rows are selected even
when they start before the final official `start` watermark. Unknown overlaps are
explicitly unresolved and not certified for publication.

Run standalone synthetic tests:

    python -m unittest -v test_source_priority_reader

Run against an approved RO compute only after injecting an approved secure
`C6_B1_READONLY_DATABASE_URL` (not via Git, stdout, or artifacts):

    python source_priority_reader.py --bundle frozen_october_382_198_bundle.json \
      --git-json alerts_combined.pinned.json --result executed.json

`--git-json` must contain the exact bytes of Git blob
`e39dfc6fdbdb90863b5bfb595e12cadf8c20b068`.

`physical_readonly_snapshot` uses one `REPEATABLE READ READ ONLY` transaction and
checks `pg_is_in_recovery`; the GitHub connector SQL audit is strictly weaker:
a **single SELECT** at `READ COMMITTED`, not a verified Python connection.

The source's legacy `merge_sources` cutoff `max(historical.start)` is insufficient
under incomplete, retrocorrected or late historical data: it silently drops
completed live rows within gaps. Selection must use exact pinned row authority
and explicit view-only overrides, with source-version monotonicity guarded.

Caveats / remaining gate: independent disposable PostgreSQL 16 SQL-backed
fixtures, full Python live Neon execution, and historical update/correction
proof are NOT EXECUTED in this environment. SQL physical readbacks and local
pure-Python fixtures are not equivalent to either. No GitHub Actions run was
started: C3-RC7 containment for indirect listener triggers remains open.
