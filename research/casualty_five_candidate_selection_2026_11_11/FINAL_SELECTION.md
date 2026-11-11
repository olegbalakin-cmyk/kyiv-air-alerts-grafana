# Final selection: five casualty WIP candidates (2026-11-11)

Scope: validation of the existing five-entry selection only. **No new candidate search, source HTTP, reviewer, CI, merge, deployment or changes to production data.**

## Pinned inputs

- [Saved selection](./selected_queue.json): research branch `research-casualty-five-candidates-2026-11-11`, pre-validation HEAD `2be0b882f8119d16837f572dfa36d607ef0ebc81`, selection file blob `050d85606f6742306d28651a410baa23947557bd` (5 entries; left unchanged).
- Active WIP: `multicity-wip-2026-09-16` at `c5ad6548e5ae901a75e5ff1b82ba25289341f59b`.
- **Queue snapshot blob:** `f3f7141aa6d7584c63ff42510b40239a18834d15`, path `kyiv-air-alerts-grafana/data/casualties/multicity_review_queue.json`, 1,657 records (1,656 `needs_review`; 1 `confirmed`). The five ID matches are each unique.
- `revisions.csv`: `main` and WIP identical blob `3b2b04438a12a55a0e42ed3b38a3b3a6ba5135c1` (header only); `site-prod` blob `8d7a2e2540bf4bf0f8c6227023821390bf82ce13` (one confirmed Sumy revision unrelated to the five IDs/cities).
- Checked `main:PROJECT_STATE.md` and `main:CHANGELOG.md`; latest accepted coordination checkpoint: `C6-REPLAY-SEVASTOPOL-MERGED-01` (separate track). Research PR #59 is still open/draft, not an accepted casualty merge.

## Exact ID-by-ID reconciliation

Each candidate was matched by `candidate_id` against **the single queue blob above**, then compared for exact `url`, `city`, `city_key`, `published_at`, `title`, `publisher` and `status`. All match the saved selection. No relevant revision entries were found.

| Candidate ID | Місто | Видавець | Є в черзі? | Статус | Вердикт / причина |
| --- | --- | --- | --- | --- | --- |
| `5d60e1c78026fdc494ea3c84` | Дніпро | Суспільне \| Новини | Так (1) | `needs_review` | `READY_FOR_HTTP_TEST` — ідентичні поля; поправки немає |
| `96dc8052cf48f4ce74df29f6` | Харків | LB.ua | Так (1) | `needs_review` | `READY_FOR_HTTP_TEST` — ідентичні поля; поправки немає |
| `6c946bfd46fffbe953d795bf` | Луцьк | УНІАН | Так (1) | `needs_review` | `READY_FOR_HTTP_TEST` — ідентичні поля; поправки немає |
| `f4719e871b92e7563c7150da` | Одеса | Суспільне \| Новини | Так (1) | `needs_review` | `READY_FOR_HTTP_TEST` — ідентичні поля; поправки немає |
| `81196e29c4a6ac2141a93617` | Харків | Korrespondent.net | Так (1) | `needs_review` | `READY_FOR_HTTP_TEST` — ідентичні поля; поправки немає |

**Conclusion: 5/5 READY_FOR_HTTP_TEST, 0 NEEDS_REPLACEMENT.** This is routing/input readiness only, **not** evidence of media URL reachability, a confirmed casualty event or a publishable deaths revision. The next worker may attempt the separately authorized source HTTP proof; no such access was made here.
