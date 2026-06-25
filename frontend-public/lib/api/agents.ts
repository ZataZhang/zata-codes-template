import { apiDelete, apiGet, apiPost, apiPut } from "./client"
import type {
  Agent,
  AgentCreatePayload,
  AgentUpdatePayload,
} from "@/lib/types/agent"

export async function listAgents(): Promise<Agent[]> {
  return apiGet<Agent[]>("/agents")
}

export async function getAgent(agentId: string): Promise<Agent> {
  return apiGet<Agent>(`/agents/${agentId}`)
}

export async function createAgent(payload: AgentCreatePayload): Promise<Agent> {
  return apiPost<Agent>("/agents", payload)
}

export async function updateAgent(
  agentId: string,
  payload: AgentUpdatePayload
): Promise<Agent> {
  return apiPut<Agent>(`/agents/${agentId}`, payload)
}

export async function deleteAgent(agentId: string): Promise<void> {
  return apiDelete(`/agents/${agentId}`)
}
