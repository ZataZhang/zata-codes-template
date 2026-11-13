import type { ReactNode } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import i18n from '@/i18n/init'
import { toast } from 'sonner'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render } from 'vitest-browser-react'
import { userEvent } from 'vitest/browser'
import { ApiRequestError } from '@/api/client'
import {
  getRegistrationPolicy,
  updateRegistrationPolicy,
} from '@/api/registration-policy'
import { RegistrationSettings } from './index'

vi.mock('@/api/registration-policy', () => ({
  getRegistrationPolicy: vi.fn(),
  updateRegistrationPolicy: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}))

vi.mock('@/features/shared/admin-page-shell', () => ({
  AdminPageShell: ({ children }: { children: ReactNode }) => (
    <main>{children}</main>
  ),
}))

const defaultRegistrationPolicy = {
  registration_mode: 'both' as const,
  allowed_email_domains: [],
}

/** 在独立 React Query 客户端中渲染注册策略页面。 */
async function renderRegistrationSettings() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <RegistrationSettings />
    </QueryClientProvider>
  )
}

describe('RegistrationSettings', () => {
  beforeEach(async () => {
    vi.clearAllMocks()
    vi.mocked(getRegistrationPolicy).mockResolvedValue(
      defaultRegistrationPolicy
    )
    await i18n.changeLanguage('en')
  })

  it.each([
    {
      locale: 'en',
      expectedMessage: 'These email domains are invalid: invalid..example',
    },
    {
      locale: 'zh',
      expectedMessage: '以下邮箱域名无效：invalid..example',
    },
  ])(
    'shows invalid email domains in the $locale locale',
    async ({ locale, expectedMessage }) => {
      await i18n.changeLanguage(locale)
      vi.mocked(updateRegistrationPolicy).mockRejectedValue(
        new ApiRequestError(422, 'Request failed with status code 422', {
          detail: {
            code: 'invalid_email_domains',
            invalid_domains: ['invalid..example'],
          },
        })
      )

      const screen = await renderRegistrationSettings()
      await expect
        .element(screen.getByTestId('registration-policy-domains'))
        .toBeInTheDocument()
      await userEvent.fill(
        screen.getByTestId('registration-policy-domains'),
        'invalid..example'
      )
      await userEvent.click(screen.getByTestId('registration-policy-save'))

      await vi.waitFor(() =>
        expect(toast.error).toHaveBeenCalledWith(expectedMessage)
      )
    }
  )
})
