import type { AdminAccount } from '@/api/admins'

export type AdminStatusFilter = AdminAccount['status'] | 'all'

/** 按用户名、邮箱、显示名与状态过滤管理员账户。 */
export function filterAdminAccounts(
  adminAccounts: AdminAccount[],
  keywordFilter: string,
  statusFilter: AdminStatusFilter
): AdminAccount[] {
  const normalizedKeyword = keywordFilter.trim().toLowerCase()
  return adminAccounts.filter((adminAccount) => {
    const matchesKeyword =
      !normalizedKeyword ||
      [
        adminAccount.username,
        adminAccount.email ?? '',
        adminAccount.display_name,
      ].some((value) => value.toLowerCase().includes(normalizedKeyword))
    const matchesStatus =
      statusFilter === 'all' || adminAccount.status === statusFilter
    return matchesKeyword && matchesStatus
  })
}
