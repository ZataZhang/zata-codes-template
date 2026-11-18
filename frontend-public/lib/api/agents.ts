import { ApiRequestError, apiClient } from "@/lib/api/client"

export interface MemberAgent {
  id: string
  name: string
  description: string
  is_enabled: boolean
  is_runnable: boolean
  unavailable_reason: string | null
}

export interface AgentRunSummary {
  id: string
  conversation_id: string | null
  agent_id: string
  agent_name: string
  status: string
  created_at: string
  finished_at: string | null
}

export interface AgentRunDetail extends AgentRunSummary {
  input_message: string
  assistant_message: string | null
  skill_version: number | null
  skill_version_id: string | null
  unavailable_reason: string | null
}

export interface AgentRunEvent {
  seq: number
  event_type: string
  occurred_at: string
  payload: Record<string, unknown>
}

/** Load the published Agent directory visible to the current organization. */
export async function getMemberAgents(): Promise<MemberAgent[]> {
  const response = await apiClient.get<{ items: MemberAgent[] }>("/agents")
  return response.data.items
}

/** Load recent Canonical Run history visible to the current member. */
export async function getAgentRuns(): Promise<AgentRunSummary[]> {
  const response = await apiClient.get<{
    items: AgentRunSummary[]
    total: number
  }>("/agent-runs", { params: { limit: 50 } })
  return response.data.items
}

/** Read a Run in a fresh request so history uses persisted state. */
export async function getAgentRun(runId: string): Promise<AgentRunDetail> {
  const response = await apiClient.get<AgentRunDetail>(
    `/agent-runs/${encodeURIComponent(runId)}`
  )
  return response.data
}

/** Read canonical Run events after `afterSeq` so the UI can show live progress. */
export async function getAgentRunEvents(
  runId: string,
  afterSeq: number
): Promise<{ items: AgentRunEvent[]; nextAfterSeq: number }> {
  const response = await apiClient.get<{
    items: AgentRunEvent[]
    next_after_seq: number
  }>(`/agent-runs/${encodeURIComponent(runId)}/events`, {
    params: { after_seq: afterSeq },
  })
  return {
    items: response.data.items,
    nextAfterSeq: response.data.next_after_seq,
  }
}

/** Keep one same-origin event stream open and deliver each persisted Run event. */
export async function streamAgentRunEvents(
  runId: string,
  afterSeq: number,
  onEvent: (agentRunEvent: AgentRunEvent) => void,
  signal: AbortSignal
): Promise<number> {
  const streamPath = `/api/agent-runs/${encodeURIComponent(runId)}/events/stream`
  const streamUrl = `${streamPath}?after_seq=${afterSeq}`
  const streamResponse = await fetch(streamUrl, {
    method: "GET",
    credentials: "same-origin",
    cache: "no-store",
    headers: { Accept: "text/event-stream" },
    signal,
  })
  if (!streamResponse.ok) {
    if (streamResponse.status === 401) window.location.href = "/login"
    const errorDocument = await streamResponse.json().catch(() => null)
    const detail =
      errorDocument && typeof errorDocument.detail === "string"
        ? errorDocument.detail
        : streamResponse.statusText
    throw new ApiRequestError(detail || "Could not read Run events", streamResponse.status)
  }
  if (!streamResponse.body) {
    throw new ApiRequestError("Run event stream is unavailable", streamResponse.status)
  }

  const streamReader = streamResponse.body.getReader()
  const utf8Decoder = new TextDecoder()
  let bufferedText = ""
  let newestSequence = afterSeq
  try {
    while (true) {
      const { done, value } = await streamReader.read()
      bufferedText += utf8Decoder.decode(value, { stream: !done })
      const eventFrames = bufferedText.split(/\r?\n\r?\n/)
      const unfinishedFrame = eventFrames.pop() ?? ""
      bufferedText = done ? "" : unfinishedFrame
      if (done && unfinishedFrame) eventFrames.push(unfinishedFrame)
      for (const eventFrame of eventFrames) {
        const eventPayload = eventFrame
          .split(/\r?\n/)
          .filter((eventLine) => eventLine.startsWith("data:"))
          .map((eventLine) => eventLine.slice(5).trimStart())
          .join("\n")
        if (!eventPayload) continue
        const agentRunEvent = JSON.parse(eventPayload) as AgentRunEvent
        newestSequence = Math.max(newestSequence, agentRunEvent.seq)
        onEvent(agentRunEvent)
      }
      if (done) return newestSequence
    }
  } finally {
    streamReader.releaseLock()
  }
}

/** Start an Agent run with a one-request idempotency key. */
export async function createAgentRun(input: {
  agentId: string
  conversationId: string | null
  message: string
}): Promise<AgentRunDetail> {
  const response = await apiClient.post<AgentRunDetail>(
    "/agent-runs",
    {
      agent_id: input.agentId,
      conversation_id: input.conversationId,
      message: input.message,
    },
    { headers: { "Idempotency-Key": crypto.randomUUID() } }
  )
  return response.data
}

/** 通过当前成员的组织权限取消正在运行的 Run。 */
export async function cancelAgentRun(runId: string): Promise<AgentRunDetail> {
  const response = await apiClient.post<AgentRunDetail>(
    `/agent-runs/${encodeURIComponent(runId)}/cancel`
  )
  return response.data
}
