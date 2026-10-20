# H2 PG18 v3 A/B original artifact retention (bounded)

This branch preserves **original GitHub Actions ZIP bytes** from run 39387213964: A artifact 12248146029 and B artifact 12247428332. Manifests and verifier are independent Git-only checks; they are **not new PostgreSQL execution**.

The archived reports were produced on tested commit 3d35d8a08f2800c8fdbe460b76a1b25d7ff59845 and each reports 42/42 assertions PASS. ZIP CRC and exact ZIP/member SHA-256 were verified before archiving.

Full offline security migration closure, restricted CAS writer integration, non-superuser owner transfer, attack suite and ACL/owner rollback have **NOT** been executed in this branch. Status: PARTIAL / NO-GO. No Neon, production or operational WIP modification.
