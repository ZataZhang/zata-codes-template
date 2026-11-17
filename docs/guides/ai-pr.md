# 对话中的 PR 交付

在当前 Agent 对话里说「帮我提 PR」，涉及实现时先在独立 worktree 中改动，再整理本次需求并调用 `just ai pr`
创建或复用 Issue/PR。命令默认检测合并条件；实际验收已通过且仓库允许时合并。若从隔离 worktree 运行，
合并后保留该 worktree 和工作分支，不切换或更新主 worktree。
交付脚本不调用第二个模型、不猜测当前会话、不自动改代码，也不绕过分支保护。

## 当前 Agent 的操作约定

1. 先读当前仓库规范并确认本次交付范围。包含实现的任务先创建专用 worktree，再开始代码或文档修改；
   用户只要求发布已有改动时，也不得为了提 PR 切换或覆盖当前工作区。用户授权提 PR 时包含这次范围内的暂存、提交、推送、
   创建 Issue/PR 与按默认策略合并；用户说「仅建 PR」或「合并前让我看」时覆盖默认策略。
2. 从当前对话选取相关用户原话，**逐字保留**初始要求、补充和纠正，另写 AI 整理的独立任务说明。
   「好，帮我修」必须带上它所确认的前文背景。AI 建议属于整理部分，不冒充用户原话。
3. 记录真实入口验证的结果与限制。未做真实验证用 `pending`，发现仍不满足需求用 `failed`；
   `validation.status=passed` 只表示调用方报告的真实入口验证完成，不代表 CI 或人工验收通过。
   没有可执行行为变化时，在 details 写明文档/配置检查及不适用原因。
4. 按下方格式准备 UTF-8 JSON。建议放在 `git rev-parse --git-path ai-pr-context.json` 指向的
   Git 元数据目录，避免把上下文本身作为未跟踪文件或提交内容。
5. 调用命令并报告 Issue/PR 链接、真实验收状态、是否已合并、当前分支及停止原因。
   不把「PR 已创建」「GitHub 检查通过」「已合并」表述成「用户问题已解决」。

## 隔离工作区

实现 PR 改动时，应在开始修改前创建独立 worktree。不要先在主 worktree 改完代码，再靠切换分支来隔离。
在当前仓库里，优先从 Git primary worktree 创建：

```bash
just worktree ai-pr-example --new --base main enter_shell=false
```

把分支名和 `--base` 替换成唯一任务名和仓库默认分支。记录命令输出的 worktree 路径；后续读取、编辑、验证和
`just ai pr` 都要以该路径作为工作目录。`just worktree`
会准备本仓库所需的本地环境、端口和专用数据库。交付脚本从非 primary worktree 合并 PR 后会留在该工作分支，
只刷新远端默认分支引用，不切换或 fast-forward 用户的 primary worktree，也不自动删除 worktree 或分支。

如果改动已经存在于 primary worktree，不要运行 `git stash`、`reset` 或直接切换分支。先创建隔离 worktree，
只把本次 `files` 范围内的已有差异和未跟踪文件复制过去；原工作区内容保留。若工作区包含必须继承的本地提交，
以当前 `HEAD` 作为新 worktree 的起点，避免从远端默认分支创建后遗漏这些提交。

没有 `just` 时，可用原生 Git 建立 worktree。先把下面的示例值替换成当前仓库匹配 GitHub 的 remote、默认分支和唯一任务标识：

```bash
repo_root="$(git rev-parse --show-toplevel)"
repo_parent="$(dirname "$repo_root")"
repo_name="$(basename "$repo_root")"
remote_name="zata" # 替换成实际 remote；不要假定名称一定是 origin
default_branch="main" # 替换成 GitHub 仓库默认分支
branch_name="ai-pr-example"
worktree_dir_name="ai-pr-example"
worktree_path="$repo_parent/${repo_name}-worktrees/$worktree_dir_name"

git fetch "$remote_name" "$default_branch"
git worktree add -b "$branch_name" "$worktree_path" "$remote_name/$default_branch"
```

之后让所有工作命令都以 `$worktree_path` 为工作目录。原生 `git worktree add` 不会复制 `.env`、安装依赖、分配端口
或准备隔离数据库；按项目文档手工完成这些步骤，尤其要确认验证不会连接主 worktree 共用的可写数据库。
如果要保留 primary worktree 中尚未提交的改动，基于远端默认分支创建后不会自动带入，须只复制已确认的交付范围。

上述 Git 命令只替代 worktree 创建，不替代 `just ai pr` 的自动交付。当前交付脚本无论通过 `just ai pr` 还是直接运行
Python 文件，都会调用 `just test`；完全没有 `just` 的仓库应使用该项目自己的验证入口，并按本指南的 GitHub、验证轴和合并条件
手动完成发布，不得把直接运行 Python 脚本当成绕过测试依赖的方式。

发布前由当前 Agent 检查原话和证据是否包含密钥、个人信息或不应公开的业务内容。必要脱敏须明确标注，
不能把脱敏或 AI 改写后的内容声称为逐字原文。不要把完整会话、环境变量或凭据文件直接发布。

## 命令与上下文

自动交付需要 Python 3.9+、Git、just，以及已登录且支持以下 JSON 字段和 `--match-head-commit` 的 GitHub CLI
（开发时以 gh 2.92.0 的本机帮助及真实只读响应核对）。
退出码 0 表示已发布或明确停留待审/待验证，不承诺已合并；退出码 1 表示交付失败。以输出和实际 PR 状态为准。

```bash
just ai pr /path/to/context.json
just ai pr /path/to/context.json only       # 只发布，不合并
just ai pr /path/to/context.json confirm    # 满足合并条件后，终端明确确认
just ai pr /path/to/context.json auto 300   # 等待检查最多 300 秒，默认 180 秒
```

`confirm` 在没有交互终端时保留 PR，不挂起等待输入。对话中确认后，Agent 可针对同一上下文再次用
`auto` 调用；命令会重新检查当前提交、审查与检查状态。`only` 不会要求已经 passed 的 PR 保持 Draft。

上下文示例（`files` 必须逐个列出本次交付范围内的文件；首次交付包含分支相对目标分支的已提交差异，
后续轮次只需列出上次已发布 head 之后的新提交与当前工作区改动。重命名列旧路径和新路径。仅更新已发布
代码的验证状态时可以传空数组）：

```json
{
  "schema_version": 1,
  "title": "fix(cli): preserve AI failure status",
  "request_source": "conversation",
  "user_messages": ["好你先帮我修吧", "仅修复这次讨论的失败状态和参数传递问题"],
  "task": "AI 整理：修复 AI 调用失败后仍执行 Git 操作的问题，并安全传递提示词。前文背景另在此补全。",
  "summary": "Preserve CLI errors and safely pass prompt arguments.",
  "iteration_summary": "首次交付，真实入口仍待验证。",
  "commit_message": "fix(cli): preserve AI failure status",
  "files": ["scripts/shared/just/ai_run.sh", "justfile.shared"],
  "validation": {
    "status": "pending",
    "details": "Local tests passed; the real user workflow still needs validation."
  }
}
```

示例原话仅用于说明格式，实际运行必须替换为真实对话内容。可选 `issue: 123` 复用目标仓库中的 Issue。
已有 PR 只有一个关联 Issue 时可自动复用；多个关联 Issue 时须由当前 Agent 明确指定。
新建 Issue 不加 `agent/ready` 标签，不另外触发 KedaCode runner 排队执行。
`request_source` 为 `conversation` 表示当前对话可见的原话；事后由人补充的需求用 `retrospective`，
其时间是整理时间，不冒充开工前快照。`task` 是 AI 整理的需求与验收要求，不能从最终代码反写答案。

`summary` 保留整个 PR 的最新改动概况；`iteration_summary` 只写本轮新增变化、反馈或结论，
不要每次重复完整功能清单。没有提供本轮说明时，新增代码用提交标题概述，同一 head 的调用标明
「无新代码提交，仅更新验证观察」。完整上下文与长证据仍放在评论的折叠 JSON 区。

## 四条独立验证轴

评论标题统一为 `Delivery update`，不再使用可能混淆范围的总体 `passed`。PR 正文与评论共用状态表：

| 验证轴 | 来源 | 含义 |
|---|---|---|
| Local checks | 程序执行 | `just test` 返回 0；不能代替 CI 或人工验收 |
| GitHub CI | GitHub 实时返回 | 仅记录与本轮 head 一致的检查结果；未读到检查为 `not_observed`，缺字段或 head 不符为 `unknown` |
| Real-entry validation (agent report) | `validation` 输入 | 当前 Agent 提供的真实入口验证及范围限制 |
| Human acceptance | 可选 `human_validation` 输入 | 仅记录明确的人工验收；未提供时为 `not_requested`，绝不由测试或合并推导 |

需要人工验收时可提供 `"human_validation": {"status": "pending", "details": "等待用户验证实际流程"}`。
可用状态为 `not_requested` / `pending` / `passed` / `failed`；填写 `passed` 时，details 必须说明
真实用户确认的原话或证据、时间与对应版本，不能由 Agent 自行把自动化结果当作人工通过。
默认不要求人工验收，因此保持自动交付；显式要求人工验收且尚未完成或失败时，保留 Draft 并阻止自动合并。

发布后，在本次命令等待结束时再读取一次 CI。若状态有变化，追加一条同 head 的观察并刷新 PR 状态表，
不重复整份功能清单，也不称为新提交。命令退出后不是后台监控，后续变化须下次调用重新观察。
没有读到 CI 检查不等于「CI 已通过」；是否允许合并仍由仓库规则与现有普通合并条件决定。

## Git 与合并行为

- 使用 `gh` 为当前仓库选择的 GitHub repository，要求本地唯一一个同仓库 remote。支持 remote 名称
  为 `origin`、`zata` 等，不硬编码。当前版本要求可向该仓库工作分支推送；不会自动创建 fork。
  推送地址按 Git 解析后的有效地址校验；`pushurl`、`pushInsteadOf` 或多推送地址不能把代码发往所选仓库之外。
  已有跨仓库 PR 或非默认目标分支的 PR 保留原状并报错，不擅自改换目标。
- 从隔离 worktree 的工作分支调用时沿用当前分支。兼容路径仍允许从默认分支创建 `ai/pr-<随机标识>`，
  但会在调用所在 worktree 切换分支；遵循本指南时不要用该路径操作 primary worktree。detached HEAD、冲突、
  未选中的暂存/未暂存/未跟踪文件会阻止交付。不会自动 stash、reset、amend 或强推。先隔离无关改动再调用。
- 提交时保留已暂存变更，只补充暂存未暂存改动与未跟踪文件；重试时已暂存的删除路径不会重复传给 `git add`。
- `just test` 必须实际返回成功才允许提交和推送；失败只保留现场，不自动扩大修复范围。
  用户提供的 `commit_message` 应遵守英文 Conventional Commits。
- `validation.status` 为 `pending` 或 `failed` 时创建/保留 Draft；已有 ready PR 会转回 Draft。
  后续 `passed` 调用可将同一 PR 标为 ready。平台/计划不支持转 Draft 时命令报错并保留现场。
- 发布成功后，每次调用向 Issue 和 PR 各追加一条简短的本轮变化与独立验证表，折叠区保存原始上下文、SHA、时间及证据，
  PR 正文的受管区只展示最新状态，受管区外的人写内容保持不变。Issue 原始正文不被后续结果覆盖。
- 默认检查 `viewerPermission`、`reviewDecision`、`mergeable`、`mergeStateStatus` 和检查汇总。
  仅 `CLEAN`、可合并、无需审批或已批准、检查完成且通过/明确跳过、远端 head 与本次 head 一致时，
  才尝试普通合并；GitHub 服务端规则仍是最终约束。缺字段、审批未满足、冲突、失败或超时均不绕过。
- 优先 merge commit 保留提交链；仓库不允许时依次用 squash、rebase。使用
  [`--match-head-commit`](https://cli.github.com/manual/gh_pr_merge) 绑定已验证提交；不传 `--admin`，
  也不启用无人值守的 `--auto`。合并队列只接受排队但尚未合并时，报告状态并留在工作分支。
- 仅确认 GitHub PR 状态为 `MERGED` 后才做本地分支收尾。从 primary worktree 调用时，快进更新本地默认分支；
  从隔离 worktree 调用时留在当前工作分支，只更新远端 tracking ref，不切换或改动 primary worktree。
  primary 路径遇到默认分支分叉、新改动或其他 worktree 占用时保留现场，绝不强制切换或覆盖。工作分支不自动删除。

首次发现问题通常不需要改仓库策略。不能自行合并的项目自然停在待审 PR；自己的项目能正常合并就自动收尾。
权限不代表验收完成，因此 `pending` / `failed` 即便在自己的仓库也不自动合并。

## 多轮修复与中断恢复

第一次提交后还要真实验证：先用 `pending` 发布 Draft。真实验证发现失败后，在同一分支继续修改，
再次调用时把新的用户反馈放入 `user_messages`，把实际失败表现和本轮验证写进 details。
这样仍是一条 Issue、一个 PR、多次提交和多条观察。最后验证通过，再用 `passed` 调用；即使没有新增
代码也能更新验收状态、尝试合并。保留中间提交，不为整理数据集改写开发历史。

如果**合并后才发现仍有问题**，在新的工作分支继续修复，显式提供原 `issue`（关闭的 Issue 会重开），
在 task/details 链接前一个 PR 并说明哪个结论被推翻。新建修复 PR，不能改写已合并 PR 的代码结果。
是否属于同一任务取决于需求是否变更：原要求未满足是同任务的新尝试，新需求则建新 Issue 并关联旧任务。

本机 Git common dir 的 `ai-pr/<分支哈希>/state.json` 保存 Issue/PR 与起点；`events.jsonl` 追加事件。
这不是长期数据仓库，不随项目提交；多个 worktree 共用状态位置。一次只在一个会话运行交付命令。
失败后先查看输出和现场，再在原分支重试；通常会复用已有 Issue/PR。评论每次调用都追加，重试也可能多
一条观察，后续按 head/context 整理去重，不以评论数量计 attempt。Issue 创建响应丢失或本机状态被清理时，
先查 GitHub 再用显式 `issue` 恢复，避免重复建任务。

## 验证边界

入口测试通过真实 `just ai pr`、真实临时 Git 工作区和裸远端运行；GitHub 网络使用传输替身，
临时项目的 `just test` 使用受控成功/失败命令，避免递归运行本仓库测试。本仓库代码另以 `just test` 验证。
CI 数据库矩阵显式安装 just 1.53.0，再运行相同入口测试；直接调用 pytest 的环境也必须提供该命令，不能静默跳过。
CI 的 `Validate Template` job 也会安装固定版本的 just，因为 AI PR 守卫用例会启动 `just` 子进程。
回归用例覆盖本地通过但 CI 失败、人工验收不被自动推导、同 head 状态更新、CI 结束后的追加观察和旧记录兼容。
覆盖多轮 Draft→失败→通过、审批/检查/权限阻塞、可选策略、head 变化、合并排队/失败、脏工作区等。
开发时对真实 GitHub 只进行了读取核对，没有在生产仓库创建测试 Issue/PR 或执行试验合并。
因此证据属于 **CLI integration（Git 真实、GitHub transport fake）**，不是 live GitHub 合并验证。

数据的长期整理、失败尝试与成功标签见[Agent 数据集构建](agent-dataset.md)。
