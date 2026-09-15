import { useTranslation } from 'react-i18next'
import { ContentSection } from '../components/content-section'
import { NotificationsForm } from './notifications-form'

/** Render the SettingsNotifications component. */
export function SettingsNotifications() {
  const { t } = useTranslation()

  return (
    <ContentSection
      title={t('settings.sections.notifications.title')}
      desc={t('settings.sections.notifications.description')}
    >
      <NotificationsForm />
    </ContentSection>
  )
}
