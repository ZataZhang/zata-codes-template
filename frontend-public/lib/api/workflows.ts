import { apiDelete, apiGet, apiPost, apiPut } from "./client"
import type {
  Workflow,
  WorkflowCreatePayload,
  WorkflowUpdatePayload,
} from "@/lib/types/workflow"

export async function listWorkflows(): Promise<Workflow[]> {
  return apiGet<Workflow[]>("/workflows")
}

export async function getWorkflow(workflowId: string): Promise<Workflow> {
  return apiGet<Workflow>(`/workflows/${workflowId}`)
}

export async function createWorkflow(
  payload: WorkflowCreatePayload
): Promise<Workflow> {
  return apiPost<Workflow>("/workflows", payload)
}

export async function updateWorkflow(
  workflowId: string,
  payload: WorkflowUpdatePayload
): Promise<Workflow> {
  return apiPut<Workflow>(`/workflows/${workflowId}`, payload)
}

export async function deleteWorkflow(workflowId: string): Promise<void> {
  return apiDelete(`/workflows/${workflowId}`)
}

export async function runWorkflow(workflowId: string): Promise<unknown> {
  return apiPost<unknown>(`/workflows/${workflowId}/run`, {})
}
