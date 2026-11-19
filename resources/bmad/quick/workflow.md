
# Code Review Workflow

Several independent reviewers hunt for defects in a code change; this workflow sends them the change, then verifies, triages, presents, and fixes what they found.

Subagents are an important part of this workflow. Use them wherever a step calls for them, if you can. If you need the user's permission to run them, ask once now for the whole run.

## Conventions

- When a step directs you to another file, read it fully and follow it. Load one step at a time, when it is reached.
- A step that shows a menu or checkpoint halts there and waits for the user.

## No-code review

Review by inspection only. Do not modify code, run builds or tests, or invoke quality gates.

## On activation

Run each of these in order before step 1 (`_None._` means skip):

_None._

Hold every entry below as fact for the whole run. Entries prefixed `file:` are paths or globs under `{project-root}` to read; the rest are facts verbatim (`_None._` means none):

- Codex host adapter governs tools, persistence and evidence: no shell, no source/spec/plan writes; verify every alleged gap; missing lenses are incomplete; allow zero findings. Root coordinator dispatches flat sibling review sessions because host depth may be one; reviewer children never spawn children. Root returns actual sibling reports for triage. Reports return to root parent for verbatim archival only in .quality/reviews; implementer retains execution logs and repairs.

Then run each of these in order (`_None._` means skip):

_None._

## First step

Read fully and follow `./step-01-gather-context.md`.

## Codex host authority
Review is read-only. Read current source through native read tools or read-only shell. Never persist reports or child prompts. Return findings and missing-lens limitations to the coordinator. The coordinator archives approved evidence in the isolated worktree. If a required independent lens is unavailable, mark it incomplete; do not simulate a reviewer or claim a full review. The host permission boundary overrides all upstream write or halt instructions.
