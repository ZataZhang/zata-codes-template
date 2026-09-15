/**
 * 客户端安全的 i18n 常量。
 *
 * 位于 i18n 模块依赖图的顶层，使服务端运行时（next-intl 的
 * getRequestConfig、`locale.ts` 里的 server action）与客户端组件都能共享
 * 这些名字，而不会把 `next/headers` 打进浏览器产物。
 *
 * 任何依赖 `cookies()` / `headers()` / `next/headers` 的代码必须放在
 * `i18n/request.ts`（只被 next-intl 运行时消费）或 `i18n/locale.ts`
 * （只作为 server action 被消费）。不要把这两个模块从客户端组件里 import。
 */

/** 持久化用户语言选择的 cookie 名，服务端渲染与切换器共用同一个契约。 */
export const LOCALE_COOKIE = "NEXT_LOCALE";

/** 本应用支持的全部 locale，顺序即语言切换器的展示顺序。 */
export const SUPPORTED_LOCALES = ["en", "zh"] as const;

/** 支持的 locale 字面量联合类型。 */
export type SupportedLocale = (typeof SUPPORTED_LOCALES)[number];

/** 无法协商时的兜底 locale（见 PRD 决策 D1）。 */
export const DEFAULT_LOCALE: SupportedLocale = "en";

/**
 * 判断任意字符串是否为受支持的 locale。
 *
 * @param value - 待判断的候选值，通常来自 cookie 或请求头。
 * @returns 命中受支持集合时为 true，同时把类型收窄为 SupportedLocale。
 */
export function isSupportedLocale(
  value: string | undefined
): value is SupportedLocale {
  return SUPPORTED_LOCALES.includes(value as SupportedLocale);
}
