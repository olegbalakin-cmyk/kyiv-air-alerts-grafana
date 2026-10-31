# 23-city persisted Neon publication candidate

Branch `br-crimson-star-b59u7ge3`, parent `br-bold-mode-b5rub8pq`, TTL `2026-11-01T12:20:00Z`. No new HTTP capture or DB write.

Generation success is distinct from source freshness. A blocked candidate is never copied into the publish directory.

| City | Semantics | Episodes | Observations | Verified capture UTC | Source checkpoint UTC | Evidence |
| --- | --- | ---: | ---: | --- | --- | --- |
| kyiv | exact_city | 2963 | 2 | 2026-10-31T13:17:26.719743Z | 2026-10-31T13:17:26.719743Z | ONE_PHYSICAL_KYIV_CAPTURE_NOT_CONTINUOUS |
| kharkiv | exact_city | 4012 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| zaporizhzhia | exact_city | 2601 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| cherkasy | raion_proxy | 1833 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| zhytomyr | raion_proxy | 956 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| dnipro | raion_proxy | 2688 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| khmelnytskyi | raion_proxy | 442 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| poltava | raion_proxy | 2212 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| rivne | raion_proxy | 459 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| sumy | raion_proxy | 2704 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| vinnytsia | raion_proxy | 589 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| kropyvnytskyi | raion_proxy | 1448 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| lviv | raion_proxy | 163 | 143 | UNPROVEN | 2026-10-01T12:53:17.906474Z | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| chernihiv | raion_proxy | 1964 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| odesa | raion_proxy | 1750 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| kherson | raion_proxy | 1542 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| mykolaiv | raion_proxy | 2175 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| lutsk | raion_proxy | 294 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| uzhhorod | raion_proxy | 93 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| ivano_frankivsk | raion_proxy | 160 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| ternopil | raion_proxy | 227 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| chernivtsi | raion_proxy | 142 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |
| sevastopol | exact_city | 560 | 0 | UNPROVEN | NONE | HISTORICAL_PERSISTED_OR_FROZEN_ONLY |

All cities remain publication-blocked. Kyiv has one genuine HTTP capture; it does not certify continuous updates, active status or upstream payload currency. Lviv has historical checkpoint evidence; its observations lack source retrieval timestamps. The other 21 cities have persisted historical episodes without current source observation/checkpoint proof. Incomplete historical source-link coverage is disclosed; accepted frozen baseline evidence is retained, and no new full historical backfill is required by this gate.

## Publication gates

- `isolated_branch_readonly`: **PASS** — Exact child hostname/role/TTL and REPEATABLE READ READ ONLY transaction
- `23city_generation`: **PASS** — Existing accepted adapter/B2/pure builders; six consumer files; no DST simulation
- `frontend_structure`: **PASS** — 23 city keys, timezone, exact/proxy semantics and required arrays; earlier browser proof remains pinned
- `source_observation_integrity`: **PASS** — Every existing observation UUID/parent/city link validated and retained; historical coverage gaps reported, not converted into a new full-backfill gate
- `source_capture_freshness`: **BLOCKED** — Require verified source captures <=21600s for all required cities; JSON/COMMIT time cannot refresh capture
- `source_continuity`: **OPEN** — Kyiv current checkpoint continuity_verified=false; no repeat source capture authorized
- `current_active_status`: **OPEN** — Closed-history-only builders; zero open DB rows does not certify no active AIR alerts
- `source_contract_and_currency`: **OPEN** — Kyiv source identity prospective; upstream cache currency and all-city source completeness uncertified
- `physical_dst_repairs`: **OPEN** — Four separately tracked physical repairs remain; this runner makes no repair
- `kyiv_current_provenance`: **OPEN** — B2 frozen view reused; later exact Git selections/prospective UUID are research-only; suppressed classifications unchanged
- `explicit_git_auxiliaries`: **PASS** — Git dependency SHA-256/blob/commit manifest; no Neon-error fallback
- `read_only_repeatability`: **PASS** — Second independent read-only snapshot fingerprint equals first; no writer invoked
- `continuous_writer_operation`: **OPEN** — No scheduler/capture/writer launched; earlier single COMMIT/crash/retry proof remains bounded
- `production_preflight`: **OPEN** — Operational source switch/rollback and release readiness require separate preflight
- `production_cutover_authorization`: **OPEN** — No explicit production cutover authorization in this task

## Next owner decision

Authorize a bounded, isolated 23-city source-continuity run: explicit source request budget (history plus current status), at least two observation rounds, durable existing writer/readback, same-source retries and fixed end time. Reuse the existing child before TTL; after expiry, a new child requires explicit authority. No capture runner is enabled by this read-only workflow. Source scope/contracts and budget must be settled before execution. DST/Kyiv repairs remain separate dependencies.

## Proof boundaries

New physical evidence: current child readback, existing UUID/source links, complete historical 23-city regeneration, independent repeated read and fail-closed publication decision. No live-source continuity or physical active-to-closed transition was executed. No new broad parity, browser, CSV, synthetic freshness or rollback tests. Historical C4/backfill/casualty tracks were not modified.
