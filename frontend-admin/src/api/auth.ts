import { apiGet, apiPost } from './client'

export type UserSession = {
  user_id: string
  display_name: string
  email: string
}

export type LoginCredentials = {
  identifier: string
  password: string
}

export async function login(credentials: LoginCredentials): Promise<UserSession> {
  return apiPost<UserSession>('/auth/login', credentials)
}

export async function logout(): Promise<void> {
  await apiPost<void>('/auth/logout', {})
}

export async function getCurrentSession(): Promise<UserSession> {
  return apiGet<UserSession>('/auth/me')
}
