# C6 physical attempt 4 — fail-closed later-C2 insertion guard (2026-11-12)

## Exact physical failure

- Protected manual physical [Actions #43180832950](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43180832950) on PR #79 HEAD `beb2ad4d1f37e88b0084e49306281f8d2650d568`, C2 #43055353190, exact bundle SHA `ebcf2b6a94080f7a374b0897715c732846c5bd55eb4127f79d202cf8fec04c1d`, **FAIL** at `SELECT_EXACT_C2_CANONICAL_EPISODES`, error `C2_EXACT_CANONICAL_SELECTION_BLOCKED:SelectionBlocked`; artifact #13926356418 contains no candidate files, no DB writes, no source HTTP.
- Independently checked live **read-only** Neon `br-bold-mode-b5rub8pq`: 33,472 closed AIR in snapshot, **75** rows have `updated_at` after original 2026-11-11T16:34:13.678Z cutoff; ALL **75** have `created_at` after cutoff, and **zero** pre-cutoff rows have later updates. Hence the existing reader's indiscriminate `updated_at <= cutoff` on *every* historical or future row fails, even though C2's 33,135 exact members and 262 older retained rows have not changed.
- New regular production C2 [#43172960738](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43172960738) SUCCESS, with immutable artifact #13923503919 SHA `c2818bf10fb731754456d5816c4705f17b6b62bc59507de21c85832b6e94e290`, current 33,210 canonical; however this run's historical source continuity receipts are only 22/23 (Sevastopol false). **Do not swap** the old frozen C2 proof for the new one and claim full source freshness.
- The original C2 #43055353190 still has all 23 historical receipts from its own same run; source freshness is evaluated at consumption, not assumed from historical PASS.

## Narrow code safety rule

- Keep SHA-bound original C2 exact 33,135 ID+seven-field checks, current canonical projection, older stale retention, frozen 382 Kyiv B2 proof, 21 UA replay and all source checks.
- For any Neon row with `updated_at > C2.ingest_committed_at`, exclude it **only when** `created_at > C2.ingest_committed_at`, `created_at <= updated_at`, and its legacy ID is absent from the pinned C2 expected membership. Any post-C2 mutation of an earlier row (including historic stale row), missing or malformed creation clock, or future inserted row reusing a pinned C2 ID **fails closed**.
- Distinguish 262 old historical rows versus 75 post-C2 inserts in diagnostics. No broad newer-overlap heuristic, DB schema alteration, write, source HTTP, deployment or publication.
- GitHub Actions narrow **offline** regressions on immutable research HEAD must PASS before proposing another separately owner-authorized physical run. No physical PASS yet; no pending owner approval on this new SHA. `GLOBAL_CUTOVER=NO; DST_CORRECTION=OFF`.
