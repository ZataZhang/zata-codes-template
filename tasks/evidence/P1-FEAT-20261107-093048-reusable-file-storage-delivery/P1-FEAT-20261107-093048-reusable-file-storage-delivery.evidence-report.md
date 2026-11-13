## 人审导航 / Human Review Navigation

| 人要确认的结果 | 呈递物与打开方式 | 自查期望 | 当前状态 |
|---|---|---|---|
| 集成页显示通过 CDN 加载的公开图片，重复读取遵守缓存策略 | 预期文件：`tasks/evidence/P1-FEAT-20261107-093048-reusable-file-storage-delivery/rv-2-cdn-image.png`；真实验证未运行，因此文件不存在。当前可查看 [rv-2 阻塞输出](rv-2-cdn-delivery.txt)，命令：`cat tasks/evidence/P1-FEAT-20261107-093048-reusable-file-storage-delivery/rv-2-cdn-delivery.txt`；配置隔离环境后运行 `just test-object-storage-e2e rv-2` | 成功证据必须显示图片可见、浏览器请求 host 为配置 CDN、正文摘要匹配 OSS，响应包含不可变缓存策略且第二次读取命中缓存 | BLOCKED：缺少隔离 OSS/CDN 配置；没有伪造截图、网络记录或缓存结果 |

Issue：[#59](https://github.com/ZataZhang/zata-codes-template/issues/59)。当前没有 PR 或 CI 链接。执行者已核对：模板没有产品 UI 变更；rv-2 是验证用消费页，不是产品原型。真实图片呈现仍未验证。

## Realistic Validation 结果

### rv-1：授权后浏览器直传 OSS

- 命令：`just test-object-storage-e2e rv-1`
- 证据：[rv-1-direct-upload.txt](rv-1-direct-upload.txt)
- 结果：BLOCKED，退出码 3。预检缺少 `OBJECT_STORAGE_E2E_ENDPOINT`、`OBJECT_STORAGE_E2E_REGION`、`OBJECT_STORAGE_E2E_BUCKET`、服务端测试凭据和 `OBJECT_STORAGE_E2E_ALLOW_WRITES=1`，没有访问外部服务。
- 负向对照：未执行；隔离 OSS 配置缺失。预期超出 policy 大小的真实 POST 被 OSS 拒绝，当前未观测。
- 结论：未证明浏览器直传、API 正文边界或独立 OSS GET 摘要。

### rv-2：CDN 公开读取与缓存

- 命令：`just test-object-storage-e2e rv-2`
- 证据：[rv-2-cdn-delivery.txt](rv-2-cdn-delivery.txt)
- 结果：BLOCKED，退出码 3。除隔离 OSS 配置外，缺少 `OBJECT_STORAGE_E2E_CDN_BASE_URL`；没有访问外部服务，也没有生成截图或网络记录。
- 负向对照：未执行；隔离 OSS/CDN 配置缺失。预期错误缓存策略对象被 CDN 缓存断言拒绝，当前未观测。
- 结论：未证明 CDN host、对象摘要、缓存头、重复读取命中或图片呈现。

### rv-3：私有授权与签名过期

- 命令：`just test-object-storage-e2e rv-3`
- 证据：[rv-3-private-expiry.txt](rv-3-private-expiry.txt)
- 结果：BLOCKED，退出码 3。预检缺少隔离 OSS 配置和 `OBJECT_STORAGE_E2E_ALLOW_WRITES=1`，没有访问外部服务。
- 负向对照：未执行；隔离 OSS 配置缺失。预期未授权请求不返回 URL，已过期 URL 的真实 OSS GET 被拒绝，当前未观测。
- 结论：未证明授权、直读或过期行为。

## 本地门禁与限制

2026-11-13 在最终代码树上复跑：

- PASS：`uv run pytest tests/guards -q` → `598 passed in 44.74s`（含新增两条分发守卫）。
- PASS：`uv run python hooks/shared/check_architecture.py` → `架构依赖方向全部合法，无违规。`
- PASS：`uv run mkdocs build` → `Documentation built in 4.81 seconds`；`--strict` 仍被仓库既有的未导航页面/锚点警告阻断，非本次新增。
- PASS：`GUARD_UPDATE_ACK=1 just lint --full` → 全部 hook `Passed`，退出码 0。不设置该变量时仅 `check-guard-test-modification` 拦截，因为本次按任务要求新增了守卫测试文件；这不是代码质量问题。
- FAIL（既有）：`just test all` 中 `test_admin_api_rejects_disabling_the_last_enabled_platform_admin` 并发测试复跑仍得到 `[200, 200]` 而不是 `[200, 400]`。该路径未由本次变更触及。
- PASS（本次真实执行）：`just copy /tmp/issue59-copy2` 退出码 0，完成 rsync、pre-commit 安装、迁移与初始提交。
- 本次自审发现并修复一个分发缺陷：模板专用守卫 `tests/guards/test_project_capabilities_distribution.py` 会被 `just copy` 复制到派生项目，而派生项目既没有 `project-capabilities/`，也没有 copy recipe 的排除行，导致派生项目测试必红。已将该守卫加入 `just copy` 排除名单，并让 `sync_template.sh` 的 `--all` 候选同样跳过它。

## 分发验证（本次真实执行）

```text
$ just copy /tmp/issue59-copy2
... copy_exit=0

$ test ! -e /tmp/issue59-copy2/project-capabilities && echo no_capabilities
no_capabilities

$ test ! -e /tmp/issue59-copy2/tests/guards/test_project_capabilities_distribution.py && echo no_template_guard
no_template_guard

$ grep -c "project-capabilities" /tmp/issue59-copy2/justfile
0

$ ./scripts/sync_template.sh --list-all | grep -c "project-capabilities"
0

$ cd /tmp/issue59-copy2 && uv run pytest tests/guards -q
1 failed, 487 passed in 45.65s
```

派生项目里唯一的失败是仓库既有问题：`tests/guards/test_local_core_tier_budget.py` 指向的 `tests/core_set.txt` 仍包含被 `just copy` 排除的 `tests/guards/test_prd_skill_checker.py`，与本次能力包无关，也不是本次引入。新增守卫已不再在派生项目中出现。

`just sync-local-skills` 只从根级 `skills/` 扫描 Skill，`project-capabilities/` 不在扫描路径；本次未执行安装命令（会写入本机 agent Skill 目录），由静态守卫 `tests/guards/test_project_capabilities_distribution.py` 与 `tests/guards/shared/test_sync_template_skips_project_capabilities.py` 固定该边界。

## 恢复尝试 1/5：门禁复跑仍失败（2026-11-13 22:43 CST）

最终代码树 `6a3a315144ff0e4f60fcc39a1e2a672631cee083`（上一轮已提交）。keda 用同一命令复跑三条 RV，结果与本报告一致：

```text
$ just test-object-storage-e2e rv-1   # exit 3
BLOCKED: rv-1 未访问外部服务。
缺少配置名: OBJECT_STORAGE_E2E_ENDPOINT, OBJECT_STORAGE_E2E_REGION,
OBJECT_STORAGE_E2E_BUCKET, OBJECT_STORAGE_E2E_ACCESS_KEY_ID,
OBJECT_STORAGE_E2E_ACCESS_KEY_SECRET, OBJECT_STORAGE_E2E_ALLOW_WRITES

$ just test-object-storage-e2e rv-2   # exit 3
（同上，另缺 OBJECT_STORAGE_E2E_CDN_BASE_URL）

$ just test-object-storage-e2e rv-3   # exit 3
（同 rv-1）
```

这不是代码回归，也不是可以靠改命令绕过的断言问题：本机只有 `~/.kedacode/config.toml` 指向的本地 MinIO（`test-minio`，`localhost:9000`，S3 协议）与仓库里的 `S3_*` 备份配置，没有任何阿里云 OSS 凭据、隔离 Bucket 或 CDN 测试域名。PRD 明确禁止用 MinIO、mock 签名器或直接 SDK 上传替代这些 oracle；Aliyun OSS 的 PostObject 签名（`OSSAccessKeyId` / `policy` / `Signature`）与 S3 POST policy 不兼容，MinIO 跑通也不能证明本 adapter 可用。

因此三条命令在缺失资源时**必须**以 exit 3 停止；把它们改成 exit 0 或在断言里吞掉失败，属于伪造证据，本次不做。要真正转绿，需要人类提供下列资源后按顺序复跑：

```bash
export OBJECT_STORAGE_E2E_ENDPOINT=https://oss-cn-<region>.aliyuncs.com
export OBJECT_STORAGE_E2E_REGION=<region>
export OBJECT_STORAGE_E2E_BUCKET=<isolated-test-bucket>
export OBJECT_STORAGE_E2E_ACCESS_KEY_ID=<test-ram-access-key-id>
export OBJECT_STORAGE_E2E_ACCESS_KEY_SECRET=<test-ram-access-key-secret>
export OBJECT_STORAGE_E2E_CDN_BASE_URL=https://<cdn-test-domain>   # rv-2 需要
export OBJECT_STORAGE_E2E_ALLOW_WRITES=1                            # 确认 Bucket 为隔离测试资源
just test-object-storage-e2e rv-1 && just test-object-storage-e2e rv-2 && just test-object-storage-e2e rv-3
```

Bucket 需保持私有、配置最小 CORS（允许 `http://127.0.0.1:19777` 的 `POST`/`GET`，暴露 `ETag`、`Cache-Control`），CDN 只回源公开路径。凭据只经环境变量传入，不写入本目录任何文件。

## 验证脚本冒烟（不构成 RV 证据）

用**无效凭据**与不存在的 Bucket 运行 `just test-object-storage-e2e rv-1`，确认 runner 能启动消费项目 API、加载 fixture 页面、签发授权表单，并由真实浏览器向 OSS 派生主机发起跨域 POST；浏览器在 `fetch` 处失败（`TypeError: Failed to fetch`，无 CORS/无效身份），未写入任何对象。该冒烟只证明验证链路可运行到 OSS 网络边界，**不能**替代 rv-1，也未写入证据文件。冒烟产生的临时输出已清理，`rv-1-direct-upload.txt` 已恢复为阻塞记录。

本报告没有把本地静态门禁或真实入口的配置预检表述为 OSS/CDN 行为通过。待隔离环境配置后，按验证计划执行负向对照和正向路径，再更新这份报告与 §9。

## 验证脚本静态检查

- Playwright `--list` 成功发现 3 条 oracle；未连接 OSS/CDN。
- TypeScript `tsc --noEmit --strict` 检查两个 evidence 脚本通过。
- 对 overlay、消费 fixture 和新增 guards 执行 `ruff check` 与 `ruff format --check` 均通过。
- 自审发现 rv-1/rv-2 的结果 JSON 未包含 fresh OSS SHA-256 对照值；已修复脚本并重新逐项运行三个入口。每次仍因真实隔离配置缺失在网络前阻塞。
