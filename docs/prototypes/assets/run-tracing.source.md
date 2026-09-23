# run-tracing.png 来源

- 类型：浏览器截图（非 AI 生成）
- 目标文件：`docs/prototypes/run-tracing.html`
- 视口：1440 × 900
- 主题：light
- 语言：zh-CN（页面为固定中文文案）
- 数据：页面内 JavaScript fixture，默认选中 `run_8f31c2`（成功，2 模型 + 2 工具 + 1 个父级 fallback）
- 截取命令：

```bash
cd frontend-admin
pnpm exec playwright screenshot --viewport-size=1440,900 --wait-for-timeout=800 \
  "file:///Users/zata/code/zata_code_template-worktrees/port-run-tracing/docs/prototypes/run-tracing.html" \
  ../docs/prototypes/assets/run-tracing.png
```

- 验证层级：interactive prototype（component preview）。该图是**设计意图**，不是生产入口的功能验收证据。
- 失效条件：原型 HTML 的默认选中项、fixture 数据或布局改变后，需重新截取。
