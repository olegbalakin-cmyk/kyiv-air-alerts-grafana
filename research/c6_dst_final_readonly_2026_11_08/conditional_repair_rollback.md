# Conditional repair and rollback

**BLOCKED. This is a set of conditions for a future repair; no writes or rollback were executed.**

The one allowed readback confirmed all four defects and saved current before-images. It also exposed two prerequisites: no supported episode supersession/count-exclusion contract was established, and candidate source observations are missing. The current six-table readback does not certify every non-FK/external consumer.

Before a separate write approval can be requested:

1. Specify and verify an auditable one-to-many mapping from the three old UUIDs/legacy IDs to six replacement episodes, plus the one missing Cherkasy episode. Preserve original identities. Define how every affected reader excludes superseded episodes and how that exclusion is reversed. The current episode state constraint cannot encode supersession; observation/classification aliases cannot be repurposed. Whether a separate versioned mapping can avoid DDL remains unproven.
2. Bind the seven candidates to genuine pinned source evidence and a correction run. Accepted `C6-DST-UTC-01` proves their boundaries, but the live snapshot contains no source observations for these cases. Do not invent capture metadata or use the original ingestion run as source-event evidence.
3. Account for any affected non-FK consumers identified by the catalog, including `attack_event_sources.classification_episode_id`. The readback found zero links in the four checked FK tables; it does not prove all consumers absent.
4. Freeze the complete proposed write set and inverse mapping, then demonstrate guarded apply/rollback in an isolated authorized environment. A future write must reject drift from the protected before-images, unexpected candidate collisions, new dependencies or changed schema. No further transaction is authorized by this document.

Only after these conditions pass, a separately approved transaction could create seven new identities, retain the three old identities with explicit supersession lineage, preserve the earlier valid Cherkasy row, and count only the seven corrected intervals. Expected net delta from accepted evidence: +4 counted episodes and −9,059,359,958 microseconds. Physical storage would retain three superseded old rows; physical row-count delta is therefore +7, not +4. Every unrelated row must remain unchanged.

Rollback must use the exact correction batch and its saved UUID mapping. Reverse only that batch's exclusions/supersessions and restore the prior counted selection and downstream state. Keep audit history; do not cascade-delete. If later observations or dependents attach to replacement rows, rollback must stop unless its approved contract accounts for them. Verify the protected Cherkasy full-row digest, the old row digests, prior counted results and all affected dependency before-images.

A safe no-schema-change repair/rollback is **NOT PROVEN**. The next decision concerns the missing lineage/exclusion contract. Approval to perform writes is not ready. `GLOBAL_CUTOVER=NO`.

