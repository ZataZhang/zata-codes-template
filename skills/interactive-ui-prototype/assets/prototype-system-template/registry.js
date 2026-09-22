/*
 * 原型清单的唯一事实源。Hub 的列表、筛选、详情，以及产品外壳侧栏都从这里读取。
 * 不要在 HTML、Markdown 或侧栏脚本里再手写第二份条目清单——三份数据必然漂移。
 *
 * 字段：
 * - system：所属产品/系统。同名原型属于同一台产品，共享同一个 app shell，
 *   在 Hub 里按「原型系统」分组；缺省表示独立原型。
 * - availability：available 之外一律不可打开，侧栏不得留下可点但会失败的链接。
 * - entry：原型入口文件名，供侧栏拼跨页链接（相对本目录）。
 */
window.PROTOTYPE_REGISTRY = [
  { id: 'example-interactive', title: '示例交互原型', system: '示例产品', project: '示例项目', module: '核心流程', form: 'code-native', version: 'v1.0', updatedAt: 'YYYY-MM-DD', availability: 'available', validationLevel: 'component preview', description: '替换为原型用途和主要流程。', preview: '', entry: './app-shell-page.html', source: './prototype-notes.html' },
  { id: 'example-image', title: '示例图片原型', system: '示例产品', project: '示例项目', module: '设置', form: 'image-state', version: 'v1.0', updatedAt: 'YYYY-MM-DD', availability: 'available', validationLevel: 'component preview', description: '替换为图片状态原型说明。', preview: './assets/example.png', entry: './image-state.html', source: './prototype-notes.html' },
  { id: 'example-archived', title: '示例失效原型', system: '示例产品', project: '示例项目', module: '归档', form: 'code-native', version: 'v0.9', updatedAt: 'YYYY-MM-DD', availability: 'archived', validationLevel: 'component preview', description: '入口失效时标记不可用：Hub 明确标灰，侧栏降级为静态文本。', preview: '', entry: './example.html', source: './prototype-notes.html' },
];
