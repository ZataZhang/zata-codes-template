# 实现决策与坑

改动 `assets/board.html` 或两个脚本前读这份。都是实测踩出来的，不是预防性说教。

## 为什么是「两个只追加文件」而不是一个可变记录

最初的设计是一个 `qa.jsonl`，问题带 `answer: null`，agent 改那一行填答案。不成立的点：改行意味着重写文件（truncate 或 rename），而 `tail -F` 在文件被 rename/truncate 后会重新打开并**从头读**——agent 会收到整份历史行的重复通知，把同一个问题回答好几遍。

拆成 `questions.jsonl`（服务只追加）+ `answers.jsonl`（agent 只追加）后，事件流单调，两端各写各的文件，互不触碰。

## 清空为什么归档而不是截断

页面上的「清空」走 `POST /qa/clear`，把两个 jsonl **移进 `<workdir>/_cleared/`**，不是 truncate。同一个理由：`tail -F` 在监听的文件被截断或替换后会重新打开并从头读，服务再往同名文件追加时，监听端会把新旧内容混在一起。归档后两个文件都消失，由服务在下次追加时新建，监听端看到的是干净的新文件；顺带让「清空」可回溯（归档件仍在产物目录里）。

清空只动问答流，**不动 `answers.json`**——那是用户的选择结果，与提问记录是两回事。

## 合并发生在读的时候

`GET /qa` 把两个文件按 `id` join，`reply` 字段是查询结果，不存在于任何文件里。所以没有锁、没有读改写，也不存在「谁拥有这条记录」。

## 提问为什么需要 Monitor

agent 没有可被外部推的入口，只有两个输入通道：对话本身、后台任务通知。整套交互的核心就是把「文件多了一行」翻译成「一条通知」。因此**起服务必须同时挂 `tail -n 0 -F questions.jsonl` 的 Monitor**，否则页面提问只是静静躺在盘上。

**提交通道同样需要 Monitor（这里出过 bug）。**「提交」的落盘目标 `answers.json` 没有任何内建事件：`POST /submit` 写完文件就结束，不会触碰 `questions.jsonl`，agent 若只挂了提问通道，用户点「提交」后 agent 依然空闲——用户以为 agent 没收到，实际文件早已写好（2026-10-03 实测，用户不得不手动喊一声）。规则：起服务后**同时挂两个 Monitor**——`tail -n 0 -F questions.jsonl`（提问）与 `tail -n 0 -F answers.json`（提交结果，首次写入即触发；`-F` 对尚不存在的文件会等待创建）。两个事件收到后都回到读文件对账，事件本身不是批准。

延迟不是网络延迟，是 agent 的轮次边界：问题落盘即时，但回答要等通知到达且那一轮空闲。所以页面文案是「已送达，等待回答」，不要写成「正在输入」。

通知携带的是数据，不是批准。绝不把一条提问事件当作用户对某项选择的确认，或继续执行某个动作的授权。

## 同源省掉了什么

页面和接收 POST 的是同一个进程、同一个端口，所以没有 CORS 预检、没有跨域配置。这是把服务与页面写在一起的主要收益之一。

## 轮询而不是 SSE

浏览器不接受推送，除非 WebSocket 或 SSE。页面每 2.5 秒 `fetch('/qa')`，零额外机制。升级成 SSE 可行（长连接 + 生成器），收益只是省掉最多 2.5 秒抖动，代价是那条连接得和 `tail -F` 一样活着。

## 两处注入面

- 渲染一律 `textContent` + `white-space:pre-wrap`。用户在提问框里敲 `<img onerror=...>`、agent 回答里带尖括号，都不该被解析成 HTML。
- board JSON 内嵌进 `<script>` 时，`json.dumps(...).replace("</", "<\\/")` 是必需的：正文里出现 `</script>` 会直接截断脚本块。JSON 字符串里 `<\/` 与 `</` 等价，不影响解析。

## 不要写死宿主 agent 的名字（这里出过 bug）

`board.html` 的文案与气泡说话人原先把宿主 agent 写成了具体产品名（"Qoder"）。这个 skill 会被多个 CLI 加载（CodeBuddy / Qoder / Claude / Codex …），写死一个产品名在别的宿主里就是错的。统一用中性称呼「助手」。新增文案或气泡时不要引入具体产品名。

## 提问框必须对输入法友好（这里出过 bug）

`#input` 的 Enter 处理一开始只判断 `e.key==='Enter' && !e.shiftKey`，于是**中文/日文输入法组字时按回车选词，会把候选词当成问题直接发出去**（用户报的：中文输入法下敲英文，回车选词的同时就发送了）。修法是在 keydown 里先排除组字态：

```js
if(e.isComposing || e.keyCode===229) return;   // 229 兜老 Safari，它在提交那一帧不给 isComposing
```

改这段时不要退回只看 `e.key`。验证要用 CDP 的 `Input.imeSetComposition` 造真实组字态——只发合成 `KeyboardEvent` 测不出浏览器差异。

## 滚动策略（这里出过 bug）

轮询每次重画会话区，早期实现无条件 `scrollTop = scrollHeight`，用户往上翻历史最多 2.5 秒就被拽回底部。现在的规则：

- 渲染**前**先量 `scrollHeight - scrollTop - clientHeight < 60` 判断用户是否本来就贴底；贴底才跟随新内容。
- 不贴底且内容变了 → 亮「↓ 有新内容」；这个状态用 `pendingJump` 记住，直到用户点它或自己滚到底才清除。曾经写成「只在内容变化的那一帧显示」，结果下一次轮询（内容没再变）就自己消失了——提示活不过 2.5 秒等于没有提示。
- 阈值 60px 是为了容忍滚动条取整与短回复。

## 为什么校验器强制 rec / why / cost

这个 skill 的价值前提是「agent 已经形成判断，人只做否决」。允许 `rec` 缺失或 `why` 留空，页面就会退化成把原始问题重新排一遍给人读——那是文档的工作，不是决策页的工作。所以这三项在 `validate_board()` 里是硬错误，宁可少放一题。

## 服务生命周期

`(python3 serve_board.py ... &)` 脱离 agent 轮次存活，但活不过重启，也不会自己拉起。页面在 `fetch` 失败时会显式提示「服务不可达，请回对话里问」，九项提交另有一条降级路径：把选择摊成 JSON 文本让用户复制。

端口占用先查：`lsof -nP -iTCP:8765 -sTCP:LISTEN`。

## 自检不得写用户的产物文件

浏览器自检会真的点「提交」，于是一份**测试生成的选择**就落进了 `answers.json`，看起来和用户提交的一模一样——而这份文件是后续回写文档的依据。踩过一次：自检脚本点了 `Q4=B`，随后 answers.json 里就存着一条用户从未做过的决定。

规则：自检用**独立 workdir 与独立端口**（`--workdir /tmp/decision-board-selftest --port <别的端口>`），只验行为不落进正式目录；若必须在正式目录里验渲染，验完立刻删除 `answers.json` 并把删除事实告诉用户。提问通道的自检同理——它会往 `questions.jsonl` 追加一条假提问，而那条会被事件监听真的送进对话，需要回答掉并标明是自检。

## 自动打开浏览器为什么是开关而不是默认

`--open` 会调系统 opener（macOS `open`）把页面弹出来，交付时省掉用户点链接。做成显式开关而不是默认，是因为同一份脚本还要被浏览器自检、渲染验证反复起服务——默认开会每验一次弹一个窗口（尤其上面那条「自检用独立端口」的场景）。所以 skill 流程固定带 `--open`，自检一律不带。opener 用 `Popen` 分离启动且吞掉输出，打开失败只告警，绝不因它让服务起不来。

## 改完必须用真浏览器验

模板的行为（预选、改动高亮、确认勾选解锁提交、提问往返）光看代码判断不出来。这次两个 bug——滚动回弹、`<h1>` 未参数化——都是浏览器跑出来的：前者是用户报的，后者是 `curl | grep <h1>` 抓到还留着硬编码文本。

可复用片段（在项目里跑，因为 `@playwright/test` 通常装在 e2e 包目录）：

```js
const { chromium } = require('@playwright/test');   // 或 'playwright'
const b = await chromium.launch();
const p = await b.newPage();
const errors = []; p.on('pageerror', e => errors.push(String(e)));
await p.goto('http://127.0.0.1:8799/');
// 断言：卡片数、推荐徽标数、改一题后 .card.changed 计数、#submit 是否解锁、
// 提交后 answers.json 落盘、提问后 .msg 计数与 questions.jsonl 行数、pageErrors 为空
```

`pageerror` 一定要收集——模板里任何一处 JS 抛错都会静默让整页交互失效，而 HTTP 仍是 200。
