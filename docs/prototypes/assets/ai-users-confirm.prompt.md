# ai-users-confirm.png

- 生成工具：ImageGen（built-in edit）
- 生成日期：2026-09-16
- 用例：`precise-object-edit`
- 画布：1536 × 1024
- 参考图片：`ai-users-detail.png`
- 上一状态：用户详情

## 保持不变

详情状态中的页面与抽屉布局。

## 本次变化

增加更深遮罩和居中的禁用确认弹窗。

## 完整提示词

```text
Use case: precise-object-edit
Asset type: third state of an image-hotspot interactive prototype
Input image: Image 1 is the exact USER DETAIL state and edit target.
Primary request: Edit Image 1 to create a DISABLE CONFIRMATION state. Add a centered white confirmation dialog approximately 460px wide over the existing page, with a stronger translucent dark overlay over the entire interface including the right drawer.
Dialog content, text verbatim: "禁用用户", "禁用后，林夏将无法登录，且当前会话会立即失效。这个操作可以随时撤销。", "取消", "确认禁用". Include a small coral warning icon. Place two clearly button-shaped actions at bottom right: neutral outlined "取消" and coral-red "确认禁用".
Constraints: add only the stronger overlay and centered dialog. Preserve the exact 1536×1024 canvas and every pixel-level layout relationship from Image 1 beneath it, including the right drawer, user data, sidebar, table and button positions. No prototype toolbar, no hotspot outlines, no watermark. Keep Chinese text crisp and horizontal.
```
