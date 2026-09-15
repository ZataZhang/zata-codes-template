import { useTranslation } from 'react-i18next'
import { Logo } from '@/assets/logo'
import { LanguageSwitcher } from '@/components/language-switcher'

type AuthLayoutProps = {
  children: React.ReactNode
}

/**
 * Root layout for the auth section.
 *
 * 登录页不经过受保护布局的顶栏，因此语言切换器在这里单独挂载，保证未登录访客
 * 也能切换语言。
 */
export function AuthLayout({ children }: AuthLayoutProps) {
  const { t } = useTranslation()

  return (
    <div className='grid min-h-svh lg:grid-cols-2'>
      {/* Left brand panel */}
      <div className='relative hidden flex-col justify-between overflow-hidden bg-zinc-900 p-10 text-white lg:flex'>
        <div className='absolute inset-0 bg-[radial-gradient(circle_at_top_right,_var(--tw-gradient-stops))] from-indigo-600/20 via-zinc-900 to-zinc-950' />
        <div className='absolute -bottom-24 -left-24 size-96 rounded-full bg-indigo-600/10 blur-3xl' />

        <div className='relative z-10 flex items-center gap-2'>
          <Logo className='size-7 text-white' />
          <span className='text-xl font-semibold tracking-tight'>Zata</span>
        </div>

        <div className='relative z-10 max-w-md'>
          <h2 className='text-3xl font-bold tracking-tight'>
            {t('auth.brandHeadline')}
          </h2>
          <p className='mt-4 text-zinc-400'>{t('auth.brandDescription')}</p>
          <ul className='mt-8 space-y-3 text-sm text-zinc-300'>
            <li className='flex items-center gap-2'>
              <span className='inline-block size-1.5 rounded-full bg-indigo-400' />
              {t('auth.brandPoint1')}
            </li>
            <li className='flex items-center gap-2'>
              <span className='inline-block size-1.5 rounded-full bg-indigo-400' />
              {t('auth.brandPoint2')}
            </li>
            <li className='flex items-center gap-2'>
              <span className='inline-block size-1.5 rounded-full bg-indigo-400' />
              {t('auth.brandPoint3')}
            </li>
          </ul>
        </div>

        <div className='relative z-10 text-sm text-zinc-500' data-testid='admin-auth-copyright'>
          {t('auth.copyright', { year: new Date().getFullYear() })}
        </div>
      </div>

      {/* Right form panel */}
      <div className='flex flex-col items-center justify-center p-6 lg:p-10'>
        <div className='flex w-full max-w-sm flex-col gap-6'>
          <div className='flex items-center justify-between gap-2'>
            <div className='flex items-center gap-2 lg:hidden'>
              <Logo className='size-6' />
              <span className='text-lg font-semibold tracking-tight'>Zata</span>
            </div>
            <LanguageSwitcher className='ms-auto flex items-center gap-1' />
          </div>
          {children}
        </div>
      </div>
    </div>
  )
}
