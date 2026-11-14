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

## Exact final HEAD
See Draft PR for final immutable GitHub Actions run IDs, test counts and proof artifact. Do not infer physical CI success until GitHub actually reports it. Verdict PARTIAL until all checks complete; even on offline SUCCESS, no real T03/T04 end-to-end count is proven.
