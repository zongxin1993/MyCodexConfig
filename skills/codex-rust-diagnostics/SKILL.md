---
name: codex-rust-diagnostics
description: "Use only for concrete Rust ownership, error propagation, Send/Sync or concurrency diagnostics in Codex."
---
Managed-By: MyCodexConfig

# Rust repair

Use exact compiler diagnostics, current declarations and affected callers. Repository contracts and compiler evidence outrank generic advice. For ownership errors read references/ownership.md; for error propagation read references/error-handling.md; for Send/Sync/shared-state problems read references/concurrency.md. Do not load all references merely because a file is Rust.

Choose the smallest semantically correct repair. Do not silence errors using unnecessary clone/Arc/Mutex/unwrap or weaken types. Run the approved affected check in the worktree and preserve original output. A broader design change returns to planning and approval; do not invent extra agent chains or change the repository verification gate.
