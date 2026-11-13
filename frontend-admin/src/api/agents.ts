import { apiDelete, apiGet, apiPost, apiPut } from './client'

export type AgentDefinition = {
  id: string
  name: string
  description: string
  instructions: string
  model_name: string | null
  skill_id: string | null
  is_enabled: boolean
  is_published: boolean
  is_runnable: boolean
  unavailable_reason: string | null
  a2a_card_url: string | null
  created_at: string
  updated_at: string
}

export type SkillDefinition = {
  id: string
  name: string
  description: string
  current_version: number
  created_at: string
  updated_at: string
}

export type SkillRevision = {
  id: string
  skill_id: string
  version: number
  body: string
  checksum: string
  created_at: string
}

export type A2APeer = {
  id: string
  name: string
  card_url: string
  endpoint_url: string
  is_approved: boolean
  is_enabled: boolean
  created_at: string
}

export type A2APeerApproval = A2APeer & { organization_id: string }

export type AgentRun = {
  id: string
  agent_id: string
  agent_name: string
  owner_id: string
  status: string
  created_at: string
  finished_at: string | null
  event_count: number
}

/** Load the Agent definitions scoped to the signed-in administrator's organization. */
export async function listAgents(): Promise<AgentDefinition[]> {
  return (await apiGet<{ items: AgentDefinition[] }>('/admin/agents')).items
}

/** Create a draft Agent in the administrator's organization. */
export async function createAgent(input: {
  name: string
  description: string
  instructions: string
  model_name: string | null
  skill_id: string | null
}): Promise<AgentDefinition> {
  return apiPost<AgentDefinition>('/admin/agents', input)
}

/** Publish an organization Agent to its members. */
export async function setAgentPublished(agentId: string, published: boolean) {
  const action = published ? 'publish' : 'unpublish'
  return apiPost<AgentDefinition>(
    `/admin/agents/${encodeURIComponent(agentId)}/${action}`
  )
}

/** Load Skill definitions and their current version numbers. */
export async function listSkills(): Promise<SkillDefinition[]> {
  return (await apiGet<{ items: SkillDefinition[] }>('/admin/skills')).items
}

/** Create a versioned Skill with its first immutable revision. */
export async function createSkill(input: {
  name: string
  description: string
  body: string
}): Promise<SkillDefinition> {
  return apiPost<SkillDefinition>('/admin/skills', input)
}

/** Read the immutable revisions for a Skill. */
export async function listSkillVersions(
  skillId: string
): Promise<SkillRevision[]> {
  return (
    await apiGet<{ items: SkillRevision[] }>(
      `/admin/skills/${encodeURIComponent(skillId)}/versions`
    )
  ).items
}

/** Append a new Skill revision. */
export async function appendSkillVersion(skillId: string, body: string) {
  return apiPost<SkillRevision>(
    `/admin/skills/${encodeURIComponent(skillId)}/versions`,
    { body }
  )
}

/** Compare two revisions without modifying either stored version. */
export async function compareSkillVersions(
  skillId: string,
  fromVersion: number,
  toVersion: number
) {
  const query = new URLSearchParams({
    from_version: String(fromVersion),
    to_version: String(toVersion),
  })
  return apiGet<{ from_version: SkillRevision; to_version: SkillRevision }>(
    `/admin/skills/${encodeURIComponent(skillId)}/compare?${query}`
  )
}

/** Restore old Skill contents by appending a new version. */
export async function restoreSkillVersion(skillId: string, version: number) {
  return apiPost<SkillRevision>(
    `/admin/skills/${encodeURIComponent(skillId)}/restore/${version}`
  )
}

/** List organization approved and pending A2A peers without saved credentials. */
export async function listA2APeers(): Promise<A2APeer[]> {
  return (await apiGet<{ items: A2APeer[] }>('/admin/a2a-peers')).items
}

/** List peer endpoints waiting for a platform network policy review. */
export async function listPendingA2APeers(): Promise<A2APeerApproval[]> {
  return (
    await apiGet<{ items: A2APeerApproval[] }>('/admin/a2a-peers/pending')
  ).items
}

/** Approve a registered peer after platform network policy review. */
export async function approveA2APeer(peerId: string): Promise<A2APeer> {
  return apiPost<A2APeer>(
    `/admin/a2a-peers/${encodeURIComponent(peerId)}/approve`
  )
}

/** Register an external A2A peer for platform policy approval. */
export async function createA2APeer(input: {
  name: string
  card_url: string
  endpoint_url: string
  credential_env_alias?: string
}): Promise<A2APeer> {
  return apiPost<A2APeer>('/admin/a2a-peers', input)
}

/** Rotate an outbound peer token by reading a server-side environment reference. */
export async function rotateA2APeerCredential(
  peerId: string,
  credentialEnvAlias: string
) {
  return apiPut<void>(
    `/admin/a2a-peers/${encodeURIComponent(peerId)}/credential`,
    {
      credential_env_alias: credentialEnvAlias,
    }
  )
}

/** List the one-time token metadata for an Agent. */
export async function createA2ACredential(agentId: string, name: string) {
  return apiPost<{ id: string; token: string }>(
    `/admin/agents/${encodeURIComponent(agentId)}/a2a-credentials`,
    { name }
  )
}

/** Remove a credential from future A2A authorization. */
export async function revokeA2ACredential(credentialId: string) {
  return apiDelete(`/admin/a2a-credentials/${encodeURIComponent(credentialId)}`)
}

/** List low-sensitivity run summaries for the current organization. */
export async function listOrganizationRuns(): Promise<AgentRun[]> {
  return (
    await apiGet<{ items: AgentRun[]; total: number }>('/admin/agent-runs')
  ).items
}

/** Read metadata-only event projections for a Run. */
export async function getOrganizationRunEvents(runId: string) {
  return apiGet<{
    items: {
      seq: number
      event_type: string
      occurred_at: string
      payload: Record<string, unknown>
    }[]
  }>(`/admin/agent-runs/${encodeURIComponent(runId)}/events`)
}

/** Replace an Agent configuration to disable it without deleting its history. */
export async function updateAgent(agent: AgentDefinition, enabled: boolean) {
  return apiPut<AgentDefinition>(
    `/admin/agents/${encodeURIComponent(agent.id)}`,
    {
      name: agent.name,
      description: agent.description,
      instructions: agent.instructions,
      model_name: agent.model_name,
      skill_id: agent.skill_id,
      is_enabled: enabled,
    }
  )
}
