import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  createAdmin,
  disableAdmin,
  enableAdmin,
  listAdmins,
  unbindAdminOidc,
  type AdminAccount,
  type CreateAdminPayload,
} from '@/api/admins'
import { getAdminOidcStatus, type AdminRole } from '@/api/auth'
import { listOrganizations } from '@/api/organizations'
import { useAuthStore } from '@/stores/auth-store'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { AdminPageShell } from '@/features/shared/admin-page-shell'
import { filterAdminAccounts } from './admin-filter'

const ADMINS_QUERY_KEY = ['admin', 'admins'] as const
const ORGANIZATIONS_QUERY_KEY = ['admin', 'organizations'] as const

type AdminFormState = {
  username: string
  email: string
  displayName: string
  role: AdminRole
  organizationId: string
  password: string
}

type PendingAdminAction = {
  admin: AdminAccount
  action: 'enable' | 'disable' | 'unbind'
}

/** 渲染平台管理员目录与管理员创建表单。 */
export function Admins() {
  const queryClient = useQueryClient()
  const { t } = useTranslation()
  const { auth } = useAuthStore()
  const [pendingAction, setPendingAction] = useState<PendingAdminAction | null>(
    null
  )
  const [keywordFilter, setKeywordFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'active' | 'disabled'
  >('all')
  const [form, setForm] = useState<AdminFormState>({
    username: '',
    email: '',
    displayName: '',
    role: 'platform',
    organizationId: '',
    password: '',
  })

  const adminsQuery = useQuery({
    queryKey: ADMINS_QUERY_KEY,
    queryFn: listAdmins,
  })
  const organizationsQuery = useQuery({
    queryKey: ORGANIZATIONS_QUERY_KEY,
    queryFn: listOrganizations,
  })
  const oidcStatusQuery = useQuery({
    queryKey: ['admin', 'auth', 'oidc-status'],
    queryFn: getAdminOidcStatus,
  })
  const oidcEnabled = oidcStatusQuery.data?.enabled === true

  const activePlatformAdminCount = useMemo(
    () =>
      (adminsQuery.data?.items ?? []).filter(
        (adminAccount) =>
          adminAccount.role === 'platform' && adminAccount.status === 'active'
      ).length,
    [adminsQuery.data?.items]
  )

  const invalidateAdminData = () => {
    void queryClient.invalidateQueries({ queryKey: ADMINS_QUERY_KEY })
  }

  const createMutation = useMutation({
    mutationFn: createAdmin,
    onSuccess: () => {
      setForm({
        username: '',
        email: '',
        displayName: '',
        role: 'platform',
        organizationId: '',
        password: '',
      })
      toast.success(t('admins.created'))
      invalidateAdminData()
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : t('admins.createFailed')
      ),
  })
  const actionMutation = useMutation({
    mutationFn: ({ admin, action }: PendingAdminAction) => {
      if (action === 'unbind') return unbindAdminOidc(admin.id)
      return action === 'disable'
        ? disableAdmin(admin.id)
        : enableAdmin(admin.id)
    },
    onSuccess: (_, variables) => {
      toast.success(
        variables.action === 'unbind'
          ? t('admins.unbound')
          : variables.action === 'disable'
            ? t('admins.disabled')
            : t('admins.enabled')
      )
      invalidateAdminData()
    },
    onError: (error) =>
      toast.error(
        error instanceof Error ? error.message : t('admins.actionFailed')
      ),
    onSettled: () => setPendingAction(null),
  })

  const handleCreate = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (form.role === 'org' && !form.organizationId) return
    if (!form.password.trim() && !oidcEnabled) {
      toast.error(t('admins.passwordRequiredWhenOidcUnavailable'))
      return
    }
    const payload: CreateAdminPayload = {
      username: form.username.trim(),
      email: form.email.trim(),
      role: form.role,
    }
    if (form.displayName.trim()) payload.display_name = form.displayName.trim()
    if (form.role === 'org') payload.organization_id = form.organizationId
    if (form.password) payload.password = form.password
    createMutation.mutate(payload)
  }

  const adminAccounts = adminsQuery.data?.items ?? []
  const organizations = organizationsQuery.data?.items ?? []
  const filteredAdmins = filterAdminAccounts(
    adminAccounts,
    keywordFilter,
    statusFilter
  )

  return (
    <>
      <AdminPageShell
        title={t('admins.title')}
        description={t('admins.description')}
      >
        <form
          className='grid max-w-5xl gap-4 rounded-md border p-4 sm:grid-cols-2 lg:grid-cols-3'
          onSubmit={handleCreate}
        >
          <div className='grid gap-2'>
            <Label htmlFor='admin-username'>{t('admins.username')}</Label>
            <Input
              id='admin-username'
              data-testid='admin-username'
              value={form.username}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  username: event.target.value,
                }))
              }
              autoComplete='off'
              required
            />
          </div>
          <div className='grid gap-2'>
            <Label htmlFor='admin-email'>{t('admins.email')}</Label>
            <Input
              id='admin-email'
              data-testid='admin-email'
              type='email'
              value={form.email}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  email: event.target.value,
                }))
              }
              required
            />
          </div>
          <div className='grid gap-2'>
            <Label htmlFor='admin-display-name'>
              {t('admins.displayName')}
            </Label>
            <Input
              id='admin-display-name'
              value={form.displayName}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  displayName: event.target.value,
                }))
              }
            />
          </div>
          <div className='grid gap-2'>
            <Label htmlFor='admin-role'>{t('admins.role')}</Label>
            <Select
              data-testid='admin-role'
              value={form.role}
              onValueChange={(value) =>
                setForm((current) => ({
                  ...current,
                  role: value as AdminRole,
                  organizationId: value === 'org' ? current.organizationId : '',
                }))
              }
            >
              <SelectTrigger id='admin-role' aria-label={t('admins.role')}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='platform'>
                  {t('admins.platformRole')}
                </SelectItem>
                <SelectItem value='org'>
                  {t('admins.organizationRole')}
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
          {form.role === 'org' && (
            <div className='grid gap-2'>
              <Label htmlFor='admin-organization'>
                {t('admins.organization')}
              </Label>
              <Select
                data-testid='admin-organization'
                value={form.organizationId}
                onValueChange={(organizationId) =>
                  setForm((current) => ({ ...current, organizationId }))
                }
              >
                <SelectTrigger
                  id='admin-organization'
                  aria-label={t('admins.organization')}
                >
                  <SelectValue placeholder={t('admins.selectOrganization')} />
                </SelectTrigger>
                <SelectContent>
                  {organizations
                    .filter((organization) => organization.is_active)
                    .map((organization) => (
                      <SelectItem key={organization.id} value={organization.id}>
                        {organization.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className='grid gap-2'>
            <Label htmlFor='admin-password'>{t('admins.password')}</Label>
            <Input
              id='admin-password'
              data-testid='admin-password'
              type='password'
              autoComplete='new-password'
              required={!oidcEnabled}
              value={form.password}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  password: event.target.value,
                }))
              }
            />
            <p className='text-xs text-muted-foreground'>
              {t('admins.passwordHelp')}
            </p>
          </div>
          <div className='flex items-end lg:col-span-3'>
            <Button
              data-testid='admin-create'
              type='submit'
              disabled={
                createMutation.isPending ||
                (form.role === 'org' && !form.organizationId)
              }
            >
              {createMutation.isPending
                ? t('admins.creating')
                : t('admins.create')}
            </Button>
          </div>
        </form>

        {!oidcEnabled && !oidcStatusQuery.isLoading && (
          <p role='status' className='text-sm text-muted-foreground'>
            {t('admins.oidcUnavailable')}
          </p>
        )}

        <div className='flex flex-wrap items-center gap-2'>
          <Input
            data-testid='admins-search'
            aria-label={t('admins.searchPlaceholder')}
            placeholder={t('admins.searchPlaceholder')}
            value={keywordFilter}
            onChange={(event) => setKeywordFilter(event.target.value)}
            className='h-9 w-72'
          />
          <Select
            value={statusFilter}
            onValueChange={(value) =>
              setStatusFilter(value as 'all' | 'active' | 'disabled')
            }
          >
            <SelectTrigger
              data-testid='admins-status-filter'
              aria-label={t('admins.statusFilter')}
              className='h-9 w-44'
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value='all'>{t('admins.allStatuses')}</SelectItem>
              <SelectItem value='active'>{t('common.active')}</SelectItem>
              <SelectItem value='disabled'>{t('common.disabled')}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className='overflow-x-auto rounded-md border'>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('admins.username')}</TableHead>
                <TableHead>{t('admins.email')}</TableHead>
                <TableHead>{t('admins.role')}</TableHead>
                <TableHead>{t('admins.organization')}</TableHead>
                <TableHead>{t('admins.oidc')}</TableHead>
                <TableHead>{t('common.status')}</TableHead>
                <TableHead className='text-end'>
                  {t('common.actions')}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {adminsQuery.isLoading ? (
                <TableRow>
                  <TableCell colSpan={7} className='h-24 text-center'>
                    {t('common.loading')}
                  </TableCell>
                </TableRow>
              ) : adminsQuery.isError ? (
                <TableRow>
                  <TableCell
                    colSpan={7}
                    className='h-24 text-center text-destructive'
                  >
                    {t('admins.loadFailed')}
                  </TableCell>
                </TableRow>
              ) : filteredAdmins.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className='h-24 text-center'>
                    {t('admins.empty')}
                  </TableCell>
                </TableRow>
              ) : (
                filteredAdmins.map((adminAccount) => {
                  const isSelf = adminAccount.id === auth.user?.user_id
                  const wouldDisableLastPlatformAdmin =
                    adminAccount.role === 'platform' &&
                    adminAccount.status === 'active' &&
                    activePlatformAdminCount <= 1
                  return (
                    <TableRow key={adminAccount.id}>
                      <TableCell className='font-medium'>
                        {adminAccount.display_name || adminAccount.username}
                        <span className='block text-xs text-muted-foreground'>
                          {adminAccount.username}
                        </span>
                      </TableCell>
                      <TableCell>{adminAccount.email ?? '—'}</TableCell>
                      <TableCell>
                        {adminAccount.role === 'platform'
                          ? t('admins.platformRole')
                          : t('admins.organizationRole')}
                      </TableCell>
                      <TableCell>
                        {adminAccount.organization_name ?? '—'}
                      </TableCell>
                      <TableCell>
                        {adminAccount.oidc_bound
                          ? t('admins.oidcBound')
                          : t('admins.oidcNotBound')}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            adminAccount.status === 'active'
                              ? 'secondary'
                              : 'outline'
                          }
                        >
                          {adminAccount.status === 'active'
                            ? t('common.active')
                            : t('common.disabled')}
                        </Badge>
                      </TableCell>
                      <TableCell className='text-end'>
                        <div className='flex flex-wrap justify-end gap-2'>
                          <Button
                            size='sm'
                            variant={
                              adminAccount.status === 'active'
                                ? 'outline'
                                : 'default'
                            }
                            disabled={
                              (adminAccount.status === 'active' && isSelf) ||
                              (adminAccount.status === 'active' &&
                                wouldDisableLastPlatformAdmin)
                            }
                            title={
                              isSelf && adminAccount.status === 'active'
                                ? t('admins.cannotDisableSelf')
                                : wouldDisableLastPlatformAdmin
                                  ? t('admins.cannotDisableLastPlatformAdmin')
                                  : undefined
                            }
                            onClick={() =>
                              setPendingAction({
                                admin: adminAccount,
                                action:
                                  adminAccount.status === 'active'
                                    ? 'disable'
                                    : 'enable',
                              })
                            }
                          >
                            {adminAccount.status === 'active'
                              ? t('common.disable')
                              : t('common.enable')}
                          </Button>
                          {adminAccount.oidc_bound && (
                            <Button
                              size='sm'
                              variant='outline'
                              onClick={() =>
                                setPendingAction({
                                  admin: adminAccount,
                                  action: 'unbind',
                                })
                              }
                            >
                              {t('admins.unbind')}
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </div>
      </AdminPageShell>

      <ConfirmDialog
        open={pendingAction !== null}
        onOpenChange={(open) => {
          if (!open) setPendingAction(null)
        }}
        title={
          pendingAction?.action === 'unbind'
            ? t('admins.unbindTitle')
            : pendingAction?.action === 'disable'
              ? t('admins.disableTitle')
              : t('admins.enableTitle')
        }
        desc={
          pendingAction?.action === 'unbind'
            ? t('admins.unbindConfirmation', {
                name: pendingAction.admin.display_name,
              })
            : pendingAction?.action === 'disable'
              ? t('admins.disableConfirmation', {
                  name: pendingAction.admin.display_name,
                })
              : t('admins.enableConfirmation', {
                  name: pendingAction?.admin.display_name,
                })
        }
        confirmText={t('common.confirm')}
        destructive={pendingAction?.action !== 'enable'}
        isLoading={actionMutation.isPending}
        handleConfirm={() => {
          if (pendingAction) actionMutation.mutate(pendingAction)
        }}
      />
    </>
  )
}
