import { useTranslation } from 'react-i18next'
import { ContentSection } from '../components/content-section'
import { ProfileForm } from './profile-form'

/** Render the SettingsProfile component. */
export function SettingsProfile() {
  const { t } = useTranslation()

  return (
    <ContentSection
      title={t('settings.sections.profile.title')}
      desc={t('settings.sections.profile.description')}
    >
      <ProfileForm />
    </ContentSection>
  )
}
