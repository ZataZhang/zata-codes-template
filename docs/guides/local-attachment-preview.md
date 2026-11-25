# 发送前附件预览

`frontend-public/components/local-attachment-preview.tsx` 提供可按需接入的本地附件预览。聊天、表单或评论区可以先显示用户选择的文件，等用户确认后再由调用方上传。

- `takePastedFiles(event)` 读取浏览器提供的剪贴板文件。有文件时接管粘贴，纯文本仍走浏览器默认行为。
- `LocalAttachmentPreview` 接收一个 `File`。PNG 和 JPEG 显示缩略图并可点击放大。Excel 和 CSV 显示首张工作表缩略图，弹窗底部提供工作表标签，每张表最多展示前 50 行、前 20 列。其他文件以名称显示。
- 浏览器从本地 `File` 生成预览。SheetJS 在首次预览表格时加载。调用方管理附件 ID、校验、队列容量、移除和重试。

## 接入已有输入框

在 Client Component 中，把粘贴交给文件选择器使用的同一条校验逻辑。先检查文件类型和大小，再把接受的文件加入待发送队列。

```tsx
import {
  LocalAttachmentPreview,
  takePastedFiles,
} from "@/components/local-attachment-preview"

// addValidatedFiles 是宿主已有的附件校验和入队入口。
<textarea
  onPaste={(event) => {
    const files = takePastedFiles(event)
    if (files.length > 0) addValidatedFiles(files)
  }}
/>

// draftAttachments 由宿主管理，每条记录有独立的 id。
{draftAttachments.map(({ id, file }) => (
  <LocalAttachmentPreview key={id} file={file} />
))}
```

验证时使用同名但内容不同的文件，以及第一张表为空、第二张有数据的工作簿。窄屏上应能横向滚动标签，用键盘切换工作表并按 Esc 回到附件卡片。文件管理器复制是否能产生文件粘贴事件取决于操作系统和浏览器，文件选择器可以覆盖该入口。
