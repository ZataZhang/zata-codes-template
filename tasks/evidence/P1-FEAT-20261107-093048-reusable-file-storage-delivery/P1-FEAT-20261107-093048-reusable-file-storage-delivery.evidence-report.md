# 证据报告：可复用的对象存储与文件直传直取能力

## 人审导航

本次没有模板产品界面变化，也没有需要呈递的 CDN 页面。当前归档 PRD 已移除真实 CDN oracle；公开 CDN 真实回源与边缘缓存由消费项目部署后自验。本报告不声称真实 CDN 已验证。

Issue：[#59](https://github.com/ZataZhang/zata-codes-template/issues/59)。本轮交付树：worktree `issue-59`（从 `8959c4048` 恢复未改动的 S3 兼容 overlay，移除了 WIP 检查点误回退的 OSS adapter）。证据包在 `tasks/evidence/P1-FEAT-20261107-093048-reusable-file-storage-delivery/`，RV 脚本位于其 `scripts/` 且不进入代码提交。环境：zata-ops `test-minio`（`http://127.0.0.1:9000`）、隔离测试桶 `object-storage-e2e`。证据不包含服务端密钥或签名 URL query。

## Realistic Validation 与补充检查

### item 1：授权后浏览器直传（PRD oracle rv-1）

- 命令：`just test-object-storage-e2e rv-1`
- 证据：[rv-1-direct-upload.txt](rv-1-direct-upload.txt)
- 结果：PASS。Playwright Chromium 实际启动页面并发出浏览器请求：授权 API 200，超限 POST 到 MinIO 被拒绝（400），合法 POST 到 MinIO 返回 201，完成 API 200；新建 boto3 客户端 GET 的 SHA-256 与夹具一致。
- 负控：浏览器提交 65,537 字节正文超出 65,536 字节 policy，对象存储拒绝；随后 fresh boto3 HEAD 确认该对象不存在。

### item 2：公开上传缓存元数据与唯一对象键（补充 MinIO policy 检查）

- 命令：`OBJECT_STORAGE_E2E_ALLOW_WRITES=1 UV_CACHE_DIR=tasks/evidence/P1-FEAT-20261107-093048-reusable-file-storage-delivery/.uv-cache uv run --with boto3 python tasks/evidence/P1-FEAT-20261107-093048-reusable-file-storage-delivery/scripts/check_upload_post_policy_http.py`
- 证据：[rv-2-public-cache-policy.txt](rv-2-public-cache-policy.txt)
- 结果：真实消费 API、boto3 POST policy 与 MinIO 检查通过。未授权、PUT、超限、错误 Content-Type 和替换 key 均被拒绝；合法 POST 为 201，fresh boto3 GET 摘要匹配；policy 绑定 Cache-Control，连续授权生成不同对象键；本轮随机前缀已清理。
- 范围：这项只证明对象存储 policy/缓存元数据/唯一键行为。它不验证 CDN URL 构造、CDN 回源或边缘缓存；真实 CDN oracle 已从当前 PRD 移除。

### item 3：私有授权与预签名过期（PRD oracle rv-3）

- 命令：`just test-object-storage-e2e rv-3`
- 证据：[rv-3-private-expiry.txt](rv-3-private-expiry.txt)
- 结果：PASS。未授权读取 403 且无 URL；授权直读 MinIO 200 且 SHA-256 匹配；新 HTTP client 在签名过期后重放返回 403。
- 负控与正控均通过真实消费 API、boto3 presigner、隔离 MinIO 和 HTTP client 执行。

`evidence.json` 的 item_number 为顺序编号：1 对应 PRD rv-1；2 是公开缓存元数据/唯一键补充检查，不代表现行 PRD 的真实 CDN oracle；3 对应 PRD rv-3。该编号结构保留 runner 要求的三个证据块，同时明确当前 PRD 已移除真实 CDN 验收。

## 本轮检查结果

- `just test-object-storage-e2e rv-1`：PASS（浏览器页面与浏览器到 MinIO 请求均有记录）。
- `just test-object-storage-e2e rv-3`：PASS。
- `OBJECT_STORAGE_E2E_ALLOW_WRITES=1 UV_CACHE_DIR=... uv run --with boto3 python .../check_upload_post_policy_http.py`：PASS，实际运行的负控均被 MinIO 拒绝，合法上传成功，前缀清理完成。
- 运行后核对测试桶 `object-storage-e2e` 的对象清单为空，本轮未遗留持久对象。
- `kc evidence check --evidence tasks/evidence/P1-FEAT-20261107-093048-reusable-file-storage-delivery`：3/3 passed。
- 红→绿对照（证明 oracle 不是恒绿）：`run_real_s3_e2e.py rv-1 --mutant` 在测试侧篡改签名表单的 `key` 后合法 POST 变红（403）；`rv-3 --mutant` 用陌生人身份执行授权步骤后变红（403）；两者均非零退出，分别记录于 `rv-1-negative-control.txt` 与 `rv-3-negative-control.txt`。item 2 在同一命令内注入 PUT、超限、错误 Content-Type 与替换 key 五种红控。
- `just test`（含 `just lint --full`）、`uv run python hooks/shared/check_architecture.py`、分发契约测试在本轮通过；本轮的产品代码变更只有恢复 S3 实现与修正 e2e 入口。

## 尚未解决

- 独立 verifier 结论仍未形成；本报告是执行侧证据复跑记录，不替代 verifier 判定，也不勾选任何 Acceptance Checklist 或 Human-Confirmed 项。
- `just test-object-storage-e2e` 依赖 evidence 包（`tasks/evidence/<prd-stem>/scripts/`），该目录按约定不进入代码提交；干净检出需先取得证据包才能执行真实入口。入口在缺包时给出明确提示而非堆栈。
- 真实 CDN 与 Aliyun OSS S3 兼容端点仍不在本次验收范围，不得据本报告宣称已验证。
