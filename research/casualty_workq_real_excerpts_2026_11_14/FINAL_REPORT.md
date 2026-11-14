# WORK Q — parser and auxiliary CI (research only)

## Confirmed evidence
Work P Actions #43521321878, artifact #14082589637, independently downloaded ZIP SHA-256 67133a7b2e94fdcdf8c1a4bf3871788b691e35b3666430b976e082355675b99f. All 4 manifest file checksums independently verified.
T03 preserved excerpt: «Загинули двоє людей»; this is a LOCAL count 2, not a verified full-article event total. A second retained excerpt describes the deceased couple. Work A already recognizes «двоє», so without complete HTML/text the exact reason for a null article-wide claim cannot be reconstructed.
T04 preserved excerpt: «Пізніше стало відомо, що загинула також 69-річна жінка». This reports an additional death, not an event total. 69 is an age, not a death count. Automatic addition or 2→3 synthesis is forbidden.
T05 remains police total 3, attack date absent, no automatic incident link, NEEDS_REVIEW.

## Narrow code change
An additional-death guard prevents an earlier count from becoming an article-wide final total. Diagnostic labels distinguish conflicting totals, multiple possible attacks, additional death and uncertain context; no source text in diagnostics. The existing minimal fact card retains claim_type ADDITIONAL_DEATH_REPORTED using the existing NEEDS_REVIEW decision. The original runner is repinned to the exact modified parser/ingestion blobs on this clean, offline-only branch; the previous authorized launch commit is untouched.
Work O offline workflow now has Work L's existing paths-ignore for launch.json-only push, and both offline workflows listen to the clean Work Q branch. Mixed changes cannot bypass the offline checks. Live workflow remains unchanged and only listens on the prior Work P branch, with actor, run_attempt=1, grant, SHA, ancestry, expiry and one-shot protections intact.

## Proof limits
All new tests are local/synthetic or use the two deidentified saved real excerpts. No full HTML/articles were retained; no article-wide verified totals for T03 or T04 can be claimed. Zero new source HTTP GET, zero auto credits, no production/WIP/Neon/C2/deploy/merge/PROMOTE. Existing 18→20→23 and five source-empty groups remain verification gates.

## Verified GitHub Actions code-and-tests checkpoint

- Exact code/test HEAD `2833106f1551e7891f9da4e713250a06fd7189a7`.
- [Work O offline Actions #43571826327](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43571826327), attempt 1 SUCCESS, five groups: frozen E/G/I/J/K/L 68 PASS; Work O/J/E 31 PASS; Work A 34 PASS + 1 expected SKIP; Work P 4 PASS; Work Q 8 PASS. **145 PASS, 0 FAIL, 1 SKIP.**
- Immutable [proof artifact #14105205043](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/43571826327/artifacts/14105205043), ZIP SHA-256 `861d5f1275e0490ee9cbeb44232c3e720d142cbbb205fe0d5aa6326c2bf12d96` physically downloaded and hashed. 10/10 manifest hashes independently verified.
- Original evidence and production generator regression 18→20→23 PASS; five insufficient-original-source clusters remain blocked. Source HTTP GET = 0; no automatic casualty credits.
- Earlier pre-final Work L run #43571690856: offline job PASS; pre-HTTP job failed on the frozen Work N branch-string assertion after a research-only branch list change. The Work L branch list was subsequently **restored byte-for-byte**; its safety suite and live workflow were not changed. Prior frozen Work L preflight remains intact; current Work Q is covered by Work O offline on exact research HEAD.

## Exact final HEAD

This documentation-only successor requires a fresh exact-HEAD GitHub Actions check. Refer to the immutable PR conversation for the later run ID and final result. Even a successful research offline run does **not** establish a full verified T03/T04 article-wide death total, so the outcome remains **PARTIAL** on real-source completeness.
