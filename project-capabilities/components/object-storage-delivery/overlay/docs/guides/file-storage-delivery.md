# 文件存储直传直取接入指南

## 配置与依赖

将组件源码合并到消费项目后，只有显式启用 [object_storage] 配置才初始化 OSS adapter。未复制或未启用组件时，模板启动路径不读取 OSS 配置，也不导入 OSS SDK。

配置只保存地域、Bucket、endpoint、CDN 域名和凭据环境变量名称。服务端从 OSS_ACCESS_KEY_ID 与 OSS_ACCESS_KEY_SECRET 读取真实凭据。启用后缺少凭据时，composition 必须明确失败。OSS endpoint 和 CDN 域名均使用 HTTPS；endpoint 仅允许 authority，不包含用户名、密码、路径、query 或 fragment。

V4 签名需要 OSS Python SDK oss2 2.18.4 或更高版本。组件复制到消费项目后再添加依赖，不要给模板默认依赖增加 oss2。

## 上传与完成确认

消费项目先校验会话、业务归属、允许的 MIME 类型和大小，再为每次上传生成不可变或唯一对象键。业务用例将对象键、Content-Type、Cache-Control、大小范围和短过期时间传入 UploadGrantRequest。

阿里云 OSS adapter 使用 V4 签名的 PostObject policy。表单只允许精确对象键和所需元数据，并由服务端限制上传长度与授权有效期。浏览器把 API 返回的表单字段和文件放入 FormData，直接 POST 到 OSS。不要把文件送入应用 API，也不要手动设置 multipart/form-data 请求头。

上传成功后，项目调用 head_object() 读取长度、Content-Type、Cache-Control 和 ETag，再按自身业务规则更新记录。授权响应与签名字段不得落日志或数据库。API 不得通过上传回调或兼容端点重新转发普通文件正文。

## 公开和私有读取

公开资源通过 public_url() 生成 CDN 域名加不可变对象键的地址。上传授权应设置与公开资源相符的 Cache-Control，例如 public, max-age=31536000, immutable。更新内容时分配新对象键，不依赖覆盖同 URL 后清缓存。

私有资源必须先由消费项目执行领域授权，然后调用 create_read_grant() 返回短期 OSS GET 地址。未经授权的分支不生成签名 URL；URL 到期后，OSS 应拒绝读取。私有对象使用 private, no-store，不进入公共 CDN 缓存。

## 后台字节处理

病毒扫描、OCR、转码和缩略图由后台任务调用 open_object() 流式读取原对象，处理后调用 write_object() 写入新的唯一对象键。同步 API 只处理授权、对象元数据和业务状态，不等待或代理对象正文。

## Bucket、CORS 与 CDN

- Bucket 保持私有；RAM 身份只授予实际业务前缀需要的 PutObject、GetObject、HeadObject 权限。
- Bucket CORS 只允许实际前端 Origin 和 POST；需要浏览器读取时再开放 GET/HEAD。允许必需的 Content-Type 与 Cache-Control，并按实际读请求暴露 ETag、Content-Length 和 Cache-Control。
- CDN 只回源公开对象路径。若 CDN 访问私有 Bucket，按阿里云配置私有 Bucket 回源，并确保客户端 URL 不携带 OSS 签名参数。
- 对公开对象检查 CDN 响应中的 Cache-Control，并连续请求同一唯一 URL，记录 CDN 缓存响应头和字节摘要。
- 服务端凭据和完整签名 URL 是 bearer capability；不打印、不持久化，也不返回给未授权调用方。

## 仓库真实验证

通过 just test-object-storage-e2e rv-1、rv-2、rv-3 分项运行。每项必须使用隔离的真实 Aliyun OSS 测试 Bucket；rv-2 还要使用配置的真实 CDN 域名。不要用 MinIO 或 mock 替代 OSS/CDN 边界。只从 OBJECT_STORAGE_E2E_* 明确提供的环境变量读取测试端点、Bucket、凭据和 CDN 域名；命令要求 OBJECT_STORAGE_E2E_ALLOW_WRITES=1 和精确 Bucket 名确认。不得自动读取通用 .env S3 配置。

真实资源未配置时，入口应在任何网络写操作前失败，并按 PRD 记录 Validation blocker。证据、浏览器 fixture、捕获脚本和临时文件均放在 PRD evidence 目录；这些 RV 脚本不得进入代码变更集。
