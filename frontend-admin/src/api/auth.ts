import { apiGet, apiPost } from './client'

/** 管理员角色。 */
export type AdminRole = 'platform' | 'org'

/** 管理员认证接口返回的会话。 */
export type UserSession = {
  user_id: string
  display_name: string
  username: string
  role: AdminRole
  organization_id: string | null
  organization_name: string | null
}

/** 管理员密码登录参数。 */
export type LoginCredentials = {
  identifier: string
  password: string
}

/** 使用密码登录并返回管理员会话。 */
export async function login(
  credentials: LoginCredentials
): Promise<UserSession> {
  return apiPost<UserSession>('/admin/auth/login', credentials)
}

/** 退出当前管理员会话。 */
export async function logout(): Promise<void> {
  await apiPost<void>('/admin/auth/logout', {})
}

/** 获取当前管理员会话。 */
export async function getCurrentSession(): Promise<UserSession> {
  return apiGet<UserSession>('/admin/auth/me')
}

/** 查询管理员企业账号登录是否可用。 */
export async function getAdminOidcStatus(): Promise<{ enabled: boolean }> {
  return apiGet<{ enabled: boolean }>('/admin/auth/oidc/status')
}

/** 管理员企业账号登录的后端起始地址。 */
export const ADMIN_OIDC_START_URL = '/api/admin/auth/oidc/start'
