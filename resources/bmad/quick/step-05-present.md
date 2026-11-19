---
deferred_work_file: '<render-root>/reports/deferred-work.md'
---

# Step 5: Present and Act

## RULES

- Return findings in the response; the reviewer must not write files, including `{plan_file}`.
- Never change a plan's `status`. The build leaves it at `built`; only the user marks a ticket done.
- `{triage_file}` is the source for every finding below: its verdict, evidence, route, options, and rejection reason. Render from it, not from memory.
- No human can answer during this run: never ask and never HALT. The report text is the deliverable -- everything a reader must act on is in it, not only in files the run writes.

## INSTRUCTIONS

### 1. Clean review shortcut

If zero findings remain after triage (all rejected or none raised): state that. Return section 2's block in the response, with the summary line and the `Rejected` appendix, so the run is recorded.
Then proceed to section 5.

### 2. Write findings to the plan

If `{plan_file}` is set, append a block to its `## Code Review` section, creating that section at the end of the file when it is absent. The block opens with `### {date}` and the summary line from section 3, then the findings below, then the `Rejected` appendix. Write all findings in this order:

1. **`decision-needed`** findings (unchecked):
   `- [ ] [Review][Decision] <Title> — <Detail> Options: <each option, one line>. Recommended: <option> — <reason>.`

2. **`patch`** findings (unchecked):
   `- [ ] [Review][Patch] <Title> [<file>:<line>]`

3. **`defer`** findings (checked off, marked deferred):
   `- [x] [Review][Defer] <Title> [<file>:<line>] — deferred: <pre-existing, or for maybe-false the evidence that would settle it>`

Also append each `defer` finding to `{deferred_work_file}` under a heading `## Deferred from: code review ({date})`. If `plan_file` is set, include its basename in the heading (e.g., `code review of story-digest-delivery-plan (2026-03-18)`). One bullet per finding with description.

### 3. Present summary

Announce what was written:

> **Code review complete.** <D> `decision-needed`, <P> `patch`, <W> `defer`, <R> rejected.

The `Rejected` appendix is one line per rejected finding: `false` with its refutation, `low` with why it was not worth fixing. Without `plan_file`, it ends the chat listing.

The listing is the review itself. List `decision-needed` entries first, then `patch`, then `defer`, then the `Rejected` appendix, highest severity first within each. Each `decision-needed` entry carries its options and the recommended one and is marked open -- nothing was decided. Each `patch` entry carries its location and the fix.

If `plan_file` is set, add: `Findings written to {plan_file}.`
Otherwise add: `Findings are listed above. No plan was provided, so nothing was persisted.`


### 5. Handle `patch` findings

Write one Markdown block a coding agent can fix the findings from without redoing the review. Name the base it was compared to by full SHA, and the reviewed commit the same way, or say that the change is uncommitted on top of the base. Then, for each `patch` finding (including any resolved from `decision-needed`): what is wrong and how you know; the files or symbols it touches; what the fixed code should do, as an outcome, not a recipe; and how to check the fix, including anything that has to be run to confirm the defect. If there are no `patch` findings, say so. Then, under their own headings, list the `decision-needed` findings still unresolved and the `defer` findings, each with its reason, so the agent knows they are not its to fix.

Nothing was run in this review, so never claim a fix works or a check passed.

Return the original report and schema-valid JSON to the native Codex parent. Do not write approved plans or any source files.


## On Complete

If anything appears below, follow it as the final terminal instruction before exiting; otherwise exit normally.
