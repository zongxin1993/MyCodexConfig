---
name: codex-execution
description: "Use to implement an approved Codex task in an isolated worktree, with bounded search, native tests, original evidence and repair/reverification."
---
Managed-By: MyCodexConfig

# Isolated implementation

- Read the approved plan and repository rules. Show `[实施｜进行中]` and actual directory. Detect isolation with native Git facts or `python3 @RUNTIME@/tools.py worktree --root <cwd>`. Prefer native worktree tools if creation is needed. Never silently implement in the primary checkout after a cancellation/denial.
- Source checkout access is read-only. Use Codex's native file tools and sandbox; do not add the source as a writable root to read it. A Git worktree shares Git metadata, not arbitrary source write permission.
- Locate files with `rg --files`, then narrow literal `rg -n -F -- <query> <paths>`. Avoid recursive grep/find shell pipelines and repeated rediscovery. Preserve limits/partial results; zero matches do not prove absence. These are native shell commands, not unavailable OpenCode execution_search tools.
- Syntax questions use codex-ast-grep over 1..64 explicit current-worktree files. Rust tasks use codex-rust-workflow for toolchain/Cargo/behavior gates; concrete Rust compiler diagnostics use codex-rust-diagnostics. Read original declarations/call sites and repair the responsible boundary.
- Apply test-driven-development/systematic-debugging when available. Run the repository's impact-selected checks using native shell. Do not replace gates, hide exit codes or weaken assertions. Retain original logs plus command, cwd, source revision and exit result in the authorized evidence location.
- RTK: preserve the existing trusted Codex hook when present; otherwise use RTK explicitly only for supported display commands. Full test logs and exit status remain authoritative. Do not claim reduced tokens prove faster execution. Never install a second competing hook.
- Return changed files, actual successful checks and missing lanes. A fresh reviewer audits source/diff and test validity. Findings return for scoped repair and affected checks, then independent re-review. Persist actual handoff identifiers; if unavailable, explain and create an explicit replacement handoff without claiming same-session continuation.
- compress/acp_status are optional host tools. Never call absent tools, guess message IDs or churn summaries instead of doing work.
