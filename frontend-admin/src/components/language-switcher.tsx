import { Languages } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { SUPPORTED_LOCALES, type SupportedLocale } from '@/i18n/init'

/**
 * 语言切换器。
 *
 * 切换时调用 `i18n.changeLanguage`，由 `i18next-browser-languagedetector` 的
 * `caches: ['localStorage']` 把选择写入 `LOCALE_STORAGE_KEY`，因此刷新或重开
 * 浏览器后仍保持上次选择；组件订阅了 i18next 的 languageChanged 事件，整页
 * 文案会立即重渲染。
 *
 * 挂在后台顶栏（`Header`）与登录页（`AuthLayout`），两处共用同一实现。
 *
 * @param props - `className` 用于让调用方微调布局位置。
 */
export function LanguageSwitcher({ className }: { className?: string }) {
  const { i18n, t } = useTranslation()

  /** 当前生效的语言主标签。 */
  const currentLocale = i18n.resolvedLanguage ?? i18n.language

  const labels: Record<SupportedLocale, string> = {
    en: t('common.english'),
    zh: t('common.chinese'),
  }

  const onSelect = (next: SupportedLocale) => {
    if (currentLocale === next) return
    void i18n.changeLanguage(next)
  }

  return (
    <div
      className={className}
      role="group"
      aria-label={t('common.language')}
      data-testid="language-switcher"
    >
      <Languages className="me-1 inline size-3.5 text-muted-foreground" />
      {SUPPORTED_LOCALES.map((locale) => (
        <Button
          key={locale}
          type="button"
          variant={currentLocale === locale ? 'secondary' : 'ghost'}
          size="sm"
          className="px-2"
          aria-current={currentLocale === locale ? 'true' : undefined}
          data-testid={`language-option-${locale}`}
          onClick={() => onSelect(locale)}
        >
          {labels[locale]}
        </Button>
      ))}
    </div>
  )
}
