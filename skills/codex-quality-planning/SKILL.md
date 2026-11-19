---
name: codex-quality-planning
description: "Use when planning a Codex development change: explicit requirements, acceptance criteria, architecture boundaries, independent plan review and repository-native quality rules."
---
Managed-By: MyCodexConfig

# Planning and acceptance

Use the quality MCP tools actually exposed by this host: quality_onboard(project=<actual absolute project directory>), then quality_info. Onboarding writes only the separate Codex registry/backup; it neither grants access nor approves work. Read the selected project's authorities before creating files. Never use OpenCode's settings or runtime CLI. If quality tools are absent, explicitly report that registration is unavailable; inspect repository rules with authorized native reads, keep planning in task context and do not invent a registry/gate response.

Repository-native mode: keep the repository's own plan/evidence locations and verification commands. Do not generate portable contracts, `.quality` artifacts, synthetic snapshot IDs or generic PASS. Use requirements IDs, acceptance examples and reviewer findings in the authorized task context. quality_prepare/quality_gate returning REPOSITORY_NATIVE_REQUIRED means use native gates, not retry with a fabricated contract.

Portable mode: read quality_resource(schema/contract), schema/policy and schema/review plus example/contract. The registered policy owns commands; never weaken it. The canonical JSON contract lives at docs/superpowers/specs/ or plans/. Each requirement maps to a task and observable AC with input, expected outcome and the source of that expectation. Address negative, boundary, recovery and concurrency cases relevant to the task. State module ownership, dependency direction, error semantics, migration, non-goals and real verification lanes. quality_prepare validates the current contract and snapshot; record actual user approvals before executing.

Use writing-plans/brainstorming if available and proportionate. Before implementation, an independent plan reviewer checks requirement completeness, feasibility and meaningful tests. Preserve exact approval scope; user-authorized execution of a concrete adaptation is not a reason to invent another mandatory approval. Unknown business requirements still require clarification.
