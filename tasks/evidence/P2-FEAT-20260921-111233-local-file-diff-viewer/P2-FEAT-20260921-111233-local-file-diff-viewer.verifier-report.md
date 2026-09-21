# Verifier Report: 本机只读文件与改动查看器（`just view`）

PASS

被复审对象：PRD `tasks/pending/P2-FEAT-20260921-111233-local-file-diff-viewer.md`、实现面 `scripts/shared/view/`、`justfile.shared`、`tests/guards/shared/test_view_server.py`、相关文档与原型登记。
复审机器与时刻：darwin 27.0.0，worktree `/Users/zata/code/zata_code_template/.iar-worktrees/issue-9`，load average 13–18（与执行器采集时同量级）。

---

## 复审覆盖

### 我亲手复现的（真实进程 + 真实 HTTP，不是读代码推断）

| 复审项 | 命令 / 手段 | 结果 |
|---|---|---|
| 守卫测试 18 项 | `uv run pytest tests/guards/shared/test_view_server.py -q` | `18 passed in 7.44s`（本次亲自跑，非引用执行器输出） |
| 路径逃逸（`..` / 绝对路径 / 符号链接 / `%2e%2e%2f` / 双重编码 / 反斜杠变体） | `curl` 打真实实例 `/api/file`、`/api/diff` | 全部 403 或 404，无仓库外内容返回；符号链接用仓库内真实存在的 `.venv/bin/python`（指向 `/Users/zata/.local/share/uv/...`，仓库外）与两跳相对链接 `.venv/bin/python3` 复测，均 403 |
| 静态资源路由逃逸 | `/assets/../server.py`、`/assets/%2e%2e%2fserver.py`、`/assets/index.html/../../server.py`、`/assets/`、`/assets//etc/hosts` | 全部 404（按文件名白名单匹配，无可拼接路径） |
| 写方法 | `POST` / `PUT` / `DELETE` / `PATCH` / `OPTIONS` / `TRACE` / `CONNECT` / `HEAD` 打 `/api/tree` | 全部 405，正文为「只读查看器只接受 GET 请求…」 |
| 源码级写入口断言 | `rg -n "do_POST\|do_PUT\|do_DELETE\|do_PATCH" scripts/shared/view/` | 无命中；服务端唯一入口是 `do_GET`（server.py:140） |
| 基线参数注入 | `base=--output=/tmp/pwned-viewer`、`-c`、`--exec=rm+-rf+/tmp`、`HEAD`、`main...HEAD`、`%00` | 全部 400 拒绝；`ls /tmp/pwned-viewer` → `No such file or directory`（**没有副作用文件产生**） |
| 白名单可否被污染 | `git check-ref-format --branch "--output=/tmp/x"` → `fatal: '--output=/tmp/x' is not a valid branch name`（exit 128） | git 本身禁止以 `-` 开头的分支名，`_build_change_revision_spec` 的白名单因此是闭合的 |
| 绑定地址 | `lsof -nP -iTCP:8791` → `TCP 127.0.0.1:8791 (LISTEN)`；非回环地址连接被拒 | 只绑回环 |
| 「查看不改变仓库」 | 6 类读取请求前后 `git status --porcelain \| shasum -a 256` | 前后指纹相同（`5657fe2b…`） |
| 正文与本地文件一致 | `/api/file?path=justfile.shared` vs 本地文件逐行比对 | 1525 行全等，首行 `# ────…` 一致（rv-1 复核） |
| 改动视图与终端一致 | `/api/changes?base=worktree` vs `git diff HEAD --name-only/--numstat/--shortstat` | 8 个文件集合一致、8 组 `+N -M` 逐项一致、合计一致；`/api/diff` 的 add/del 计数与终端一致 |
| 生命周期：复用 | 连续 20+ 次真实 `just view` | 进程号始终不变（94899），输出「复用既有实例」，未重启 |
| 生命周期：陈旧登记 | 手动把 `VIEW_PID` 写成已退出进程号 | 输出「登记项已陈旧…，重新起服务。」并起新实例，未打开死页面 |
| 生命周期：`--stop` | 正规回收路径 | 进程退出、端口不再监听、登记文件被删 |
| 生命周期：空闲回收 | `just view --no-reuse --no-open --idle-timeout 4` | 约 5 秒后进程退出、登记被清理、端口连接失败；日志有「查看器已闲置 5 秒（上限 4 秒），退出并清理登记。」 |
| 生命周期：`--idle-timeout 0` | 直接起 `server.py --idle-timeout 0` | 3.5 秒后仍存活且 `/api/info` 200 |
| 命令面 | `just view <路径>` / `--diff [基线]` / `just diff [基线]` / `--port` / `--no-reuse` / `--no-open` / `--stop` | 全部按 PRD §6 工作；`just diff main` → `?view=diff&base=main`；`--port 8791`（被占）→ 明确报错 |
| 前端有无轮询 | `rg -n "setInterval\|setTimeout\|requestAnimationFrame\|WebSocket\|EventSource\|\.poll\|heartbeat" scripts/shared/view/assets/` | 唯一命中是 `viewer.js:5` 的注释；`fetch` 只有一个调用点（viewer.js:51），仅由用户操作触发 |
| XSS（`innerHTML` 注入面） | 请求 `docs/prototypes/file-viewer-interactive.html`（含真实 `<script>`） | 渲染行中 `"<script"` 字面量出现 0 次，Pygments 已转义；前端唯一的服务器数据 HTML 汇点是 `viewer.js:700`，路径类文本一律走 `textContent` |
| rv-6 五处登记 | `rg -c …` | `prototype-registry.js:4`、`tooling.md:6`、`file-viewer.md:18`、`mkdocs.yml:1`、`prototypes/index.md:1`；`just --list` 同时列出 `view` / `diff` |
| shebang recipe 开销（justfile 注释里的理由） | 自建临时 justfile 对比同名 recipe | shebang recipe 中位数 **247.3ms**，普通单行 **29.8ms**——注释里「约 200ms」属实 |
| venv 缺失时的 `uv run --no-sync python` 兜底 | 在临时工程（无 `.venv`）里实跑同一命令 | uv 自建环境并成功执行（`FALLBACK OK /private/tmp/.viewverify-scratch/.venv/bin/python 3.14.7`），兜底路径**可用**（详见 NON-BLOCKING N-3 的限定） |
| 复用命中耗时 | `perf_counter` 包住真实 `just view` / `just view --no-open` | 见 NON-BLOCKING N-3，结论：安静时中位 119.9–136.7ms，噪声/负载下常超 150ms |

### 我只读了代码、没有独立复现的（明确区分）

- `instance.py:199-221` `clear_instance_record(expected_process_id=…)` 的归属校验：逻辑正确（先读登记比对 pid 再 unlink），守卫测试 `test_registry_clear_never_removes_another_instances_record` 覆盖；我**没有**构造并发场景实测。
- 浏览器侧真实交互（键盘快捷键、过滤、目录折叠、服务退出态的切换渲染）：只读 `viewer.js`，没有驱动真实浏览器。`enterDisconnectedState` / `guardAgainstServiceExit`（viewer.js:60-131）逻辑正确，但 UI 实际观感属于我未验证的部分。
- `just lint` / `just test` / `uv run mkdocs build`：不在我的命令范围内，未复跑。
- `.venv` 被删除时的兜底路径**in situ**：我未删除本 worktree 的 `.venv`（会破坏环境），只做了等价工程的模拟，故兜底为「模拟验证，非现场验证」。
- 证据截图（rv-1/rv-2 PNG）的像素内容：我只比对了接口与本地文件的逐行一致性，没有逐像素核对截图。

---

## BLOCKER

**无。**

工作区保留的候选（`%00` 未捕获异常、`--no-reuse` 孤儿实例、证据期望值漂移）都已逐条复核：它们都没有推翻 Part A 锁定的两条决策，也没有产生越权读写；定性为 SECURITY 与 NON-BLOCKING，不触发重跑。

---

## SECURITY

### S-1 `path` 参数含 NUL 字节时抛未捕获异常，连接被丢弃并在日志写入 traceback

- **证据（我复现的）**：
  - `curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8791/api/file?path=justfile.shared%00.txt"` → `000`（无任何 HTTP 应答）
  - `curl "http://127.0.0.1:8791/api/diff?path=..%00&base=worktree"` → `000`
  - `logs/view-viewer.log` 中留有完整 traceback，末行为：
    `File "scripts/shared/view/workspace.py", line 133, in resolve_repository_path` → `ValueError: lstat: embedded null character in path`
- **定位**：`workspace.py:132-135` 只 `except OSError`；`Path.resolve()`（CPython 3.13 的 `pathlib._local` 走 `os.path.realpath`）对 NUL 抛的是 `ValueError`。异常穿越 `server.py:144-146`（只捕 `WorkspaceReadError`）后由 `socketserver` 打印到 stderr、连接被直接关闭。
- **边界判定（重要）**：这**不是**越权——没有返回仓库外内容，没有写操作，服务在异常后继续正常服务（后续请求均 200）；且该函数对 NUL 的处理结果本来就是「拒绝」。它违反的是函数自己写下的契约（`workspace.py:125` 「解析失败时为 None」）与「越界一律拒绝」的应答形态：现在是「无应答 + 日志 traceback」。
- **可达性**：服务只绑回环，触发者只能是本机进程或用户浏览器里的页面（跨源 `fetch` 无法读取应答，但请求确实会落到服务）。影响局限于单次连接被丢弃与日志噪音，不构成可用性打击。
- **建议**：`except (OSError, ValueError)` 一行即可，并在 `tests/guards/shared/test_view_server.py` 补一条 NUL 用例。建议随本次提交一并修掉。

---

## NON-BLOCKING

### N-1 证据/PRD 的「逐项期望值」在采集之后被工作树变化漂移

- **证据（我复现的）**：交付物时间线——证据工件 `tasks/evidence/…/rv-*.{png,txt}` 全部落在 13:41:46（`.iar/evidence/` 里的原件为 13:32:12–13:38:30），而 `tasks/pending/P2-FEAT-20260921-111233-local-file-diff-viewer.md` 的 mtime 是 **13:46:25**。
- 于是当前树与证据里的数字不一致：
  - 现测 `git diff HEAD --shortstat` = `8 files changed, 174 insertions(+), 17 deletions(-)`；证据与 PRD §9.1 写的是 `8 files changed, 93 insertions(+), 11 deletions(-)`。差异全部来自 PRD 自身的 `+111 -16`（采集时是 `+30 -10`）。
  - 现测界面文件树 `count = 743`；证据与 PRD §9.1 写的是 `741 个文件`。
- **不推翻 oracle**：rv-2 判的是「界面与终端逐项一致」，这个不变式**我独立复跑后仍然成立**（8 文件集合、8 组 `+N -M`、合计均与终端一致）。工件自身也是同一时刻的截图 + 终端输出，内部自洽。
- **代价**：人审按 §9.1 的期望值复跑时会看到对不上的数字（743 vs 741、+174 -17 vs +93 -11），第一眼像是实现坏了。
- **建议**：PRD 文本冻结后重跑 `rv1_file_view.sh` / `rv2_diff_view.sh`，或把期望值标注为「采集时刻快照」。注意本报告自身也会让文件树计数 +1（新增的未跟踪 `.md`），这类计数不适合写成硬期望值。

### N-2 `--no-reuse` 与 launch 侧登记清理会留下未被登记的活实例

- **证据（我复现的）**：清理现场时同时存在三个服务进程：`94899`（8791，最早起）、`419`（54877）、`3233`（55805）；`just view --stop` 只回收了登记里的 `3233`，另外两个只能由我手工 `kill` 收掉。`--no-reuse` 会直接覆盖登记，把上一个活实例变成「无人登记的常驻进程」。
- **叠加的竞态（代码读取，未复现）**：`launch.py:119` 的 `instance.clear_instance_record(repository_root)` **没有**传 `expected_process_id`。当登记陈旧且两个 `just view` 并发时，后到者可能删掉先到者刚写入的新登记，留下一个 `--stop` 够不着的活实例。服务端侧同一 API 是带归属校验的（`server.py:282-285`），`instance.py:199-221` 也已支持该参数——只有这一个调用点漏了。
- **影响有界**：漏掉的实例仍会被 30 分钟空闲回收兜住，不是永久孤儿；但它与 FR-5「不会留下孤儿进程」的表述存在张力。
- **建议**：`launch.py:119` 传入 `expected_process_id=remembered_instance.process_id`；并在 `docs/guides/file-viewer.md` 的 `--no-reuse` 一栏写明「旧实例需自行 `--stop`（或等空闲回收）」。

### N-3 150ms 复用预算：证据薄，且在本机负载下我未能稳定复现

- **执行器结论**：真实 `just view` 中位 142.9ms（n=5，最大 268.7）、`--no-open` 中位 121.4ms（n=8），按中位数判 PASS。方法（`perf_counter` 包住真实 `just` 子进程、记录极值、负控注入 300ms 延迟后判 FAIL）**本身是站得住的**，负控也确实有判别力。真正的问题是样本量与判定统计量的选择：n=5 配中位数，且极值已达预算的 179%。
- **我的复测**（同机、load 13–18）：
  - 安静批次：`just view --no-open` 中位 **119.9ms**、p90 128.5、最大 158.4，超预算 1/15；把 `open` 用 PATH 影子换成 `/usr/bin/true` 后 `just view` 中位 **136.7ms**、超预算 4/15。
  - 连开浏览器标签的批次：`just view` 中位 **186.4 / 333.1ms**（两批）、超预算 12/15 与 11/15；同批 `--no-open` 中位也涨到 250ms。
  - 分解：`.venv/bin/python` 启动 + `just` 自身约 50–70ms，`launch.py` 内部（`--no-open`）约 48ms，浏览器交接（`Popen(["open", …])`）实测 3–9ms。
- **结论**：进程侧确实能进 150ms，但**几乎没有余量**；PRD 的措辞是「从敲命令到浏览器开始加载」，按真实入口计，我在本机负载下多次超过预算。「预算达成」应表述为「安静环境下按中位数达成，p90 贴近上限，负载下不成立」，而不是无条件的 PASS。
- **justfile 兜底路径**：`justfile.shared:245-248` 用 `path_exists(_view_python)` 在 `.venv/bin/python` 不存在时退回 `uv run --no-sync python`。我在临时工程（有 `pyproject.toml`、无 `.venv`）里实跑了同一命令：uv 自建环境并成功执行，**兜底可用**（模拟验证）。两点限定：(1) 我**没有**删除本 worktree 的 `.venv`，故不是现场验证；(2) `--no-sync` 不安装依赖，兜底环境里大概率没有 pygments，会走降级纯文本（PRD 明确接受），且该路径比直连解释器多 20–40ms——这些在文档里未写明。

### N-4 `just view --diff <路径>` 的静默回退

- **证据（我复现的）**：`just view --diff justfile.shared --no-open` → URL 为 `?view=diff&base=justfile.shared`；`/api/changes?base=justfile.shared` → `HTTP 400`；`viewer.js:185-201` 的 `renderBaselineOptions` 检测到取值不在下拉选项中就回落到 `worktree`，因此界面不会报错，只是基线选择器显示「工作区改动」。
- 执行器已在证据报告 §11 披露。属安全回退、非静默错误，但用户没有任何提示——列在这里是为了让它别在归档时丢失。

### N-5 文档细节

- `docs/guides/file-viewer.md:18`：`just view --port <端口>` 一行写「默认优先 8791，被占用则退回系统空闲端口」，漏掉了实际优先级里的「登记值」（`launch.py:274-298` 的顺序是：显式 `--port` → 登记值 → 8791 → 系统随机）。同页 101 行又说「端口实际值只写在 `.env.view-state` 里，不在任何文档里硬编码」——两句放一起略刺眼（8791 是默认值而非实际值，严格说不矛盾）。
- `docs/guides/file-viewer.md:55-57` 关于「页面不做心跳、服务退出后给提示」的描述与实现一致；浏览器冷启动不在承诺内这一点在 68-70 行**明确写了**（FR-10 要求满足）。

### N-6 非读取方法的 405 不读请求体、也不关连接（HTTP 细节）

- **证据（我复现的）**：`curl -X POST -d 'x=1' http://127.0.0.1:8791/api/file` → 405；紧接着 `logs/view-viewer.log` 出现 `code 400, message Bad request syntax ('x=1')`——405 应答没有消费请求体，在 keep-alive 连接上残留的 body 被当成下一条请求行。
- 只读边界不受影响，仅影响 HTTP 语义正确性与日志噪音（`_refuse_non_read_method` 可加 `Connection: close` 或排空 body）。`HEAD` 也被 405 拒绝（服务只实现了 GET），对 `curl -I` 一类习惯动作不友好，属可接受的取舍。

---

## 裁定理由

- **两条锁定决策都成立，且是我亲手推翻失败后才确认的。**
  - 决策一（生命周期）：复用命中时进程号 20+ 次不变；`--stop` 真正释放端口并清登记；`--idle-timeout 4` 端到端走到「进程退出 + 清登记 + 端口关闭」；`--idle-timeout 0` 确实关闭自动回收；`viewer.js` 里没有任何 `setInterval` / `setTimeout` / WebSocket / EventSource / 轮询式 `fetch`，唯一 `fetch` 由用户操作触发——「页面不轮询」这个前提没有被实现悄悄破坏，空闲回收不会静默失效。陈旧登记（死 pid）实测被接管并重起，不会打开死页面。
  - 决策二（只读边界）：`..`、绝对路径、单跳与两跳符号链接、URL 编码与双重编码、超长 `..`、静态资源路由拼接全部无法越出仓库；写方法一律 405，源码里不存在任何 `do_POST/do_PUT/do_DELETE/do_PATCH` 名字，`__getattr__` 的写法让「不存在写入口」这一事实可被静态断言；`base=` 的 `-` 开头取值进不了 git 命令行，且 `git check-ref-format` 证实分支名不可能以 `-` 开头，白名单闭合且无副作用文件产生；读取前后工作区指纹不变。
- **除了 S-1 与 N-1…N-6，没有发现其他偏离**：生命周期只有一份实现（`scripts/shared/view/` 之外无第二处 `.env.view-state` / `idle-timeout` 逻辑）；未触碰 `src/backend/`、`frontend-admin/`、`frontend-public/`；不依赖、也不复刻 `skills/git-diff-report/`；`pygments` 已在 `pyproject.toml` dev 组显式声明且缺失时降级；终端 TUI 依赖无回流；`.env.view-state` 被 `.gitignore` 的 `.env*` 覆盖。
- **证据绑定**：执行器声称 rv-1/rv-2 在 `justfile.shared` 最后一次改动之后重收。时间戳表面上不成立（rv-1 截图 13:38:12 < `justfile.shared` mtime 13:38:24），但那是 rv-2 的 fresh-state probe 追加一行后用 `cp` 还原造成的 mtime 触碰（`.iar/evidence/scripts/rv2_diff_view.sh:74-78`），内容逐字节还原；旁证是 `justfile.shared` 的 `--numstat` 在采集时与现在都是 `26 0`，且我复跑接口得到的正文与本地文件 1525 行全等。因此**生产代码的绑定关系我判定成立**（属推断，无留存哈希）。真正未绑定的只是 N-1 里那份 PRD 文本编辑造成的数字漂移。
- **S-1 不构成 BLOCKER**：它没有越权、没有写入、服务不中断，只是把一种畸形输入从「拒绝应答」变成了「丢弃连接 + 日志 traceback」；两条锁定决策与全部验收不变式均未被突破。N-1…N-6 都是可在一处小改或一句文档说明内收敛的披露项。因此裁定 **PASS**，并把 S-1 与 N-2 列为提交前值得顺手一并处理的两条。

**收尾**：本次复审期间我启动的全部查看器进程已收掉（`just view --stop` 回收登记中的实例，其余手工 `kill`），`pgrep -f scripts/shared/view/server.py` 无命中，`lsof -iTCP:8791` 无监听，`.env.view-state` 不存在，worktree 的 `git status` 与复审开始前一致，`/tmp` 下的临时工件已删除。
