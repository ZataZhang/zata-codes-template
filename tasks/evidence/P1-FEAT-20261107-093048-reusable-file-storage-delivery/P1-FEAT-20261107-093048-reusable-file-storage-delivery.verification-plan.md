# 验证计划：可复用的对象存储与文件直传直取能力

## 验证边界

行为 oracle 通过真实消费项目 API、Playwright 浏览器和真实 S3 兼容对象存储（本机 zata-ops MinIO）运行。adapter 使用 boto3 预签名 POST/GET；不使用 mock signer、TestClient 或直接 SDK 上传替代。

全部 RV 源码（runner、消费项目 API/页面、Playwright oracle 与配置）位于本目录的 `scripts/`，不进入代码变更集。Playwright 依赖复用 `tests/playwright-e2e/node_modules`。evidence manifest 位于 `evidence.json`；只记录环境变量名，不记录密钥值。

## Realistic Validation

| 项目 | 真实入口 | 必需证据 | negative control | 当前结果 |
|---|---|---|---|---|
| rv-1 浏览器直传 S3 兼容存储 | `just test-object-storage-e2e rv-1` | `rv-1-direct-upload.txt`；浏览器网络记录与 fresh boto3 GET 摘要 | 65,537 字节 POST 对抗 65,536 字节 policy，应被 MinIO 拒绝；随后允许的图片直传成功 | PASS：超限 400、对象不存在、合法 201、摘要匹配 |
| rv-3 私有授权与过期 | `just test-object-storage-e2e rv-3` | `rv-3-private-expiry.txt`；未授权拒绝、授权直读和过期拒绝 | 未授权身份请求；过期后用 fresh HTTP client 重放同一 URL | PASS：未授权 403 无 URL、授权 200、过期 403 |

`rv-2`（真实 CDN 回源/缓存）已从本 PRD 移除；CDN 只交付公开 URL 构造代码与缓存元数据文档，由消费项目部署后自验。

## 环境

- 本机 MinIO：`http://127.0.0.1:9000`（zata-ops `test-minio`），默认测试凭据仅用于 loopback。
- 测试桶：`object-storage-e2e`；runner 在 `OBJECT_STORAGE_E2E_ALLOW_WRITES=1` 下可创建缺失桶。
- 每轮随机前缀 `issue-59-e2e/<uuid>`；成功或失败后清理该前缀对象。
- 生产/非 loopback 必须使用 HTTPS；`allow_insecure_http` 默认 false。

## 本地门禁

| 命令 | 当前观察 |
|---|---|
| `just test` | PASS：核心档 `544 passed, 1 skipped`；本地 OIDC `17 passed` |
| `uv run python hooks/shared/check_architecture.py` | PASS |
| `just lint --full` | PASS（staged tree 一致后） |
| `just lint --reuse` | PASS |
| `just test-object-storage-e2e` | PASS：rv-1、rv-3 |
| 测试桶前缀清理 | PASS：残留对象 0 |

以上本地门禁与执行者自测不能替代独立 verifier 复核；§9 非人工项留给 verifier 在最终代码树上勾选。
