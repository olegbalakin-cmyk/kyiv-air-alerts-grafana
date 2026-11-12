# C6 — Final offline end-to-end Neon → JSON: BLOCKED

**Date:** 2026-11-12. **Scope:** offline only; no SQL against Neon, upstream alert HTTP, new C2 writer, merge, deployment or publication.  
**Frozen reference:** C2 [#43055353190](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43055353190), GitHub artifact **#13873291895**.  
**Code under assessment:** [PR #82](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/82) at `82a7cc775ed2f2a6fd0134440db709690f0c04d1`; [offline CI #43181978935](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43181978935) SUCCESS.  
**Latest accepted main coordination checkpoint:** `C6-POSTMERGE-C2-EXPORT-23-01`. This research finding is **not** a new accepted release checkpoint.

## Verified in this work

Downloaded and unpacked the *actual* C2 Actions artifact, rather than relying on earlier reports. Recomputed the outer artifact SHA-256 `0bbbe59ba6d4066a949f071a1bbf61f7c3a21a4ba487cb9e3d1dcadd297c2922`, inner bundle SHA-256 `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`, manifest SHA-256 `f64620936677b3a329a5e7823d3f4d52e4bc60c5b6a29bb8da6ff943adf3e433`, and all **8/8** embedded file SHA-256 values. Recomputed the exact seven-field, ordered 23-city corpus digest `4cd2fce445e49ec200ea3a202ed8bf9e1ada9c17d60c23eb7e9c7c65e1526226`: **33,135** unique valid closed AIR episode IDs, **23/23** city blocks, matching the C2 receipt, with **23/23** historical source-receipt entries. `status.json` confirms `NEON_SUCCEEDED` and `CONFIRMED`.

Reviewed [Work B #74](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/74) (262 historical superseded rows, source receipts), [Work C #75](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/75) (exact ID-based canonical selection) and PR #82 (later-insert isolation and fail-closed mutation tests). These are *separate evidence*, not substitutes for a full same-snapshot reader fixture. #43181978935 ran the existing 382→198 Kyiv B2 and full-C2 offline regressions; it **did not run** `neon_json_shadow.execute(reader=...)` with a complete physical Neon snapshot.

Downloaded and inspected proof ZIPs for the prior physical runs:

| Run | Exact artifact | Actual outcome |
| --- | --- | --- |
| [#43098776474](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43098776474) | #13892361332 | BLOCKED `VERIFY_HISTORICAL_RECEIPT_BINDING`; no candidate |
| [#43104972888](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43104972888) | #13893437446 | BLOCKED `GENERATE_FRONTEND:FROZEN_PHYSICAL_PARENT_COUNT_CHANGED`; freshness receipts 23/23, no candidate |
| [#43180832950](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43180832950) | #13926356418 | BLOCKED `SELECT_EXACT_C2_CANONICAL_EPISODES`; no candidate |
| [#42487688608](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42487688608) | #13619973574 | Six-file older physical candidate, **different** corpus digest `f8d29705…` / 32,457 episodes; cannot certify this frozen C2 |

The manifest hashes of all files in the #43104972888 proof ZIP (5/5) and the older candidate ZIP (14/14) also match. The latter contains table **hashes and counts**, but no underlying seven-table row snapshot.

## Exact blocker

The frozen C2 ZIP contains `payload.json`, `manifest.json`, `status.json`, `receipt.json`, and **five** Git site-data inputs. It does **not** contain the read-only Neon row snapshot consumed by the **existing** `scripts/neon_json_shadow.py` and `scripts/neon_json_shadow_generator.py`. The inspected physical artifacts likewise do not contain such a snapshot.

`generator.snapshot()` requires **one consistent REPEATABLE READ / READ ONLY transaction**, including `meta` (role, snapshot, read time, permissions) and complete rows for **seven** datasets: `episodes` (including created/updated clocks and run IDs), `observations`, `checkpoints`, `runs`, `classifications`, `source_links`, `events`. The 382 frozen Kyiv B2 physical parents and their provenance must be present in that same evidence. The existing B2 offline test reconstructs its *own limited fixture* from the accepted frozen bundle; it does not establish the physical full-table snapshot.

PR #82 documents a real read-only observation of **33,472** closed AIR rows: 33,135 C2 members, 262 older superseded rows and 75 post-C2 inserts, with zero observed pre-cutoff updates. This observation is not a retained full seven-table, same-transaction fixture. Without that fixture, independent testing of the 262/75 exclusion, old-row mutation gate, 382→198 physical B2 selection, 23-city builders, casualty/non-AIR preservation, and all six generated JSON against current Git is **not executable**.

**No synthetic Neon wrapper was used to manufacture an E2E PASS.** No new `execute(reader=...)` full E2E was run; no six-file exact-C2 candidate or SHA-256 list exists. The older six-file artifact is **not** repinned as current.

## One minimum action to unblock

With separate owner approval, **capture exactly one complete read-only Neon snapshot** using the already existing `generator.snapshot()` transaction and the frozen C2 binding. Retain all seven row sets, run/cutoff metadata and the 382 Kyiv B2 parent evidence as a **private, integrity-checked offline fixture**; store only its non-sensitive manifest, hashes and counts in GitHub (do not commit raw database material to the public repository). No new C2 writer, source fetch, database mutation or replacement generator is needed.

Then inject this verified fixture into the *existing* `neon_json_shadow.execute(reader=...)`, keep `DST_CORRECTION=OFF`, compare all six outputs with pinned Git JSON for 23 cities, and fail on any unexplained change. This capture was **not performed** in the present work.

**Verdict: BLOCKED — VERIFIED_COMPLETE_SEVEN_TABLE_NEON_SNAPSHOT_MISSING.**  
`GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF; publication_allowed=false`.
