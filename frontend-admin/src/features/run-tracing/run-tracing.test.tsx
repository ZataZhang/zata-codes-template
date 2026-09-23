import { type ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import i18n from '@/i18n/init'
import { toast } from 'sonner'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import {
  downloadRunTrace,
  getRunTrace,
  listRunTraces,
  type TraceDetail,
  type TraceSpan,
  type TraceSummary,
} from '@/api/run-traces'
import { RunTracing } from './index'

vi.mock('@/api/run-traces', () => ({
  downloadRunTrace: vi.fn(),
  listRunTraces: vi.fn(),
  getRunTrace: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

// 浏览器模式下真实点击下载链接会尝试写文件；这里只观察下载机制本身。
const createObjectUrlSpy = vi
  .spyOn(URL, 'createObjectURL')
  .mockReturnValue('blob:run-trace-export')
const revokeObjectUrlSpy = vi
  .spyOn(URL, 'revokeObjectURL')
  .mockImplementation(() => {})
const anchorClickSpy = vi
  .spyOn(HTMLAnchorElement.prototype, 'click')
  .mockImplementation(() => {})

vi.mock('@/components/layout/header', async () => {
  const { createElement } = await import('react')
  return {
    Header: ({ children }: { children?: ReactNode }) =>
      createElement('header', null, children),
  }
})

vi.mock('@/components/layout/main', async () => {
  const { createElement } = await import('react')
  return {
    Main: ({ children }: { children?: ReactNode }) =>
      createElement('main', null, children),
  }
})

vi.mock('@/components/profile-dropdown', () => ({
  ProfileDropdown: () => null,
}))

const ISO_START = '2026-09-21T08:42:08.000Z'

/** 构造一个 Run 级摘要，未指定的字段使用稳定的默认值。 */
function makeSummary(overrides: Partial<TraceSummary> = {}): TraceSummary {
  return {
    run_id: 'run_8f31c2',
    subject_id: 'subject-freight',
    subject_name: 'freight-agent',
    owner_id: 'owner-chen',
    status: 'succeeded',
    created_at: ISO_START,
    started_at: ISO_START,
    finished_at: ISO_START,
    duration_ms: 12_400,
    trace_id: 'trace-61d9ac2',
    visibility: 'full',
    model_call_count: 2,
    tool_call_count: 2,
    usage: { prompt: 800, completion: 686, total: 1486 },
    error_count: 0,
    ...overrides,
  }
}

/** 构造一个执行轨迹节点，未指定的字段使用稳定的默认值。 */
function makeSpan(overrides: Partial<TraceSpan> = {}): TraceSpan {
  return {
    span_id: 'root',
    parent_span_id: null,
    kind: 'root',
    name: 'Canonical Run',
    status: 'completed',
    started_at: ISO_START,
    finished_at: ISO_START,
    duration_ms: 12_400,
    model_call_id: null,
    model_name: null,
    turn_index: null,
    usage: null,
    finish_reason: null,
    tool_call_id: null,
    tool_name: null,
    result_checksum: null,
    result_length: null,
    error_code: null,
    error_message: null,
    diagnostics: [],
    ...overrides,
  }
}

/** 默认成功 Run 的详情：根节点 + 两个模型节点 + 一个带父级 fallback 的工具节点。 */
function makeDefaultDetail(): TraceDetail {
  const rootSpan = makeSpan({ span_id: 'root' })
  const modelTurn1 = makeSpan({
    span_id: 'm1',
    parent_span_id: 'root',
    kind: 'model',
    name: 'LLM turn 1 · qwen3-max',
    turn_index: 1,
    model_name: 'qwen3-max',
    usage: { total: 812 },
    finish_reason: 'stop',
    duration_ms: 2100,
  })
  const toolRead = makeSpan({
    span_id: 't1',
    parent_span_id: 'root',
    kind: 'tool',
    name: 'read_attachment',
    tool_name: 'read_attachment',
    tool_call_id: 'call_7c2a',
    result_length: 2048,
    result_checksum: 'abc12345deadbeef',
    duration_ms: 6800,
  })
  const toolFallback = makeSpan({
    span_id: 't2',
    parent_span_id: 'root',
    kind: 'tool',
    name: 'lookup_rate',
    tool_name: 'lookup_rate',
    tool_call_id: 'call_a18f',
    result_length: 128,
    result_checksum: 'ff00aa11bb22cc33',
    status: 'incomplete',
    duration_ms: 1200,
    diagnostics: ['parent_source_unavailable'],
  })
  const modelTurn2 = makeSpan({
    span_id: 'm2',
    parent_span_id: 'root',
    kind: 'model',
    name: 'LLM turn 2 · qwen3-max',
    turn_index: 2,
    model_name: 'qwen3-max',
    usage: { total: 674 },
    finish_reason: 'stop',
    duration_ms: 2300,
  })
  return {
    summary: makeSummary(),
    root_span_id: 'root',
    spans: [rootSpan, modelTurn1, toolRead, toolFallback, modelTurn2],
    tree: [
      {
        span: rootSpan,
        children: [
          { span: modelTurn1, children: [] },
          { span: toolRead, children: [] },
          { span: toolFallback, children: [] },
          { span: modelTurn2, children: [] },
        ],
      },
    ],
    diagnostics: [
      {
        code: 'parent_source_unavailable',
        message: 'lookup_rate 的父级来源无法确认',
        span_id: 't2',
      },
    ],
    content_policy: 'metadata-only',
  }
}

/** 只含 Run 根节点、没有任何模型/工具子节点的空轨迹详情。 */
function makeEmptyDetail(): TraceDetail {
  const rootSpan = makeSpan({ span_id: 'root', duration_ms: 400 })
  return {
    summary: makeSummary({
      run_id: 'run_empty',
      duration_ms: 400,
      model_call_count: 0,
      tool_call_count: 0,
      usage: { total: 18 },
    }),
    root_span_id: 'root',
    spans: [rootSpan],
    tree: [{ span: rootSpan, children: [] }],
    diagnostics: [],
    content_policy: 'metadata-only',
  }
}

/** 历史受限 Run 的详情：没有 tracing 事件，不应伪造根节点。 */
function makeLimitedDetail(): TraceDetail {
  return {
    summary: makeSummary({
      run_id: 'run_19c04a',
      subject_name: 'legacy-subject',
      status: 'cancelled',
      visibility: 'limited',
      model_call_count: 0,
      tool_call_count: 1,
      usage: null,
      duration_ms: null,
    }),
    root_span_id: null,
    spans: [],
    tree: [],
    diagnostics: [
      {
        code: 'no_tracing_events',
        message: '该 Run 没有 tracing 事件',
        span_id: null,
      },
    ],
    content_policy: 'metadata-only',
  }
}

/** 失败 Run 的详情：模型节点带 provider_timeout 错误码。 */
function makeFailedDetail(): TraceDetail {
  const rootSpan = makeSpan({
    span_id: 'root',
    name: 'Canonical Run',
    status: 'failed',
  })
  const failedModel = makeSpan({
    span_id: 'm1',
    parent_span_id: 'root',
    kind: 'model',
    name: 'LLM turn 2 · qwen3-max',
    turn_index: 2,
    model_name: 'qwen3-max',
    usage: { total: 622 },
    status: 'failed',
    error_code: 'provider_timeout',
    error_message: '未收到 completed 事件',
    duration_ms: 4400,
  })
  return {
    summary: makeSummary({
      run_id: 'run_76a9bd',
      subject_name: 'sandbox-subject',
      status: 'failed',
      error_count: 1,
      duration_ms: 8700,
    }),
    root_span_id: 'root',
    spans: [rootSpan, failedModel],
    tree: [{ span: rootSpan, children: [{ span: failedModel, children: [] }] }],
    diagnostics: [],
    content_policy: 'metadata-only',
  }
}

/** 在新鲜 QueryClient 与已选 zh 语言下渲染页面。 */
async function renderRunTracing() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return await render(
    <QueryClientProvider client={queryClient}>
      <RunTracing />
    </QueryClientProvider>
  )
}

describe('RunTracing', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    await i18n.changeLanguage('zh')
  })

  it('renders the default detail tree with model spans and a parent fallback tool node', async () => {
    const detail = makeDefaultDetail()
    vi.mocked(listRunTraces).mockResolvedValue({
      items: [detail.summary],
      total: 1,
      page: 1,
      page_size: 50,
    })
    vi.mocked(getRunTrace).mockResolvedValue(detail)

    const screen = await renderRunTracing()

    await expect.element(screen.getByTestId('run-row-run_8f31c2')).toBeInTheDocument()
    await expect.element(screen.getByTestId('trace-node-root')).toBeInTheDocument()
    await expect.element(screen.getByTestId('trace-node-m1')).toBeInTheDocument()
    await expect.element(screen.getByTestId('trace-node-m2')).toBeInTheDocument()
    await expect.element(screen.getByTestId('trace-node-t1')).toBeInTheDocument()
    await expect.element(screen.getByTestId('trace-node-t1')).toHaveTextContent(/成功/)

    await expect
      .element(screen.getByTestId('trace-diagnostic-t2-parent_source_unavailable'))
      .toBeInTheDocument()
    await expect.element(screen.getByTestId('trace-node-t2')).toHaveTextContent(/父级来源不可确认/)
    await expect.element(screen.getByText('metadata-only')).toBeInTheDocument()
  })

  it('renders the limited legacy notice without fabricating a root node', async () => {
    const detail = makeLimitedDetail()
    vi.mocked(listRunTraces).mockResolvedValue({
      items: [detail.summary],
      total: 1,
      page: 1,
      page_size: 50,
    })
    vi.mocked(getRunTrace).mockResolvedValue(detail)

    const screen = await renderRunTracing()

    await expect.element(screen.getByTestId('trace-limited-notice')).toBeInTheDocument()
    await expect
      .element(screen.getByTestId('trace-limited-notice'))
      .toHaveTextContent(/诊断信息有限/)
    await expect.element(screen.getByTestId('trace-node-root')).not.toBeInTheDocument()
  })

  it('shows failed node styling and the error code', async () => {
    const detail = makeFailedDetail()
    vi.mocked(listRunTraces).mockResolvedValue({
      items: [detail.summary],
      total: 1,
      page: 1,
      page_size: 50,
    })
    vi.mocked(getRunTrace).mockResolvedValue(detail)

    const screen = await renderRunTracing()

    await expect.element(screen.getByTestId('trace-node-m1')).toHaveTextContent(/provider_timeout/)
    await expect.element(screen.getByTestId('trace-node-m1')).toHaveTextContent(/错误/)
  })

  it('renders the empty trace notice for a root-only run', async () => {
    const detail = makeEmptyDetail()
    vi.mocked(listRunTraces).mockResolvedValue({
      items: [detail.summary],
      total: 1,
      page: 1,
      page_size: 50,
    })
    vi.mocked(getRunTrace).mockResolvedValue(detail)

    const screen = await renderRunTracing()

    await expect.element(screen.getByTestId('trace-node-root')).toBeInTheDocument()
    await expect.element(screen.getByTestId('trace-empty-state')).toBeInTheDocument()
    await expect
      .element(screen.getByTestId('trace-empty-state'))
      .toHaveTextContent(/没有模型或工具步骤/)
  })

  it('renders an empty list state when the search keyword matches nothing', async () => {
    const detail = makeDefaultDetail()
    vi.mocked(listRunTraces).mockResolvedValue({
      items: [detail.summary],
      total: 1,
      page: 1,
      page_size: 50,
    })
    vi.mocked(getRunTrace).mockResolvedValue(detail)

    const screen = await renderRunTracing()
    await expect.element(screen.getByTestId('run-row-run_8f31c2')).toBeInTheDocument()

    const searchInput = screen.getByRole('textbox')
    await userEvent.fill(searchInput, 'no-such-run')

    await expect.element(screen.getByTestId('run-list-empty')).toBeInTheDocument()
    await expect.element(screen.getByTestId('run-row-run_8f31c2')).not.toBeInTheDocument()
  })

  it('disables the raw-event download while no Run is selected', async () => {
    vi.mocked(listRunTraces).mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 50,
    })

    const screen = await renderRunTracing()

    await expect.element(screen.getByTestId('run-list-empty')).toBeInTheDocument()
    await expect.element(screen.getByTestId('trace-download-button')).toBeDisabled()
    expect(downloadRunTrace).not.toHaveBeenCalled()
  })

  it('keeps the raw-event download disabled for a non-terminal Run', async () => {
    const detail = makeDefaultDetail()
    vi.mocked(listRunTraces).mockResolvedValue({
      items: [{ ...detail.summary, status: 'running' }],
      total: 1,
      page: 1,
      page_size: 50,
    })
    vi.mocked(getRunTrace).mockResolvedValue(detail)

    const screen = await renderRunTracing()

    // 后端对未终结 Run 一律 409，所以这里必须在点击之前就挡住。
    await expect.element(screen.getByTestId('trace-node-root')).toBeInTheDocument()
    await expect.element(screen.getByTestId('trace-download-button')).toBeDisabled()
    expect(downloadRunTrace).not.toHaveBeenCalled()
  })

  it('downloads the selected terminal Run as a json file', async () => {
    const detail = makeDefaultDetail()
    vi.mocked(listRunTraces).mockResolvedValue({
      items: [detail.summary],
      total: 1,
      page: 1,
      page_size: 50,
    })
    vi.mocked(getRunTrace).mockResolvedValue(detail)
    const exportBlob = new Blob(['{"run_id":"run_8f31c2"}'], {
      type: 'application/json',
    })
    vi.mocked(downloadRunTrace).mockResolvedValue(exportBlob)

    const screen = await renderRunTracing()
    const downloadButton = screen.getByTestId('trace-download-button')
    await expect.element(downloadButton).toBeEnabled()

    await userEvent.click(downloadButton)

    await vi.waitFor(() => {
      expect(downloadRunTrace).toHaveBeenCalledWith('run_8f31c2')
    })
    await vi.waitFor(() => {
      expect(createObjectUrlSpy).toHaveBeenCalledWith(exportBlob)
    })
    expect(anchorClickSpy).toHaveBeenCalled()
    await vi.waitFor(() => {
      expect(revokeObjectUrlSpy).toHaveBeenCalledWith('blob:run-trace-export')
    })
    expect(toast.success).toHaveBeenCalledWith('原始事件已下载')
    expect(toast.error).not.toHaveBeenCalled()
  })

  it('reports a failed download without leaving the page stuck', async () => {
    const detail = makeDefaultDetail()
    vi.mocked(listRunTraces).mockResolvedValue({
      items: [detail.summary],
      total: 1,
      page: 1,
      page_size: 50,
    })
    vi.mocked(getRunTrace).mockResolvedValue(detail)
    vi.mocked(downloadRunTrace).mockRejectedValue(new Error('HTTP 409'))

    const screen = await renderRunTracing()
    const downloadButton = screen.getByTestId('trace-download-button')
    await expect.element(downloadButton).toBeEnabled()

    await userEvent.click(downloadButton)

    await vi.waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('下载失败')
    })
    // 失败时不应该产出一个空文件，按钮也要恢复可用而不是一直转圈。
    expect(createObjectUrlSpy).not.toHaveBeenCalled()
    expect(anchorClickSpy).not.toHaveBeenCalled()
    await expect.element(downloadButton).toBeEnabled()
  })
})
