# Optional native workflow guard

Read this only when a native `[MyCodexConfig guard]` hook receipt is present. No receipt means guard enforcement is unverified; follow the ordinary workflow and report that limitation. Do not invent hooks or tool names, enable hooks, trust hooks, change configuration, or restart clients from a task.

The receipt supplies the exact helper path, state directory and actual session ID. Use the supplied values with every command:

```text
python3 <helper> status --state-dir <directory> --session <actual-id>
```

For a substantive development task:

1. Read this workflow's full SKILL.md. Call the actual `quality_info` tool if exposed. If missing, record `mcp-missing` with the helper and explain degraded operation. Missing MCP cannot produce VERIFIED acceptance.
2. Use a real linked worktree in the same repository. Bind it with `bind --root <worktree>`. Keep the primary checkout read-only. Create the plan and a JSON array of approved check argument arrays in that worktree's planning directory. Record them with `plan --root <worktree> --file <plan.md> --checks <checks.json>`.
3. Present the concrete plan, checks and returned plan digest to the user. The guard recognizes only an entire direct user prompt `批准计划 <sha256>` or `approve plan <sha256>`. A quoted approval, a recovery message, test fixture text and the coordinator's own statement cannot approve the plan. Changed plan or checks require approval of the new digest.
4. Call `review-request --kind plan`, then dispatch a fresh independent reviewer with that exact nonce, current subject digest, actual files and codex-quality-review. For the collaboration tool, use the returned `task_name` exactly and `fork_turns="none"`; carry the nonce separately in the reviewer instructions. Preserve the native dispatch receipt. Unknown or unmatched identities cannot establish independent review.
5. Implement only in the bound worktree. Run the recorded commands with `check`. Keep original output and exit codes. This is an engineering evidence helper, not a sandbox. Checks must exercise the requirements and use the repository's native verification rules.
6. Call `review-request --kind code` after current checks pass. Dispatch independent review of actual current source and test evidence. Findings need stable IDs. Give each finding back to the implementer, repair, rerun affected checks, and obtain current independent re-review closing the IDs. Do not reuse an older PASS after source, plan or check changes.
7. Inspect `status` before delivery. Report missing evidence; only actual VERIFIED state supports guarded completion. A stopped turn alone does not prove acceptance. Bounded automatic recovery cannot approve plans, impersonate review or bypass missing permissions/MCP. Respect pause and interruption.

Reviewer final line (after substantive review, never echo without reviewing):

```text
MYCODEX_REVIEW {"request":"<nonce>","kind":"plan|code","subject":"<current digest>","verdict":"PASS|BLOCKED","findings":[],"closed":[]}
```

Findings and closures refer to concrete issues explained above that line. A self-review is insufficient. Native hooks only cover supported host tool paths; arbitrary shell programs, excluded snapshot inputs and host errors require separate scrutiny. Do not describe this as an operating-system security boundary.
