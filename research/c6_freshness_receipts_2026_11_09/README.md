# C6-SAME-RUN-HISTORICAL-CAPTURE-RECEIPTS-01 (proposed)

Research only. Implementation checkpoint; verification in progress.
`publication_allowed=false`; `GLOBAL_CUTOVER=NO`.

The main coordination files were read first. No newer accepted checkpoint than
C6-UA-CURRENT-ONEGET-01 was present. Base: 3453492b7f5c0b1e46f115a8fa1a949e4b50109d.

The helper retains existing response bytes in the existing ephemeral canonical
payload, plus independent capture clocks, identity, previous checkpoint and
completed AIR overlap. No new request, writer or scheduler. The small independent
checkpoint file is retained by the regular data commit; a missing first checkpoint
bootstraps but remains BLOCKED. Failed overlap does not advance that checkpoint.

The main workflow checks out site-prod for collectors. Therefore
`site-prod-integration.patch` contains the narrow collector hooks against verified
site-prod blobs, rather than copying production scripts wholesale into main.
The new helper is under the corresponding scripts path. These hooks are proposed,
not deployed. The existing exporter hashes the entire same-run payload and binds
its receipts to the C2 corpus, workflow/input SHA, run/attempt and readback.

Source proofs are replayed with existing parsers. Raw bytes, parsed completed AIR,
previous checkpoint and all clocks are rechecked. Modern receipts never fall back
to an older dashboard receipt. Six-file JSON contract and 36-hour gate remain.

Run 42487688608 retains artifact 13619973574 with digest
b0aa64392cb2b682eae14faf15df5df45da3fc208d8c45323dffab63b3d4245e.
Run 42452793451 retains bridge/C2 diagnostics but no full C2 export or corresponding
readback; it cannot replace the earlier physical proof. No physical proof is rerun.

No root coordination update, production deployment, Neon write/DDL, PR #42/#44/#45
change, Work A or DST edit. A new physical proof needs separate owner approval.
