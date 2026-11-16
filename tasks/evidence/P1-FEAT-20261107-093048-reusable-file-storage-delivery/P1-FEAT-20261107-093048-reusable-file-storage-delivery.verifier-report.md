# Pre-PR 审查报告：可复用的对象存储与文件直传直取能力

## 状态

**VERDICT: 待独立 verifier 复核** — 执行者已完成 S3/MinIO 改写的自测；本文件不是独立验证 PASS。

## 验收视图

交付边界是按需复制的 core 契约、S3 兼容 adapter（boto3）、配置装配与模板分发规则。消费项目拥有领域授权与对象引用；普通文件字节由浏览器直接传给 S3 兼容对象存储；不新增模板产品路由、ORM 或页面。CDN 只保留公开 URL 构造与缓存元数据文档，不再作为本轮验收项。

## 本轮审查与修复

- [HIGH][scope] 原 PRD 依赖阿里云 OSS/CDN 真实环境，runner 连续因缺少隔离凭据在 rv-1/2/3 预检 exit 3。已按用户决定切换为 S3 兼容 boto3 + zata-ops MinIO，并删除 rv-2（真实 CDN 验收）。
- [HIGH][implementation] overlay 从 `oss2` PostObject 改为 boto3 `generate_presigned_post` / `generate_presigned_url`；core 契约不变。配置 provider 改为 `s3`，新增 `addressing_style` 与默认关闭的 loopback `allow_insecure_http`。
- [MEDIUM][validation] rv-1/rv-3 已在真实 MinIO 上通过，包含超限负控、API 正文边界、fresh boto3 摘要与过期 403；证据位于本目录。
- [MEDIUM][docs] README、接入指南、配置示例、SKILL 路由与分发说明同步为 S3/MinIO；Aliyun OSS S3 兼容端点记录为未验证后续项。

## 代码审查

已阅读 core 契约、S3 预签名适配、配置校验、composition、消费 fixture、Playwright oracle 与分发规则。未发现新的高置信度产品代码缺陷。服务端 Secret 只从环境读取，bearer grant 的 `repr` 已隐藏，普通 API 不转发对象正文。

## 本地门禁

- `just test`：PASS（核心档 544 passed, 1 skipped；OIDC 17 passed）。
- `uv run python hooks/shared/check_architecture.py`：PASS。
- `just lint --full` / `just lint --reuse`：PASS（staged tree 一致后）。
- `just test-object-storage-e2e`：PASS（rv-1、rv-3）。
- 测试桶清理：残留对象 0。

## 结论

执行者侧实现与真实验证已完成，但仍需独立 verifier 在最终提交树上复核并给出 PASS；在此之前不勾选 §9 非人工项，也不宣称人工验收完成。runner 重新触发后会再次执行 RV 并生成新的 verifier 结论。
