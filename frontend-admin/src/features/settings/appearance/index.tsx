import { useTranslation } from 'react-i18next'
import { ContentSection } from '../components/content-section'
import { AppearanceForm } from './appearance-form'

/** Render the SettingsAppearance component. */
export function SettingsAppearance() {
  const { t } = useTranslation()

  return (
    <ContentSection
      title={t('settings.sections.appearance.title')}
      desc={t('settings.sections.appearance.description')}
    >
      <AppearanceForm />
    </ContentSection>
  )
}
