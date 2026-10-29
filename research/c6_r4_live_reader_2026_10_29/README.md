# C6-R4 research-only proof

Source: C6-R3 reader Python code and accepted nine UID crosswalk. CI exercises disposable PostgreSQL 16; it does not contact Neon, publish data, or modify production workflows.

For a protected direct Python run only, supply a read-only database URL in `C6_R4_READONLY_DATABASE_URL` and Neon control-plane key `NEON_API_KEY` to the local secured process (never commit either). Run `python c6_r4_reader_wrapper.py --git-repo <full-git-checkout> --scope september` and separately `--scope october`. A trusted actual origin/site-prod ref and pinned source objects are mandatory. A failed authority check must reject. The control-plane key is used only to verify branch and read-only endpoint metadata. The expected October command is a nonzero exit with explicit HARD_FAIL, with no callback to a consumer and no publication artifacts.

CI-generated `proof/` runtime evidence and SHA256 manifest are the only accepted test results; committed pre-CI gate files are deliberately pending. No claim of live Python execution without protected database connectivity.
