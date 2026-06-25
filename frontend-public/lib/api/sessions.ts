import { apiDelete, apiGet, apiPost } from "./client"
import type {
  ChatMessage,
  ChatMessageCreatePayload,
  ChatSession,
  ChatSessionCreatePayload,
} from "@/lib/types/session"

export async function listSessions(): Promise<ChatSession[]> {
  return apiGet<ChatSession[]>("/sessions")
}

export async function getSession(sessionId: string): Promise<ChatSession> {
  return apiGet<ChatSession>(`/sessions/${sessionId}`)
}

export async function createSession(
  payload: ChatSessionCreatePayload
): Promise<ChatSession> {
  return apiPost<ChatSession>("/sessions", payload)
}

export async function deleteSession(sessionId: string): Promise<void> {
  return apiDelete(`/sessions/${sessionId}`)
}

export async function listMessages(sessionId: string): Promise<ChatMessage[]> {
  return apiGet<ChatMessage[]>(`/sessions/${sessionId}/messages`)
}

export async function sendMessage(
  sessionId: string,
  payload: ChatMessageCreatePayload
): Promise<ChatMessage> {
  return apiPost<ChatMessage>(`/sessions/${sessionId}/messages`, payload)
}
