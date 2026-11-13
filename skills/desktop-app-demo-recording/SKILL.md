---
name: desktop-app-demo-recording
description: "[Created 2026-11-13] 在 macOS 宿主机上用 cua-driver 驱动桌面应用（以 WorkBuddy 为例）跑一批演示案例并录屏留存：每个案例离屏准备工作空间与样例数据 → 开录 → 粘贴提示词 → 轮询处理弹窗 → 核对产出 → 停录 → 头尾原速、中段快进剪成 1–2 分钟成片。重点是录屏安全（整屏录制不能露出私人文件、聊天、终端）和让录屏不中途断掉。Use when 用户要 给培训/课后资料录演示视频, 用 cua 录屏, 让 agent 操作 WorkBuddy/桌面 App 并录下来, 批量录制案例, 录屏留存。Not for 网页或容器内应用的录屏（用 Playwright 录制或 Xvfb + ffmpeg x11grab）、动画解说视频（faceless-explainer / hyperframes）。"
user-invocable: true
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
---

# Desktop App Demo Recording

## 适用范围

- **只在 macOS 宿主机上做**。cua-driver 在 macOS 上靠辅助功能接口操作应用、靠 ScreenCaptureKit 录屏；Docker 容器是 Linux，看不到 macOS 桌面，录不了桌面应用。容器里只能录容器内的东西（网页、Xvfb 里的 Linux 程序）。
- **会独占屏幕**：发送提示词、点弹窗都要把目标应用切到前台。批量录制只适合无人用电脑的时段，录制期间不能锁屏或休眠。
- 先确认 cua-driver 的权限：`check_permissions` 返回 `accessibility` 和 `screen_recording` 都为 `true`。

## 安全红线（开录前逐条确认）

`start_recording(record_video=true)` 录的是**整个主屏幕**，不只是目标窗口。

1. **文件选择框不能入镜**：系统 Open 面板会展示「文稿」等目录里的真实文件名。选工作空间一律在录屏之外完成（见下文流程），录屏中途也不要触发「打开本地文件夹」。
2. **目标窗口铺满屏幕**：`set_window_frame` 设成整屏（菜单栏以下），开录前用 `get_desktop_state` 截一张全屏图确认四周没有露出终端、邮件、聊天窗口。窗口后面常压着 Outlook 等应用，每次轮询都要确认目标应用还在最前面。
3. **收起侧边栏、切走敏感历史任务**：历史任务的标题和内容（可能含口令、后台链接）会入镜。先新建空任务，再收起侧边栏。
4. **权限保持「默认权限」**，不要用「允许完全访问」。每个案例开录前都看一眼权限标签，被误切了就当场改回。
5. **样例数据全部虚构**：公司名用「示例/演示/虚拟」这类明显假的名字，电话用 `138-0000-xxxx`，邮箱用 `example.com`。
6. 发现录进了不该录的内容：立即 `stop_recording`，删掉那段录屏和 `turn-*` 截图目录，修正流程后重录，并如实告诉用户录到了什么。

## 每个案例的流程

以 WorkBuddy 为例（其他桌面应用照同样的骨架调整定位）：

1. **离屏准备（不录）**
   - 点「新建任务」。
   - 「选择工作空间 → 新建工作空间」，命名如 `AI培训案例01`。WorkBuddy 会建 `~/WorkBuddy/<名字>/` 并自动选中，**不弹文件选择框**。
   - 用 Bash 把该案例的样例数据 `cp` 进 `~/WorkBuddy/<名字>/`。
   - `clipboard_write` 写入提示词。多行提示词不能用 `type_text` 直接输入，换行会被当成发送。
   - `bring_to_front` 目标窗口，确认权限标签是「默认权限」。
2. **开录**：`start_recording(output_dir=<scratchpad>/recNN, record_video=true)`。
3. **输入并发送**：`hotkey(["cmd","v"], x, y, delivery_mode="foreground")` 点进输入框并粘贴，截图确认文本已粘进去后，再点发送按钮。
4. **轮询等待**：后台 `sleep 25–60` 后 `get_window_state` 看一眼。有弹窗就处理，没有就继续等。
5. **核对产出（还在录）**：在应用里打开结果文件、切到关键 sheet 或页面停几秒；同时用脚本独立核对（数量、公式、是否残留敏感字段、是否编了金额等），结论写进案例说明。
6. **停录**：`stop_recording`。
7. **剪辑**：`scripts/stitch.sh <案例目录>/录屏.mp4 25 25 <scratchpad>/recNN/recording.mp4 [补录段.mp4]`。开头和结尾各 25 秒原速，中间 8 倍速。
8. **归档**：把 `~/WorkBuddy/<名字>/` 里生成的文件复制到案例目录的 `结果/`，并在案例说明末尾追加「录制时的实际情况」：耗时、核对结论、AI 出错或需要人判断的地方、没有人工核实的内容。

## 让录屏不中途断掉

- **录屏绑定在 cua-driver 的默认会话上**。等待期间**所有 cua 调用都不要传 `session`**（走默认会话），并且每 1–2 分钟至少调用一次，否则默认会话约 5 分钟闲置后过期，录屏会被自动收尾。用自定义 session 名轮询保不住录屏。
- 会话报 `has ended` 时，先 `start_session()`（不传名字）恢复，再 `get_recording_state` 看录屏是否还在。已经断了就补录一段结尾，剪辑时作为第二段传给 `stitch.sh`。
- 每段结束后用 `ffprobe` 看时长是否覆盖了整个过程。

## 弹窗与误操作

- WorkBuddy 转换文档时会反复弹出「删除文件命中询问规则」：删的是它自己在 `/tmp`、LibreOffice 缓存、无头 Chrome 临时目录里的文件。按用户事先给的授权处理；文件路径不属于这几类时停下来问用户。「本次会话内始终允许」并不持久，每次都会再弹。
- **点击前先截图确认弹窗还在**。不要凭上一次的坐标盲点，尤其不要用 `delivery_mode="foreground"` 补点：弹窗关闭后，同一位置可能正好是权限开关，会把权限误切成「允许完全访问」。
- `get_window_state` 的截图偶尔是旧画面，判断「是否已粘贴/已发送」时以第二张截图为准。
- WorkBuddy 是 Electron/Chromium 窗口，后台 `scroll` 不可用，需要 `delivery_mode="foreground"`。
- 终端本身没有屏幕录制权限，`ffmpeg -f avfoundation` 看不到屏幕，录屏只能走 cua-driver。

## 产出规格

- 成片为 H.264 + yuv420p、宽 1710、30fps，单个案例 1–2 MB、1–2 分钟。符合 keda `agent_runner_video_evidence.py` 视频证据门禁的编码要求，可直接作为证据或演示附件。
- 一批案例的目录建议：每个案例一个子目录，内含样例数据、`提示词.md`（业务问题 / 提示词 / 怎么核对 / 录制时的实际情况）、`录屏.mp4`、`结果/`；根目录一个 `README.md` 索引加录制说明（日期、应用版本、模型、权限档、快进说明、未经人工核实的内容）。
- 结束后告诉用户留在电脑上的改动：新建的工作空间目录、窗口大小与侧边栏状态、被覆盖的剪贴板、scratchpad 里的原始录屏。
