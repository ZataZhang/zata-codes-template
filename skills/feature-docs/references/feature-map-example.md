# 功能代码地图示例

以下是虚构的小型导出功能，仅示范写作深度与证据形式；路径、符号和命令不是目标仓库事实。
实际交付必须从目标源码重新确认，优先沿用其模板，不复制本例业务约定。

## 报表导出

用户提交导出请求并轮询状态，成功后下载文件。

### 入口与执行链

`POST /exports` → `api/exports.py:create_export` 校验登录与请求格式 →
`core/exports.py:ExportService.submit` 创建 pending 记录并入队 →
`workers/export_job.py:run_export` 读取记录、生成文件、保存结果 →
`GET /exports/{id}` 经 `ExportService.get` 校验归属后返回状态。

生成失败由 `run_export` 捕获并保存 failed；下载接口仅允许读取成功且属于当前用户的任务。
这里的依据分别是 `run_export` 的异常分支和 `ExportService.download` 的权限、状态检查。
队列服务断连时请求最终返回什么，需要检查入队异常如何被处理，不能从这条成功链推断。

### 契约与修改提示

| 要改什么 | 实现依据 | 影响及验证 |
|---|---|---|
| 单次导出条数上限 | `core/exports.py:ExportService.submit` 读取 `export.max_rows` | 核对配置默认值、请求拒绝边界；运行 `tests/test_exports.py::test_row_limit` |
| 下载授权 | `core/exports.py:ExportService.download` | 覆盖其他用户访问、未完成与文件失效分支；核对下载路由是否复用此方法 |

队列配置链接配置指南，持久化字段链接 schema 说明；本页只解释它们在执行链中的作用。
源码显示当前失败后没有自动重试，不能因为状态枚举有 retrying 就写“支持自动重试”。

### 验证与限制

本文列出的测试是后续修改的验证入口。本次仅完成源码核对与文档链接检查，未运行测试或启动
队列，因此未验证部署环境与外部队列实际行为。不能把文档构建通过写成导出功能验收通过。
