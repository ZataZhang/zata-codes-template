import { useNavigate, useLocation } from '@tanstack/react-router'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'
import { logout } from '@/api/auth'
import { useAuthStore } from '@/stores/auth-store'
import { ConfirmDialog } from '@/components/confirm-dialog'

interface SignOutDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

/**
 * Render the SignOutDialog component.
 *
 * 退出确认弹窗从导航区的用户菜单进入，属于核心界面的一部分，因此标题、说明、
 * 确认按钮与成功提示都走 i18n，避免中文界面下残留英文（或反之）。
 */
export function SignOutDialog({ open, onOpenChange }: SignOutDialogProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { auth } = useAuthStore()
  const { t } = useTranslation()

  const handleSignOut = async () => {
    try {
      await logout()
    } catch {
      // ignore logout errors, still clear local state
    }
    auth.reset()
    const currentPath = location.href
    navigate({
      to: '/sign-in',
      search: { redirect: currentPath },
      replace: true,
    })
    toast.success(t('userMenu.signOutSuccess'))
  }

  return (
    <ConfirmDialog
      open={!!open}
      onOpenChange={onOpenChange}
      title={t('userMenu.signOutTitle')}
      desc={t('userMenu.signOutDescription')}
      confirmText={t('userMenu.signOutConfirm')}
      destructive
      handleConfirm={handleSignOut}
      className='sm:max-w-sm'
    />
  )
}
