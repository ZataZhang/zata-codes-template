import { useSearch } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { Card, CardContent } from '@/components/ui/card'
import { AuthLayout } from '../auth-layout'
import { UserAuthForm } from './components/user-auth-form'

/** Render the SignIn component. */
export function SignIn() {
  const { redirect } = useSearch({ from: '/(auth)/sign-in' })
  const { t } = useTranslation()

  return (
    <AuthLayout>
      <div className='flex flex-col gap-6'>
        <div className='flex flex-col gap-2 text-center'>
          <h1
            data-testid='admin-sign-in-heading'
            className='text-2xl font-semibold tracking-tight'
          >
            {t('auth.signInTitle')}
          </h1>
          <p className='text-sm text-muted-foreground'>
            {t('auth.signInSubtitle')}
          </p>
        </div>

        <Card className='border shadow-lg'>
          <CardContent className='pt-6'>
            <UserAuthForm redirectTo={redirect} />
          </CardContent>
        </Card>

        <p className='text-center text-xs text-muted-foreground'>
          {t('auth.termsNotice')}
        </p>
      </div>
    </AuthLayout>
  )
}
