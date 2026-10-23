# Windows psql H2 role-existence kit — research implementation

STATUS: **IMPLEMENTATION PUBLISHED FOR OFFLINE VALIDATION; NOT KIT READY; DO NOT EXECUTE LIVE.** H2_ROLE_EXISTENCE=UNVERIFIED; authorization for one future read remains UNUSED according to the bounded prior operator receipt.

Immutable source `ROLE_EXISTENCE_PINNED.sql`: Git blob `dd3595f7402cdc6e44d3fce6c5632dd9cfb88052`, SHA-256 `3e8a8d62440ec30245f64da21a263d84793e7e77a8cf45806f60a656ba6a31ee`. Immutable `ROUTE_ATTESTATION_TEMPLATE.json` blob `0ea2e8688c5b5a5e3934704a29b2ad51195584b4`: independently verified port and reviewer **remain false/unpopulated**.

Published alongside these immutable inputs: PowerShell launcher `Invoke-H2RoleExistence.ps1`, standalone offline `verify_receipt.py`, `test_offline.py` negative fixtures, `mock_psql.py` synthetic process, `test_windows.ps1` Windows test orchestration, and `OPERATOR_GUIDE_UA.md`. Tests are mock-only and cannot prove actual TLS, live Postgres behavior, or physical connection count. A live operator must have a fresh independently reviewed route/port/CA mapping, authorized separate one-read execution, and an independent security reviewer; no execution in this branch task.

**Reviewed README diff:** replaced the unverified claim that missing files existed as "separate local-chat artifacts" with explicit published filenames; changed "INCOMPLETE GITHUB STAGING" to "IMPLEMENTATION PUBLISHED FOR OFFLINE VALIDATION", retaining **NOT KIT READY / NO LIVE EXECUTION**; retained immutable SQL pin and the unapproved route gate. No ZIP is claimed to exist.

Source main `c93e77fab07fe1997385f85394b6a4ddfbea61f6`; research `2f650243f2569f20050da0eb590cff0c82957eb8`; blocked no-execution receipt `05684ebaad63e00834bb37fe6045afc2a3308617`. No main, production, site-prod, WIP or Neon changes.
