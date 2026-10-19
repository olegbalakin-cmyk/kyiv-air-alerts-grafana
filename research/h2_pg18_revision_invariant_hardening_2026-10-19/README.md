# H2 PG18 candidate hardening

Isolated research only. The schema fixture is the exact frozen observed-partial fixture Git blob 09f9c5a2f0c4eeddaba63e7c9c5834cce85f7ab3, not full Neon equivalence. Candidate 001 checks historical chain consistency, adds uniqueness per predecessor and root and atomic current-head CAS, with append-only classifications. Candidate 002 models a restricted synthetic role. Object owners retain power to modify tables/triggers. Operational writer differs from the research writer, and Neon runtime grants, write durability, schema compatibility remain unverified.

Rollback after stopping all writers and verifying consistency: drop trigger h2_revision_head_after_insert, then function h2_enforce_revision_head(), table h2_classification_heads and two h2_classification_* unique indexes in a controlled transaction; restore ACL using a verified snapshot. This is NOT authorized for Neon.

Two fresh isolated PG18 containers run A and B. GitHub Actions raw JSON retention is 30 days; independent freeze is required. No accepted contract counts are promoted. NEON_AUTHORITY_ACTIVE=NO. PRODUCTION_CUTOVER_EXECUTED=NO. WIP_ACTIVATION=NO-GO.
