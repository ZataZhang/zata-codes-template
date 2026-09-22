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
