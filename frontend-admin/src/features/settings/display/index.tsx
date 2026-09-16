import { useTranslation } from 'react-i18next'
import { ContentSection } from '../components/content-section'
import { DisplayForm } from './display-form'

/** Render the SettingsDisplay component. */
export function SettingsDisplay() {
  const { t } = useTranslation()

  return (
    <ContentSection
      title={t('settings.sections.display.title')}
      desc={t('settings.sections.display.description')}
    >
      <DisplayForm />
    </ContentSection>
  )
}
