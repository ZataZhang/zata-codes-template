import { useTranslation } from 'react-i18next'
import { ContentSection } from '../components/content-section'
import { AccountForm } from './account-form'

/** Render the SettingsAccount component. */
export function SettingsAccount() {
  const { t } = useTranslation()

  return (
    <ContentSection
      title={t('settings.sections.account.title')}
      desc={t('settings.sections.account.description')}
    >
      <AccountForm />
    </ContentSection>
  )
}
