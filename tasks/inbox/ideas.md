# Idea Inbox — 原话日志

> 追加式、逐字保留。AI 只在末尾追加，永不改写已有条目。事实来源是本文件。

## 2026-06-15 10:49 · template-sync

> Scripts 我觉得要不也抽一个模板scripts 文件夹,把会同步的都放在模板script文件夹里面

## 2026-06-25 18:39 · hooks

> '/Users/zata/code/zata_code_template/hooks'  现在我感觉 这个也要抽一个shared 子文件夹, 你觉得呢

## 2026-09-22 19:11 · just view

> Staged ChangeS 的减号暂时就不加了，因为我觉得我的使用频率比较低， 这个决策可以稍微记录一下

**AI 派生（非原话）：** 「减号」指在 `Staged Changes` 段上做反向的「取消暂存」按钮，与本次
一起落地的「`Changes` 段加号（`git add`）」成对。本次只做加号：暂存是查看器里最高频的下一步
动作，而取消暂存频率低，用户判断不值得为它再开一个写口。同一次里 `just view` 的只读边界也从
「完全不写」收窄为「只读 + 一个只做暂存的写口」——见 `docs/guides/file-viewer.md` 与
`docs/ai-standards/tooling.md` 的写边界条目。何时想加回取消暂存：需要新的写口（`git restore
--staged`），那要重新过一遍边界决策，而不是「顺手补一个按钮」。

## 2026-09-22 22:09 · just view

> 增加一个能力， just view  staged   和 changes  能一整个的折叠

**AI 派生（非原话）：** 「一整个的折叠」指改动视图左树的 `Staged Changes` / `Changes` 两个
分段标题本身可点，点一下收起或展开**整段**；在此之前折叠粒度只到段内目录（分段标题刻意做成
不可点）。两层折叠同一条口径：默认展开、每段各自记、只在本次会话内记住、过滤生效时强制展开。
已就地落地（前端 `scripts/shared/view/assets/viewer.js` 的 `changeGroupExpansion` 与
`.section-toggle`），见 `docs/guides/file-viewer.md` 的「界面用法」。

## 2026-09-22 22:09 · just view

> 还有我发现Markdown的渲染有问题，里面插入了图片，但是预览的时候并没有渲染。

**AI 派生（非原话）：** 根因不是渲染失败，而是预览片段里的**相对引用**没有改写：markdown 输出
的 `src="images/a.png"` 是相对文档所在目录写的，而片段被内联进查看器页面（`/`），浏览器按页面根
解析成 `/images/a.png` —— 路由白名单里没有它，必然 404。已就地落地（服务端按标签改写 `src` /
`href`：`src` 指向 `/raw/<仓库相对路径>`，指向另一份 Markdown 的链接走查看器直达链接；带 scheme
的、纯片段的、带查询串的、越界的原样保留），见 `docs/guides/file-viewer.md` 的「预览的边界」。
这条把该文件原先写着「正文里的相对图片也不会解析（图片会加载失败）」的那句已知后果改掉了。
