import { describe, expect, it } from 'vitest'
import type { AdminAccount } from '@/api/admins'
import { filterAdminAccounts } from './admin-filter'

const legacyAdminAccount: AdminAccount = {
  id: 'legacy-admin',
  username: 'legacy-admin',
  display_name: 'Legacy Admin',
  email: null,
  role: 'platform',
  organization_id: null,
  organization_name: null,
  status: 'active',
  oidc_bound: false,
  created_at: null,
}

describe('filterAdminAccounts', () => {
  it('searches legacy admins with a null email without throwing', () => {
    expect(
      filterAdminAccounts([legacyAdminAccount], 'legacy-admin', 'all')
    ).toEqual([legacyAdminAccount])
    expect(
      filterAdminAccounts([legacyAdminAccount], 'missing@example.com', 'all')
    ).toEqual([])
  })
})
