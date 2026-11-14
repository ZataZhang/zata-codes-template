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
| `just test` | PASS：核心测试 542 passed、1 skipped；本地 OIDC 17 passed |
| `uv run python hooks/shared/check_architecture.py` | PASS |
| `just lint --reuse` | PASS |
| `just lint --full` | PASS：在测试 flag 更新后复跑 |
| `uv run mkdocs build` | PASS；有仓库现存导航警告 |
| `just test all` | FAIL：既有 admin 并发测试期望 `[200, 400]`，实际为 `[200, 200]`；定向复跑仍失败，本次未改其生产路径或测试 |

以上本地门禁不能替代 rv-1 至 rv-3。
