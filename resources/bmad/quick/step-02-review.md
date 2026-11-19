---
failed_layers: '' # set at runtime: comma-separated list of lenses that failed or returned empty
---

# Step 2: Review

## RULES

- Use the user-authorized model and effort; this resource does not choose a provider or model.
- Only the coordinator dispatches authorized flat sibling reviewers, using available host tools and actual identities. Reviewer children never dispatch nested agents.

## INSTRUCTIONS

1. The review lenses are listed below. For each lens:
   - `Run only when` present and not satisfied by the current context (`{review_mode}`, `{plan_file}`, `{ticket_file}`, `{verbatim_intent}`) → skip the lens and tell the user which lens was skipped and why.
   - otherwise → the lens is active.

2. Announce skipped lenses, then dispatch active lenses through the coordinator. Supply the absolute authorized `{worktree}`, full `{base_sha}`, review scope (branch or uncommitted), and optional already-existing `{diff_file}`, `{claims_file}`, `{plan_file}` and `{ticket_file}` paths. Missing optional files are not prerequisites and must not be created. Supply `{verbatim_intent}` as the user's approved requirements or plan intent in task context. Reviewers read repository authorities and surrounding source directly. For branch review, use the actual merge-base; for uncommitted review, inspect tracked changes with read-only `git diff` and enumerate/read necessary untracked source with native tools. Never materialize a temporary diff or access another checkout without authorization. Give each reviewer the absolute path to its instruction file beside this resource; relative child working directories must not be assumed. If required source, baseline or intent is unavailable, report that limitation. Launch all authorized flat sibling lenses before collecting results; reviewers never dispatch children.

#### Quick (`quick`)

Launch a context-free subagent with this prompt:

Read `{ticket_file}` in full — the ticket, or the epic of a story with no file; it is empty when there is none. The change must meet this intent, not the rest of an epic: {verbatim_intent}

Then read `{plan_file}` — the plan holding the acceptance criteria and intent; empty when there is none — and the files its frontmatter `context:` lists. Read the agent instruction files (`AGENTS.md`, `CLAUDE.md`, or equivalents) at the repository root and in the directories the diff touches; those are the rules. Inspect the supplied authorized worktree and baseline through native read-only Git/source tools, including untracked source for an uncommitted review. Read `{diff_file}` only if an existing artifact was supplied; it is optional.

Report unmet acceptance criteria, broken rules, and bugs. Each finding: the location, what goes wrong, and evidence checked against the surrounding code. Output a Markdown list of findings only — no severity, priority, or ranking.

Review by inspection only. Do not modify code, run builds or tests, or invoke quality gates. Do not invoke any skill, and do not spawn subagents of your own — you are the reviewer. Return your findings as text in your final message; do not route them through any findings-reporting tool the host may offer.

3. If independent lenses are unavailable, return their names as incomplete to the coordinator. Never write child prompts, simulate independence, ask for filesystem transfers or spawn nested agents.

4. **Lens failure handling**: If any lens fails, times out, or returns empty results, append the lens's `name` to `failed_layers` (comma-separated) and proceed with findings from the remaining lenses.

5. Collect all findings from the completed lenses, keeping track of each finding's originating lens `id`.

## NEXT

Read fully and follow `./step-03-triage.md`

Codex override: unavailable independent lenses are reported as incomplete in the response. Never write child prompts or ask for filesystem transfers; the coordinator handles any needed independent delegation.
