# H2 offline mutation controls and genuine operational writer
Runs A1-A5 and genuine operational writer integration against fresh PostgreSQL 18.6
containers. No Neon access. The operational writer is a byte-identical snapshot
of `multicity-wip-2026-09-16@b05d1ea61aabb7d9d476a88778a0599103407d94`,
Git blob `0118ca9e5f1308173e657257f1b49fe91cc19fe1`.
The research writer `2a5354aa4ad2bc67893ffa40589024ecb84fa15e`
is not substituted.
Inputs are pinned observed-partial synthetic schema and 001/002 SQL scripts.
A3 and A4 intentionally commit inconsistent synthetic states to prove detection.
Owner bypass is demonstrated through SQL rather than a hardcoded boolean.
The API lacks explicit expected-tip authority; serially consistent concurrent
commits do not count as stale-state rejection. Reports distinguish these.
Own-connection and externally owned transactions are tested separately.
Source SHA and report fingerprints are retained; no credentials in reports.
The experiment is not live Neon equivalence and is not a migration approval.

CI captures two full JSON reports; independent byte-exact Git freeze is a separate
step after the jobs finish. No accepted H2 counts or coordination docs are changed.
