# Live attack-event monitor: smallest offline executable slice (2026-10-21)

This isolated development proof uses **one REAL frozen Kyiv alert episode** from the operational WIP 2026-10-14 report (run `38575039007`, original Git blob `43f5dd38ad01d22cfce4810ac7f97025a8d85675`) and **two explicitly SYNTHETIC news candidates**. No collected real news evidence or real attack confirmation is asserted.

Inputs are fixed: exact-city alert start/end from original parent gate; synthetic news with and without explicit event time. Processing writes a local atomic JSON envelope containing both classification and durable processing acknowledgement; stale/unavailable source cannot acknowledge, injected failed commit cannot acknowledge, three successive invocations remain idempotent. Produces an offline HTML/JSON example report.

**What this proves:** tiny end-to-end data shape, basic strict-vs-review semantics for synthetic evidence, local atomic storage/ACK, missing-source retryability, no-duplicate restart, report generation.

**What it emphatically DOES NOT prove:** real live news discovery, Telegram/Google coverage, 23-city alert precision, historical classifier parity, real WIP queue migration, Neon schema/writes, full canonical revisions/expected-tip CAS, real publisher, three *scheduled* cycles or production readiness. The real WIP 2026-10-14 `ok:false` and 0 canonical classification writes are recorded as the origin diagnostic; do not present these synthetic test outputs as actual attacks.

Next milestone **only after independent PASS:** bounded real-source read-only replay on a chosen small 1-3-city completed-alert cohort with exact provenance and source error visibility; ensure actual accepted classifier semantics (rather than this deliberately tiny synthetic illustration) and real local-only no-DB candidate queue state, then demonstrate 3 actual separate no-write scheduled/test cycles. Separate authority/canonical Neon work remains NO-GO.

Research branch only; production, `site-prod`, operational WIP, H2/Neon, casualty and historical backfill unchanged.
