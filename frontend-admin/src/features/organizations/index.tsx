import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import {
  createOrganization,
  disableOrganization,
  enableOrganization,
  listOrganizations,
  type Organization,
} from '@/api/organizations'
import { ConfirmDialog } from '@/components/confirm-dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { AdminPageShell } from '@/features/shared/admin-page-shell'

const ORGANIZATIONS_QUERY_KEY = ['admin', 'organizations'] as const
const DEFAULT_ORGANIZATION_ID = 'default'

type PendingOrganizationAction = {
  organization: Organization
  action: 'enable' | 'disable'
}

/** 渲染平台管理员可用的组织目录。 */
export function Organizations() {
  const queryClient = useQueryClient()
  const { t } = useTranslation()
  const [organizationName, setOrganizationName] = useState('')
  const [pendingAction, setPendingAction] =
    useState<PendingOrganizationAction | null>(null)
  const organizationsQuery = useQuery({
    queryKey: ORGANIZATIONS_QUERY_KEY,
    queryFn: listOrganizations,
  })

  const createMutation = useMutation({
    mutationFn: createOrganization,
    onSuccess: () => {
      setOrganizationName('')
      toast.success(t('organizations.created'))
      void queryClient.invalidateQueries({ queryKey: ORGANIZATIONS_QUERY_KEY })
    },
    onError: () => toast.error(t('organizations.createFailed')),
  })
  const statusMutation = useMutation({
    mutationFn: ({ organization, action }: PendingOrganizationAction) =>
      action === 'disable'
        ? disableOrganization(organization.id)
        : enableOrganization(organization.id),
    onSuccess: (_, variables) => {
      toast.success(
        variables.action === 'disable'
          ? t('organizations.disabled')
          : t('organizations.enabled')
      )
      void queryClient.invalidateQueries({ queryKey: ORGANIZATIONS_QUERY_KEY })
    },
    onError: () => toast.error(t('organizations.updateFailed')),
    onSettled: () => setPendingAction(null),
  })

  const handleCreate = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const trimmedName = organizationName.trim()
    if (trimmedName) createMutation.mutate(trimmedName)
  }

  const organizations = organizationsQuery.data?.items ?? []

  return (
    <>
      <AdminPageShell
        title={t('organizations.title')}
        description={t('organizations.description')}
      >
        <form
          className='flex max-w-xl items-center gap-2'
          onSubmit={handleCreate}
        >
          <Input
            data-testid='organization-name'
            aria-label={t('organizations.name')}
            value={organizationName}
            onChange={(event) => setOrganizationName(event.target.value)}
            placeholder={t('organizations.namePlaceholder')}
            required
            maxLength={100}
          />
          <Button
            data-testid='organization-create'
            type='submit'
            disabled={createMutation.isPending || !organizationName.trim()}
          >
            {createMutation.isPending
              ? t('organizations.creating')
              : t('organizations.create')}
          </Button>
        </form>

        <div className='overflow-hidden rounded-md border'>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('organizations.name')}</TableHead>
                <TableHead>{t('organizations.status')}</TableHead>
                <TableHead>{t('organizations.createdAt')}</TableHead>
                <TableHead className='text-end'>
                  {t('common.actions')}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {organizationsQuery.isLoading ? (
                <TableRow>
                  <TableCell colSpan={4} className='h-24 text-center'>
                    {t('common.loading')}
                  </TableCell>
                </TableRow>
              ) : organizationsQuery.isError ? (
                <TableRow>
                  <TableCell
                    colSpan={4}
                    className='h-24 text-center text-destructive'
                  >
                    {t('organizations.loadFailed')}
                  </TableCell>
                </TableRow>
              ) : organizations.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={4} className='h-24 text-center'>
                    {t('organizations.empty')}
                  </TableCell>
                </TableRow>
              ) : (
                organizations.map((organization) => (
                  <TableRow key={organization.id}>
                    <TableCell className='font-medium'>
                      <span>{organization.name}</span>
                      {organization.id === DEFAULT_ORGANIZATION_ID && (
                        <span className='ms-2 text-xs text-muted-foreground'>
                          {t('organizations.default')}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge
                        variant={
                          organization.is_active ? 'secondary' : 'outline'
                        }
                      >
                        {organization.is_active
                          ? t('common.active')
                          : t('common.disabled')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {organization.created_at
                        ? new Date(organization.created_at).toLocaleString()
                        : '—'}
                    </TableCell>
                    <TableCell className='text-end'>
                      {organization.id !== DEFAULT_ORGANIZATION_ID && (
                        <Button
                          variant={
                            organization.is_active ? 'outline' : 'default'
                          }
                          size='sm'
                          onClick={() =>
                            setPendingAction({
                              organization,
                              action: organization.is_active
                                ? 'disable'
                                : 'enable',
                            })
                          }
                        >
                          {organization.is_active
                            ? t('common.disable')
                            : t('common.enable')}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))
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
          pendingAction?.action === 'disable'
            ? t('organizations.disableTitle')
            : t('organizations.enableTitle')
        }
        desc={
          pendingAction?.action === 'disable'
            ? t('organizations.disableConfirmation', {
                name: pendingAction.organization.name,
              })
            : t('organizations.enableConfirmation', {
                name: pendingAction?.organization.name,
              })
        }
        confirmText={t('common.confirm')}
        destructive={pendingAction?.action === 'disable'}
        isLoading={statusMutation.isPending}
        handleConfirm={() => {
          if (pendingAction) statusMutation.mutate(pendingAction)
        }}
      />
    </>
  )
}
