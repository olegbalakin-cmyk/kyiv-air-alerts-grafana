# H2 real PostgreSQL 18 Windows client: independently reproducible offline evidence

## Scope and source

Evidence from commit `be52705406c612e295171aab82a2c65b6e894178`, same research branch, with zero SQL, no Neon API or connection, no credential, no route attestation. The test harness does not execute `Invoke-H2RoleExistence.ps1 -ExecuteOneRead`. It only launches the genuine client with `-W -h 127.0.0.1` and an OS-allocated, independently rebind-checked unused local port; `-f` and `-c` are omitted.

Vendor package: EnterpriseDB `postgresql-18.6-5-windows-x64-binaries.zip`, URL `https://get.enterprisedb.com/postgresql/postgresql-18.6-5-windows-x64-binaries.zip`. Independently obtained public EDB staff package checksum, `e2246ba91d22345bc3d017586c09ede52d9df180b1eeb480f050445f1cad84e2`. Exact archive 384620317 bytes, package hash matched. Extracted 69 client-bin entries without installing server.

Executable `C:\Program Files\PostgreSQL\18\bin\psql.exe`, real `--version`: `psql (PostgreSQL) 18.6`, executable SHA-256 `fde952534f520909c02db04675588ecb1da8d618b6e5c93e106f42a752daf720`. Authenticode `NotSigned`: **do not claim independently signed EXE**; provenance rests on EDB HTTPS archive and published independently pinned archive digest. Real version accepted by exact launcher regex `^psql \(PostgreSQL\) 18\.\d+(?:\.\d+)?$`; invalid/unsupported string fixtures rejected. The missing EXE is verified by explicit existence gate; the actual published launcher itself was NOT executed in live mode because that requires Neon route/authorization.

## Independent Actions evidence

- Actual real client workflow `40013884410`, job `120620867376`, **success** on checked-out commit `be52705406c612e295171aab82a2c65b6e894178`. Log: `REAL_CLIENT_VERSION_GUARD=PASS`, loopback `127.0.0.1:52552`, `LOOPBACK_PORT_BIND_PROOF=PASS`. Under `RedirectStandardError=true`, `RedirectStandardInput=false`, `-W`, `CreateNoWindow=false`, and a 20-second bound, noninteractive CI observed `STDERR_FALLBACK_PROMPT_CAPTURED=False`, `CONNECTION_REFUSED_OBSERVED=False`, `CHILD_TIMED_OUT=True`, `CHILD_ELAPSED_MS=20016`, `CHILD_NONZERO_EXIT=True`. One launched process, killed on timeout; no password in child argv/environment or captured stdout/stderr, no SQL or Neon use. A bounded PASS in this workflow means fail-closed noninteractive timeout, **not** prompt/no-echo success.
- Existing synthetic workflow re-ran on the exact same commit: `40013884219`, job `120620866492`, **success** with 23/23 Python and 13/13 Windows mock-process cases. Synthetic tests do not establish TLS or physical session counts.
- Neither run captures a real manual console, and neither independently proves a genuine human password prompt/no echo; the fallback was not observed on stderr, so treating this as a working hidden-input fallback would be unsound.

## Mandatory genuine Windows Terminal operator observation (offline-only)

Run only from a genuine, private Windows Terminal / PowerShell 7.4+ session on a machine with the same authenticated PG18 client binary. Turn OFF terminal transcripts, screen recordings and key loggers; never use production or Neon credentials. Do **not** invoke `-ExecuteOneRead`, do **not** use the pinned SQL, and do **not** supply an attestation. Confirm `C:\Program Files\PostgreSQL\18\bin\psql.exe` is present and independently check its `--version` and SHA-256.

From the repository root at the tested SHA, execute:

```powershell
$env:H2_NO_NEON = '1'
pwsh -NoProfile -File ".\research\h2_role_existence_windows_psql_2026_10_22\Test-H2Psql18RealClientOffline.ps1" -PsqlPath "C:\Program Files\PostgreSQL\18\bin\psql.exe" -ManualConsole
```

Only if `Password for user h2_dummy_local:` is **visibly shown** in the parent console, type the literal dummy text `h2PROMPT_TEST_9397` once and press Enter. Confirm the characters and dummy password do **not** appear on screen. Do not copy console output into public logs; note only boolean outcomes. If no prompt appears, do not type a password blindly: observe the 20-second timeout and safe child exit, record prompt visibility `NO`, no-echo `UNVERIFIED`, and fallback `UNVERIFIED`. Optionally repeat a separate manual run with Ctrl+C to check cancellation; never use any Neon host. No infinite retries, no alternate endpoints, no SQL. The loopback address is hard-coded and a port is chosen by the script; the command contains no route or secrets.

Record independently: console actually interactive? prompt visible? characters echoed? masked? dummy string absent from stderr, stdout, terminal transcript and receipt? timeout/cancellation leaves no child? (Use `Get-Process psql -ErrorAction SilentlyContinue` after the script to check.) Whether a failure is `connection refused` or `timeout` must be reported literally, not guessed. Do not upload the dummy input or any real secret to CI.

## Verdict and blockers

```
POSTGRESQL_18_CLIENT_VERIFIED=YES
PASSWORD_PROMPT_VERIFIED=UNVERIFIED
PASSWORD_HANDLING_SECURITY=UNVERIFIED
WINDOWS_OFFLINE_TESTS_PASS=YES
LIVE_TLS_VERIFIED=NO
H2_WINDOWS_PSQL_KIT_READY=NO
H2_ROLE_EXISTENCE=UNVERIFIED
```

The real client and 20-second noninteractive failure are independently proven. Manual visible/no-echo prompt and fallback security remain unverified, as do authorized direct RO route/port/CA, independent reviewer, real TLS/hostname verification, single physical session and server-side rollback. The earlier single-use owner SQL authorization remains UNUSED according to the bounded prior receipt, not an independently audited database fact. This record must not be used to infer live execution readiness or role existence.
