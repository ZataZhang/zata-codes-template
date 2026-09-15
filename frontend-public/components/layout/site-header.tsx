import Link from "next/link"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { LanguageSwitcher } from "@/components/language-switcher"

/** 顶部导航链接：href 与 `nav` 命名空间下的文案 key 一一对应。 */
const NAV_LINKS = [
  { href: "/features", labelKey: "features" },
  { href: "/pricing", labelKey: "pricing" },
  { href: "/about", labelKey: "about" },
] as const

/**
 * Site header for public pages.
 *
 * 服务端组件，因此文案在 SSR 阶段就按协商出的 locale 渲染，首屏不会出现语言闪烁。
 */
export function SiteHeader() {
  const t = useTranslations("nav")
  const tCommon = useTranslations("common")

  return (
    <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="container mx-auto flex h-14 items-center justify-between">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <span className="size-6 rounded-md bg-primary" />
            {tCommon("appName")}
          </Link>
          <nav className="hidden gap-4 text-sm text-muted-foreground md:flex">
            {NAV_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="hover:text-foreground"
              >
                {t(link.labelKey)}
              </Link>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2">
          <LanguageSwitcher className="mr-1" />
          <Button variant="ghost" size="sm" asChild>
            <Link href="/login">{t("signIn")}</Link>
          </Button>
          <Button size="sm" asChild>
            <Link href="/register">{t("getStarted")}</Link>
          </Button>
        </div>
      </div>
    </header>
  )
}
