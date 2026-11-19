# Workflow guard implementation plan

User authorized: backup, isolated fixture validation, low cloud probes, global apply and sanitized publication only after acceptance. No other running task may be disturbed.

## Requirements and acceptance

1. Inject entry/recovery guidance on startup/resume/compact. Sessions lacking the new startup receipt stay inactive. Simple read-only questions must not activate a development task; pause must suppress continuation.
2. Private atomic locked state bound to session and repository. No shared task acceptance across sessions. Implementation must bind an actual linked Git worktree; primary source stays read-only.
3. Covered source-write tools refuse missing plan, approval, skill-read or readiness evidence. Allow planning artifacts/read tools/worktree creation. Shell detection is bounded and is not a security sandbox.
4. Observe actual hook tool events and independent SubagentStop receipts. Reviews bind current plan/source and stable finding IDs, never coordinator-authored PASS. Restricted test helper retains original logs/exit code/source snapshot.
5. Stop checks missing evidence with at most two recovery continuations. Waiting for approval/permission or explicit pause does not loop. Missing native MCP is explicit degradation, not native success.
6. Preserve foreign config/RTK; add owned hooks with idempotent merge and rollback. Never alter models/credentials or hook trust records; never restart clients.

## Steps

- Independent plan review.
- Hook adapter, persistent state/gates, bounded helper, installer merge, skill recovery instructions.
- Isolated Git fixture negative controls: omitted plan/approval, primary writes, skill/MCP missing, absent/self/stale review, unresolved findings, failed retest, recovery/pause/retry cap, concurrent isolation, installer rollback.
- Real low cloud probes: hook loading, denial, automatic continuation, MCP missing. Distinguish protocol fixtures, native CLI and real Desktop proof.
- Independent code review and repairs, full regression; apply/publish only after required acceptance.

## Limits

Host hook trust may require user review; never manufacture it. Specialized tools and persistent shells can escape coverage. Prompt classification is bounded. Approval is human provenance, never invented. Engineering gates are not a hostile-model security boundary. If actual Desktop validation cannot run autonomously, preserve that missing gate rather than claim CLI equals Desktop.

## Independent plan review amendments (GPR-01..04)

- Only source=startup may create a new guard receipt. Resume/compact without a receipt are no-ops. Synthetic recovery prompts match a stored one-shot digest and never approve/reset budgets. Interrupt/pause survives resume.
- Approval must be a direct UserPromptSubmit after the current plan exists and explicitly name its digest. No coordinator-authored approval file or generic preapproval is accepted. The prompt hash and plan digest are retained; only their binding is authorization evidence.
- Independent review uses an explicit review-request nonce bound to kind/plan/source. PreToolUse must observe a matching agent dispatch; SubagentStart supplies the actual independent agent identity. Only its matching final strict receipt can advance the phase. Receipt schemas are not proof of review thoroughness.
- Resolve every covered patch/file target against the effective tool cwd; reject any mixed primary/sibling/symlink target. Arbitrary shell interpretation is not a security boundary; native host sandbox still governs actual writes. Conservative prerequisites apply before shell execution.
- Required acceptance includes isolated real low local-CLI hook dispatch/denial/recovery, plus actual Desktop proof before global apply. Neither protocol tests nor local CLI substitutes for Desktop. Existing conflicting Stop hooks must be reported rather than silently overridden. Private state is retained until explicit cleanup; backups support rollback.
