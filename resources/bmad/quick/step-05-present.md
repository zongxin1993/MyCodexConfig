# Step 5: Return findings (Codex read-only adapter)

The reviewer returns a response and never writes source, plans, triage files, reports or deferred-work files. Do not change ticket status or claim checks were run. Only the coordinator may persist an approved report using repository-authorized artifacts.

Return a summary with counts of decision-needed, patch, defer and rejected findings. Zero findings is valid. List findings highest severity first within each route. Include stable ID, source location, actual trigger, expected/actual behavior, evidence, severity, impact scope, urgency, confidence, repair value, cost and regression risk. Decisions remain open unless explicitly approved. Defer only with the governing policy's required human acceptance; do not downgrade a blocker to obtain PASS. Include rejected findings and refutation, plus every missing lens and unverified check.

Give a repair handoff in the response: full baseline and reviewed SHA (or uncommitted source state), finding IDs, touched symbols, required outcome, and checks needed. Do not prescribe unrelated refactors. Return the original report and schema-valid JSON where the host contract requires it. A native repository's own authority takes precedence; do not invent portable acceptance artifacts.

The terminal verdict is PASS, BLOCKED or NEEDS_EVIDENCE according to verified scope, never inferred from a model's earlier summary. Return to the coordinator without edits or nested delegation.
