-- H2 ROLE EXISTENCE ONLY / NOT AUTHORIZED / DO NOT EXECUTE IN THIS TASK
--
-- Proposed subsequent authorization: exactly one connection and one SELECT.
-- Target (owner-observed, independent routing still required):
-- project green-cake-44216048; branch br-bold-mode-b5rub8pq;
-- database neondb; read-only compute ep-calm-rice-b5073ypp;
-- direct TLS hostname ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech.
-- Never use primary compute ep-still-violet-b5bg6mhp or default branch.
--
-- A named, authorized project owner/operator (potentially neondb_owner) may
-- run this only after separate approval and nonsecret route verification.
-- Owner's privileged login is NOT the dedicated inspector and cannot be
-- accepted as Candidate A's I2 or I3-I7 runtime inspector session.
-- Preconditions: read replica compute confirmed by provider metadata, direct
-- unpooled verified hostname/port/branch, TLS verify-full, no fallback,
-- client read-only policy, connection timeout 5s, total wall clock <=20s.
-- If any precondition, identity, guard, result shape or rollback fails:
-- STOP, report UNVERIFIED; do not retry against another compute/role.
-- Budget: 1 connection, 1 transaction, 7 SQL statements incl. 1 SELECT,
-- 1 result row, <=2048 sanitized UTF-8 result bytes, no application rows,
-- no DDL/DML, no role switch, no Neon API; no secrets/DSNs in evidence.
-- PostgreSQL 18 required; protocol expected REPEATABLE READ and READ ONLY.
-- Server transaction_read_only must return 'on' in result.

BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
SET LOCAL statement_timeout = '3s';
SET LOCAL lock_timeout = '500ms';
SET LOCAL idle_in_transaction_session_timeout = '10s';
SET LOCAL transaction_timeout = '15s';

SELECT
    pg_catalog.current_database() AS database_name,
    session_user AS session_role,
    current_user AS current_role,
    pg_catalog.current_setting('server_version_num')::integer AS server_version_num,
    pg_catalog.current_setting('transaction_read_only') AS transaction_read_only,
    pg_catalog.current_setting('transaction_isolation') AS transaction_isolation,
    EXISTS (
        SELECT 1
        FROM pg_catalog.pg_roles AS r
        WHERE r.rolname = 'h2_catalog_inspector_ro'
    ) AS inspector_exists;

ROLLBACK;

-- Decision: FALSE => ABSENT_CONFIRMED only if all independent route, identity,
-- guard, successful rollback and receipt controls PASS. TRUE => EXISTS_CONFIRMED
-- (privileges still unknown). NULL/missing/error => UNVERIFIED, never absence.
-- Do not execute G02-G14 or change a role within this authorization.
