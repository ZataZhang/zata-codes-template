import { createFileRoute, redirect } from '@tanstack/react-router'
import { getCurrentSession, type UserSession } from '@/api/auth'
import { useAuthStore } from '@/stores/auth-store'
import { AuthenticatedLayout } from '@/components/layout/authenticated-layout'

export const Route = createFileRoute('/_authenticated')({
  beforeLoad: async ({ location }) => {
    let session: UserSession
    try {
      session = await getCurrentSession()
      useAuthStore.getState().auth.setUser(session)
    } catch {
      useAuthStore.getState().auth.reset()
      throw redirect({
        to: '/sign-in',
        search: { redirect: location.pathname + location.searchStr },
      })
    }
    if (
      session.role === 'org' &&
      !['/users', '/agents', '/run-tracing'].some(
        (allowedPath) =>
          location.pathname === allowedPath ||
          location.pathname.startsWith(`${allowedPath}/`)
      )
    ) {
      throw redirect({ to: '/agents' })
    }
  },
  component: AuthenticatedLayout,
})
