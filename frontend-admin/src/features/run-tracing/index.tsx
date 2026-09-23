import { useMemo, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Download, RefreshCw, Search } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  downloadRunTrace,
  getRunTrace,
  listRunTraces,
  type RunStatus,
  type TraceDetail,
  type TraceSummary,
} from '@/api/run-traces'
import { cn } from '@/lib/utils'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import {
  RUN_TRACE_QUERY_KEY,
  diagnosticLabel,
  formatDuration,
  formatTokenUsage,
  formatTraceTime,
  isLimitedVisibility,
  isTerminalRunStatus,
  runStatusLabel,
} from './run-tracing-shared'
import { TraceTree } from './trace-tree'

/** 列表状态筛选值：legacy 表示历史受限的 visibility，而非 Run 状态。 */
type TraceStatusFilter = 'all' | 'succeeded' | 'failed' | 'running' | 'legacy'

/** 时间范围筛选值。 */
type TraceTimeRange = '24h' | '7d'

/** 状态圆点的颜色分类。 */
type TraceStatusTone = 'success' | 'failed' | 'running' | 'muted'

/**
 * 把 Run 状态收敛为列表圆点与标签使用的四种色调。
 *
 * @param status - Canonical Run 状态。
 * @returns 圆点色调。
 */
function runStatusTone(status: RunStatus): TraceStatusTone {
  if (status === 'succeeded') return 'success'
  if (status === 'failed') return 'failed'
  if (status === 'running' || status === 'queued' || status === 'cancelling') return 'running'
  return 'muted'
}

/** 列表行左侧的状态圆点。 */
function RunStatusDot({ tone }: { tone: TraceStatusTone }) {
  return (
    <span
      aria-hidden='true'
      data-tone={tone}
      className={cn(
        'mt-1.5 size-2 rounded-full bg-emerald-500',
        tone === 'failed' && 'bg-red-500',
        tone === 'running' && 'bg-blue-500',
        tone === 'muted' && 'bg-gray-400'
      )}
    />
  )
}

/** 渲染左侧「最近 Runs」列表中的一行。 */
function RunListRow({
  summary,
  active,
  onSelect,
}: {
  summary: TraceSummary
  active: boolean
  onSelect: () => void
}) {
  const { t } = useTranslation()
  const limited = isLimitedVisibility(summary)
  const statusText = limited
    ? t('runTracing.statusLegacy')
    : runStatusLabel(summary.status, (key) => String(t(key)))

  return (
    <button
      type='button'
      data-testid={`run-row-${summary.run_id}`}
      aria-current={active ? 'true' : undefined}
      onClick={onSelect}
      className={cn(
        'grid w-full grid-cols-[10px_minmax(0,1fr)_auto] gap-2.5 rounded-lg border border-transparent p-3 text-left',
        'hover:border-border hover:bg-card focus-visible:border-border focus-visible:bg-card focus-visible:outline-none',
        active && 'border-border bg-card shadow-sm'
      )}
    >
      <RunStatusDot tone={limited ? 'muted' : runStatusTone(summary.status)} />
      <span className='min-w-0'>
        <strong className='block truncate font-mono text-xs font-semibold'>
          {summary.run_id}
        </strong>
        <small className='mt-1 block truncate text-xs text-muted-foreground'>
          {summary.subject_name} · {statusText} · {formatDuration(summary.duration_ms)}
        </small>
      </span>
      <span className='text-xs text-muted-foreground'>
        {formatTraceTime(summary.started_at ?? summary.created_at)}
      </span>
    </button>
  )
}

/** 详情区顶部的 Run 概要行：Run ID、状态、主体、开始时间、耗时与复制按钮。 */
function TraceDetailHeader({ detail }: { detail: TraceDetail }) {
  const { t } = useTranslation()
  const { summary } = detail
  const limited = isLimitedVisibility(summary)
  const tone = limited ? 'muted' : runStatusTone(summary.status)

  const copyRunId = async () => {
    try {
      await navigator.clipboard?.writeText(summary.run_id)
      toast.success(t('runTracing.runIdCopied'))
    } catch {
      toast.error(t('runTracing.runIdCopyFailed'))
    }
  }

  return (
    <div className='flex items-start justify-between gap-4'>
      <div>
        <div className='flex flex-wrap items-center gap-2.5'>
          <h2 className='font-mono text-base font-semibold'>{summary.run_id}</h2>
          <Badge
            variant='outline'
            data-testid='detail-status-badge'
            className={cn(
              'border-emerald-300 text-emerald-700',
              tone === 'failed' && 'border-red-300 text-red-700',
              tone === 'running' && 'border-blue-300 text-blue-700',
              tone === 'muted' && 'border-muted-foreground/40 text-muted-foreground'
            )}
          >
            {limited
              ? t('runTracing.statusLegacy')
              : runStatusLabel(summary.status, (key) => String(t(key)))}
          </Badge>
        </div>
        <p className='mt-1 text-xs text-muted-foreground'>
          {summary.subject_name} · {formatTraceTime(summary.started_at ?? summary.created_at)} ·{' '}
          {formatDuration(summary.duration_ms)}
        </p>
      </div>
      <Button variant='outline' onClick={() => void copyRunId()}>
        {t('runTracing.copyRunId')}
      </Button>
    </div>
  )
}

/** 详情区的四宫格汇总：模型调用 / 工具调用 / Token / 诊断。 */
function TraceSummaryGrid({ detail }: { detail: TraceDetail }) {
  const { t } = useTranslation()
  const { summary } = detail
  const items = [
    { label: t('runTracing.summaryModelCalls'), value: summary.model_call_count },
    { label: t('runTracing.summaryToolCalls'), value: summary.tool_call_count },
    { label: t('runTracing.summaryTokens'), value: formatTokenUsage(summary.usage) },
    { label: t('runTracing.summaryDiagnostics'), value: detail.diagnostics.length },
  ]
  return (
    <div className='mt-4 grid grid-cols-2 rounded-lg border sm:grid-cols-4'>
      {items.map((item, index) => (
        <div key={item.label} className={cn('p-3', index < items.length - 1 && 'border-e')}>
          <span className='block text-xs text-muted-foreground'>{item.label}</span>
          <strong className='mt-1 block text-lg font-semibold'>{item.value}</strong>
        </div>
      ))}
    </div>
  )
}

/** 详情区的 trace 上下文条：trace ID 与内容策略。 */
function TraceContextStrip({ detail }: { detail: TraceDetail }) {
  const { t } = useTranslation()
  return (
    <div className='mt-4 flex flex-wrap items-center gap-2.5 rounded-lg bg-muted/60 px-3 py-2 text-xs text-muted-foreground'>
      <span className='font-semibold'>TRACE</span>
      <code className='font-mono text-foreground'>{detail.summary.trace_id}</code>
      <span className='ms-auto'>{t('runTracing.contentPolicyLabel')}</span>
      <strong className='text-foreground'>{detail.content_policy}</strong>
    </div>
  )
}

/** 渲染右侧选中 Run 的详情：汇总、trace 上下文、节点树与受限/空态提示。 */
function TraceDetailPanel({
  detail,
  isLoading,
  errorMessage,
}: {
  detail: TraceDetail | null
  isLoading: boolean
  errorMessage: string | null
}) {
  const { t } = useTranslation()

  if (errorMessage) {
    return <p className='text-sm text-destructive'>{errorMessage}</p>
  }
  if (isLoading && !detail) {
    return (
      <div className='space-y-3'>
        <Skeleton className='h-6 w-64' />
        <Skeleton className='h-20 w-full' />
        <Skeleton className='h-40 w-full' />
      </div>
    )
  }
  if (!detail) {
    return (
      <p className='text-sm text-muted-foreground' data-testid='trace-no-selection'>
        {t('runTracing.noSelection')}
      </p>
    )
  }

  const limited = isLimitedVisibility(detail.summary)
  const rootNode = detail.tree[0] ?? null
  const hasChildNodes = detail.tree.some((node) => node.children.length > 0)
  const runLevelDiagnostics = detail.diagnostics.filter(
    (diagnostic) => diagnostic.span_id === null
  )

  return (
    <>
      <TraceDetailHeader detail={detail} />
      <TraceSummaryGrid detail={detail} />
      <TraceContextStrip detail={detail} />

      {limited ? (
        <div
          className='mt-4 rounded-lg border border-dashed p-6 text-center text-muted-foreground'
          data-testid='trace-limited-notice'
        >
          <strong className='mb-2 block text-foreground'>{t('runTracing.limitedTitle')}</strong>
          {t('runTracing.limitedBody')}
        </div>
      ) : (
        <>
          <TraceTree tree={detail.tree} diagnostics={detail.diagnostics} />
          {!hasChildNodes || !rootNode ? (
            <div
              className='mt-4 rounded-lg border border-dashed p-6 text-center text-muted-foreground'
              data-testid='trace-empty-state'
            >
              <strong className='mb-2 block text-foreground'>{t('runTracing.emptyTitle')}</strong>
              {t('runTracing.emptyBody')}
            </div>
          ) : null}
        </>
      )}

      {runLevelDiagnostics.length > 0 ? (
        <ul className='mt-3 space-y-1 text-xs text-amber-800'>
          {runLevelDiagnostics.map((diagnostic) => (
            <li key={diagnostic.code} data-testid={`run-diagnostic-${diagnostic.code}`}>
              {diagnosticLabel(diagnostic.code, (key) => String(t(key)))}
            </li>
          ))}
        </ul>
      ) : null}
    </>
  )
}

/** 渲染 Admin 端 Run 执行轨迹页：Run 列表与选中 Run 详情并列展示。 */
export function RunTracing() {
  const { t } = useTranslation()
  const queryClient = useQueryClient()
  const [searchText, setSearchText] = useState('')
  const [statusFilter, setStatusFilter] = useState<TraceStatusFilter>('all')
  const [timeRange, setTimeRange] = useState<TraceTimeRange>('24h')
  const [selectedRunId, setSelectedRunId] = useState('')

  const statusParam: RunStatus | undefined =
    statusFilter === 'all' || statusFilter === 'legacy' ? undefined : statusFilter

  const listQuery = useQuery({
    queryKey: [...RUN_TRACE_QUERY_KEY, 'list', { statusParam, timeRange }],
    queryFn: () => {
      const lookbackHours = timeRange === '24h' ? 24 : 24 * 7
      const createdAfter = new Date(Date.now() - lookbackHours * 3_600_000).toISOString()
      return listRunTraces({ status: statusParam, createdAfter, pageSize: 50 })
    },
  })

  const visibleRuns = useMemo(() => {
    const keyword = searchText.trim().toLowerCase()
    return (listQuery.data?.items ?? []).filter((run) => {
      if (statusFilter === 'legacy' && !isLimitedVisibility(run)) return false
      if (!keyword) return true
      return `${run.run_id} ${run.subject_name} ${run.subject_id}`.toLowerCase().includes(keyword)
    })
  }, [listQuery.data, searchText, statusFilter])

  const effectiveRunId =
    selectedRunId && visibleRuns.some((run) => run.run_id === selectedRunId)
      ? selectedRunId
      : (visibleRuns[0]?.run_id ?? '')

  const detailQuery = useQuery({
    queryKey: [...RUN_TRACE_QUERY_KEY, 'detail', effectiveRunId],
    queryFn: () => getRunTrace(effectiveRunId),
    enabled: Boolean(effectiveRunId),
  })

  const [isDownloading, setIsDownloading] = useState(false)

  // 后端只允许下载已终结 Run 的整份事件；未终结时按钮保持禁用，不让操作员点到一个必然 409 的动作。
  const selectedRunIsTerminal = visibleRuns.some(
    (run) => run.run_id === effectiveRunId && isTerminalRunStatus(run.status)
  )

  const downloadSelectedRun = async () => {
    if (!selectedRunIsTerminal || isDownloading) return
    setIsDownloading(true)
    try {
      const exportBlob = await downloadRunTrace(effectiveRunId)
      const objectUrl = URL.createObjectURL(exportBlob)
      const anchor = document.createElement('a')
      anchor.href = objectUrl
      anchor.download = `run-${effectiveRunId}.json`
      document.body.appendChild(anchor)
      anchor.click()
      anchor.remove()
      window.setTimeout(() => URL.revokeObjectURL(objectUrl), 0)
      toast.success(t('runTracing.downloadSuccess'))
    } catch {
      toast.error(t('runTracing.downloadFailed'))
    } finally {
      setIsDownloading(false)
    }
  }

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: RUN_TRACE_QUERY_KEY })
  }

  const detailErrorMessage = detailQuery.isError ? (detailQuery.error as Error).message : null

  return (
    <>
      <Header fixed>
        <div className='me-auto font-semibold'>{t('runTracing.header')}</div>
        <ProfileDropdown />
      </Header>
      <Main className='space-y-4'>
        <div className='flex flex-wrap items-start justify-between gap-4'>
          <div>
            <h2 className='text-2xl font-bold'>{t('runTracing.pageTitle')}</h2>
            <p className='text-muted-foreground'>{t('runTracing.pageDescription')}</p>
          </div>
          <div className='flex items-center gap-2 text-sm font-semibold text-emerald-700'>
            <span aria-hidden='true' className='size-2 rounded-full bg-emerald-500' />
            {t('runTracing.localDiagnostics')}
            <small className='font-normal text-muted-foreground'>
              {t('runTracing.otlpNote')}
            </small>
          </div>
        </div>

        <div className='flex flex-wrap items-center gap-2'>
          <div className='relative min-w-64 flex-1 sm:max-w-md'>
            <Search className='absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground' />
            <Input
              className='ps-9'
              value={searchText}
              onChange={(event) => setSearchText(event.target.value)}
              placeholder={t('runTracing.searchPlaceholder')}
              aria-label={t('runTracing.searchPlaceholder')}
            />
          </div>
          <Select
            value={statusFilter}
            onValueChange={(next) => setStatusFilter(next as TraceStatusFilter)}
          >
            <SelectTrigger className='w-40' aria-label={t('runTracing.statusFilterLabel')}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='all'>{t('runTracing.allStatus')}</SelectItem>
              <SelectItem value='succeeded'>{t('runTracing.statusSucceeded')}</SelectItem>
              <SelectItem value='failed'>{t('runTracing.statusFailed')}</SelectItem>
              <SelectItem value='running'>{t('runTracing.statusRunning')}</SelectItem>
              <SelectItem value='legacy'>{t('runTracing.statusLegacy')}</SelectItem>
            </SelectContent>
          </Select>
          <Select
            value={timeRange}
            onValueChange={(next) => setTimeRange(next as TraceTimeRange)}
          >
            <SelectTrigger className='w-40' aria-label={t('runTracing.timeRangeLabel')}>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='24h'>{t('runTracing.range24h')}</SelectItem>
              <SelectItem value='7d'>{t('runTracing.range7d')}</SelectItem>
            </SelectContent>
          </Select>
          <Button variant='outline' data-testid='trace-refresh-button' onClick={refresh}>
            <RefreshCw className='size-4' />
            {t('runTracing.refresh')}
          </Button>
          <Button
            variant='outline'
            data-testid='trace-download-button'
            disabled={!selectedRunIsTerminal || isDownloading}
            onClick={() => void downloadSelectedRun()}
          >
            <Download className='size-4' />
            {t('runTracing.downloadRaw')}
          </Button>
        </div>

        <div
          className='grid overflow-hidden rounded-xl border bg-card shadow-sm lg:grid-cols-[310px_minmax(0,1fr)]'
          data-testid='trace-workspace'
        >
          <Card className='rounded-none border-0 border-e bg-muted/30 lg:border-e'>
            <CardHeader>
              <CardTitle className='text-base'>{t('runTracing.recentRuns')}</CardTitle>
              <p className='text-xs text-muted-foreground' data-testid='run-count-label'>
                {t('runTracing.runCount', { count: visibleRuns.length })}
              </p>
            </CardHeader>
            <CardContent className='p-2 pt-0'>
              <ScrollArea className='h-[520px]'>
                <div className='space-y-1 pe-2'>
                  {listQuery.isLoading ? (
                    <div className='space-y-2 p-2'>
                      <Skeleton className='h-14 w-full' />
                      <Skeleton className='h-14 w-full' />
                      <Skeleton className='h-14 w-full' />
                    </div>
                  ) : visibleRuns.length === 0 ? (
                    <div
                      className='rounded-lg border border-dashed p-5 text-center text-xs text-muted-foreground'
                      data-testid='run-list-empty'
                    >
                      <strong className='mb-1 block text-foreground'>
                        {t('runTracing.noMatchingRuns')}
                      </strong>
                      {t('runTracing.noMatchingRunsHint')}
                    </div>
                  ) : (
                    visibleRuns.map((run) => (
                      <RunListRow
                        key={run.run_id}
                        summary={run}
                        active={run.run_id === effectiveRunId}
                        onSelect={() => setSelectedRunId(run.run_id)}
                      />
                    ))
                  )}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          <div className='min-w-0 p-5' data-testid='trace-detail-panel'>
            <TraceDetailPanel
              detail={detailQuery.data ?? null}
              isLoading={detailQuery.isLoading}
              errorMessage={detailErrorMessage}
            />
          </div>
        </div>
      </Main>
    </>
  )
}
