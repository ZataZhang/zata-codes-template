import type { AdminRole } from './auth'
import { apiGet, apiPost } from './client'

/** 管理员目录接口返回的管理员。 */
export type AdminAccount = {
  id: string
  username: string
  display_name: string
  email: string | null
  role: AdminRole
  organization_id: string | null
  organization_name: string | null
  status: 'active' | 'disabled'
  oidc_bound: boolean
  created_at: string | null
}

/** 创建管理员请求。 */
export type CreateAdminPayload = {
  username: string
  email: string
  display_name?: string
  role: AdminRole
  organization_id?: string
  password?: string
}

/** 获取管理员目录。 */
export async function listAdmins(): Promise<{ items: AdminAccount[] }> {
  return apiGet<{ items: AdminAccount[] }>('/admin/admins')
}

/** 创建管理员。 */
export async function createAdmin(
  payload: CreateAdminPayload
): Promise<AdminAccount> {
  return apiPost<AdminAccount>('/admin/admins', payload)
}

/** 启用管理员。 */
export async function enableAdmin(adminId: string): Promise<AdminAccount> {
  return apiPost<AdminAccount>(`/admin/admins/${adminId}/enable`, {})
}

/** 禁用管理员。 */
export async function disableAdmin(adminId: string): Promise<AdminAccount> {
  return apiPost<AdminAccount>(`/admin/admins/${adminId}/disable`, {})
}

/** 清除管理员的企业账号绑定。 */
export async function unbindAdminOidc(adminId: string): Promise<AdminAccount> {
  return apiPost<AdminAccount>(`/admin/admins/${adminId}/unbind-oidc`, {})
}
