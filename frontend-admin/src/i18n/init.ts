import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'

import en from '@/locales/en.json'
import zh from '@/locales/zh.json'

/** 本后台支持的全部 locale，顺序即语言切换器的展示顺序。 */
export const SUPPORTED_LOCALES = ['en', 'zh'] as const

/** 受支持 locale 的字面量联合类型。 */
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number]

/** 无法检测时的兜底 locale（见 PRD 决策 D1）。 */
export const DEFAULT_LOCALE: SupportedLocale = 'en'

/**
 * 持久化语言选择的 localStorage 键。
 *
 * 沿用 `i18next-browser-languagedetector` 的默认键名，使检测器的读取、缓存与
 * 外部写入（例如端到端测试直接 `localStorage.setItem`）共享同一份事实源。
 */
export const LOCALE_STORAGE_KEY = 'i18nextLng'

/**
 * 把任意检测结果归一化为受支持的 locale。
 *
 * 检测器可能返回 `zh-CN`、`zh-Hans` 这类带区域的标签，这里只取语言主标签，
 * 保证 `<html lang>` 与 `supportedLngs` 的取值域一致。
 *
 * @param language - 检测器或 i18next 给出的语言标签。
 * @returns 归一化后的受支持 locale。
 */
export function normalizeLocale(language: string | undefined): SupportedLocale {
  return language?.toLowerCase().startsWith('zh') ? 'zh' : DEFAULT_LOCALE
}

/**
 * 让 `<html lang>` 跟随当前语言。
 *
 * 该属性被端到端用例与屏幕阅读器读取，因此必须在语言变化时同步，而不是只在
 * 启动时写一次。
 *
 * @param language - 当前生效的语言标签。
 */
function syncDocumentLanguage(language: string | undefined): void {
  if (typeof document === 'undefined') return
  document.documentElement.lang = normalizeLocale(language)
}

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      zh: { translation: zh },
    },
    fallbackLng: DEFAULT_LOCALE,
    supportedLngs: [...SUPPORTED_LOCALES],
    // 只保留语言主标签，避免 navigator 给出 zh-CN 时匹配不到受支持集合。
    load: 'languageOnly',
    // 优先级：显式选择（localStorage）→ navigator → fallbackLng。
    detection: {
      order: ['localStorage', 'navigator'],
      lookupLocalStorage: LOCALE_STORAGE_KEY,
      caches: ['localStorage'],
    },
    interpolation: {
      // React 已经做了转义，这里再转一次会把文案里的引号显示成实体。
      escapeValue: false,
    },
  })
  .then(() => syncDocumentLanguage(i18n.resolvedLanguage ?? i18n.language))

i18n.on('languageChanged', (language) => {
  syncDocumentLanguage(language)
})

export default i18n
