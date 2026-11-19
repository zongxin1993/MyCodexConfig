# Codex Workflow Adapter Implementation Plan

> **For agentic workers:** Use executing-plans to implement this approved adaptation task by task.

**Goal:** Preserve requirements clarification, explicit plans, isolated implementation, independent review and repair/reverification in Codex without modifying OpenCode.

**Architecture:** A Codex-only skill pack, independent stdio quality MCP registry/runtime, bounded search helpers and a backup-first installer. Existing generic shared skills remain unchanged. Repository-native governance remains authoritative.

**Tech Stack:** Python 3.11+, Codex CLI/Desktop, Git, optional rg/ast-grep/RTK, Context7 HTTP MCP.

**Spec:** User authorized the recommended combination, backup, full workflow validation, noninterference and publication to MyCodexConfig. No model/provider credential transfer; Context7 uses its own Codex OAuth authorization.

## Global Constraints

- Do not edit/reload/restart OpenCode or running task directories.
- Back up Codex config/guidance and installer-owned files before replacing them.
- Keep Codex settings/registry/runtime independent of OpenCode and all credentials out of Git.
- Native project rules override portable artifacts. Read-only review must not mutate sources.
- Fresh CLI sessions validate configuration; no claim that the already-running Desktop thread has hot-reloaded.
- Existing user tasks keep their processes and configuration snapshot.

## Review Focus

- Config merge must preserve existing providers, hooks, permissions, plugins and unrelated sections.
- Repeated installation and rollback must be deterministic; refuse foreign skill collisions/symlinks.
- Source checkout must remain unchanged; worktree reads/searches must not escape via symlinks.
- A failed/stale review or test cannot become acceptance through a summary or registration.
- A deliberately broken isolated fixture must fail, then pass only after repair and independent re-review.

## Tasks

- [x] Build independent MCP package from the established quality core; bundle pinned public BMAD resources with provenance/license.
- [x] Add Codex-only skills for workflow, planning, execution, review, syntax search and Rust diagnostics. Disable OpenCode adapters only in Codex discovery.
- [x] Add backup-first idempotent installer, scoped tool helpers, checks and rollback.
- [x] Test fixture install/rollback, registry isolation, protocol, source containment and existing quality gate cases.
- [x] Install after backup; verify a new Codex session discovers skills/MCP and Context7.
- [x] Validate clarification/plan/worktree implementation/review/fix/reverification; preserve actual results.
- [x] Confirm OpenCode files unchanged and sanitize standalone Git repository. Publication is recorded by the actual Git remote receipt, not this checklist.

Validation fixture approval is supplied by the operator for testing only. This must never be presented as a real product user's requirement/plan approval.
