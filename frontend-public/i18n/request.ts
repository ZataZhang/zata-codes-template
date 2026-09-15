import { cookies, headers } from "next/headers";
import { getRequestConfig } from "next-intl/server";
import type { AbstractIntlMessages } from "next-intl";

import {
  DEFAULT_LOCALE,
  LOCALE_COOKIE,
  isSupportedLocale,
  type SupportedLocale,
} from "./constants";
import { negotiateAcceptLanguage } from "./negotiate";

/**
 * 解析当前请求应使用的 locale。
 *
 * 优先级：显式 `NEXT_LOCALE` cookie > `Accept-Language` 请求头 > 默认 locale。
 *
 * cookie 名必须与语言切换器写入的名字一致（`LOCALE_COOKIE`），否则服务端渲染、
 * 客户端渲染与端到端测试会各自为政。
 *
 * @returns 本次请求生效的受支持 locale。
 */
export async function getRequestLocale(): Promise<SupportedLocale> {
  const cookieStore = await cookies();
  const cookieValue = cookieStore.get(LOCALE_COOKIE)?.value;
  if (cookieValue && isSupportedLocale(cookieValue)) {
    return cookieValue;
  }
  const headerStore = await headers();
  const acceptLanguage = headerStore.get("accept-language");
  if (acceptLanguage) {
    const negotiated = negotiateAcceptLanguage(acceptLanguage);
    if (negotiated) {
      return negotiated;
    }
  }
  return DEFAULT_LOCALE;
}

export default getRequestConfig(async () => {
  // 本应用不使用 URL locale 前缀，next-intl 插件无法从路由推断语言，
  // 因此这里自行读 NEXT_LOCALE cookie 与 Accept-Language 头；插件传入的
  // requestLocale 被忽略，因为它会用 en 兜底而不是我们协商出的结果。
  const locale: SupportedLocale = await getRequestLocale();
  const effective: SupportedLocale = isSupportedLocale(locale)
    ? locale
    : DEFAULT_LOCALE;
  const messages = (await import(`../messages/${effective}.json`)).default as
    | AbstractIntlMessages
    | Record<string, unknown>;
  return {
    locale: effective,
    messages: messages as AbstractIntlMessages,
  };
});
