# C4-E5 research — owner review (unaccepted)

**Verdict: C4_E5_PARTIAL.** This research branch adds a defensive verifier and offline test scaffold. It does NOT provide full six Git expectations, six one-snapshot Neon exports, or an executed field-parity proof. No parent exception approved.

## Verified preflight
- Main HEAD: `a470fb66550a47c01578bad19d7633105b8b85cd`.
- site-prod: `552de9cfc8ee7fff7e169caf0a928f4e17ca9cb2`.
- Operational WIP: `d834aad2a175c71217da9cab102ffd54bda3b3bc`.
- Accepted C4-E4: `EXECUTED_STRUCTURAL_PARTIAL_ACCEPTED_BOUNDED`.
- C4-E3 executable contract: `6794ee1a:research/c4_e3_exact_field_parity_2026_10_28/verify_c4_e3.py`; exact blob `4b1a438f218eb044d585c0fe1b579a5dea63650e`.
- Confirmed replica metadata via Neon API: `green-cake-44216048/br-bold-mode-b5rub8pq/ep-calm-rice-b5073ypp` is `read_only`. SQL read-only information_schema inspected; **no DML/DDL**.

## Non-equivalence
Six same-snapshot structural aggregate counts from E4 are not six full JSONL field projections. The Neon MCP transaction tool returns structured SELECT results and does not supply durable client-side COPY streams or proven local export files. Direct PostgreSQL connection credentials are absent in this execution environment and read-only Neon connector cannot issue privileged connection strings. No read-write credential workaround allowed. The verifier cannot certify a transcript solely because it contains `single_transaction=true`.

## Machine proof scope
This branch only establishes independently executable *offline code/fault tests*, not real Neon export parity. Synthetic test assertions cannot be counted as 15 live verifier integration tests. A fake snapshot receipt is insufficient. Any CI green test is **test harness green only**.

## Unresolved proof dependencies
1. Independently reconstruct all 26,405 / 3,769 / 1,080 expected required fields from immutable Git source bytes, recording field-level JSON pointers and provenance status; never fill gaps from Neon.
2. Execute six complete actual exports from one real `REPEATABLE READ READ ONLY` connection, under controlled storage with cryptographically anchored transaction evidence; hash all six files.
3. Execute actual bidirectional verifier with six files, 25-UID registry, 18 frozen dual-ID cases, and 76 replay-only memberships. Do not call absent original authority a Neon mismatch.
4. Produce job/artifact proof with exact research SHA; prohibit uploading private Neon rows or privileged credentials to public GitHub.
5. Complete actual mutated-fixture integration assertions for every requested fault class, not merely primitive-level unit tests.

**Decision:** `C4_E5_PARTIAL`, `C4=PARTIAL`, `C4_OWNER_EXCEPTIONS_ACCEPTED=0/25`, `C4_PRODUCTION_RELEASE_AUTHORIZED=NO`, `NEON_AUTHORITY_ACTIVE=NO`, `PRODUCTION_CUTOVER_EXECUTED=NO`.

No changes to `main:PROJECT_STATE.md`, `CHANGELOG.md`, production, operational WIP, classifications, parents, source adjudications or Neon.
