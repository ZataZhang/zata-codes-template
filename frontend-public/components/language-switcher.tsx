"use client";

import { useTransition } from "react";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { Languages } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  LOCALE_COOKIE,
  SUPPORTED_LOCALES,
  isSupportedLocale,
  type SupportedLocale,
} from "@/i18n/constants";
import { setUserLocale } from "@/i18n/locale";
import { cn } from "@/lib/utils";

/** 语言选择 cookie 的有效期：一年（与 server action 保持一致）。 */
const LOCALE_COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365;

type LanguageSwitcherProps = {
  className?: string;
};

/**
 * 公开站语言切换器。
 *
 * 挂在站点导航区，点击后同时做三件事：写 `document.cookie`（立即生效，覆盖
 * server action 失败的情形）、调用 `setUserLocale` server action（让服务端
 * 也拿到选择）、`router.refresh()` 触发 SSR 重渲染，使 `<html lang>` 与首屏
 * 文案跟随新 locale。
 *
 * 形态说明：本仓库的公开站没有 shadcn DropdownMenu 原语（UI 原语基于
 * `@base-ui/react`，`components/ui` 未包含 menu 封装），因此这里复用现有
 * `Button` 做成分段式切换器，与后台保持同一交互语义。
 *
 * @param props - `className` 用于让调用方微调外边距。
 */
export function LanguageSwitcher({ className }: LanguageSwitcherProps) {
  const t = useTranslations("common");
  const router = useRouter();
  const currentLocale = useLocale();
  const [isPending, startTransition] = useTransition();

  const labels: Record<SupportedLocale, string> = {
    en: t("english"),
    zh: t("chinese"),
  };

  const onSelect = (next: string) => {
    if (!isSupportedLocale(next) || next === currentLocale) return;
    document.cookie = `${LOCALE_COOKIE}=${next}; path=/; max-age=${LOCALE_COOKIE_MAX_AGE_SECONDS}; samesite=lax`;
    startTransition(async () => {
      try {
        await setUserLocale(next);
      } catch {
        // 上面的 document.cookie 已经持久化了选择，server action 失败不阻断切换
      }
      router.refresh();
    });
  };

  return (
    <div
      className={cn("flex items-center gap-1", className)}
      role="group"
      aria-label={t("language")}
      data-testid="language-switcher"
    >
      <Languages
        className="size-4 shrink-0 text-muted-foreground"
        aria-hidden="true"
      />
      {SUPPORTED_LOCALES.map((locale) => (
        <Button
          key={locale}
          type="button"
          variant={locale === currentLocale ? "secondary" : "ghost"}
          size="sm"
          className="px-2"
          disabled={isPending}
          aria-current={locale === currentLocale ? "true" : undefined}
          data-testid={`language-option-${locale}`}
          onClick={() => onSelect(locale)}
        >
          {labels[locale]}
        </Button>
      ))}
    </div>
  );
}
