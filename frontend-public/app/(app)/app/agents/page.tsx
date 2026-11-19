"use client"

import { useCallback, useEffect, useMemo, useRef, useState } from "react"
import { useTranslations } from "next-intl"
import { Bot, Clock3, LoaderCircle, Send, Sparkles } from "lucide-react"
import {
  cancelAgentRun,
  createAgentRun,
  getAgentRun,
  getAgentRuns,
  getMemberAgents,
  streamAgentRunEvents,
  type AgentRunDetail,
  type AgentRunSummary,
  type MemberAgent,
} from "@/lib/api/agents"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"

/** 由 Canonical Event 推导的、可展示的逐步运行状态。 */
const RUN_STATUS_BY_EVENT: Record<string, string> = {
  "run.started": "running",
  "run.cancelling": "cancelling",
}
const ACTIVE_RUN_STATUS_ORDER: Record<string, number> = {
  queued: 0,
  running: 1,
  cancelling: 2,
}
const POLLABLE_RUN_STATUSES = new Set(["queued", "running", "cancelling"])
const TERMINAL_RUN_STATUSES = new Set([
  "succeeded",
  "failed",
  "cancelled",
  "interrupted",
])

/** 合并同一 Run 的状态时，阻止迟到事件覆盖终态或回退活动状态。 */
function mergeRunStateWithoutRegression(
  currentRun: AgentRunDetail | null,
  incomingRun: AgentRunDetail
): AgentRunDetail {
  if (!currentRun || currentRun.id !== incomingRun.id) return incomingRun
  if (
    TERMINAL_RUN_STATUSES.has(currentRun.status) &&
    currentRun.status !== incomingRun.status
  ) {
    return currentRun
  }
  const currentStatusOrder = ACTIVE_RUN_STATUS_ORDER[currentRun.status]
  const incomingStatusOrder = ACTIVE_RUN_STATUS_ORDER[incomingRun.status]
  if (
    currentStatusOrder !== undefined &&
    incomingStatusOrder !== undefined &&
    incomingStatusOrder < currentStatusOrder
  ) {
    return { ...incomingRun, status: currentRun.status }
  }
  return incomingRun
}

/** Show the organization Agent directory and persisted run history. */
export default function AgentsPage() {
  const t = useTranslations("agents")
  const common = useTranslations("common")
  const [agents, setAgents] = useState<MemberAgent[]>([])
  const [runs, setRuns] = useState<AgentRunSummary[]>([])
  const [selectedAgentId, setSelectedAgentId] = useState("")
  const [activeRun, setActiveRun] = useState<AgentRunDetail | null>(null)
  const [message, setMessage] = useState("")
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [cancellingRun, setCancellingRun] = useState(false)
  const [error, setError] = useState("")
  const [liveReply, setLiveReply] = useState("")
  const eventCursorRef = useRef(0)
  const activeRunId = activeRun?.id ?? null
  const shouldPollActiveRun =
    activeRun !== null && POLLABLE_RUN_STATUSES.has(activeRun.status)

  const selectedAgent = useMemo(
    () => agents.find((agent) => agent.id === selectedAgentId) ?? null,
    [agents, selectedAgentId]
  )

  const reloadHistory = useCallback(async () => {
    const recentRuns = await getAgentRuns()
    setRuns(recentRuns)
  }, [])

  useEffect(() => {
    let cancelled = false
    Promise.all([getMemberAgents(), getAgentRuns()])
      .then(([directory, recentRuns]) => {
        if (cancelled) return
        setAgents(directory)
        setRuns(recentRuns)
        setSelectedAgentId(directory[0]?.id ?? "")
      })
      .catch(() => {
        if (!cancelled) setError(t("loadFailed"))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [t])

  useEffect(() => {
    if (!activeRunId || !shouldPollActiveRun) return
    const runId = activeRunId
    let cancelled = false
    let activeStreamController: AbortController | null = null
    /**
     * 重新读取持久化 Run 并合并状态，返回是否应停止消费事件。SSE 正常结束和订阅
     * 失败都必须走这个入口，否则流式通道故障时页面会停在运行中，看不见已提交的终态。
     */
    const refreshRunState = async (): Promise<boolean> => {
      const refreshedRun = await getAgentRun(runId)
      if (cancelled) return true
      setActiveRun((previous) => {
        if (!previous || previous.id !== runId) return previous
        return mergeRunStateWithoutRegression(previous, refreshedRun)
      })
      if (POLLABLE_RUN_STATUSES.has(refreshedRun.status)) return false
      setLiveReply("")
      await reloadHistory()
      return true
    }
    /**
     * 读取新增的 Canonical Event：`message.delta` 立即拼接到实时回复，
     * 流关闭后重新读取持久化 Run 并刷新历史。断线后从最后处理的事件序号
     * 重连，避免重复消费或漏掉已提交事件。
     */
    const consumeEvents = async () => {
      while (!cancelled) {
        const streamController = new AbortController()
        activeStreamController = streamController
        try {
          await streamAgentRunEvents(
            runId,
            eventCursorRef.current,
            (runEvent) => {
              if (cancelled) return
              eventCursorRef.current = Math.max(eventCursorRef.current, runEvent.seq)
              if (
                runEvent.event_type === "message.delta" &&
                typeof runEvent.payload.delta === "string"
              ) {
                setLiveReply((previous) => previous + runEvent.payload.delta)
              }
              if (Object.hasOwn(RUN_STATUS_BY_EVENT, runEvent.event_type)) {
                const nextStatus = RUN_STATUS_BY_EVENT[runEvent.event_type]
                setActiveRun((previous) => {
                  if (!previous || previous.id !== runId) return previous
                  return mergeRunStateWithoutRegression(previous, {
                    ...previous,
                    status: nextStatus,
                  })
                })
              }
            },
            streamController.signal
          )
          if (cancelled) return
          if (await refreshRunState()) return
        } catch (streamError) {
          if (cancelled) return
          if (
            streamError instanceof Error &&
            "status" in streamError &&
            [401, 404].includes(Number(streamError.status))
          ) {
            setError(t("historyFailed"))
            return
          }
          setError(t("refreshFailed"))
          // 订阅失败不等于运行失败：终态仍要取自持久化 Run，否则页面会停在运行中。
          try {
            if (await refreshRunState()) return
          } catch {
            // 持久化读取也失败时保留提示，等下一轮重连后重新判断。
          }
        } finally {
          if (activeStreamController === streamController) {
            activeStreamController = null
          }
        }
        await new Promise<void>((resolve) => window.setTimeout(resolve, 1000))
      }
    }
    void consumeEvents()
    return () => {
      cancelled = true
      activeStreamController?.abort()
    }
  }, [activeRunId, shouldPollActiveRun, reloadHistory, t])

  /** Submit a message through the same-origin API and reuse its persisted conversation. */
  const submitMessage = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (
      !selectedAgent ||
      !selectedAgent.is_runnable ||
      !message.trim() ||
      sending
    )
      return
    setSending(true)
    setError("")
    try {
      const createdRun = await createAgentRun({
        agentId: selectedAgent.id,
        conversationId:
          activeRun?.agent_id === selectedAgent.id
            ? activeRun.conversation_id
            : null,
        message: message.trim(),
      })
      setMessage("")
      setLiveReply("")
      eventCursorRef.current = 0
      setActiveRun(createdRun)
      await reloadHistory()
    } catch (submissionError) {
      setError(
        submissionError instanceof Error
          ? submissionError.message
          : t("submitFailed")
      )
    } finally {
      setSending(false)
    }
  }

  /** Reopen an existing Run from server-side history. */
  const reopenRun = async (runId: string) => {
    setError("")
    try {
      const persistedRun = await getAgentRun(runId)
      setLiveReply("")
      eventCursorRef.current = 0
      setActiveRun(persistedRun)
      setSelectedAgentId(persistedRun.agent_id)
    } catch {
      setError(t("historyFailed"))
    }
  }

  /** 取消当前运行，并刷新持久状态与历史。 */
  const cancelActiveRun = async () => {
    if (!activeRun || cancellingRun) return
    setCancellingRun(true)
    setError("")
    try {
      const cancelledRun = await cancelAgentRun(activeRun.id)
      setActiveRun((previous) => {
        if (!previous || previous.id !== cancelledRun.id) return previous
        return mergeRunStateWithoutRegression(previous, cancelledRun)
      })
      setLiveReply("")
      await reloadHistory()
    } catch {
      setError(t("cancelFailed"))
    } finally {
      setCancellingRun(false)
    }
  }

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        <LoaderCircle className="mr-2 size-4 animate-spin" />
        {common("loading")}
      </div>
    )
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_20rem]">
      <section className="space-y-5">
        <header>
          <p className="text-sm font-medium text-primary">{t("eyebrow")}</p>
          <h1 className="mt-1 text-3xl font-bold tracking-tight">
            {t("title")}
          </h1>
          <p className="mt-2 text-muted-foreground">{t("subtitle")}</p>
        </header>

        {error && (
          <p
            role="alert"
            className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm"
          >
            {error}
          </p>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="size-5 text-primary" /> {t("chooseAgent")}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-3 sm:grid-cols-2">
            {agents.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {t("emptyAgents")}
              </p>
            )}
            {agents.map((agent) => (
              <button
                key={agent.id}
                type="button"
                onClick={() => setSelectedAgentId(agent.id)}
                aria-pressed={selectedAgentId === agent.id}
                className={`rounded-lg border p-4 text-left transition-colors focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
                  selectedAgentId === agent.id
                    ? "border-primary bg-primary/5"
                    : "hover:bg-muted/50"
                }`}
              >
                <span className="flex items-center justify-between gap-3">
                  <strong>{agent.name}</strong>
                  <span className="text-xs text-muted-foreground">
                    {agent.is_runnable ? t("available") : t("unavailable")}
                  </span>
                </span>
                <span className="mt-2 block text-sm text-muted-foreground">
                  {agent.description || t("noDescription")}
                </span>
                {!agent.is_runnable && agent.unavailable_reason && (
                  <span className="mt-2 block text-xs text-destructive">
                    {t("unavailableReason", {
                      reason: agent.unavailable_reason,
                    })}
                  </span>
                )}
              </button>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Sparkles className="size-5 text-primary" />
              {selectedAgent?.name ?? t("conversation")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {activeRun ? (
              <div
                className="space-y-3"
                aria-live="polite"
                data-testid="agent-run-detail"
              >
                <div className="rounded-lg bg-muted/60 p-4">
                  <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                    {t("you")}
                  </p>
                  <p className="mt-2 text-sm whitespace-pre-wrap">
                    {activeRun.input_message}
                  </p>
                </div>
                <div className="rounded-lg border p-4">
                  <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                    <span>{t("agentReply")}</span>
                    <span>{t("runStatus", { status: activeRun.status })}</span>
                  </div>
                  {["queued", "running", "cancelling"].includes(
                    activeRun.status
                  ) && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="mt-3"
                      disabled={
                        cancellingRun || activeRun.status === "cancelling"
                      }
                      onClick={() => void cancelActiveRun()}
                    >
                      {cancellingRun || activeRun.status === "cancelling"
                        ? t("cancelling")
                        : t("cancelRun")}
                    </Button>
                  )}
                  <p
                    className="mt-2 min-h-6 text-sm whitespace-pre-wrap"
                    data-testid="agent-run-reply"
                  >
                    {activeRun.assistant_message ??
                      (liveReply ||
                        (["queued", "running", "cancelling"].includes(
                          activeRun.status
                        )
                          ? t("thinking")
                          : t("noReply")))}
                  </p>
                  {liveReply &&
                    ["queued", "running", "cancelling"].includes(
                      activeRun.status
                    ) && (
                      <p
                        className="mt-2 font-mono text-[11px] text-muted-foreground"
                        data-testid="agent-run-live-reply"
                      >
                        {t("streamingReply")}
                      </p>
                    )}
                  <p
                    className="mt-3 font-mono text-[11px] break-all text-muted-foreground"
                    data-testid="agent-run-id"
                  >
                    {t("runId", { id: activeRun.id })}
                  </p>
                  {activeRun.skill_version !== null && (
                    <p
                      className="mt-1 text-xs text-muted-foreground"
                      data-testid="agent-run-skill-version"
                    >
                      {t("skillVersion", { version: activeRun.skill_version })}
                    </p>
                  )}
                </div>
              </div>
            ) : (
              <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">
                {t("emptyConversation")}
              </div>
            )}
            <form
              className="space-y-3"
              onSubmit={(event) => void submitMessage(event)}
            >
              <Textarea
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder={t("messagePlaceholder")}
                rows={4}
                maxLength={32000}
                disabled={!selectedAgent?.is_runnable || sending}
                aria-label={t("messagePlaceholder")}
              />
              <div className="flex justify-end">
                <Button
                  type="submit"
                  disabled={
                    !selectedAgent?.is_runnable || !message.trim() || sending
                  }
                >
                  {sending ? (
                    <LoaderCircle className="mr-2 size-4 animate-spin" />
                  ) : (
                    <Send className="mr-2 size-4" />
                  )}
                  {t("send")}
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      </section>

      <aside>
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Clock3 className="size-4" /> {t("history")}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {runs.length === 0 && (
              <p className="text-sm text-muted-foreground">
                {t("emptyHistory")}
              </p>
            )}
            {runs.map((run) => (
              <button
                key={run.id}
                type="button"
                data-testid={`agent-run-history-${run.id}`}
                onClick={() => void reopenRun(run.id)}
                className={`w-full rounded-md border p-3 text-left hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none ${
                  activeRun?.id === run.id ? "border-primary" : ""
                }`}
              >
                <strong className="block truncate text-sm">
                  {run.agent_name}
                </strong>
                <span className="mt-1 block text-xs text-muted-foreground">
                  {run.status} · {new Date(run.created_at).toLocaleString()}
                </span>
                <span className="mt-1 block truncate font-mono text-[10px] text-muted-foreground">
                  {run.id}
                </span>
              </button>
            ))}
          </CardContent>
        </Card>
      </aside>
    </div>
  )
}
