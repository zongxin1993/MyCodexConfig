# 来源与第三方内容

- `workflow/`、`schemas/` 和相关测试从本账户的 MyOpenCodeConfig 质量核心适配，新增 Codex 安装与原生工具工作流；未包含 OpenCode provider、私有 registry 或凭据。
- `resources/bmad/` 为 BMAD-METHOD 固定提交的渲染审查资源及 Codex host 修改。来源提交、适配说明、渲染摘要在 provenance/manifest；上游 MIT 许可证保留在该目录。并未接入整个 BMAD 安装器或声称完成其所有审查视角。
- Context7 是独立远程服务，使用其自身条款、账户与配额；仓库不保存其凭据。
- ast-grep 可选可执行文件由使用者本机提供，安装器仅复制到本机独立运行目录，Git 仓库不分发二进制。
- RTK、GrillMe、Superpowers、Codex 本身均不捆绑分发，也不在安装时变更它们的已有配置或凭据。
