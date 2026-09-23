import { useTranslation } from 'react-i18next'
import type { TraceDiagnostic, TraceSpan, TraceTreeNode } from '@/api/run-traces'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import {
  diagnosticLabel,
  formatDuration,
  formatTokenUsage,
  isParentFallbackCode,
  spanStatusLabel,
} from './run-tracing-shared'

/** 每种节点类别用于图标方块的缩写字母。 */
const SPAN_KIND_LETTERS: Record<TraceSpan['kind'], string> = {
  root: 'R',
  model: 'M',
  tool: 'T',
  artifact: 'A',
}

/** 子节点按层级递进的缩进 class，超出层级后保持最深一级。 */
const DEPTH_INDENT_CLASSES = ['ms-0', 'ms-6', 'ms-10', 'ms-14'] as const

/** 组装一个节点在标题下方展示的结构化事实。 */
function nodeFacts(span: TraceSpan, statusText: string): string[] {
  if (span.kind === 'root') {
    return [span.name, span.status]
  }
  const facts: string[] = [statusText]
  if (span.kind === 'model') {
    if (span.turn_index !== null) facts.push(`turn ${span.turn_index}`)
    if (span.model_name) facts.push(span.model_name)
    if (span.usage) facts.push(`${formatTokenUsage(span.usage)} token`)
    if (span.finish_reason) facts.push(span.finish_reason)
  } else if (span.kind === 'tool') {
    if (span.tool_name) facts.push(span.tool_name)
    if (span.result_length !== null) facts.push(`len ${span.result_length}`)
    if (span.result_checksum) facts.push(`sha ${span.result_checksum.slice(0, 8)}`)
  } else if (span.name) {
    facts.push(span.name)
  }
  return facts
}

/** 合并节点自身诊断与整棵轨迹上指向该节点的诊断，保持顺序去重。 */
function spanDiagnosticCodes(span: TraceSpan, diagnostics: TraceDiagnostic[]): string[] {
  const codes = [...span.diagnostics]
  for (const diagnostic of diagnostics) {
    if (diagnostic.span_id === span.span_id && !codes.includes(diagnostic.code)) {
      codes.push(diagnostic.code)
    }
  }
  return codes
}

/** 渲染单个执行轨迹节点及其子节点。 */
function TraceNode({
  node,
  diagnostics,
  depth,
}: {
  node: TraceTreeNode
  diagnostics: TraceDiagnostic[]
  depth: number
}) {
  const { t, i18n } = useTranslation()
  const { span } = node
  const codes = spanDiagnosticCodes(span, diagnostics)
  const hasParentFallback = codes.some(isParentFallbackCode)
  const isFailed = span.status === 'failed' || Boolean(span.error_code)
  const isRunning = span.status === 'running'
  const translate = (key: string): string => String(i18n.t(key))
  const facts = nodeFacts(span, spanStatusLabel(span.status, translate))

  return (
    <>
      <article
        data-testid={`trace-node-${span.span_id}`}
        className={cn(
          'relative grid grid-cols-[20px_minmax(0,1fr)_auto] items-start gap-3 rounded-lg border bg-card p-3',
          DEPTH_INDENT_CLASSES[Math.min(depth, DEPTH_INDENT_CLASSES.length - 1)],
          isFailed && 'border-red-200 bg-red-50/40',
          !isFailed && hasParentFallback && 'border-amber-200 bg-amber-50/40',
          !isFailed && !hasParentFallback && isRunning && 'border-blue-200'
        )}
      >
        <span
          aria-hidden='true'
          className={cn(
            'grid size-5 place-items-center rounded-md bg-indigo-50 text-[10px] font-extrabold text-indigo-600',
            isFailed && 'bg-red-100 text-red-600',
            !isFailed && hasParentFallback && 'bg-amber-100 text-amber-700'
          )}
        >
          {SPAN_KIND_LETTERS[span.kind]}
        </span>
        <div className='min-w-0'>
          <div className='flex flex-wrap items-center gap-2'>
            <strong className='text-sm font-semibold'>
              {span.kind === 'root' ? t('runTracing.nodeRunRoot') : span.name}
            </strong>
            {isRunning ? (
              <Badge variant='outline' className='border-blue-300 text-blue-700'>
                {t('runTracing.nodeStatusRunning')}
              </Badge>
            ) : null}
            {isFailed ? (
              <Badge variant='outline' className='border-red-300 text-red-700'>
                {t('runTracing.nodeStatusFailed')}
              </Badge>
            ) : null}
            {codes.map((code) => (
              <Badge
                key={code}
                variant='outline'
                className='border-amber-300 text-amber-700'
                data-testid={`trace-diagnostic-${span.span_id}-${code}`}
              >
                {t('runTracing.diagnosticBadge')}: {diagnosticLabel(code, translate)}
              </Badge>
            ))}
          </div>
          {facts.length > 0 ? (
            <div className='mt-1 text-xs text-muted-foreground'>{facts.join(' · ')}</div>
          ) : null}
          {hasParentFallback ? (
            <div className='mt-2 text-xs text-amber-800'>
              {t('runTracing.parentFallbackNote')}
            </div>
          ) : null}
          {isFailed ? (
            <div className='mt-2 text-xs text-red-800'>
              {t('runTracing.nodeErrorLabel')}: {span.error_code ?? span.status}
              {span.error_message ? ` · ${span.error_message}` : ''}
            </div>
          ) : null}
        </div>
        <span className='font-mono text-xs text-muted-foreground'>
          {formatDuration(span.duration_ms)}
        </span>
      </article>
      {node.children.map((child) => (
        <TraceNode
          key={child.span.span_id}
          node={child}
          diagnostics={diagnostics}
          depth={depth + 1}
        />
      ))}
    </>
  )
}

/**
 * 渲染执行轨迹节点树：以唯一 RUN ROOT 开始，模型与工具作为后代节点。
 *
 * @param props - 嵌套节点树和整棵轨迹的诊断列表。
 */
export function TraceTree({
  tree,
  diagnostics,
}: {
  tree: TraceTreeNode[]
  diagnostics: TraceDiagnostic[]
}) {
  return (
    <div className='mt-3 space-y-2.5'>
      {tree.map((node) => (
        <TraceNode
          key={node.span.span_id}
          node={node}
          diagnostics={diagnostics}
          depth={0}
        />
      ))}
    </div>
  )
}
