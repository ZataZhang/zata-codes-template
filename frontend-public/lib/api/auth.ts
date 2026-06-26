import { apiGet, apiPost } from "./client"

export type UserSession = {
  user_id: string
  display_name: string
  email: string
}

export type LoginCredentials = {
  identifier: string
  password: string
}

export type RegisterPayload = {
  email: string
  password: string
  displayName: string
}

export async function login(credentials: LoginCredentials): Promise<UserSession> {
  return apiPost<UserSession>("/auth/login", credentials)
}

export async function logout(): Promise<void> {
  await apiPost<void>("/auth/logout", {})
}

export async function getCurrentSession(): Promise<UserSession> {
  return apiGet<UserSession>("/auth/me")
}

export async function register(payload: RegisterPayload): Promise<UserSession> {
  return apiPost<UserSession>("/auth/register", {
    display_name: payload.displayName,
    email: payload.email,
    password: payload.password,
  })
}
