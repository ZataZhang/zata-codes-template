# 验证计划：可复用的对象存储与文件直传直取能力

## 验证边界

当前归档 PRD 的 Realistic Validation oracle 为 rv-1（浏览器直传）和 rv-3（私有授权/过期）。真实 CDN oracle rv-2 已按 PRD Change Log 移除。item 2 在 manifest 中作为公开上传缓存元数据与唯一键的补充 MinIO 检查，不宣称真实 CDN 验证。

所有 RV runner、consumer fixture、浏览器 oracle、临时设置和补充检查均在 `scripts/` 下，且不进入代码变更集。manifest 在 `evidence.json`；证据文件名按 `item_number` 编号，证据只关联对应检查输出。

## 检查项

| 项目 | 命令 | 证据 | negative control / 结果 |
|---|---|---|---|
| item 1 / PRD rv-1 浏览器直传 | `just test-object-storage-e2e rv-1` | `rv-1-direct-upload.txt` | 浏览器负控因 Chromium 在页面启动前退出而未执行；该项保持阻塞，无浏览器请求证据 |
| item 2 / 补充缓存元数据与唯一 key 检查 | `OBJECT_STORAGE_E2E_ALLOW_WRITES=1 UV_CACHE_DIR=tasks/evidence/P1-FEAT-20261107-093048-reusable-file-storage-delivery/.uv-cache uv run --with boto3 python tasks/evidence/P1-FEAT-20261107-093048-reusable-file-storage-delivery/scripts/check_upload_post_policy_http.py` | `rv-2-public-cache-policy.txt` | 未授权、PUT、超限、Content-Type 和替换 key 的请求实际被拒绝；合法上传 201、fresh GET 摘要一致。只验证 MinIO policy，不验证真实 CDN |
| item 3 / PRD rv-3 私有授权与过期 | `just test-object-storage-e2e rv-3` | `rv-3-private-expiry.txt` | 未授权请求无 URL 且返回 403；授权 GET 200；过期后新 HTTP client GET 403 |

## 环境与限制

- MinIO：`http://127.0.0.1:9000`，测试桶 `object-storage-e2e`，仅 loopback 测试。
- rv-1/rv-3 使用真实消费 API 与 MinIO；不 mock signer 或 object store。
- item 2 是补充的真实 API/MinIO 检查。当前 PRD 不要求真实 CDN 域名、回源或边缘缓存，不能据此宣称 CDN 已验证。
- rv-1 仍需一个允许 Chromium 完成 macOS Mach/bootstrap 注册的运行环境。
