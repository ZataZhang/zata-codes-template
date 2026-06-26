import { apiGet, apiPost } from './client'

export type UserSession = {
  user_id: string
  display_name: string
  username: string
}

export type LoginCredentials = {
  identifier: string
  password: string
}

export async function login(credentials: LoginCredentials): Promise<UserSession> {
  return apiPost<UserSession>('/admin/auth/login', credentials)
}

export async function logout(): Promise<void> {
  await apiPost<void>('/admin/auth/logout', {})
}

export async function getCurrentSession(): Promise<UserSession> {
  return apiGet<UserSession>('/admin/auth/me')
}
