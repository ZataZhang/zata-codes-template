import { apiGet, apiPost } from './client'

/** 组织管理接口返回的组织。 */
export type Organization = {
  id: string
  name: string
  is_active: boolean
  created_at: string | null
}

/** 获取所有组织。 */
export async function listOrganizations(): Promise<{ items: Organization[] }> {
  return apiGet<{ items: Organization[] }>('/admin/organizations')
}

/** 创建组织。 */
export async function createOrganization(name: string): Promise<Organization> {
  return apiPost<Organization>('/admin/organizations', { name })
}

/** 启用组织。 */
export async function enableOrganization(
  organizationId: string
): Promise<Organization> {
  return apiPost<Organization>(
    `/admin/organizations/${organizationId}/enable`,
    {}
  )
}

/** 停用组织。 */
export async function disableOrganization(
  organizationId: string
): Promise<Organization> {
  return apiPost<Organization>(
    `/admin/organizations/${organizationId}/disable`,
    {}
  )
}
