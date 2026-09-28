# Database

Phase 1 now includes a repository persistence adapter, but no database is production-authoritative yet and the current JSON artifacts remain the authoritative fallback. The schema remains ordinary PostgreSQL; `db/migrations/001_phase1_core.sql` is unchanged by the adapter work.

The persistence mechanics live in `scripts/db_phase1_persistence.py`. The accepted Lviv canonical payload is rebuilt by `scripts/db_phase1_lviv_import.py`, which reuses the frozen Phase-1 canonicalization/proof code and pinned fixtures rather than fetching live source data.

Dry-run is the default and never opens a database connection:

```bash
python scripts/db_phase1_lviv_import.py --dry-run
```

PostgreSQL support is an isolated optional dependency. Install from `requirements-db-phase1.txt` when a real database run is intentionally required; production `requirements.txt` is unchanged. `psycopg` is imported lazily only for `--apply`. The database URL is supplied only through an environment variable selected by `--database-url-env` (default `DATABASE_URL`), while `--db-branch` is required separately for ingestion provenance. Connection secrets are not command-line values and are not printed or written to `.env` files by this adapter.

The transaction contract is: build and validate the payload before entering the DB transaction; `BEGIN`; acquire one deterministic `phase1-stream-lock-v1` advisory transaction lock for source/city/stream; re-read `current_ingestion_checkpoints`; insert the ingestion-run provenance row; validate/persist canonical episodes; validate/persist source observations; insert the bootstrap checkpoint or recognize its exact retry; mark the ingestion run succeeded; `COMMIT`. Any exception before commit causes `ROLLBACK` rather than a partial commit.

Existing episodes are reused only when their frozen canonical semantics exactly match; an exact retry does not rewrite episode provenance. Existing source observations are likewise checked by their versioned source-record identity and semantic fields. Their `source_observation_id`, `first_persisted_by_run_id`, and `first_persisted_at` remain unchanged; an exact repeat updates only `last_seen_by_run_id` and `last_seen_at`. Unknown historical `source_retrieved_at` values remain null rather than being fabricated from bootstrap time. A matching seq-1 bootstrap checkpoint is a no-op exact retry, not a new seq-2 poll.

Production cutover remains blocked on an executable two-session PostgreSQL test proving all of the following: two distinct PostgreSQL backend sessions; same-stream lock contention; Writer B try-lock = false; Writer B post-lock reread sees Writer A checkpoint; and a sequential checkpoint chain. The current status is exactly:

`PHASE-1 SAME-STREAM CONCURRENCY ENVIRONMENT-BLOCKED`

The presence of advisory-lock code in the adapter does not satisfy that gate. No production cutover is authorized by this implementation.
