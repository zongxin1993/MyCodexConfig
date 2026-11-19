# Rust adaptation plan

User-approved scope: complete Codex Rust guidance; validate a separate Rust project with real low-effort cloud sessions, independent review and same-worker repair; preserve active tasks/OpenCode; publish sanitized configuration after success.

- R1: add an ordinary Rust workflow entry and progressive Cargo/review references; retain diagnostic-specific entry. Route execution and review to it, preserving repository native gates.
- R2: dependency-free reservation fixture: `reserve(available, requested)` accepts positive requested <= available, returns remaining capacity; zero -> ZeroRequest; excess -> Insufficient. Error leaves caller's capacity unchanged. Unit/integration/doc tests and release profile verify contract.
- R3: prove the harness rejects compiler and Clippy failures; verify valid fixture; inject an independently reviewable semantic defect that existing tests miss; fresh reviewer must block it; original worker repairs and adds regression evidence; independent re-review and all native gates pass.
- R4: record real identifiers, toolchain, commands, source digests and private logs; publish only sanitized facts. The fixture operator's approvals are fixture-only.
- R5: stage install/tests first; backup and apply global skills only after verification; preserve model/provider/auth/hook/OpenCode configuration and primary checkout. Existing sessions are not restarted.

Non-goals: no NAS/service changes, no Strata load, no general Rust safety certification, no forced all-features/MSRV/Miri setup. Actual host has no Rust; provision test-private toolchain without modifying shell/global defaults. Independent adapter review before publication; retain unresolved evidence honestly.
