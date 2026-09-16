# Image Hotspot Contract

仅在图片状态原型需要可点击流程时读取。

## 主交互

- 热点覆盖在图片中真实按钮、链接或可操作控件的位置。
- 图片外部的步骤导航只能辅助预览，不得代替主流程。
- 看起来禁用的控件不得绑定推进动作；需要推进时应使用图中实际可操作控件或补画正确状态。

## 热点配置

每个热点至少包含 `label`、`left`、`top`、`width`、`height`、`action`。坐标和尺寸均使用相对原图的百分比。

- 热点框与动作标签默认持续可见，不依赖辅助开关。
- hover 和 focus 进一步强化反馈。
- 热点是原生 `button` 或 `a`，带可读 `aria-label`。
- 图片缩放、窄屏横向滚动时，热点层必须与图片共享同一定位容器。

## 验证

桌面与窄屏分别验证：热点中心仍落在所画控件内、键盘可聚焦、点击到达预期状态、返回 Hub 可用。

可复制骨架：`assets/prototype-system-template/image-state.html`、`image-state.css`、`image-state.js`。
