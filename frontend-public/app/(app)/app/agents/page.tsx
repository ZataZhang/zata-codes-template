"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useTranslations } from "next-intl"
import { Bot, Clock3, LoaderCircle, Send, Sparkles } from "lucide-react"
import {
  createAgentRun,
  getAgentRun,
  getAgentRuns,
  getMemberAgents,
  type AgentRunDetail,
  type AgentRunSummary,
  type MemberAgent,
} from "@/lib/api/agents"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"

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
  const [error, setError] = useState("")

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
    if (
      !activeRun ||
      !["queued", "running", "cancelling"].includes(activeRun.status)
    )
      return
    let cancelled = false
    const poll = async () => {
      try {
        const refreshed = await getAgentRun(activeRun.id)
        if (!cancelled) {
          setActiveRun(refreshed)
          if (!["queued", "running", "cancelling"].includes(refreshed.status)) {
            void reloadHistory()
          }
        }
      } catch {
        if (!cancelled) setError(t("refreshFailed"))
      }
    }
    const timer = window.setInterval(() => void poll(), 650)
    void poll()
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [activeRun, reloadHistory, t])

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
      setActiveRun(persistedRun)
      setSelectedAgentId(persistedRun.agent_id)
    } catch {
      setError(t("historyFailed"))
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
              <div className="space-y-3" aria-live="polite">
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
                  <p className="mt-2 min-h-6 text-sm whitespace-pre-wrap">
                    {activeRun.assistant_message ??
                      (["queued", "running", "cancelling"].includes(
                        activeRun.status
                      )
                        ? t("thinking")
                        : t("noReply"))}
                  </p>
                  <p className="mt-3 font-mono text-[11px] break-all text-muted-foreground">
                    {t("runId", { id: activeRun.id })}
                  </p>
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
