---
name: codex-ast-grep
description: "Use syntax-aware ast-grep searches over explicit current Codex worktree files; ordinary text lookup stays with native rg/read."
---
Managed-By: MyCodexConfig

# Structural search

Select actual language and already-located files. Run `python3 @RUNTIME@/tools.py ast --root <worktree> --language <language> --pattern '<pattern>' -- <relative-files>` using native shell permissions. The helper requires an available ast-grep binary; an explicit verified absolute `--bin` can be supplied. Do not install dependencies into the task repository. Never call OpenCode execution_ast_search.

Use $NAME for a captured syntax node and $$$BODY for an allowed variable sequence. Validate against a known example. Wrong grammar or qualification can cause zero matches; read source and adjust once before concluding. This is syntax search, not a semantic call graph. Limited output is incomplete. No rewrite/fix mode or project-wide uncontrolled crawling. If the binary is unavailable, state that and use native rg/read.
