import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { ApiRequestError } from '@/api/client'
import {
  getRegistrationPolicy,
  type RegistrationMode,
  updateRegistrationPolicy,
} from '@/api/registration-policy'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group'
import { Textarea } from '@/components/ui/textarea'
import { AdminPageShell } from '@/features/shared/admin-page-shell'

const REGISTRATION_POLICY_QUERY_KEY = ['admin', 'registration-policy'] as const

/** 渲染平台管理员可编辑的前台注册策略。 */
export function RegistrationSettings() {
  const queryClient = useQueryClient()
  const { t } = useTranslation()
  const policyQuery = useQuery({
    queryKey: REGISTRATION_POLICY_QUERY_KEY,
    queryFn: getRegistrationPolicy,
  })
  const [registrationModeOverride, setRegistrationModeOverride] =
    useState<RegistrationMode | null>(null)
  const [domainsTextOverride, setDomainsTextOverride] = useState<string | null>(
    null
  )
  const registrationMode =
    registrationModeOverride ?? policyQuery.data?.registration_mode ?? 'both'
  const domainsText =
    domainsTextOverride ??
    policyQuery.data?.allowed_email_domains.join('\n') ??
    ''

  const saveMutation = useMutation({
    mutationFn: updateRegistrationPolicy,
    onSuccess: (savedPolicy) => {
      setRegistrationModeOverride(savedPolicy.registration_mode)
      setDomainsTextOverride(savedPolicy.allowed_email_domains.join('\n'))
      toast.success(t('registration.saved'))
      void queryClient.invalidateQueries({
        queryKey: REGISTRATION_POLICY_QUERY_KEY,
      })
    },
    onError: (error) => {
      const responseDetail =
        error instanceof ApiRequestError ? error.detail : null
      const detail =
        responseDetail &&
        typeof responseDetail === 'object' &&
        'detail' in responseDetail
          ? responseDetail.detail
          : responseDetail
      if (
        detail &&
        typeof detail === 'object' &&
        'code' in detail &&
        detail.code === 'invalid_email_domains' &&
        'invalid_domains' in detail &&
        Array.isArray(detail.invalid_domains)
      ) {
        toast.error(
          t('registration.invalidDomains', {
            domains: detail.invalid_domains.join(', '),
          })
        )
        return
      }
      toast.error(t('registration.saveFailed'))
    },
  })

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    const allowedEmailDomains = Array.from(
      new Set(
        domainsText
          .split(/\r?\n/)
          .map((domain) => domain.trim().toLowerCase())
          .filter(Boolean)
      )
    )
    saveMutation.mutate({
      registration_mode: registrationMode,
      allowed_email_domains: allowedEmailDomains,
    })
  }

  return (
    <AdminPageShell
      title={t('registration.title')}
      description={t('registration.description')}
    >
      {policyQuery.isLoading ? (
        <p role='status' className='text-sm text-muted-foreground'>
          {t('common.loading')}
        </p>
      ) : policyQuery.isError ? (
        <Alert variant='destructive'>
          <AlertDescription>{t('registration.loadFailed')}</AlertDescription>
        </Alert>
      ) : (
        <form className='grid max-w-3xl gap-6' onSubmit={handleSubmit}>
          <fieldset className='grid gap-3'>
            <legend className='text-sm font-medium'>
              {t('registration.modeLabel')}
            </legend>
            <RadioGroup
              value={registrationMode}
              onValueChange={(value) =>
                setRegistrationModeOverride(value as RegistrationMode)
              }
              aria-label={t('registration.modeLabel')}
            >
              <div className='flex items-start gap-3'>
                <RadioGroupItem id='registration-both' value='both' />
                <Label htmlFor='registration-both' className='grid gap-1'>
                  <span>{t('registration.modeBoth')}</span>
                  <span className='font-normal text-muted-foreground'>
                    {t('registration.modeBothDescription')}
                  </span>
                </Label>
              </div>
              <div className='flex items-start gap-3'>
                <RadioGroupItem id='registration-oidc-only' value='oidc_only' />
                <Label htmlFor='registration-oidc-only' className='grid gap-1'>
                  <span>{t('registration.modeOidcOnly')}</span>
                  <span className='font-normal text-muted-foreground'>
                    {t('registration.modeOidcOnlyDescription')}
                  </span>
                </Label>
              </div>
              <div className='flex items-start gap-3'>
                <RadioGroupItem id='registration-closed' value='closed' />
                <Label htmlFor='registration-closed' className='grid gap-1'>
                  <span>{t('registration.modeClosed')}</span>
                  <span className='font-normal text-muted-foreground'>
                    {t('registration.modeClosedDescription')}
                  </span>
                </Label>
              </div>
            </RadioGroup>
          </fieldset>

          <div className='grid gap-2'>
            <Label htmlFor='registration-domains'>
              {t('registration.allowedDomains')}
            </Label>
            <Textarea
              id='registration-domains'
              data-testid='registration-policy-domains'
              value={domainsText}
              onChange={(event) => setDomainsTextOverride(event.target.value)}
              placeholder={t('registration.domainsPlaceholder')}
              rows={5}
            />
            <p className='text-sm text-muted-foreground'>
              {t('registration.domainsHelp')}
            </p>
            <p className='text-sm text-muted-foreground'>
              {t('registration.passwordEmailNotice')}
            </p>
          </div>

          <div>
            <Button
              data-testid='registration-policy-save'
              type='submit'
              disabled={saveMutation.isPending}
            >
              {saveMutation.isPending
                ? t('registration.saving')
                : t('registration.save')}
            </Button>
          </div>
        </form>
      )}
    </AdminPageShell>
  )
}
