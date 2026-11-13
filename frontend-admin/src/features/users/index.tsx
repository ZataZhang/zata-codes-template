import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { listOrganizations } from '@/api/organizations'
import {
  type PublicUser,
  disablePublicUser,
  enablePublicUser,
  listPublicUsers,
  setPublicUserOrganization,
} from '@/api/users'
import { useAuthStore } from '@/stores/auth-store'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
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
/* jscpd:ignore-start -- 后台目录页面复用公共布局组件导入，不包含用户或权限业务逻辑。 */
import { ConfigDrawer } from '@/components/config-drawer'
import { Header } from '@/components/layout/header'
import { Main } from '@/components/layout/main'
import { ProfileDropdown } from '@/components/profile-dropdown'
import { Search } from '@/components/search'
import { ThemeSwitch } from '@/components/theme-switch'
/* jscpd:ignore-end */

const PUBLIC_USERS_QUERY_KEY = ['admin', 'public-users'] as const

/** Format an ISO date string for display. */
function formatDateTime(value: string | null): string {
  if (!value) return '-'
  const parsedDate = new Date(value)
  return Number.isNaN(parsedDate.getTime()) ? '-' : parsedDate.toLocaleString()
}

/** Render the Users component. */
export function Users() {
  const queryClient = useQueryClient()
  const { t } = useTranslation()
  const { auth } = useAuthStore()
  const isPlatformAdmin = auth.user?.role === 'platform'
  const [keywordInput, setKeywordInput] = useState('')
  const [appliedKeyword, setAppliedKeyword] = useState('')
  const [organizationFilter, setOrganizationFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'active' | 'disabled'
  >('all')
  const [pendingUser, setPendingUser] = useState<PublicUser | null>(null)

  const organizationsQuery = useQuery({
    queryKey: ['admin', 'organizations'],
    queryFn: listOrganizations,
    enabled: isPlatformAdmin,
  })
  const usersQuery = useQuery({
    queryKey: [
      ...PUBLIC_USERS_QUERY_KEY,
      appliedKeyword,
      isPlatformAdmin ? organizationFilter : 'own-organization',
      statusFilter,
    ],
    queryFn: () =>
      listPublicUsers({
        ...(appliedKeyword ? { keyword: appliedKeyword } : {}),
        ...(statusFilter !== 'all' ? { status: statusFilter } : {}),
        ...(isPlatformAdmin && organizationFilter !== 'all'
          ? { organization_id: organizationFilter }
          : {}),
      }),
  })

  const toggleMutation = useMutation({
    mutationFn: (targetUser: PublicUser) =>
      targetUser.status === 'active'
        ? disablePublicUser(targetUser.id)
        : enablePublicUser(targetUser.id),
    onSuccess: (updatedUser) => {
      toast.success(
        t(
          updatedUser.status === 'active' ? 'users.enabled' : 'users.disabled',
          {
            name: updatedUser.display_name,
          }
        )
      )
      void queryClient.invalidateQueries({ queryKey: PUBLIC_USERS_QUERY_KEY })
    },
    onError: (error) => {
      toast.error(
        error instanceof Error ? error.message : t('users.actionFailed')
      )
    },
    onSettled: () => setPendingUser(null),
  })

  const organizationMutation = useMutation({
    mutationFn: ({
      userId,
      organizationId,
    }: {
      userId: string
      organizationId: string
    }) => setPublicUserOrganization(userId, organizationId),
    onSuccess: (updatedUser) => {
      toast.success(
        t('users.organizationUpdated', { name: updatedUser.display_name })
      )
      void queryClient.invalidateQueries({ queryKey: PUBLIC_USERS_QUERY_KEY })
    },
    onError: () => toast.error(t('users.organizationUpdateFailed')),
  })

  const publicUsers: PublicUser[] = usersQuery.data?.items ?? []

  /** Render the table body rows. */
  function renderTableBody() {
    if (usersQuery.isLoading) {
      return (
        <TableRow>
          <TableCell colSpan={6} className='h-24 text-center'>
            {t('common.loading')}
          </TableCell>
        </TableRow>
      )
    }
    if (usersQuery.isError) {
      return (
        <TableRow>
          <TableCell colSpan={6} className='h-24 text-center text-destructive'>
            {t('users.loadFailed')}
          </TableCell>
        </TableRow>
      )
    }
    if (publicUsers.length === 0) {
      return (
        <TableRow>
          <TableCell colSpan={6} className='h-24 text-center'>
            {t('users.empty')}
          </TableCell>
        </TableRow>
      )
    }
    return publicUsers.map((publicUser) => (
      <TableRow key={publicUser.id}>
        <TableCell>{publicUser.display_name}</TableCell>
        <TableCell>{publicUser.email}</TableCell>
        <TableCell>
          {isPlatformAdmin ? (
            <Select
              value={publicUser.organization_id}
              onValueChange={(organizationId) =>
                organizationMutation.mutate({
                  userId: publicUser.id,
                  organizationId,
                })
              }
              disabled={organizationMutation.isPending}
            >
              <SelectTrigger
                data-testid={`user-organization-${publicUser.id}`}
                className='h-8 w-48'
                aria-label={t('users.organizationFor', {
                  name: publicUser.display_name,
                })}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(organizationsQuery.data?.items ?? []).map((organization) => (
                  <SelectItem key={organization.id} value={organization.id}>
                    {organization.name}
                    {!organization.is_active && ` (${t('common.disabled')})`}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          ) : (
            publicUser.organization_name
          )}
        </TableCell>
        <TableCell>
          <Badge
            variant='outline'
            className={
              publicUser.status === 'active'
                ? 'border-teal-200 bg-teal-100/30 text-teal-900 dark:text-teal-200'
                : 'border-destructive/20 bg-destructive/10 text-destructive'
            }
          >
            {publicUser.status === 'active'
              ? t('common.active')
              : t('common.disabled')}
          </Badge>
        </TableCell>
        <TableCell>{formatDateTime(publicUser.created_at)}</TableCell>
        <TableCell className='text-end'>
          <Button
            variant={publicUser.status === 'active' ? 'outline' : 'default'}
            size='sm'
            onClick={() => setPendingUser(publicUser)}
          >
            {publicUser.status === 'active'
              ? t('common.disable')
              : t('common.enable')}
          </Button>
        </TableCell>
      </TableRow>
    ))
  }

  return (
    <>
      {/* jscpd:ignore-start -- 后台列表页复用通用页头与标题布局样板，页面数据和操作各自实现。 */}
      <Header fixed>
        <Search className='me-auto' />
        <ThemeSwitch />
        <ConfigDrawer />
        <ProfileDropdown />
      </Header>

      <Main className='flex flex-1 flex-col gap-4 sm:gap-6'>
        <div className='flex flex-wrap items-end justify-between gap-2'>
          <div>
            <h2 className='text-2xl font-bold tracking-tight'>
              {t('users.title')}
            </h2>
            <p className='text-muted-foreground'>{t('users.description')}</p>
          </div>
        </div>
      {/* jscpd:ignore-end */}

        <form
          className='flex flex-wrap items-center gap-2'
          onSubmit={(event) => {
            event.preventDefault()
            setAppliedKeyword(keywordInput.trim())
          }}
        >
          <Input
            placeholder={t('users.searchPlaceholder')}
            value={keywordInput}
            onChange={(event) => setKeywordInput(event.target.value)}
            className='h-9 w-64'
          />
          {isPlatformAdmin && (
            <Select
              value={organizationFilter}
              onValueChange={setOrganizationFilter}
            >
              <SelectTrigger
                data-testid='users-organization-filter'
                className='h-9 w-56'
                aria-label={t('users.filterOrganization')}
              >
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value='all'>
                  {t('users.allOrganizations')}
                </SelectItem>
                {(organizationsQuery.data?.items ?? []).map((organization) => (
                  <SelectItem key={organization.id} value={organization.id}>
                    {organization.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          <Select
            value={statusFilter}
            onValueChange={(value) =>
              setStatusFilter(value as 'all' | 'active' | 'disabled')
            }
          >
            <SelectTrigger
              className='h-9 w-40'
              aria-label={t('users.statusFilter')}
            >
              <SelectValue />
            </SelectTrigger>
            {/* jscpd:ignore-start -- 用户与管理员目录共用状态选项 JSX 样板，筛选状态独立处理。 */}
            <SelectContent>
              <SelectItem value='all'>{t('users.allStatuses')}</SelectItem>
              <SelectItem value='active'>{t('common.active')}</SelectItem>
              <SelectItem value='disabled'>{t('common.disabled')}</SelectItem>
            </SelectContent>
          </Select>
            {/* jscpd:ignore-end */}
          <Button type='submit' variant='outline' size='sm'>
            {t('users.search')}
          </Button>
        </form>

        <div className='overflow-hidden rounded-md border'>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('users.displayName')}</TableHead>
                <TableHead>{t('users.email')}</TableHead>
                <TableHead>{t('users.organization')}</TableHead>
                <TableHead>{t('common.status')}</TableHead>
                <TableHead>{t('users.createdAt')}</TableHead>
                <TableHead className='text-end'>
                  {t('common.actions')}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>{renderTableBody()}</TableBody>
          </Table>
        </div>
      </Main>

      <AlertDialog
        open={pendingUser !== null}
        onOpenChange={(open) => {
          if (!open) setPendingUser(null)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {pendingUser?.status === 'active'
                ? t('users.disableTitle')
                : t('users.enableTitle')}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {pendingUser?.status === 'active'
                ? t('users.disableConfirmation', {
                    name: pendingUser.display_name,
                  })
                : t('users.enableConfirmation', {
                    name: pendingUser?.display_name,
                  })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={toggleMutation.isPending}>
              {t('common.cancel')}
            </AlertDialogCancel>
            <AlertDialogAction
              disabled={toggleMutation.isPending}
              onClick={() => {
                if (pendingUser) toggleMutation.mutate(pendingUser)
              }}
            >
              {t('common.confirm')}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
