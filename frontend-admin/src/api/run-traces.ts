import { apiGet } from './client'

/** Canonical Run 状态：与后端 RunStatus 枚举一致。 */
export type RunStatus =
  | 'queued'
  | 'running'
  | 'cancelling'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'interrupted'

/** 轨迹可见性：full 表示有 tracing 事件，limited 表示历史 Run 能力受限。 */
export type TraceVisibility = 'full' | 'limited'

/** 节点类别：Run 根 / 模型 / 工具 / 产物。 */
export type TraceSpanKind = 'root' | 'model' | 'tool' | 'artifact'

/** 节点状态：running / completed / failed / incomplete。 */
export type TraceSpanStatus = 'running' | 'completed' | 'failed' | 'incomplete'

/** Run 级诊断摘要，对应后端 RunTraceSummaryResponse。 */
export type TraceSummary = {
  run_id: string
  subject_id: string
  subject_name: string
  owner_id: string
  status: RunStatus
  created_at: string
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  trace_id: string
  visibility: TraceVisibility
  model_call_count: number
  tool_call_count: number
  usage: Record<string, number> | null
  error_count: number
}

/** 执行轨迹中的单个节点，对应后端 RunTraceSpanResponse。 */
export type TraceSpan = {
  span_id: string
  parent_span_id: string | null
  kind: TraceSpanKind
  name: string
  status: TraceSpanStatus
  started_at: string | null
  finished_at: string | null
  duration_ms: number | null
  model_call_id: string | null
  model_name: string | null
  turn_index: number | null
  usage: Record<string, number> | null
  finish_reason: string | null
  tool_call_id: string | null
  tool_name: string | null
  result_checksum: string | null
  result_length: number | null
  error_code: string | null
  error_message: string | null
  diagnostics: string[]
}

/** 按父子关系嵌套的节点，对应后端 RunTraceTreeNodeResponse。 */
export type TraceTreeNode = {
  span: TraceSpan
  children: TraceTreeNode[]
}

/** 整棵轨迹上的稳定诊断项，对应后端 RunTraceDiagnosticResponse。 */
export type TraceDiagnostic = {
  code: string
  message: string
  span_id: string | null
}

/** 单个 Run 的完整诊断投影，对应后端 RunTraceDetailResponse。 */
export type TraceDetail = {
  summary: TraceSummary
  root_span_id: string | null
  spans: TraceSpan[]
  tree: TraceTreeNode[]
  diagnostics: TraceDiagnostic[]
  content_policy: string
}

/** 分页的 Run 诊断摘要列表，对应后端 RunTraceListResponse。 */
export type TraceListResponse = {
  items: TraceSummary[]
  total: number
  page: number
  page_size: number
}

/** 列表查询条件；字段为 undefined 时不发送对应 query 参数。 */
export type RunTraceListQuery = {
  runId?: string
  subjectId?: string
  status?: RunStatus
  createdAfter?: string
  createdBefore?: string
  page?: number
  pageSize?: number
}

/** 分页查询执行轨迹摘要列表（admin 权限）。 */
export function listRunTraces(query: RunTraceListQuery = {}): Promise<TraceListResponse> {
  return apiGet<TraceListResponse>('/admin/run-traces', {
    params: {
      run_id: query.runId,
      subject_id: query.subjectId,
      status: query.status,
      created_after: query.createdAfter,
      created_before: query.createdBefore,
      page: query.page,
      page_size: query.pageSize,
    },
  })
}

/** 读取单个 Run 的完整执行轨迹；Run 不存在时后端返回 404。 */
export function getRunTrace(runId: string): Promise<TraceDetail> {
  return apiGet<TraceDetail>(`/admin/run-traces/${encodeURIComponent(runId)}`)
}

/** 下载管理员可访问的单个 Run 原始事件文件。 */
export function downloadRunTrace(runId: string): Promise<Blob> {
  return apiGet<Blob>(`/admin/run-traces/${encodeURIComponent(runId)}/export`, {
    responseType: 'blob',
  })
}
