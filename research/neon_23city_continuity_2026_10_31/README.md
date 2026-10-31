# C6 two-cycle live continuity experiment

Accepted result: **C6-23CITY-CONTINUITY-02 — PARTIAL, publication BLOCKED**.
Kyiv passed both cycles; UkraineAlarm stopped after a documentation HTTP 403,
and Sevastopol's second capture timed out. See [the closeout](ACCEPTANCE.md).

One owner-authorized experiment on the existing child, capped at 60 upstream
GETs including documentation and 70 minutes including preservation. No scheduler,
publication, production/parent write or operational branch modification.

The workflow uses the existing protected `c6-live-writer-proof` Environment,
checks its current metadata, and validates the exact child hostname, database,
role, TTL and accepted child-only role attestation before source access.
An immutable C2 control checkpoint prevents accidental re-execution.

Source contracts are taken from `site-prod@0ecbb291`. UkraineAlarm history uses
the 21 pinned region IDs and a shared 70-second request floor. Kyiv Digital
uses its accepted completed-history parser and continues the existing checkpoint
chain. Sevastopol uses the pinned strict AIR parser on one latest public channel
page per cycle; occupation-administration provenance is retained. Non-API
sources have a 25-minute minimum interval. Documentation discovery may confirm
the active endpoint; no guessed data endpoint is requested. Every redirect,
retry and pagination request is disabled. A failed provider is stopped for the
experiment, including on 429/403; Retry-After is preserved and no follow-up
attempt can violate it. Source acquisition takes at most 60 minutes, the
process has a 63-minute alarm, and the job has a 65-minute timeout.

Existing canonical parents are reused by exact UTC interval. A source interval
overlapping a different existing parent is withheld and reported instead of
creating another canonical identity or repairing DST/selection. Existing source
UUIDs retain their first-capture hash/time; each new capture hash and time is
bound independently in the new checkpoint and ingestion-run receipt. Two-cycle
history overlap is a bounded observation, never long-term continuity.

Each cycle has a separate read-only UUID/source/checkpoint/run readback and one
23-city candidate generation using the accepted generator. Current positive AIR
source signals are reported separately. Missing rows, history-only data and
zero open database rows never certify current inactivity or ancestor coverage.
The final gate remains fail-closed while required current-status, cache/source
completeness, DST, Kyiv provenance or production preflight gates are open.

Full source bytes, SQL receipts and candidates are stored in the Actions
artifact with a SHA-256 manifest. The save-proof job verifies every hash and
pushes bounded JSON receipts to this research branch without force. Root
coordination documentation is updated later through a separate PR and CI.
