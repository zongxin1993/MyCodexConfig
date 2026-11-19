---
name: codex-rust-workflow
description: "Use for Rust planning, Cargo implementation/verification, and code review in Codex; choose the repository toolchain, features, native gates and semantic acceptance cases."
---
Managed-By: MyCodexConfig

# Rust engineering

Read Cargo.toml (workspace and affected packages), rust-toolchain.toml/rust-toolchain, Cargo.lock, CI and repository rules before choosing checks. Record the actual toolchain, edition, rust-version/MSRV, affected packages, features and targets. Do not upgrade dependencies/toolchains, regenerate a lockfile or enable every feature just to obtain a green check. Missing tools/components are a missing lane; obtain authorized provisioning or report the limitation.

For planning/implementation read references/cargo-gates.md. Map each approved requirement to a behavior test, including relevant invalid input, boundary, error and recovery cases. Keep verification in the isolated worktree; use the repository's wrapper/container when required. The command examples are a fallback for a small dependency-free fixture, not a replacement for project policy.

For review read references/review.md. A compiler/Clippy pass does not prove semantic correctness. Review current source, callers and original logs in a fresh reviewer context. Preserve finding IDs through same-worker repair and independent re-review using codex-quality-review. Use codex-rust-diagnostics only when an actual ownership, error propagation or Send/Sync diagnostic needs investigation; load the corresponding reference, not all Rust material.

Never fix a failure by weakening assertions, dropping a required target/feature, adding blanket allow attributes or converting failures into successful defaults. Optional Miri, sanitizer, dependency-advisory or feature-matrix tools require a justified risk and an available environment; don't claim these checks ran from a skill being loaded.
