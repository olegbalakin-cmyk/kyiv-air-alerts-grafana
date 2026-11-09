# C6-SAME-RUN-HISTORICAL-CAPTURE-RECEIPTS-01 (proposed)

**BLOCKED on physical evidence. Capture/export integration prepared and tested.**
`publication_allowed=false`; `GLOBAL_CUTOVER=NO`.

Main PROJECT_STATE.md and CHANGELOG.md were read first. Their latest accepted
checkpoint remains C6-UA-CURRENT-ONEGET-01. This research result does not change
accepted coordination state. Base: 3453492b7f5c0b1e46f115a8fa1a949e4b50109d.

## Evidence counts

| Evidence | Bound historical checkpoints | Full capture receipts | Passing 36h gate |
| --- | ---: | ---: | ---: |
| Retained C2 42297035421 / readback 42487688608 | 21/23 | 0/23 under the new raw-response contract | 0/23 |
| Later C2 42452793451 | 21 bridge continuity diagnostics | No full same-run export/readback | Not evaluable |
| Constructed offline fixtures | 23/23 | 23/23 | 23/23 at the fixture consumption time |

The first row retains the earlier result: the 21 source checkpoints were
40.12–40.51 hours old at that physical readback. They remain valid bounded
checkpoint evidence. No real captures were produced in this task, so the new
full-receipt count is zero. Synthetic fixtures are not physical receipts.

Artifact 13619973574 was independently hashed again: SHA-256
`b0aa64392cb2b682eae14faf15df5df45da3fc208d8c45323dffab63b3d4245e`, matching
GitHub's metadata for successful run 42487688608. Successful run 42452793451
retains four diagnostic artifacts, with no full C2 bundle or matching readback.
Its newer receipt cannot be attached to the older corpus.

## Receipt contract

The new helper captures bytes from responses the existing collectors have
already fetched. It records request start and response capture clocks, source
URL/region/channel, raw payload SHA-256, parsed completed AIR pairs and their
hash, previous checkpoint and its hash, run/attempt, workflow and input SHA.

- The 21 bridge cities use the existing last_checked_at, previous bridge poll,
  resolved region identity and history-continuity result. Their source timestamp
  is now recorded immediately after the existing successful HTTP response.
- Kyiv uses the existing Kyiv Digital history response and its existing parser.
- Sevastopol retains every page from the existing razvozhaev history loop. It
  uses fresh completed pairs only; stored pairs and corrections cannot supply
  capture continuity. Unresolved recent anomalies keep continuity BLOCKED.

The independent checkpoint file is `data/c2_history_capture_checkpoints.json`.
The regular data commit retains it. A missing checkpoint bootstraps from a real
capture and stays BLOCKED. A failed overlap does not advance a prior checkpoint.
The next regular capture may pass only if its completed history reaches that
independently recorded checkpoint. Sevastopol may remain BLOCKED if the source
window has no qualifying pair or an unresolved anomaly.

Raw responses remain in the existing ephemeral canonical payload. They do not
enter the frontend dashboard or the small persistent checkpoint file. Export
rehashes and replays them with the existing parsers. Its existing manifest binds
the payload SHA to the successful C2 receipt and corpus. The readback proof also
records the exact payload/receipts SHA and capture run identity. The source
report carries these identities and recomputes age at consumption. Readback
diagnostics retain historical_source_receipts.json with the raw responses,
independently of the seven-day C2 export retention.

Modern receipts require their exact hashed export. Missing captures cannot fall
back to old dashboard clocks. The 36-hour limit and six-file JSON contract remain.
DB commit, JSON generation and last-event times never supply the capture clock.

## Proposed integration

The main workflow checks out site-prod for collectors. The narrow hooks are in
[site-prod-integration.patch](site-prod-integration.patch), based on these verified
production blobs:

| Collector | Original blob | Receipt-hook blob |
| --- | --- | --- |
| update_data.py | cebc2b455fb08ee16e03b9e4fcdb17aa2d9d6833 | 9649f75e5ed841ca5c855a7639eede9356af2766 |
| apply_ukrainealarm_bridge.py | 8b95c4b508b9a473240889603f593e399cf8815d | 1f912bca289035056cc8b19a086000ef8f24111a |
| add_sevastopol_exact.py | e4c091a677622eb28e504b0592a89e4d92d5fe02 | f14437658cdb13f9464db63fc754db85c6447a86 |

Copy the new c2_history_capture.py into the corresponding site scripts path
when applying those hooks through a separately approved production change.
The generator allows exactly these three additional hashes; arbitrary builder
drift still fails closed. The regular shadow step passes the existing export
and its checksum to the freshness gate. Export/shadow flags and the scheduler
were not changed. Production collection/publication were not run or deployed.

## Validation

**70 offline tests PASS:** 21 new capture/integration checks, 17 existing freshness
checks, 14 export/access checks and 18 receipt/frontend contract checks.

```
python -m unittest tests.test_c6_capture_receipts tests.test_c6_history_freshness tests.test_c2_shadow_bundle tests.test_neon_json_shadow_frontend -v
```

The new checks block socket connections, replay all source parsers, apply the
collector patch to hash-verified production fixtures, exercise Kyiv/Sevastopol
collector hooks and verify existing request counts. They cover bootstrap,
missing bridge/independent receipts, same-run identity, altered bytes/metadata,
stale captures, corpus/readback mismatch, exact allowed builder hashes and the
six-file orchestration contract. Full frontend generation is stubbed in the
orchestration checks. No DST, browser, CSV, old physical proof or broad audit was
rerun. The retained physical artifact hash check was read-only.

## Remaining dependencies

1. Review and apply the collector/helper and exporter/reader patches through
   their existing release process; retain a successful full same-run C2 export.
2. Let the existing regular collection bootstrap Kyiv/Sevastopol independent
   checkpoints and then prove real history overlap. No manual source poll is
   authorized by this result.
3. Obtain one separately owner-approved read-only Neon → JSON proof using that
   exact export/corpus, within 36 hours of every source capture. A regular shadow
   artifact with the same complete binding can satisfy this proof; no new
   scheduler or writer is needed. Retained older artifacts cannot satisfy it.

No Neon SQL/write/DDL, deployment, PR #42/#44/#45 change, root coordination update,
Work A or DST edit. Publication stays disabled pending a separate release.
