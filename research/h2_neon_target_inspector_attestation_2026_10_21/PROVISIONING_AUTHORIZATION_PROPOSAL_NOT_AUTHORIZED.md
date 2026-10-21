# CONDITIONAL DRAFT — separate inspector provisioning authorization proposal

**NOT AUTHORIZED. NO PROVISIONING WAS ATTEMPTED.** This proposal is inactive unless a named authorized Neon owner supplies dated primary evidence that `h2_catalog_inspector_ro` **does not exist** on the freshly verified exact target. `UNVERIFIED` role existence is not a finding of absence and does not trigger provisioning.

## Separate user decision to request

Approve or reject a later, independently reviewed, narrowly scoped Neon role-provisioning operation for one dedicated login named `h2_catalog_inspector_ro` on the exact pinned project/branch/database and validated route. This is a control-plane/database-change request distinct from offline evidence work and distinct from the later catalog-only read-only inspection. It requires **a new explicit user authorization**, plus owner and independent security review. None is implied by this file.

## Mandatory preconditions before even considering approval

- Fresh owner-sourced control-plane ID/branch/database/compute/full direct TLS FQDN mapping with trustworthy UTC observation and immutable evidence hash, and no shadow/default/writer ambiguity.
- Documented `DOES_NOT_EXIST_CONFIRMED` for the exact role and verified existing external role graph, with a named authorized owner/operator and independent reviewer.
- Specific mechanism and reviewed statement/control-plane plan; secret issuance, rotation and secure storage remain owner-managed, **never Git, CI artifacts, logs, prompts or this research branch**.
- Approved purpose: strictly catalog-only reads for the eight immutable Candidate A relations and selected system metadata. No application-row SELECT, no DML/DDL ownership, no CREATEROLE/CREATEDB/BYPASSRLS/REPLICATION/SUPERUSER, no SECURITY DEFINER escalation, no membership permitting inheritance or `SET ROLE` into privileged actors, and no blanket PUBLIC/application grants.
- Defined fail-closed checks for effective database/schema/table/function/default privileges and ownership, including transitive membership/role-switch paths, with evidence before/after any separately authorized operation.
- A rollback/remediation and lifecycle plan (disable/delete role, revoke only newly granted rights, invalidate issued credentials without altering unrelated grants); identify any collateral impact. Provisioning must never choose ACL Option B or normalize the seven physical relacl differences.

## Proposed later deliverables if separately approved

Owner-executed nonsecret creation and privilege receipts, exact route-and-role binding, post-provision negative privilege and membership audit, independent reviewer sign-off, scope-limited secure credential handling, expiry/revocation policy and new acceptance decision. Post-provision proof is still **not** I1–I7 runtime acceptance and does not authorize a catalog session, migration, disposable writes, writer privilege changes, WIP, R6, production or cutover.

## Current disposition

`PROVISIONING=NOT_AUTHORIZED / CONDITION_NOT_MET`; `ROLE_EXISTENCE=UNVERIFIED`; `I1=UNVERIFIED/NO-GO`; `I2=NOT_PROVEN_TO_EXIST/NO-GO`. Return the owner evidence request first. No SQL, API, console, secrets, host probing, role creation or privilege change was performed here.
