import { apiGet, apiPost } from "./client"

/** Public 认证接口返回的会话。 */
export type UserSession = {
  user_id: string
  display_name: string
  email: string
}

/** Public 密码登录参数。 */
export type LoginCredentials = {
  identifier: string
  password: string
}

/** Public 注册参数。 */
export type RegisterPayload = {
  email: string
  password: string
  displayName: string
}

/** 使用密码登录并返回用户会话。 */
export async function login(
  credentials: LoginCredentials
): Promise<UserSession> {
  return apiPost<UserSession>("/auth/login", credentials)
}

/** 退出当前用户会话。 */
export async function logout(): Promise<void> {
  await apiPost<void>("/auth/logout", {})
}

/** 获取当前用户会话。 */
export async function getCurrentSession(): Promise<UserSession> {
  return apiGet<UserSession>("/auth/me")
}

/** 注册用户并返回新会话。 */
export async function register(payload: RegisterPayload): Promise<UserSession> {
  return apiPost<UserSession>("/auth/register", {
    display_name: payload.displayName,
    email: payload.email,
    password: payload.password,
  })
}

/** 查询 public 企业账号登录是否可用。 */
export async function getUserOidcStatus(): Promise<{ enabled: boolean }> {
  return apiGet<{ enabled: boolean }>("/auth/oidc/status")
}

/** 读取公开的注册模式。 */
export async function getRegistrationStatus(): Promise<{
  registration_mode: "both" | "oidc_only" | "closed"
}> {
  return apiGet("/auth/registration-status")
}

/** Public 企业账号登录的后端起始地址。 */
export const USER_OIDC_START_URL = "/api/auth/oidc/start"

/** 前台可用的注册模式。 */
export type RegistrationMode = "both" | "oidc_only" | "closed"
