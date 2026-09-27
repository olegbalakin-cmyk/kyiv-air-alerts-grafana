# Database

Phase 1 currently contains schema only. No database is production-authoritative yet, and the current JSON artifacts remain the authoritative fallback.

Versioned PostgreSQL migrations live in db/migrations. Neon is intended to provide the database environment and orchestration; the schema remains ordinary PostgreSQL and is not Neon-specific.

Migration application is intentionally outside this commit. 001_phase1_core.sql must not be applied as part of this architecture-only change.
