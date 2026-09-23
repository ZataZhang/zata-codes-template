import type { RunStatus, TraceSpanStatus, TraceSummary } from '@/api/run-traces'

/** React Query cache key shared by the Run list and the selected-run detail. */
export const RUN_TRACE_QUERY_KEY = ['admin', 'run-traces'] as const

/** 后端已知诊断 code 到根级 i18n key 的映射；未知 code 直接展示原始 code。 */
export const DIAGNOSTIC_CODE_I18N_KEYS: Record<string, string> = {
  parent_source_unavailable: 'runTracing.diagnostic.parentSourceUnavailable',
  unknown_parent: 'runTracing.diagnostic.unknownParent',
  self_parent: 'runTracing.diagnostic.selfParent',
  cyclic_parent: 'runTracing.diagnostic.cyclicParent',
  started_without_completion: 'runTracing.diagnostic.startedWithoutCompletion',
  completion_without_start: 'runTracing.diagnostic.completionWithoutStart',
  duplicate_completion: 'runTracing.diagnostic.duplicateCompletion',
  missing_span_id: 'runTracing.diagnostic.missingSpanId',
  no_tracing_events: 'runTracing.diagnostic.noTracingEvents',
}

/** 需要提示“父级来源不可确认，已挂到 Run 根节点”的 fallback code。 */
const PARENT_FALLBACK_CODES = new Set([
  'parent_source_unavailable',
  'unknown_parent',
  'self_parent',
  'cyclic_parent',
])

/** 已终结的 Run 状态：只有这些状态的 Run 事件流不再变化，可以整份下载。 */
const TERMINAL_RUN_STATUSES = new Set<RunStatus>([
  'succeeded',
  'failed',
  'cancelled',
  'interrupted',
])

/** 节点状态到根级 i18n label key 的映射。 */
const SPAN_STATUS_I18N_KEYS: Record<TraceSpanStatus, string> = {
  running: 'runTracing.nodeStatusRunning',
  completed: 'runTracing.nodeStatusCompleted',
  failed: 'runTracing.nodeStatusFailed',
  incomplete: 'runTracing.nodeStatusIncomplete',
}

/** Run 状态到根级 i18n label key 的映射。 */
const RUN_STATUS_I18N_KEYS: Record<RunStatus, string> = {
  queued: 'runTracing.statusQueued',
  running: 'runTracing.statusRunning',
  cancelling: 'runTracing.statusCancelling',
  succeeded: 'runTracing.statusSucceeded',
  failed: 'runTracing.statusFailed',
  cancelled: 'runTracing.statusCancelled',
  interrupted: 'runTracing.statusInterrupted',
}

/**
 * 在当前语言下渲染诊断 code；未知 code 回退为原始 code，保证页面不崩。
 *
 * @param code - 后端返回的稳定诊断 code。
 * @param translate - i18n 翻译函数。
 * @returns 可直接展示的诊断文案。
 */
export function diagnosticLabel(code: string, translate: (key: string) => string): string {
  const i18nKey = DIAGNOSTIC_CODE_I18N_KEYS[code]
  return i18nKey ? translate(i18nKey) : code
}

/**
 * 判断诊断 code 是否属于父级来源不可信、已挂到 Run 根节点的情况。
 *
 * @param code - 后端返回的稳定诊断 code。
 * @returns 属于父级 fallback 时为 true。
 */
export function isParentFallbackCode(code: string): boolean {
  return PARENT_FALLBACK_CODES.has(code)
}

/**
 * 判断 Run 是否受历史能力限制（没有 tracing 事件，不应伪造根节点）。
 *
 * @param summary - Run 级摘要。
 * @returns visibility 为 limited 时为 true。
 */
export function isLimitedVisibility(summary: TraceSummary): boolean {
  return summary.visibility === 'limited'
}

/**
 * 判断 Run 是否已终结。
 *
 * @param status - Canonical Run 状态。
 * @returns 已终结时为 true。
 */
export function isTerminalRunStatus(status: RunStatus): boolean {
  return TERMINAL_RUN_STATUSES.has(status)
}

/**
 * 节点状态在当前语言下的展示文案。
 *
 * @param status - 单节点状态。
 * @param translate - i18n 翻译函数。
 * @returns 节点状态展示文案。
 */
export function spanStatusLabel(
  status: TraceSpanStatus,
  translate: (key: string) => string
): string {
  return translate(SPAN_STATUS_I18N_KEYS[status])
}

/**
 * Run 状态在当前语言下的展示文案。
 *
 * @param status - Canonical Run 状态。
 * @param translate - i18n 翻译函数。
 * @returns 状态展示文案。
 */
export function runStatusLabel(status: RunStatus, translate: (key: string) => string): string {
  return translate(RUN_STATUS_I18N_KEYS[status])
}

/**
 * 节点耗时展示：毫秒级保留 ms，秒级保留一位小数，未知返回占位符。
 *
 * @param durationMs - 已确认耗时（毫秒），可能为空。
 * @returns 如 `820ms` / `12.4s` / `—`。
 */
export function formatDuration(durationMs: number | null): string {
  if (durationMs === null) return '—'
  if (durationMs < 1000) return `${durationMs}ms`
  return `${(durationMs / 1000).toFixed(1)}s`
}

/**
 * 低敏 usage 汇总展示：优先取 total，无 usage 时返回占位符。
 *
 * @param usage - 低敏 usage 计数，可能为空。
 * @returns 千分位 token 数或 `—`。
 */
export function formatTokenUsage(usage: Record<string, number> | null): string {
  const totalTokens = usage?.total
  if (totalTokens === undefined) return '—'
  return totalTokens.toLocaleString('en-US')
}

/**
 * ISO 8601 时间点的展示文案，保持浏览器本地时区。
 *
 * @param isoMoment - ISO 8601 时间字符串，可能为空。
 * @returns 如 `09-21 16:42`，未知时间返回占位符。
 */
export function formatTraceTime(isoMoment: string | null): string {
  if (!isoMoment) return '—'
  const parsed = new Date(isoMoment)
  if (Number.isNaN(parsed.getTime())) return '—'
  return parsed.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}
