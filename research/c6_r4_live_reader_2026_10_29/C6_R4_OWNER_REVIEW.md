# C6-R4 owner review — research-only execution candidate

**Scope:** C6 only. Preflight: main `a470fb66550a47c01578bad19d7633105b8b85cd`; site-prod `552de9cfc8ee7fff7e169caf0a928f4e17ca9cb2`; operational WIP `d834aad2a175c71217da9cab102ffd54bda3b3bc`; C6-R3 `0cc4d4b56c547ff0b1b0ccc75c0fd0c7e4027c1e`. All refs checked 2026-10-29. R3 CI 40867099080 SUCCESS / job 123424515961, no artifact.

## Neon read-only control plane and executed SQL
Project green-cake-44216048; branch br-bold-mode-b5rub8pq; endpoint ep-calm-rice-b5073ypp type read_only confirmed. Independently executed Neon SQL transaction (2026-10-29 13:14:22 UTC), repeatable read/read only, pg_is_in_recovery=true, snapshot 429056:429056:, replay LSN 0/117CE058. Results: September raw 199, candidate exact-minute 9; October raw 379, candidate exact-minute 184 (184 unique minute and 184 unique precise); 25 historical UNBOUND/NULL; 14 related sources and two ACTIVE events; 28/27 classifications on October candidate sides. These are **actual SQL reads, not execution of Python reader**.

## Implementation and evidence boundaries
R4 Python wrapper derives actual Git blob SHA-1 identity from pinned Git objects, independently validates source and crosswalk contents, requires control-plane matching project, branch, compute type and connection host, validates full September intervals including Kyiv local date/duration, checks all nine start/end mappings, and refuses October unknown pairs. No consumer callback prior to completed gates. Failure must not produce any downstream publication artifact. C6-R4 research branch has regression/tests/CI. CI is **disposable synthetic PostgreSQL**, not live Neon. Exact-SHA CI result is ONLY proven if GitHub Actions run and uploaded artifact independently verified after this commit.

## Live proof limitation
No C6_R4_READONLY_DATABASE_URL or independent runtime authenticated Neon control plane key available to the executing container. A direct Python wrapper Neon execution is **NOT_PROVEN**. Running SQL through Neon MCP must not be substituted for wrapper execution. September full 190/190 actual Python row parity NOT_PROVEN; October actual Python hard fail NOT_PROVEN. If no protected runtime becomes available, final verdict remains **C6_R4_PARTIAL** even if synthetic CI fully passes.

## Strict decision
`C6_R4_PARTIAL`; `C6_PRODUCTION_READER_SWITCH_AUTHORIZED=NO`; `NEON_AUTHORITY_ACTIVE=NO`; `PRODUCTION_CUTOVER_EXECUTED=NO`. Any workflow PASS here is regression, not migration or release approval. October 184 mappings remain uncertified; no rewrite of classifications, A5 FK, source memberships, events, live tips or JSON. No operational WIP, site-prod or main mutation. Do not update PROJECT_STATE or CHANGELOG before coordinator acceptance.
