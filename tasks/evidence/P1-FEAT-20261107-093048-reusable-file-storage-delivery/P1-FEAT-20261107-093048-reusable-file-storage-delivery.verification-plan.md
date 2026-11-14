# 验证计划：可复用的对象存储与文件直传直取能力

## 验证边界

行为 oracle 必须通过真实消费项目 API、浏览器、OSS 和 CDN 运行。未配置隔离 OSS Bucket、CDN 或服务端测试凭据时，入口应在外部写入前失败；MinIO、mock signer、TestClient 或直接 SDK 上传均不能替代这些 oracle。

全部 RV 源码（runner、消费项目 API/页面、Playwright oracle 与配置）位于本目录的 `scripts/`，不得进入代码变更集。Playwright 依赖复用 `tests/playwright-e2e/node_modules`，由 runner 在 scripts 目录建立依赖链接。evidence manifest 位于 `evidence.json`；只记录环境变量名，不记录任何密钥值。

## Realistic Validation

| 项目 | 真实入口 | 必需证据 | negative control | 当前结果 |
|---|---|---|---|---|
| rv-1 浏览器直传 OSS | `just test-object-storage-e2e rv-1` | `rv-1-direct-upload.txt`；真实成功后还需浏览器网络记录和独立 OSS GET 摘要 | 真实 POST 超出 OSS policy 大小限制，应被 OSS 拒绝；之后允许的图片直传成功 | BLOCKED：隔离 OSS 配置和显式写入授权缺失，预检以 exit 3 结束；未执行负向对照 |
| rv-2 CDN 公开读取 | `just test-object-storage-e2e rv-2` | `rv-2-cdn-delivery.txt`；真实成功后还需 `rv-2-cdn-image.png` 与网络/缓存记录 | 上传 `Cache-Control=no-store` 的隔离对象并运行同一缓存断言，应被断言拒绝 | BLOCKED：OSS 与 CDN 配置缺失，预检以 exit 3 结束；未生成截图或执行负向对照 |
| rv-3 私有授权与过期 | `just test-object-storage-e2e rv-3` | `rv-3-private-expiry.txt`；真实成功后还需未授权拒绝、授权读取和过期 OSS 响应 | 先以未授权身份请求，再用新 HTTP client 重放已过期签名 URL | BLOCKED：隔离 OSS 配置和显式写入授权缺失，预检以 exit 3 结束；未执行负向对照 |

每条命令单独执行。配置补齐后按 rv-1、rv-2、rv-3 顺序运行；每项先观察负向对照失败，再记录正常路径通过，随后更新对应证据和 `evidence.json`。

## 本地门禁

| 命令 | 当前观察 |
|---|---|
| `just test` | PASS：提交 7a62d7c1 的修复树完成核心档与本地 OIDC 测试；分发过滤器另有五项定向测试通过 |
| `uv run python hooks/shared/check_architecture.py` | PASS |
| `just lint --reuse` | PASS |
| `just lint --full` | PASS：在测试 flag 更新后复跑 |
| `uv run mkdocs build` | PASS；有仓库现存导航警告 |
| `just test all` | FAIL：既有 admin 并发测试期望 `[200, 400]`，实际为 `[200, 200]`；定向复跑仍失败，本次未改其生产路径或测试 |

以上本地门禁不能替代 rv-1 至 rv-3。

## 环境负责人交接与恢复条件

当前阻塞需要在实际执行上述命令的 runner 进程环境中注入配置；仅在另一个终端 export 不会自动传给已运行的 runner。真实密钥由现有 secret 注入机制提供，不写入本计划、脚本、命令日志或聊天。

- OSS 连接：`OBJECT_STORAGE_E2E_ENDPOINT`、`OBJECT_STORAGE_E2E_REGION`、`OBJECT_STORAGE_E2E_BUCKET`。
- 服务端测试身份：`OBJECT_STORAGE_E2E_ACCESS_KEY_ID`、`OBJECT_STORAGE_E2E_ACCESS_KEY_SECRET`；限制到隔离测试前缀，允许实际上传、读取、HEAD 和清理所需操作。
- 写入确认：确认仅使用隔离测试 Bucket 后设置 `OBJECT_STORAGE_E2E_ALLOW_WRITES=1`。
- 公开交付：`OBJECT_STORAGE_E2E_CDN_BASE_URL`；CDN 只回源公开对象路径，按组件指南配置 CORS 和缓存观察头。

资源就绪后，由拥有该环境的执行者在工作区运行：

```bash
just test-object-storage-e2e rv-1
just test-object-storage-e2e rv-2
just test-object-storage-e2e rv-3
```

每条命令必须真实通过后才能更新该项为通过。接受条件仍包括真实负向对照、fresh 对象/HTTP 探测、rv-2 截图及网络/缓存证据；配置预检输出不满足这些条件。缺少资源时保留验证阻塞，由环境负责人接管，不再尝试源码补丁来改变命令退出结果。
