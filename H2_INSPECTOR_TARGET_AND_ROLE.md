# H2 inspector target and role — OFFLINE / ACCESS NO-GO

Accepted upstream: `576ac42b7734106ccc0edc858173c90f82537d85`, coordination `66fbabf20644797bd67d3790893b4103a5dcb8ef`. No new Neon access/provisioning.

The **historical proposed** Neon target is project `green-cake-44216048`, populated permanent shadow branch `br-bold-mode-b5rub8pq`, DB `neondb`, previously observed read-only endpoint `ep-calm-rice-b5073ypp`. The endpoint's **current** branch attachment, readiness, direct TLS hostname and exact routing are **UNVERIFIED**. Never substitute default branch `br-wandering-sunset-b5835alw` or write endpoint `ep-still-violet-b5bg6mhp`. A SQL database name is NOT proof of Neon branch identity: current owner-attested control-plane metadata must bind all identities **before connecting**, after separate explicit approval.

Proposed login `h2_catalog_inspector_ro` is an **unprovisioned name**. Provisioning needs a separate authorization; no assumption that `neondb_owner` is safe. Required: direct login; non-superuser, no CREATEDB/CREATEROLE/BYPASSRLS/REPLICATION, no ownership, no role memberships or SET ROLE, no CREATE/TEMP/DML/TRUNCATE/MAINTAIN/TRIGGER, only catalog visibility; password/DSN NEVER published. An existing alternative needs separately accepted compensating controls and is **NOT** approved by this dossier.

Old Oct 19 catalog evidence at `380e16f4d8e8` used `neondb_owner` in READ ONLY / READ COMMITTED; it is historical and does not meet the new proposed inspector standard. Old secret-metadata run `39309315728` is one-time metadata, not a current auth binding. **I1/I2 unresolved; actual access BLOCKED.**
