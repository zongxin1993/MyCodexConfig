# MyCodexConfig

为 Codex CLI / Desktop 准备的独立工程工作流：**需求澄清 → 明确计划与验收 → worktree 实施和测试 → 独立审计 → 修复复验**。

它复用了 MyOpenCodeConfig 的质量规程思路，并改成 Codex 原生工具、会话与配置。不会配置云端/本地模型路由，不覆盖你的模型、provider、推理档位、RTK hook 或 OpenCode 配置。模型由当前 Codex 会话决定。

## 提供什么

| 部件 | 作用 |
| --- | --- |
| `codex-workflow` | 阶段提示、确认边界、工作树隔离、独立审计与修复闭环 |
| `codex-quality-planning` | 需求编号、验收案例、负向/边界条件、模块与依赖约束、独立计划复核 |
| `codex-execution` | 原生搜索、必要时结构搜索、仓库原生测试、真实证据保留 |
| `codex-quality-review` | 核对需求实现、结构、测试有效性；报告严重性、影响范围、紧迫性与修复价值 |
| `codex-ast-grep` | 对已定位的明确源码文件做语法结构搜索 |
| `codex-rust-workflow` | Rust 工具链/Cargo 矩阵、编译与 Clippy、行为测试及独立审计闭环 |
| `codex-rust-diagnostics` | 针对实际 Rust 所有权、错误传播和并发诊断按需读取参考资料 |
| `quality` MCP | 独立项目登记、固定公开 schema/BMAD 资源、可移植质量门禁；不执行任意 shell |
| Context7 MCP | 查询第三方库官方文档；使用 Codex 自己的 OAuth 授权 |

GrillMe、Superpowers 与 RTK 可按需配合。安装器不捆绑或安装这些外部插件：已有 GrillMe/grilling、brainstorming、writing-plans 等技能时按需使用；没有时也能按本包的澄清/计划规程执行。RTK 优先保留现有配置，测试结论仍以原始日志为准。Serena、浏览器 MCP、Quota、Plannotator、记忆和 DCP 均未随此包接入。

## 从零开始

需要 Python **3.11+**、Git 和已经安装并登录的 Codex。先确认实际环境：

```sh
python3 --version
codex --version
codex login status
```

克隆后安装：

```sh
git clone git@github.com:zongxin1993/MyCodexConfig.git
cd MyCodexConfig
python3 install.py
```

如果 `python3` 低于 3.11，请改用本机实际安装的 `python3.12` 等新版本执行。安装器把当次 Python 的绝对路径写入 MCP 启动命令，之后需要保留这个 Python。

安装会先备份需要改动的文件，然后：

- 在 `~/.codex/config.toml` 追加有边界标记的 `quality` / `context7` MCP 配置。
- 在 `~/.codex/AGENTS.md` 追加工作流入口，保留已有内容。
- 安装七个 `codex-*` skill 到 `~/.codex/skills/`。
- 将运行文件放入 `~/.local/share/mycodexconfig/releases/<摘要>/`；项目登记独立保存在 `~/.config/mycodexconfig/settings.json`。
- 仅在 Codex 的技能发现配置中禁用已知 OpenCode 专用同类适配器，避免调用不存在的工具；不编辑共享技能或 OpenCode。

已有同名非本包 MCP / skill 会导致安装拒绝，先由你决定如何协调，不会静默覆盖。修改过的已安装 release、符号链接目标及无效 TOML 也会被拒绝。重复安装无差异时返回 `UNCHANGED`；仅运行目录丢失时可重建。

Context7 首次需要单独授权：

```sh
codex mcp login context7
codex mcp list
```

按终端中的 OAuth 地址完成登录。它不复用 OpenCode 的凭据；服务配额和可用性由 Context7 账户决定。如暂时不用它，安装时加 `--without-context7`。

安装后在 **新 Codex 会话**中使用。已经运行的会话可能持有旧的工具/技能列表；不要为此重启正在工作的任务。Desktop 对用户级配置和 MCP 的加载以实际版本为准，可从新会话调用 `quality_info` 核验。

### 可选结构搜索

已安装 `ast-grep` 时，将真实可执行文件路径传给安装器：

```sh
python3 install.py --ast-grep /absolute/path/to/ast-grep
```

该文件会复制到本包独立 release；仓库不上传机器专用二进制。未传时辅助工具从 PATH 查找 `ast-grep`。缺失会明确报错，不会在业务仓库内自动安装依赖。

## 日常如何使用

直接提出需求，例如：

> 为这个工程增加导入数据校验。先确认需求和异常行为，再给计划及验收标准；确认后在 worktree 实施，独立审计，有问题修复复验。

每阶段应显示 `[需求澄清｜进行中]`、`[计划｜待确认]`、`[实施｜进行中]`、`[审计｜BLOCKED/PASS]`、`[修复复验｜进行中]` 等状态，列出实际工作目录、执行者标识（可取得时）、验证结果和缺失证据。简单问答不强制走完整流程。

新工程通过 `quality_onboard` 自动登记到本包私有 registry。默认采用**仓库原生规程**：读取工程自己的 AGENTS、规范、计划和验证命令，不为它杜撰通用 PASS，不改工程规程。登记不授予目录访问权限。需要定制可移植 JSON 门禁时，参考 `schemas/`、`examples/` 和对应测试，并明确配置验证策略。

独立审计必须使用独立上下文；当前平台不能创建独立评审者时，应报告未完成，不能把自审当独立审计。原实施会话可以恢复时把问题交还原会话；无法恢复则明确交接给新执行者，携带实际基线、计划、问题编号和证据，避免因丢失 sessionID 停滞。

## 审计结论怎么读

每个问题包含位置、触发条件、预期/实际行为、P0–P3、影响范围、可信度、修复紧迫性、成本和回归风险。风险/修复价值数字是本工作流的排序启发式，**不是 CVSS 或第三方认证**。缺失的测试环境、评审视角和运行证据必须单独列出。

BMAD 使用固定提交的 v7 preview 审查资源，包含 quick/thorough 两组视角，已修改 host 指令以适应 Codex 只读审计。调用部分资源不等于完成完整 BMAD 审计；缺失独立 lens 必须报告 incomplete。来源、修改说明和哈希见 `resources/bmad/provenance.json` 及各 manifest，MIT 许可证随附。

## 隔离、安全与回滚

worktree 是工作流要求；文件是否真正可写由 Codex 宿主沙箱决定。本包不能给目录提权，也不能仅靠提示词建立操作系统级访问控制。主工程只读、实施工作树可写需要与实际宿主权限匹配。现有未提交修改必须保留，必要时取得经过授权的只读源码快照。取消的 worktree 请求不得绕过。

安装输出包含本次备份目录，用它回滚：

```sh
python3 install.py --rollback /absolute/path/to/.codex/backups/mycodexconfig/<本次备份>
```

回滚先核对当前文件与安装后摘要；有用户后续改动则拒绝，避免覆盖新设置。保留 release 目录供恢复，不删除现有任务、凭据、共享技能或 OpenCode 数据。OAuth 凭据由 Codex 管理，不在本包备份和发布范围内。

## 验证

```sh
python3 -m unittest discover -s tests -v
```

真实会话验证脚本：

```sh
python3 scripts/validate_native.py --home /absolute/path/to/private-staging-home --fixture /absolute/path/to/new-private-fixture
```

先在 staging home 建立独立 Codex 配置并安装本包，使用你授权的 Codex 登录；不要把 staging 凭据或原始会话日志提交到 Git。脚本会产生真实模型请求，固定为 `low` 推理档，只在一次性 fixture 中模拟需求/计划批准，并故意植入缺陷验证审计和同会话修复闭环。测试中禁用 Context7，文档查询另行验证。详见 `docs/validation/2026-11-19.md`。

这套配置能加强规程和证据约束，不能保证每次任务无缺陷。CLI 的真实流程通过不代表已经逐屏验证 Desktop 交互，也不代表所有语言和大型项目均已验收。

## Rust 工程如何使用

直接提出 Rust 需求即可，`codex-execution` 和审计入口会转到 `codex-rust-workflow`，按需读取 Cargo 与 Rust 审查参考；实际编译诊断继续用 `codex-rust-diagnostics`。先识别仓库的 toolchain、edition、MSRV、features、targets 和原生验证入口，再选择编译、Clippy、单元/集成/文档测试及必要的 release 测试。不会自动升级 Rust、依赖或强加 `--all-features`。

新机器另需 Rust/Cargo，以及仓库要求的 Clippy、rustfmt；本包安装器不安装或修改工具链。缺工具会报告缺失环境。普通检查不能替代 MSRV、其他平台、并发恢复或 unsafe 专项证明。

无依赖小工程示例在 `examples/rust-reservation/`。本机或 CI 原生验证：

```sh
python3 scripts/check_rust_fixture.py --root examples/rust-reservation --evidence /absolute/path/to/new-private-evidence
```

真实 low 会话闭环（需要独立 staging home 已安装本包、经授权的 Codex 登录，以及 PATH 中的 codex/cargo/rustc/clippy/rustfmt）：

```sh
python3 scripts/validate_rust_native.py --home /absolute/path/to/private-staging-home --fixture /absolute/path/to/new-private-rust-fixture
```

脚本验证编译/Clippy 负向控制、需求澄清、计划、隔离实施、独立审计、原会话修复和复审；模型请求固定 `low`，不修改用户默认档位。审计结论须以独立消息的精确终行返回；完整日志及源码摘要留在私有目录，禁止上传凭据或原始会话。CI 只运行原生 Cargo/Python 验证，不运行需要账户的模型会话。

Rust 真实会话 harness 拒绝活动 Codex home 及共享认证文件链接，使用 staging 文件认证并剥离继承的 `OPENAI_API_KEY` / `CODEX_API_KEY`。使用自定义 provider 的其他认证环境或外部凭据代理时，须先单独隔离；该脚本不提供任意 provider 的凭据隔离保证。

本轮 Rust 的真实执行、负向控制及适配审计记录见 [Rust 验收记录](docs/validation/2026-11-19-rust.md)。
