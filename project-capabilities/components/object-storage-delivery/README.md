# 对象存储直传直取

此组件向派生项目提供 SDK 无关的 ObjectStorage 契约、阿里云 OSS adapter、可选配置和接入说明。它是模板初始化时显式选择的源码 overlay；模板本身不导入组件、不读取 OSS 配置，也不增加常驻运行时依赖。

## 传输边界

- 消费项目 API 先执行身份、业务归属、MIME 类型和大小授权，再为一个不可变或唯一对象键签发短期 PostObject 表单。
- 浏览器将文件正文直接 POST 到 OSS。API 响应只包含授权字段和业务所需元数据，不包含文件正文。
- OSS policy 将表单绑定到单个 Bucket、精确对象键、Content-Type、Cache-Control、大小范围和过期时间。
- 上传完成后，项目可通过 HEAD 元数据检查长度、类型和 ETag，再更新自己的业务记录。
- 公开对象 URL 使用已配置的 CDN 域名和 URL 编码后的唯一对象键；对象写入缓存元数据，并通过真实 CDN 直接读取。
- 私有对象由项目先完成领域授权，再获取短期 OSS GET 地址。未授权时不得签发 URL；到期后 OSS 拒绝读取。
- 扫描、OCR、转码和缩略图由后台任务通过 ObjectStorage 流式读取和写入。

## 复制 overlay

按目标项目现有分层合并以下文件：

- overlay/src/backend/core/shared/interfaces/object_storage.py
- overlay/src/backend/infrastructure/config/object_storage_settings.py
- overlay/src/backend/infrastructure/storage/oss_object_storage.py
- overlay/src/backend/infrastructure/storage/__init__.py
- overlay/src/backend/composition/object_storage_wiring.py
- overlay/docs/guides/file-storage-delivery.md

只在消费项目选择此能力后安装 OSS Python SDK oss2。使用 V4 签名的 SDK 至少需要 2.18.4。模板项目与未选择能力的派生项目不添加该依赖。配置示例在 config.toml.example；服务端 AccessKey 只从 OSS_ACCESS_KEY_ID 和 OSS_ACCESS_KEY_SECRET 等环境变量读取，严禁提交真实值或将凭据放入浏览器 bundle。

## 消费项目接入顺序

1. 在 composition root 调用 build_object_storage()；未启用配置时返回空值，不初始化 OSS SDK。
2. 上传授权用例校验会话、业务记录、内容类型与大小，并创建不可变或唯一对象键。
3. 用例传入 UploadGrantRequest；项目 API 将 URL、表单字段、对象键和过期时间作为 JSON 返回。不要记录授权字段或完整响应。
4. 浏览器从授权响应构造 FormData，并把文件 POST 到授权 URL。不要设置 multipart/form-data 的 Content-Type 请求头。
5. 上传结束后，项目通过 head_object() 校验元数据，再更新自己的业务状态。
6. 公开资源使用 public_url() 生成 CDN 地址，并写入 public, max-age=31536000, immutable 等与唯一对象键相配的缓存策略。更新内容时生成新对象键。
7. 私有资源用例先完成领域授权，再调用 create_read_grant()；不允许授权分支不得调用签名方法或返回 URL。
8. 后台任务用 open_object() 和 write_object() 处理对象正文；普通同步 API 不承担文件字节传输。

## Bucket、CORS 与 CDN

- 使用隔离 Bucket 和最小权限 RAM 身份。业务服务按需获得 PutObject、GetObject、HeadObject；验证清理另需 ListBucket、DeleteObject。不要授予公共读写。
- Bucket 默认保持私有。只允许实际前端 Origin、POST 方法及所需请求头；如浏览器需读取对象，再允许 GET/HEAD。按真实请求暴露 ETag、Content-Length 和 Cache-Control。
- CDN 只回源公开对象路径。私有对象首版只使用短时 OSS GET 地址，不走公共 CDN。通过真实 CDN 域名访问，并检查响应 Cache-Control 和重复请求的缓存响应。
- 公开对象键不可变并设置长期缓存；私有对象使用 private, no-store。不要原地覆盖长期缓存 URL。
- PostObject 不能替代分片或断点续传；大文件上传方案应由消费项目按需设计。
- AccessKey 与签名 URL 属于高敏凭据。不要记录签名 query、表单签名字段或服务端密钥。

## 验证

仓库的真实入口为 just test-object-storage-e2e。每个 rv-1、rv-2、rv-3 都通过独立的真实 OSS Bucket 与配置的真实 CDN 域名运行；禁止用 MinIO、mock、fake、TestClient 或代理请求代替验收边界。测试 Bucket 必须隔离，并由调用者显式提供 endpoint、region、Bucket、AccessKey、CDN 域名和 OBJECT_STORAGE_E2E_ALLOW_WRITES=1。入口在凭据或隔离资源缺失时安全退出；不得回退读取通用 .env S3 备份配置。

每轮使用唯一测试对象前缀并清理创建的对象。脚本、临时 fixture 和逐项证据都留在 PRD evidence 目录；不可将 RV 脚本放入代码变更集。缺少真实 OSS/CDN 资源时，保留未勾选的验收项并记录验证阻塞。

## 阿里云官方参考

- [Python SDK V1 配置与 V4 凭据](https://help.aliyun.com/zh/oss/python-configuration-access-credentials)
- [OSS PostObject V4 policy 与签名规则](https://help.aliyun.com/zh/oss/developer-reference/signature-version-4-recommend)
- [配置 CORS 规则允许网站跨域访问 OSS](https://help.aliyun.com/zh/oss/user-guide/configure-cross-origin-resource-sharing)
- [通过 CDN 加速访问 OSS](https://help.aliyun.com/zh/oss/user-guide/cdn-acceleration)
