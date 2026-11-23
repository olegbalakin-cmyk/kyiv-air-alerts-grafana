# Issue #247 — October next: offline source-proof and anti-dup review

**Status:** RESEARCH ONLY; `PROMOTE=OFF`. This does not authorize publication, a new revision, a monthly exact total, or an HTTP publisher capture.

## Outcome and precise totals

Reviewed all **13 preliminary groups** from PR #235 against the accepted PR #236 four events and the existing site-prod review queue. Identified **four new Kyiv candidate groups** covering **six physical subincident locations** with an evidence-supported **minimum of 11 additional civilian deaths**; 4 preapproved groups are excluded; 5 groups remain held. Four prior attacks had a lower bound of **11**, giving a research-supported distinct-incident subtotal of **22** (11 old + 11 new) *across five cities, NOT a complete October city-month or national total*. The 11 newly evidenced deaths are Kyiv incident-level minima, not a certified October monthly statistic.

The material is strong enough for *coordinator evidence review* and future revised sidecar preparation. It is **not** permission to publish: the prior collector stored short excerpts, not full independent source bodies; production credit/identity contracts still require independent verification and a separate owner GO.

| Attack/date | Physical source-backed grouping | Newly evidenced minimum | No double count |
|---|---|---:|---|
| Kyiv 7 Oct pre-dawn | Darnytskyi garage ballistic strike; two elderly men | 2 | Independent of evening 7 Oct UAV impacts |
| Kyiv 7 Oct evening | Obolonskyi courtyard 2; Desnianskyi residential building 2 | 4 | Oct8 morning reporting of Desnianskyi bodies still belongs to Oct7 attack; 2+2, not 4+2 |
| Kyiv 8 Oct daytime | Holosiivskyi 1; Solomianskyi shop 3 | 4 | Interim 3 replaced by 4; preliminary shop 2 replaced by police 3, hospital death counted once |
| Kyiv 20 Oct | Holosiivskyi UAV / near fuel station 1 | 1 | Chabany, Fastiv raion 3 are Kyiv oblast and excluded |
| **NEW verified incident minima** | **4 groups, 6 location-specific subincidents** | **11** | **0 automatic credits** |

## Source and baseline pins (verified read-only)

- `main@b35ca5c8d189a011c1b7158275f189a195192890`; `site-prod@f7e0681ca6aa98405638dae7a63c884f4ed55d20`.
- PR #235: `17291da5ab7a682eabc1b9458685b2a2724b3d71`; PR #236: `270702ccc4a76d81ee8cc5b9cf73059fd19df025`; [offline CI #45073045655](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45073045655) SUCCESS.
- Prior one-shot [#45070256716](https://github.com/olegbalakin-cmyk/kyiv-air-alerts-grafana/actions/runs/45070256716) SUCCESS, ZIP artifact **#14773425588**, SHA256 `f2a95945e98dc92cdc49529be2bb127a5d4c3fe8a9e71ad82ebf2437b7c2eb9f`; inner capture SHA256 `be053f77ade09db833eb976a67a6bcb036fb42cff1c98f81bfd90dde1fbe7ed8`. Rehashed exact downloaded ZIP and report locally: PASS. 27 earlier requests, 21 successful, no reusable GO.
- Current site-prod `review_queue.json` blob `8ae078bc60f2c27838b61e9aebf90b7286e0dd55`; `revisions.csv` blob `8d7a2e2540bf4bf0f8c6227023821390bf82ce13`; 20-city baseline blob `f3b7fdf6750e12d7b9af05ffd094bb47aa9ed801`. Exact inspected current revisions: **only one confirmed Sumy 20 Sep +1**, no October revision. October site-prod city-month rows absent, hence no credited October deaths. The review queue records are candidate evidence, not already-credited entries.
- Machine source registry in `october_next_incident_ledger.json` includes **12 HTTPS source URLs and saved content hashes**, with explicit distinction between one-shot decoded HTML hash (`s10/s11`) and existing queue content hash (`q*`). None is misrepresented as a full-body archive. Queue sources include statements citing Kyiv police, municipality, prosecutor and DSNS; they are not necessarily wholly independent primary captures.

## Five held high-priority groups (not zero deaths)

| Place | Captured candidate | Exact missing proof before accepted credit |
|---|---|---|
| Dnipro 20 Oct | 3 reported in capture s23; Oct24 hospital follow-up uncertain | Dated city police/medical cumulative account, whether hospital death revises prior three |
| Zaporizhzhia 22 Oct | 2→3 likely same attack | City MVA/police proof of locality within Zaporizhzhia city; victims and cumulative identity T03–T05 |
| Kropyvnytskyi 14/15 Oct | Police regional 3 | Exact municipality/incident location, victims, attack date; s13 returned HTTP403 |
| Chernihiv 29 Oct | Police city fatalities but missing count | Full police city incident numeric and location; oblast 26 cannot be copied |
| Kherson 23 Oct | OVA one reported in broader geography | City street/locality, direct UAV attack causation vs unexploded munition, civilian status |

The approved Lutsk 6, Poltava 1, Ivano-Frankivsk 1 and Khmelnytskyi 3 are individually marked `ALREADY_APPROVED_DO_NOT_RECOUNT` in CSV. Sumy September is excluded. Unknown October months remain UNKNOWN, never zeros.

## Deterministic offline guard

Run in the existing research branch:

```bash
python research/casualty_monthly_sources_2026_11_22/test_october_next_incidents.py
python research/casualty_monthly_sources_2026_11_22/check_october_reconciliation.py
python research/casualty_monthly_sources_2026_11_22/prepare_october_partial_preview.py --validate
```

Ten stdlib `unittest` cases assert exact source/branch pins, 13/13 coverage, SHA formats, group↔physical-incident sums, unique IDs, 7 Oct ballistic vs evening UAV, 8 Oct cumulative supersession, Chabany exclusion, 4 previously credited decisions, five blocked cases, no October revisions, unknown-not-zero, and `PROMOTE=OFF`. No external Python packages, network libraries, generator import, or writes.

## Next coordinator handoff and bounded owner GO request

Hand this PR's ledger + decisions to **Issue #245** integration. Coordinator should only add event minima after independent evidence/credit checks; the existing #245 release must remain unmerged and `publication_allowed=false`. The final UI needs a partial lower-bound presentation, source trace, and no exact-total/annual inflation.

**GO request — NOT AUTHORIZED HERE:** owner may separately permit up to **five read-only exact article GETs**, one for each narrowly scoped unresolved publisher source, exact immutable URLs pinned before execution, HTTPS/public IP, timeout 15 s, redirects/retries OFF, 2 MiB max/body, no WIP writes, no credits, and `PROMOTE=OFF`. Obtain direct approved URLs and a fresh grant; do not reuse Nov22 spent grant. Research of the current Kyiv additions also needs independent immutable body evidence before any production credit. Do not dispatch anything under this Issue.

**No edits to main, site-prod, Neon, C6, Netlify, live review queue, revisions, or public casualty totals.**
