# 证据报告：可复用的对象存储与文件直传直取能力

## 人审导航 / Human Review Navigation

| 人要确认的结果 | 呈递物与打开方式 | 自查期望 | 当前状态 |
|---|---|---|---|
| 本次没有模板产品界面或 CDN 呈现项 | §9.1 说明；CDN 只交付 URL 构造代码与缓存元数据文档 | 确认没有需要人读的界面截图或 CDN 网络证据 | 无需呈递 |

Issue：[#59](https://github.com/ZataZhang/zata-codes-template/issues/59)。本次没有产品 UI 变更；rv-1/rv-3 使用验证用消费页，不是产品原型。真实 CDN 与 Aliyun OSS S3 兼容端点不在本次验收范围。

## Realistic Validation 结果（2026-11-16，本机 MinIO）

运行环境：zata-ops `test-minio`（`minio/minio:RELEASE.2025-09-07T16-13-09Z`，`http://127.0.0.1:9000`），隔离测试桶 `object-storage-e2e`，随机对象前缀 `issue-59-e2e/<uuid>`，`OBJECT_STORAGE_E2E_ALLOW_WRITES=1`。runner 为本机 loopback 提供默认 endpoint/region/bucket/测试凭据；未使用 mock。

### rv-1：授权后浏览器直传 S3 兼容对象存储

- 命令：`just test-object-storage-e2e rv-1`
- 证据：[rv-1-direct-upload.txt](rv-1-direct-upload.txt)
- 结果：PASS。
  - 负向对照：65,537 字节浏览器 POST 超过签名中的 65,536 字节 policy，MinIO 返回 HTTP 400；fresh boto3 HEAD 确认对象不存在。
  - 正向：允许的 PNG 直传返回 201；API 授权响应不含文件正文；fresh boto3 GET 的 SHA-256 为 `1197db0305fd9d7841ab1298306276da18432b1317acbfdd635c8675f52ccbb1`。
  - 网络记录：`POST 127.0.0.1:9000/object-storage-e2e 201`；API 请求停留在临时 fixture 端口，仅返回小型 JSON。
- 结论：浏览器直传、API 正文边界和独立对象读取均已在真实 S3 兼容服务上观测。

### rv-3：私有授权与预签名过期

- 命令：`just test-object-storage-e2e rv-3`
- 证据：[rv-3-private-expiry.txt](rv-3-private-expiry.txt)
- 结果：PASS。
  - 负向对照：intruder 身份请求私有读取返回 403，响应无 URL。
  - 正向：owner 获得 6 秒预签名 URL，直接 GET MinIO 返回 200，SHA-256 与 fixture 一致。
  - 过期：fresh HTTP client 在过期后重放同一 URL 返回 403。
- 结论：项目授权、直读对象存储和过期拒绝均已观测；对象正文未经过应用 API。

## 本地门禁与清理

- PASS：`just test` → 核心档 `544 passed, 1 skipped`；本地 OIDC 包 `17 passed`。
- PASS：`uv run python hooks/shared/check_architecture.py` → 架构依赖方向全部合法。
- PASS：`just lint --full` / `just lint --reuse`（staged tree 一致后运行）。
- PASS：`just test-object-storage-e2e` 全量运行 rv-1、rv-3。
- PASS：测试桶 `issue-59-e2e/` 前缀清理后残留对象数为 0。

## 分发与范围

- `just test` 包含 `tests/test_project_capabilities_distribution.py`，确认 `project-capabilities/` 不进入 Skill 安装候选与派生项目副本；本轮没有修改分发逻辑。
- 全部 RV 源码（runner、消费 API/页面、Playwright oracle）位于本 evidence 包的 `scripts/`，不进入代码提交。
- 删除 rv-2 后，真实 CDN 回源、边缘缓存与截图不再是本 PRD 的验收项；Aliyun OSS S3 兼容端点因 boto3 SigV2 限制也未在本轮验证，均记录为后续项。

## 待独立复核

本报告记录执行者自测结果；§9 非人工项仍留给独立 verifier 复核后在最终代码树上勾选。runner 重新触发后会再次执行 rv-1、rv-3 并把证据绑定到提交树。
