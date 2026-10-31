# C6-LIVE-WRITER-PHYSICAL-02 — isolated child verified; writer blocked

**Result: BLOCKED. Production writer ready: NO.** No application SQL, writer execution, COMMIT, crash/retry, physical UUID readback or site JSON generation occurred.

The owner authorized this isolated test in the current request. Exactly one child was created in project `green-cake-44216048`: **`br-crimson-star-b59u7ge3`**, parent **`br-bold-mode-b5rub8pq`**. Separate get-branch, compute-list and connection-host reads confirm identity, parent, ready/nondefault/unprotected status and endpoint. Capacity changed from 9/10 to 10/10. The first create attempt with a custom suspend interval failed HTTP 412; a separate inventory confirmed it created no branch. The successful create used platform defaults.

TTL expires **2026-11-01T12:20:00Z** (14:20 Kyiv), less than 24 hours after creation. No manual deletion was performed. Owner permission remains required for manual cleanup.

## Concrete execution blocker

The local Python runtime cannot resolve the independently verified child host: `socket.gaierror: [Errno -3] Temporary failure in name resolution`. Psycopg is also unavailable in that Python. No DB credential was supplied to it.

The Neon connector returned a URL targeting the child's verified pooled hostname, using the existing `neondb_owner` role. A role restricted to the new child was not attested. The exposed GitHub connector has no secrets-management or workflow-dispatch operation to securely inject a child URL into a network-capable Actions runner. Existing Actions secret availability was not inspected and is **unknown**; the shadow URL was not reused. No credential was written to files, commits or logs. Manual SQL was not substituted for Phase-1 persistence.

## Additional real freshness blocker

The saved HTTP entity, canonical candidate and capture metadata hashes were independently recomputed; all match the accepted manifest. The original writer and gate Git blobs are unchanged. Original source/preservation Actions and artifact digest were rechecked without rerunning them.

The unchanged gate was evaluated once against the **real saved capture timestamp and actual current time**, with writer/readback/output evidence absent. It rejected `STALE_SOURCE_CAPTURE`: approximately 13.6 hours old versus the existing six-hour limit. No synthetic timestamps, self-tests or fresh HTTP request were used. This proves only this real stale-input rejection; other physical fail-closed scenarios remain unexecuted. A recent COMMIT or generation time cannot refresh this source timestamp.

## Resume

Use this same child before expiry, with an authorized network-capable Python runner and an independently verified child-scoped credential. Run the unchanged two Phase-1 invocations from proof commit `0f0d7181e04cb053b773fb5c0ecf284bb82bc66a`. Keep the saved capture for persistence/retry proof. A current-source freshness PASS needs a separately authorized fresh source observation; do not redate the saved capture or widen the threshold.

Evidence is under `proof/resume_physical_02/`. Database readback and generated JSON are explicitly **NOT EXECUTED**, not represented by control-plane branch metadata. No production Neon, parent data, site-prod, operational WIP, Netlify or production writer changes. **C6/C3=PARTIAL; GLOBAL_CUTOVER=NO.**
