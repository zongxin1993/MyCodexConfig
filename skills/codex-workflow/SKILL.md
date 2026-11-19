---
name: codex-workflow
description: "Use for substantive software requirements in Codex: clarify requirements, approve a concrete plan, implement in a worktree, independently review, and repair/reverify."
---
Managed-By: MyCodexConfig

# Codex engineering workflow

1. Announce `[需求澄清｜进行中]`. Read repository rules and actual source before assuming behavior. Use GrillMe/grilling when available to resolve consequential ambiguities; ask one focused question at a time and do independent investigation meanwhile. Preserve the user's exact acceptance intent, explicit non-goals, failure behavior and unresolved facts. Do not ask again about decisions already made.
2. Load codex-quality-planning. Separate requirements/design approval from implementation-plan approval when the project requires both. For an already approved concrete change, continue within that authorization; do not manufacture extra approval gates. A test harness's scripted answers/approvals are fixture-only.
3. Announce `[计划｜待确认]` with requirements -> tasks -> acceptance checks, module ownership/dependencies, risks and actual verification environment. Do not implement unapproved product semantics.
4. Load codex-execution. Prefer native Codex worktree tools; reuse an existing linked worktree. If creation is cancelled or denied, do not bypass it. Keep the source checkout read-only. Show actual worktree and status.
5. After implementation and impact-selected tests, use an independent reviewer in a fresh context, with codex-quality-review and source/diff/check evidence. A self-review is useful but is not independent review. Do not spawn nested reviewer chains. The coordinator records the actual worker/reviewer identifiers and worktree in task context (or repository-authorized artifacts) before handoff.
6. On findings, announce `[修复复验｜进行中]`, return concrete findings to the implementation worker, verify each defect, repair, rerun affected checks and request independent re-review of current bytes. Prefer the same worker; if it cannot be recovered, explicitly record the handoff and start a replacement with actual plan, source baseline, finding IDs and original evidence. Missing session IDs must not deadlock the work or justify an invented continuation.
7. Announce `[交付｜通过/阻塞]`: requirements covered, actual tests and environments, resolved/unresolved findings and publication state. Only publish/merge when authorized. Registration, skill loading, MCP startup and mocks are not proof of product correctness.

Do not force cloud/local models, reasoning settings, providers or OpenCode session APIs. Display actual executor when known, never invent model IDs. Follow user scope and repository authorities above this pack. A simple read-only answer does not need this full workflow.
