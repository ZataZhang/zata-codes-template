import { apiGet, apiPost } from './client'

export type PublicUserStatus = 'active' | 'disabled'

export type PublicUser = {
  id: string
  email: string
  display_name: string
  status: PublicUserStatus
  created_at: string | null
}

export type PublicUserListResponse = {
  items: PublicUser[]
  total: number
  page: number
  page_size: number
}

export type ListPublicUsersParams = {
  page?: number
  page_size?: number
  status?: PublicUserStatus
  keyword?: string
}

export async function listPublicUsers(
  params: ListPublicUsersParams = {}
): Promise<PublicUserListResponse> {
  return apiGet<PublicUserListResponse>('/admin/users', { params })
}

export async function getPublicUser(userId: string): Promise<PublicUser> {
  return apiGet<PublicUser>(`/admin/users/${userId}`)
}

export async function enablePublicUser(userId: string): Promise<PublicUser> {
  return apiPost<PublicUser>(`/admin/users/${userId}/enable`, {})
}

export async function disablePublicUser(userId: string): Promise<PublicUser> {
  return apiPost<PublicUser>(`/admin/users/${userId}/disable`, {})
}
