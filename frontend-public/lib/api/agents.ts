import { apiClient } from "@/lib/api/client"

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
