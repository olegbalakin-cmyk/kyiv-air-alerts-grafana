# H2 G03: narrow PostgreSQL 18 creator-ADMIN exception (offline only)

**Scope:** Interpret the *existing* exact Candidate A G03 `SELECT` result without weakening any other H2 gate. The original Candidate A manifest, 14 SQL statements, independent acceptance evidence, source pins, and CI proofs remain byte-for-byte unchanged.

## Reason

The Neon owner executed the approved SQL-only `CREATE ROLE h2_catalog_inspector_ro ... PASSWORD NULL` on the shadow branch. Independent read-only `pg_roles` and `pg_auth_members` checks (coordinator checkpoint `main@d090b9ce75f1cfc4ca53271615e0cef7c8a23c84`) observed **exactly one** incoming edge: `h2_catalog_inspector_ro` granted to `neondb_owner`, with `ADMIN=true`, `INHERIT=false`, `SET=false`. The inspector itself was not granted `neondb_owner`, `neon_superuser`, or `pg_*` roles. The observed row is consistent with PostgreSQL 18's automatic creator-ADMIN behavior; `pg_auth_members` does not independently prove the row's historical creation mechanism.

Original Candidate A's G03 SQL already returns **both directions** of membership, up to 17 rows. There is no reason to change its SQL or its SHA-256 `3935fdb9...`. The outdated expectation was **zero rows**. The one-row exception must be applied to the **result validation**, not implemented by filtering the creator's row out of the SQL or falsifying the result count.

## Exact amended G03 interpretation

Using unmodified `G03` output, accept a result **only when it is a list containing exactly one dictionary** with the five original columns and exactly these values:

```json
{
  "granted_role": "h2_catalog_inspector_ro",
  "member_role": "neondb_owner",
  "admin_option": true,
  "inherit_option": false,
  "set_option": false
}
```

Any missing, duplicate, additional incoming/outgoing membership; swapped parent/member; changed `ADMIN/INHERIT/SET`; renamed creator; wrong column, null, or non-boolean flag is a **hard failure**. Do not normalize booleans, hide the row, or equate one edge with a zero-edge result. The correct G03 receipt records **one observed membership row**, never zero.

The companion `verify_g03_creator_admin.py` exposes `verify_g03_rows(rows)`, pins the original Git blob and G03 SQL hash, and runs synthetic negative tests. To check locally:

```sh
python3 research/h2_g03_creator_admin_2026_10_26/verify_g03_creator_admin.py
```

Independent offline CI also re-runs the earlier accepted Candidate A acceptance script to prove the original evidence remains intact.

## Limits and next integration step

This is **a proposed G03 rowset validation overlay**, not a replacement for the unchanged original offline Candidate A verifier, whose old synthetic receipt still expects `direct_membership_edges=0` and `G03.row_count=0`. A future runtime receipt/integration must explicitly use the revised one-row rule and remain independently reviewed. Do not claim the old Candidate A runtime verifier passed as written.

G01/G02 role identity, I1 routing/TLS, session guards and `ROLLBACK`, I3/I4/I5/I6/I7, application ACL checks, physical seven-`relacl` differences, and all other limits remain independently binding. The inspector has `PASSWORD NULL` under the authorized creation statement; no temporary credential, inspector connection, read-only runtime session, or Neon SQL is created by these files. Only the verified read-only compute may later be used after separate authorization. This research branch does not modify production, development, historical/backfill, casualty, or persistence tracks.
