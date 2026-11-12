# CASUALTY-ZAPORIZHZHIA-SOURCE-RECOVERY-PREFLIGHT-01

**Decision: `SOURCE_CAPTURE_AWAITING_APPROVAL`. Research-only, 2026-11-12. No media HTTP, no source-body capture, no casualty publication.**

## Scope and evidence

Start point: [PR #88 frozen matrix](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/blob/34bc539d0c7abb8af4f699b2e2c9ecec4b668397/research/casualty_zaporizhzhia_additional_events_2026_11_12/verification_matrix.json); matrix Git blob `12e9f43a41469d5916c918a11b5d5c7fdb4e8320`. Exactly 11 IDs / five publication-date clusters. The source inventory is [PR #85](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/85). Do **not** re-screen 208 WIP candidates.

Read `main:PROJECT_STATE.md` and `main:CHANGELOG.md`, at `375e69351e6a5aee1be16892821f7cdde2a8f21a`, and checked the newer casualty-specific [PR #71](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/pull/71): the incident-dedup code was moved to `site-prod`, but no new casualty deaths or production data were published. These updates do not authorize fresh source requests.

The frozen WIP `source_state.json` (Git blob `c78f4e2c0ec5e8ae34ed32d71ca757c1aa80fdcb`) has no relevant Zaporizhzhia article text according to the earlier evidence audit. The recorded source selections of the prior two HTTP collections exclude all 11 target IDs:

- [Run #42998441793 / artifact #13844887603](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/42998441793), five unrelated candidates, ZIP SHA-256 `81f29dcfb29db64a98466febf5fd3abb77816b827e01d29dad9b19ab7d78c2ba`.
- [Run #43053796144 / artifact #13870872313](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43053796144), three unrelated candidates, ZIP SHA-256 `f7255cba58faea1ecb7defbe2cdbed40db2ddf05a5b92f5fe3530cead32f2148`. This includes the separately confirmed *10 October* Suspilne original supporting 23, but no target ID.

Both artifact records remain available on GitHub and their metadata/digests were checked; the ZIP bytes were **not downloaded/rehashed in this pass**, and there was no exhaustive search of every historical artifact. A missing target match in those two selected sets is not a proof that no original exists anywhere else. Previous SHA values are retained as historical receipts, not newly computed checksums. No new HTTP requests to media, no RSS redirect resolution, and no source-text downloads were performed.

## Result by publication cluster

Dates in this table describe **WIP publication clusters**, not independently verified strike dates.

| Publication cluster | Candidate IDs and publishers | Original text in inspected stored evidence | Current independent attack/death decision |
| --- | --- | --- | --- |
| 18.10 | `43a268ae2e19123554d6d476` ZPRZ.CITY | Missing | Incident date, city impact, civilian status, later updates and count unverified |
| 22–23.10 | `7c3ac3280ba7ad4b9c10f3b1` Ukrinform; `dcdd2fe28fd1464e7fbabdc1` Газета МИГ; `24654383bd30cc0f4e29c95f` ZPRZ.CITY | Missing | Possible *2→3* cumulative revision; cannot count 2+3 or assume next-day article is a new strike |
| 26.10 | `103256b72707ad66d91f6aae`, `cb222eea2a20aa1db2d67d5d` Ukr.net | Missing | Identical headlines are possible duplicated publication; body/source/incident not verified |
| 25–26.09 | `89a03da642500bf4def8ec9c` shelter.in.ua; `05affefbcbb9f27a322ff5d3` Радіо Свобода; `db8ada77be0650fbf7c686cd` Інтерфакс-Україна | Missing | A drone headline and two reported deaths could concern one strike or multiple strikes |
| 27.09 | `7f57e0e0e4743e98c8a88186` Перший Запорізький; `a3e25aad501f5f76e30ae65e` Справжнє | Missing | Possible same Shahed strike; check also independence from 25–26 September |

**Confirmed deaths added from these five groups: none established.** The number is not evidence of zero actual deaths. Current retained October research minimum is **at least 23**, entirely from the independently verified 10 October KAB wave. October's month-level status remains `COVERAGE_INCOMPLETE`; September 19–30 actual total remains unknown.

## Exact approval queue

See [`source_capture_request_queue.json`](source_capture_request_queue.json) for **all 11** individually named items, original Google News RSS URLs as saved in WIP, immutable candidate WIP links/line numbers, source names, timestamps, direct article URL `null`, requested verification facts and possible duplicates. **Google News is an aggregator, not the publisher original.** No exact direct article URL has been substantiated by the checked archival records; inventing a plausible slug is not permitted.

Priority: (1) three 22–23 October records, to resolve 2-versus-3 cumulative reports; (2) 18 and 26 October records to isolate city attack and duplicates; (3) 25–27 September records, including cross-cluster deduplication.

After **separate owner approval**, first reuse any exact archived article body discovered later. Resolve only the approved item URLs; fetch originals and necessary official primary confirmations at a limited rate, without circumventing blocking. For each record keep requested URL, timestamp, HTTP status, redirect chain, resolved publisher URL, response SHA-256 and byte length. Do not commit copyrighted full articles to the public repository. If new originals are not obtained, remain `BLOCKED_MISSING_EVIDENCE` for factual adjudication.

For every recovered original, separately establish attack date and time, municipal geography, air-attack mechanism, civilian versus military status, cumulative victim updates, incident identity, earlier credits and independence from the 10 October wave.

## Isolation and next gate

Research-only files. No WIP queue, `revisions.csv`, casualty totals, generator/reviewer, frontend, Git publication, production, Netlify, Neon or C6 changes. No CI run is claimed; no source-capture job was initiated. **NO MERGE / NO DEPLOY / NO PUBLISH.**

Decision remains `SOURCE_CAPTURE_AWAITING_APPROVAL` pending a separate owner authorization scoped to these 11 records and required official originals. A future approved capture and adjudication may then establish additional independent fatalities; nothing in this report authorizes them today.
