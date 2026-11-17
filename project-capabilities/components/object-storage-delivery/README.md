# 对象存储直传直取组件

此组件将无 SDK 依赖的对象存储端口与 S3 兼容 adapter（boto3）作为源码 overlay 提供给派生项目。模板本身不导入 overlay、不读取对象存储配置，也不增加运行时依赖。用户选择组件后，由维护者只复制 `overlay/` 中所需代码并在消费项目接入。

## 组件边界

- 消费项目 API 负责身份、业务归属、文件类型、文件大小、对象键与读写权限。此组件不会推断授权，也不新增 API、ORM、迁移或通用文件记录。
- 浏览器收到 S3 POST policy 后，使用 `FormData` 将文件直接 POST 到 S3 兼容对象存储。policy 绑定精确对象键、Content-Type、Cache-Control、大小范围与过期时间。浏览器不要自行设置 `multipart/form-data` 的 Content-Type。
- 预签名表单中的访问凭据标识会出现在授权字段中；服务端 Secret 不返回给浏览器，也不写入日志、数据库或前端构建产物。
- endpoint 默认必须使用不带 URL 凭据的 HTTPS 地址；仅当 `allow_insecure_http = true` 时允许 loopback（`127.0.0.1` / `localhost` / `::1`）HTTP，供本地 MinIO 测试。
- 上传完成后，消费项目可调用 `head_object()` 校验元数据，再保存自己的业务引用。普通 API 不接收或返回对象正文。
- 公开 URL 由项目配置的 CDN 域名与唯一对象键组成，`public_url(object_key)` 负责拼接并编码对象键，但能力不验证真实 CDN。私有对象须先经过消费项目授权，再通过短时预签名 GET URL 直接读取。
- 后台扫描或转换任务可以通过 `open_object()` 流式读取，并通过 `write_object()` 流式写入。

## 复制 overlay

将 `overlay/src/backend/core/shared/interfaces/object_storage.py`、
`overlay/src/backend/infrastructure/config/object_storage_settings.py`、
`overlay/src/backend/infrastructure/storage/s3_object_storage.py`、
`overlay/src/backend/infrastructure/storage/__init__.py` 与
`overlay/src/backend/composition/object_storage_wiring.py` 合并到目标项目对应层；
`storage/__init__.py` 导出 adapter，缺失时目标项目的常规包导入会失败。
`overlay/docs/guides/file-storage-delivery.md` 可一并复制到目标项目的 `docs/guides/`。
这些文件遵循 `api -> core -> engines -> infrastructure` 依赖方向；仅 composition
连接 core 契约、配置与 S3 adapter。

在消费项目的 Python 依赖中添加 `boto3`。安装组件前不添加此依赖。
将 `config.toml.example` 的 `[object_storage]` 片段按环境改写后合入项目配置，并只在启用时设置
`enabled = true`。密钥变量名可调整，真实值由服务端 `.env` / `.env.local` 或部署密钥注入提供；
仓库中的 `.env.example` 不保存密钥值。

## 消费项目接入顺序

1. 在消费项目 composition root 中调用 `build_object_storage()`，只在启用后把返回值注入用例。
2. 上传授权用例先验证当前会话、业务归属、允许的 MIME 类型和项目文件大小上限，再创建唯一对象键。
3. 用例调用 `create_upload_grant(UploadGrantRequest(...))`；把返回的 `url`、`form_fields`、对象键和过期时间作为 JSON 返回。不要记录 `policy`、签名字段或完整授权响应。
4. 浏览器创建 `FormData`，按 `form_fields` 加入字段，再加入 `file`，将表单 POST 到授权返回的 URL。上传正文不经过项目 API。
5. 上传完成后，应用可通过 `head_object(object_key)` 检查长度、Content-Type 与 ETag，再由消费项目更新自己的业务记录。
6. 公开图片 URL 使用 `public_url(object_key)`（配置的 CDN 域名加上 URL 编码后的唯一对象键）；未配置 `cdn_base_url` 时该方法会报错，不应退回使用对象存储原始地址。建议上传时使用 `Cache-Control: public, max-age=31536000, immutable`。替换内容时生成新对象键。
7. 私有读取用例先完成业务授权，再调用 `create_read_grant(ReadGrantRequest(...))`。未经授权的分支不得调用签名方法或返回 URL。
8. 后台任务使用 `open_object()` / `write_object()` 处理扫描、OCR、转码或缩略图，不让同步 HTTP 请求等待正文下载或上传。

## S3 / MinIO / CDN 部署检查

- 创建隔离或生产 Bucket 并保持私有；为服务端身份只授予测试或业务前缀所需的 `s3:PutObject`、`s3:GetObject`、`s3:HeadObject`（验证清理另需 `s3:ListBucket` / `s3:DeleteObject`）。不要授予公开读写。
- Bucket CORS 只允许实际前端 Origin。浏览器直传需要 `POST`；后台或浏览器直接读取如有需要可允许 `GET` / `HEAD`。允许 `Content-Type` 与 `Cache-Control` 请求头，并按项目验证需要暴露 `ETag`、`Content-Length` 和 `Cache-Control`。MinIO 官方兼容说明称 BucketCORS 默认启用；若实际版本拦截跨域请求，用 `mc cors` 或 `MINIO_API_CORS_ALLOW_ORIGIN` 配置。
- CDN 只回源公开对象路径，源站 Bucket 保持私有并限制回源权限。私有对象使用短时预签名 URL，不走共享 CDN。CDN 域名、回源和缓存头由消费项目部署后自验，本组件不做运行时验证。
- 公开对象使用不可变键与长期缓存头；私有对象使用 `private, no-store`。不要原地覆盖长期缓存 URL。
- adapter 将 POST policy 上限设为 5,000,000,000 字节；模板建议消费项目采用远低于该上限的业务值。该方式不支持 multipart / resumable 上传。
- 保留密钥在服务端。授权表单包含短时 bearer capability；不要将授权字段持久化或打印到日志。
- 阿里云 OSS 的 S3 兼容端点对 boto3 有签名限制（SigV4/aws-chunked 不兼容，需要 SigV2），本组件未对 OSS 做真实验证；接入前需单独验证预签名 POST/GET 与 CORS。

## 验证

组件源码复制到目标项目后，至少验证未配置时应用可正常启动、启用后缺少密钥会明确失败，并运行目标项目的授权与配置测试。本仓库的真实入口为 `just test-object-storage-e2e`，使用 zata-ops 已运行的本地 MinIO（`http://127.0.0.1:9000`）；无真实测试桶或 MinIO 不可用时记录验证阻塞，不使用 mock 声称直传已通过。

真实验证的 runner、消费 API/页面和 Playwright oracle 由 `tasks/evidence/P1-FEAT-20261107-093048-reusable-file-storage-delivery/scripts/` 下的 evidence 包提供，不随代码提交分发；先取得该包并安装 `tests/playwright-e2e` 的依赖，再运行上述入口。

runner 默认可使用 `OBJECT_STORAGE_E2E_ENDPOINT=http://127.0.0.1:9000`、`OBJECT_STORAGE_E2E_REGION=us-east-1`、`OBJECT_STORAGE_E2E_BUCKET=object-storage-e2e` 与 MinIO 默认测试凭据；调用者也可显式提供 `OBJECT_STORAGE_E2E_ACCESS_KEY_ID`、`OBJECT_STORAGE_E2E_ACCESS_KEY_SECRET`。确认 Bucket 是隔离测试资源后，才设置 `OBJECT_STORAGE_E2E_ALLOW_WRITES=1`。脚本只检查配置是否存在，不打印密钥值；不要把生产 Bucket 用作测试资源。每轮使用独立随机对象前缀，并在成功或失败后清理该前缀下已创建的对象。

### 官方协议参考

- [boto3 generate_presigned_post](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3/client/generate_presigned_post.html)
- [MinIO S3 API 兼容性](https://www.minio.org.cn/docs/minio/linux/reference/s3-api-compatibility.html)
- [Alibaba Cloud: Access OSS with an AWS SDK](https://help.aliyun.com/en/oss/developer-reference/use-aws-sdks-to-access-oss)
