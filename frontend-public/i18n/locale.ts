"use server";

import { cookies } from "next/headers";

import {
  LOCALE_COOKIE,
  isSupportedLocale,
  type SupportedLocale,
} from "./constants";

/** 语言选择 cookie 的有效期：一年。 */
const LOCALE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

/**
 * 把用户选择的 locale 写入 cookie。
 *
 * 同时被语言切换器（客户端调用）与 SSR 的 `getRequestConfig`（读取）消费，
 * 是"切换后刷新仍保持语言"的唯一事实源。
 *
 * @param locale - 用户选择的 locale；非受支持值时静默忽略，避免写入脏 cookie。
 */
export async function setUserLocale(locale: SupportedLocale): Promise<void> {
  if (!isSupportedLocale(locale)) {
    return;
  }
  const cookieStore = await cookies();
  cookieStore.set({
    name: LOCALE_COOKIE,
    value: locale,
    path: "/",
    sameSite: "lax",
    maxAge: LOCALE_COOKIE_MAX_AGE_SECONDS,
  });
}
