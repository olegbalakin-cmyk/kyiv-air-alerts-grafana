# Work AD — source URL and Work J facts (isolated, offline only)

Base: Work AC PR #169, 1cd3e85f72f8c80dadd2b53d2b9ce2bb0b0984cf. Existing AB #163, AA #160, X #142 and merged Y #147 unchanged.

## Change boundaries
- RSS item link and explicitly permalink-marked RSS guid are the only original-article URL candidates. RSS source URL points to publisher homepage, not an article; opaque Google News articles with no direct permalink remain SOURCE_URL_UNRESOLVED, with zero HTTP. Conflicts and off-allowlist references fail closed. URL resolution never establishes attack identity.
- Pinned Work J PR #121 source blob 19d0ed3911b62b7abc02700bd9f9a431e1d442e0: helper definitions for counting, dates, attribution and incident scopes copied verbatim to a compatibility module. Work AC article extraction calls these, retains only source-linked complete Work AA sentences and uses Work X for review indexing. No new parser or fetcher.
- Count kind cumulative/delta/unknown; an isolated delta is not a total. Injury-only, age numbers, incompatible totals and multi-attack narratives never become an incident credit. Work X preserves source hash, text hash, source URL, RSS link, capture timestamp and attribution. Date of publication not automatically date of attack.
- Existing GET ceilings (RSS 23, article 10), RSS timeout 15s, article connect 8s / total 20s, 2MiB compressed and decoded, exact HTTPS allowlist, private-IP DNS blocking, redirects OFF, zero automatic retries, 48-hour overlap, network flags OFF preserved. No production path, WIP branch, casualty revisions, JSON, C2 or Neon changes.

## Evidence limitations
- Synthetic RSS and synthetic article text exercise a complete adapter-to-index path, but do NOT demonstrate first-party original URL availability in actual Google News RSS. The existing Work Z stored excerpt proof T03–T05 cannot establish same-incident identity; remain INSUFFICIENT_EVIDENCE. Pre-existing WIP candidate queue is a saved real dataset, not archived RSS HTML.
- CI in existing offline test workflow is restricted to this separate integration branch and reuses saved Work Z artifact. Exact-head Actions, inner SHA-256 proof manifest and artifact digest required; cannot infer success before checks pass.
- Technical PASS does not authorize live shadow, publication, credit, or PROMOTE. Live shadow must remain owner-gated; Google News opaque URL coverage remains a substantive limitation.

## Control and rollback
After separate owner GO: rebase only code and tests onto fresh current WIP HEAD without moving its state files, retain the main-owned four-hour schedule `45 */4 * * *`, and recheck current Work Y hard-OFF. A further GO is required to enable existing separate RSS/article/write flags for one bounded shadow cycle. Disable flags immediately if provenance, network budget, or WIP continuity fails; revert only the new integration commit using a separate PR, not a force push.
