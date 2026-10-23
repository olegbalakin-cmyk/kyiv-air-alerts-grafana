# H2 Windows/Neon route and TLS readiness — offline security review (2026-10-23 UTC)

**Scope:** GitHub source, accepted CI logs, official public documentation only. No Neon Console/API/DNS/TCP/TLS/SQL, no credentials, no actual role check. This research report is NOT coordinator acceptance. `H2_WINDOWS_PSQL_KIT_READY=NO`, `H2_ROLE_EXISTENCE=UNVERIFIED`.

## Evidence reviewed / exact accepted checkpoints

- Current main observed `264282ff93f5dfcbf7951205eb5f15d4c7dc9917`; read `main:PROJECT_STATE.md` and `main:CHANGELOG.md` before changes; newest accepted local owner no-echo checkpoint retained as bounded observation.
- Research entry HEAD `bf9898728df86dc15c8004ec4445df0d503ed716`; accepted SQL blob `dd3595f7402cdc6e44d3fce6c5632dd9cfb88052`, SHA-256 `3e8a8d62440ec30245f64da21a263d84793e7e77a8cf45806f60a656ba6a31ee`; route template blob `0ea2e8688c5b5a5e3934704a29b2ad51195584b4`; no changes to either.
- Windows synthetic run `39962251480` = success at `314149c2`; Windows actual-client run `40013884410` = success at `be527054`; regression `40013884219` = success at `be527054`; final regression `40014066664` = success at `bf989872`. GitHub job metadata and step logs checked; 23 Python + 13 Windows mock cases; EDB genuine psql 18.6 SHA-256 `fde952534f520909c02db04675588ecb1da8d618b6e5c93e106f42a752daf720`. Neither CI result proves live TLS or a hidden console prompt. Operator personally observed hidden password characters in local terminal, not independently instrumented.
- Historical provider-metadata-only receipt: `05684ebaad63e00834bb37fe6045afc2a3308617`, Git blob `7b621fbb93bb602073067f4791920c513eb900f5`; observed 2026-10-22T14:25:02.731Z to 14:25:03.798Z. It is historic metadata, not a fresh independently signed/reviewed route attestation.

## Proposed target versus current independently attested route

| Item | Historical intended value | Present evidence | Current gate |
|---|---|---|---|
| Project | `green-cake-44216048` | 22 Oct metadata-only receipt | UNVERIFIED current owner attestation |
| Branch | `br-bold-mode-b5rub8pq` | Same old metadata | UNVERIFIED |
| Database | `neondb` | Intended database only; no current confirmed branch-binding | UNVERIFIED |
| Read-only compute | `ep-calm-rice-b5073ypp` | Historical endpoint type `read_only`, state idle | UNVERIFIED current |
| Direct FQDN | `ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech` | Historical connector metadata and immutable proposed host pin | UNVERIFIED current |
| Port | `5432` | Historical provider default; no endpoint-specific proof | UNVERIFIED |
| Pooling | false/direct | Historical metadata only; no fresh primary proof | UNVERIFIED |
| PostgreSQL major | 18 | Historical project metadata; no SQL runtime | UNVERIFIED live |
| Operator principal | `neondb_owner` | Pinned candidate, not authenticated | UNVERIFIED |
| Read-only inspector role | `h2_catalog_inspector_ro` | SQL candidate queries existence, not executed | UNVERIFIED |
| Named independent reviewer | none | No real distinct person identified | NO |

A hostname containing the correct endpoint ID or lacking `-pooler` is insufficient proof that it currently maps to this project/branch/read-only compute. Neon docs distinguish a direct and a `-pooler` hostname, and a read replica is a distinct read-only compute. References: https://neon.com/docs/connect/connection-pooling and https://neon.com/docs/introduction/read-replicas . Reject any unexpected identity or fallback.

## TLS / CA / environment findings

- Actual published launcher sets `PGSSLMODE=verify-full`, `PGSSLROOTCERT=system`, `PGGSSENCMODE=disable`, `PGCONNECT_TIMEOUT=5`, fixed `-h` / `-p 5432`, `-U neondb_owner`, `-d neondb`, and explicit `-f` to hashed SQL. The child environment is cleared and a short allowlist rebuilt; `PGPASSWORD`, `PGSERVICE`, `PGHOSTADDR`, `PGOPTIONS`, `PGSSLROOTCERT` inherited overrides, `OPENSSL_CONF`, `SSL_CERT_FILE`, `SSL_CERT_DIR` are not forwarded. Any missing CA or mismatch should fail closed, not downgrade. This is a static configuration conclusion, not a live handshake.
- PostgreSQL 18 explicitly documents that `sslrootcert=system` loads CA roots from the SSL implementation, **not necessarily the Windows OS certificate store**, and OpenSSL trust locations can be influenced by `SSL_CERT_FILE` / `SSL_CERT_DIR`. `verify-full` verifies the certificate trust chain and hostname; weaker modes cannot replace this gate. Documentation: https://www.postgresql.org/docs/18/libpq-connect.html and https://www.postgresql.org/docs/18/libpq-ssl.html .
- The real EDB Windows 18.6 executable and SHA/version are verified, but the precise effective libpq/OpenSSL CA directory/bundle and availability under this specific portable Windows installation have NOT been directly inspected. The executable's Authenticode state is `NotSigned`; provenance is via EDB HTTPS archive hash. Its `--version` cannot prove CA trust or OpenSSL runtime loading.
- **Risk:** if the portable distribution has no usable default CA roots, `sslrootcert=system` could fail closed even with a valid server chain. Do not use `sslmode=require`, `prefer` or inferred fallback. Obtain offline vendor/installed OpenSSL config + default-trust-path evidence, then independently capture actual TLS chain/hostname validation ONLY in a separately authorized connection. Current `LIVE_TLS_VERIFIED=NO`, `CA_CONFIGURATION_REVIEW=UNVERIFIED` pending effective trust-root confirmation.
- Additional bounded risk: a user-writable portable bin directory and dependent DLL search paths mean verifying psql.exe SHA does NOT authenticate all adjacent DLLs, current ACLs or protection against local replacement between hash and execution. Independently validate executable and adjacent EDB DLLs/vendor package consistency and directory ownership before real execution. No privilege escalation or install is required for this offline review.

## Launcher, password handling and execution review

- Pre-existing execution-path defect: live mode hardcoded `$env:ProgramFiles\PostgreSQL\18\bin\psql.exe` while owner verified `$HOME\h2-psql18\pgsql\bin\psql.exe`. A narrow research-branch change adds `-PsqlPath` with exact allowlist for just those two full paths; validates absence of reparse-point file/path, exact EDB SHA-256, PG 18 version, and adds `-ClientPathPreflight` that MUST NOT connect or execute SQL. No binary edit, installer, PATH auto-discovery or SQL/route change.
- Child launches one process, one target, no retry; 20-second process wall limit and 5-second libpq connect timeout. A 20-second timeout is a client-kill guarantee, NOT proof of successful remote rollback. SQL explicitly states `BEGIN ... REPEATABLE READ READ ONLY`, four `SET LOCAL`, one narrow `SELECT`, `ROLLBACK` (7 SQL statements). Output parser requires exactly eight transcript lines, fixed headers/identity and `ROLLBACK`; receipt remains provisional/unverified. This guards shape but does not independently prove a single physical session, actual server rollback, or TLS.
- Password prompt: owner observed visible prompt and non-echo test typing on a genuine Windows console; accepted only `YES_BOUNDED_OWNER_OBSERVED`. Under redirected stderr on noninteractive CI, no fallback prompt was captured and child timed out; therefore `PASSWORD_HANDLING_SECURITY=UNVERIFIED`. Do not repeat successful owner manual test without a concrete defect. For future real credential entry: private interactive terminal only; no stdin redirection, logging, terminal transcript, CI/argv/env/DSN/receipt secrets. If prompt is absent or behavior changes, stop without blind entry or retry. The sanitized result includes the selected catalog-only row and identity, not a password; operator must review its redaction before sharing.
- Caveat: immutable SQL + parser cannot independently prove the route or disambiguate remote process count, and a route JSON with syntactically true review flags is not evidence. Independent reviewer must inspect primary source and SHA.

## Exact owner-controlled nonsecret evidence request

Owner: provide a fresh, attributed export or screenshots from the **authorized Neon owner** tying project ID `green-cake-44216048`, branch `br-bold-mode-b5rub8pq` (name/default flag), database `neondb`, read-only compute `ep-calm-rice-b5073ypp` (type/state/branch association), exact direct `ep-calm-rice-b5073ypp.c-7.us-east-2.aws.neon.tech`, **endpoint port 5432**, pooling DISABLED, PostgreSQL major 18, and `neondb_owner` as a permitted *operator*, not inspector. If any value differs, STOP: no new target selection in this task. For each original artifact record source system/owner, observation UTC, capture UTC, redactions, filename, independent SHA-256; observation within launcher 72-hour window at authorized execution time. Provide no DSNs, credential panels, tokens, certificates' private keys or API secrets. A publicly available documentation page or historical receipt alone does not meet this requirement.

Separately name a real human local operator and a genuinely distinct independent reviewer with acceptance responsibility. Reviewer must inspect each direct route binding and artifact digest, currentness and port, explicit no-pooler/no-primary/no-default fallback, certificate/hostname/CA evidence plan, and potential compute wake-up/log impact. Owner supplies offline trusted-root/EDB library location/config and local file/ACL integrity evidence, with no connection. Once these are independently accepted, owner gives **new explicit and narrow approval** for at most one SQL existence query, one process/physical connection, immutable SQL, 5s connection/20s wall, repeatable-read RO and explicit rollback. No automatic provisioning or broad H2 inspector package follows.

Evidence for later runtime TLS verification (separate authorization only): actual verified peer certificate chain, SAN hostname match against exact approved FQDN, trust anchor identity, TLS version/cipher, exact client build and its trust roots, server identity and a bounded immutable client/connection receipt, independently reviewed. Do not collect it now through any connection.

## Current gates (must not be upgraded by this report)

```text
POSTGRESQL_18_CLIENT_VERIFIED=YES_BOUNDED
PASSWORD_PROMPT_VERIFIED=YES_BOUNDED_OWNER_OBSERVED
PASSWORD_HANDLING_SECURITY=UNVERIFIED
WINDOWS_CLIENT_PATH_READY=UNVERIFIED_PENDING_EXACT_WINDOWS_CI
DIRECT_RO_ROUTE_ATTESTED=UNVERIFIED
PORT_5432_ATTESTED=UNVERIFIED
CA_CONFIGURATION_REVIEW=UNVERIFIED
LIVE_TLS_VERIFIED=NO
INDEPENDENT_REVIEWER_IDENTIFIED=NO
H2_WINDOWS_PSQL_KIT_READY=NO
H2_ROLE_EXISTENCE=UNVERIFIED
```

**No Neon access, SQL, TLS handshake, DNS/TCP probe or role provisioning performed.** Previous one-read authorization is `UNUSED` per historical bounded operator receipt, not independent server proof. No modifications to main/coordination, site-prod/production, WIP, R6, historical/backfill or casualty tracks. Coordinator acceptance remains separate.
