# 对象存储直传直取组件

此组件将无 SDK 依赖的对象存储端口与阿里云 OSS adapter 作为源码 overlay 提供给派生项目。模板本身不导入 overlay、不读取 OSS 配置，也不增加运行时依赖。用户选择组件后，由维护者只复制 `overlay/` 中所需代码并在消费项目接入。

## 组件边界

- 消费项目 API 负责身份、业务归属、文件类型、文件大小、对象键与读写权限。此组件不会推断授权，也不新增 API、ORM、迁移或通用文件记录。
- 浏览器收到 PostObject policy 后，使用 `FormData` 将文件直接 POST 到 OSS。OSS policy 绑定精确对象键、Content-Type、Cache-Control、大小范围与过期时间。浏览器不要自行设置 `multipart/form-data` 的 Content-Type。
- OSS `AccessKeyId` 是 PostObject 协议要求的公开标识，会出现在授权字段中；服务端 `AccessKeySecret` 不返回给浏览器，也不写入日志、数据库或前端构建产物。
- OSS endpoint 必须使用不带 URL 凭据的 HTTPS 地址；签名表单和读取 URL 不会发送到明文 HTTP 端点。
- 上传完成后，消费项目可调用 `head_object()` 校验元数据，再保存自己的业务引用。普通 API 不接收或返回对象正文。
- 公开 URL 由项目配置的 CDN 域名与唯一对象键组成。私有对象须先经过消费项目授权，再通过短时 OSS GET URL 直接读取。
- 后台扫描或转换任务可以通过 `open_object()` 流式读取，并通过 `write_object()` 流式写入。

## 复制 overlay

将 `overlay/src/backend/core/shared/interfaces/object_storage.py`、
`overlay/src/backend/infrastructure/config/object_storage_settings.py`、
`overlay/src/backend/infrastructure/storage/aliyun_oss.py` 与
`overlay/src/backend/composition/object_storage_wiring.py` 合并到目标项目对应层。
这些文件遵循 `api -> core -> engines -> infrastructure` 依赖方向；仅 composition
连接 core 契约、配置与 OSS adapter。

在消费项目的 Python 依赖中添加阿里云 OSS Python SDK（`oss2`）。安装组件前不添加此依赖。
将 `config.toml.example` 的 `[object_storage]` 片段按环境改写后合入项目配置，并只在启用时设置
`enabled = true`。密钥变量名可调整，真实值由服务端 `.env` / `.env.local` 或部署密钥注入提供；
仓库中的 `.env.example` 不保存密钥值。

## 消费项目接入顺序

1. 在消费项目 composition root 中调用 `build_object_storage()`，只在启用后把返回值注入用例。
2. 上传授权用例先验证当前会话、业务归属、允许的 MIME 类型和项目文件大小上限，再创建唯一对象键。
3. 用例调用 `create_upload_grant(UploadGrantRequest(...))`；把返回的 `url`、`form_fields`、对象键和过期时间作为 JSON 返回。不要记录 `policy`、`Signature` 或完整授权响应。
4. 浏览器创建 `FormData`，按 `form_fields` 加入字段，再加入 `file`，将表单 POST 到授权返回的 URL。上传正文不经过项目 API。
5. 上传完成后，应用可通过 `head_object(object_key)` 检查长度、Content-Type 与 ETag，再由消费项目更新自己的业务记录。
6. 公开图片 URL 使用 CDN 域名加上 URL 编码后的唯一对象键；建议上传时使用 `Cache-Control: public, max-age=31536000, immutable`。替换内容时生成新对象键。
7. 私有读取用例先完成业务授权，再调用 `create_read_grant(ReadGrantRequest(...))`。未经授权的分支不得调用签名方法或返回 URL。
8. 后台任务使用 `open_object()` / `write_object()` 处理扫描、OCR、转码或缩略图，不让同步 HTTP 请求等待正文下载或上传。

## OSS / CDN 部署检查

- 创建隔离或生产 Bucket 并保持私有；为服务端 RAM 身份只授予必需的 `oss:PutObject`、`oss:GetObject`、`oss:HeadObject` 权限及对应对象前缀。不要授予公开读写。
- Bucket CORS 只允许实际前端 Origin。浏览器直传需要 `POST`；后台或浏览器直接读取如有需要可允许 `GET` / `HEAD`。允许 `Content-Type` 与 `Cache-Control` 请求头，并按项目验证需要暴露 `ETag`、`Content-Length` 和 `Cache-Control`。CDN 域名也需配置适合页面的 CORS 响应头。
- CDN 只回源公开对象路径，源站 Bucket 保持私有并限制回源权限。私有对象使用 OSS 短时签名 URL，不走共享 CDN。
- 检查 CDN 回源 Host、HTTPS、缓存键与忽略参数规则；不得让缓存层忽略私有 OSS 签名参数。
- 公开对象使用不可变键与长期缓存头；私有对象使用 `private, no-store`。不要原地覆盖长期缓存 URL。
- adapter 将 PostObject policy 上限设为 5,000,000,000 字节，低于 OSS 单次表单上传的 5 GB 服务端上限；模板建议消费项目采用远低于该上限的业务值。该方式不支持 OSS multipart / resumable 上传。
- 保留密钥在服务端。授权表单包含短时 bearer capability；不要将授权字段持久化或打印到日志。

## 验证

组件源码复制到目标项目后，至少验证未配置时应用可正常启动、启用后缺少密钥会明确失败，并运行目标项目的授权与配置测试。真实浏览器、OSS 与 CDN 行为必须在隔离 Bucket、测试身份和实际 CDN 上验证；本仓库的真实入口为 `just test-object-storage-e2e`。无真实隔离资源时记录验证阻塞，不使用 mock 声称直传或 CDN 已通过。

本仓库 e2e 需由调用者在命令环境提供 `OBJECT_STORAGE_E2E_ENDPOINT`、`OBJECT_STORAGE_E2E_REGION`、`OBJECT_STORAGE_E2E_BUCKET`、`OBJECT_STORAGE_E2E_ACCESS_KEY_ID` 与 `OBJECT_STORAGE_E2E_ACCESS_KEY_SECRET`；rv-2 另需 `OBJECT_STORAGE_E2E_CDN_BASE_URL`。确认 Bucket 是隔离测试资源后，才设置 `OBJECT_STORAGE_E2E_ALLOW_WRITES=1`。脚本只检查配置是否存在，不打印密钥值；不要把生产 Bucket 用作测试资源。

### 官方协议参考

- [OSS PostObject 与 POST policy](https://help.aliyun.com/en/oss/developer-reference/postobject)
- [OSS 从客户端直传对象](https://help.aliyun.com/en/oss/user-guide/uploading-objects-to-oss-directly-from-clients/)
- [OSS CORS 配置](https://help.aliyun.com/en/oss/user-guide/configure-cross-origin-resource-sharing)
- [OSS Python SDK V1](https://help.aliyun.com/en/oss/developer-reference/python-sdk-v1/)
