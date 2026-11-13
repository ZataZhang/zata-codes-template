# 对象存储直传直取接入指南

本页随 overlay 复制到消费项目的 `docs/guides/`。它说明组件接入后的职责边界和运维配置；不创建任何模板产品 API。

## 配置与启动

未复制或未启用 `[object_storage]` 时，`build_object_storage()` 返回 `None`，模板启动路径无需 OSS 配置。启用后，配置中只保存非密钥值与环境变量名，服务端在环境中读取 `OSS_ACCESS_KEY_ID`、`OSS_ACCESS_KEY_SECRET`。启用但缺少环境变量时应在 composition 阶段失败，避免能力看似启用却无法签名。

OSS endpoint 只接受无 URL 凭据、无 query/path 的 HTTPS authority；不要把签名请求发到明文 HTTP 端点。

`ObjectStorageSettings` 的 `cdn_base_url` 只供消费项目构造公开 CDN URL；adapter 不代理 CDN 请求。不要把 URL、对象正文或完整签名字段写入日志或数据库。

## 上传

消费项目先检查身份、业务归属、MIME 类型和文件大小，再为每次上传分配唯一对象键。将键、Content-Type、Cache-Control、大小范围和短过期时间传入 `UploadGrantRequest`。OSS PostObject policy 将这些值绑定到单个 POST 表单；OSS 会拒绝超限大小或与策略字段不符的请求。

浏览器通过授权 API 获取表单后，使用 `FormData` 直接请求 OSS。不要把文件传给应用 API，也不要手工设置 `multipart/form-data` 请求头。完成后应用只调用 `head_object()` 读取元数据，再更新消费项目自己的业务状态。

## 公开与私有读取

公开资源用配置的 CDN 域名加不可变对象键。推荐 `public, max-age=31536000, immutable`。替换图片时新建版本键，避免清缓存或覆盖同 URL。浏览器从 CDN 读取对象正文。

私有资源在每次读取前由消费项目完成领域授权。仅授权通过后才能调用 `create_read_grant()`，签名 URL 只对单个 key 的 GET 操作有效，短时过期。私有 URL 直接读 OSS，不进入公开 CDN 缓存。

## CORS 与缓存

Bucket CORS 应按消费项目实际页面 Origin 配置最小范围：直传允许 POST，必要时允许 GET / HEAD；允许 Content-Type 和 Cache-Control；按浏览器验证需要暴露 ETag、Content-Length 和 Cache-Control。CDN 跨域响应由 CDN 配置负责，仍须在浏览器真实请求中检查。

Bucket 保持私有，只授予服务器处理身份所需的前缀与操作权限，并配置 CDN 对公开路径的私有回源访问。缓存 key 不得丢弃私有签名参数；私有对象不应经共享 CDN。

## 异步处理

同步 API 只负责授权、元数据校验与业务状态。扫描、OCR、转码和缩略图等任务由后台进程通过 `open_object()` 和 `write_object()` 流式读写。调用方应关闭读取句柄，并按业务需要写回新的对象键。

## 安全边界

- AccessKeySecret 只存在服务端；`OSSAccessKeyId` 是 PostObject 协议要求的标识，不是签名密钥。
- Policy、Signature 与读取签名 URL 都是短时 bearer capability，不入库、不打日志、不放到可长期缓存的响应中。
- 上传 policy 的大小上限由 OSS 强制；浏览器端文件限制只是体验优化，不替代服务端授权与 OSS 校验。
- 无权限读取时不生成签名 URL。过期链接必须重新走消费项目授权。
