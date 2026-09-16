import Link from "next/link"
import { useTranslations } from "next-intl"

/** 页脚导航链接：href 与 `nav` 命名空间下的文案 key 一一对应。 */
const NAV_LINKS = [
  { href: "/features", labelKey: "features" },
  { href: "/pricing", labelKey: "pricing" },
  { href: "/about", labelKey: "about" },
] as const

/** Site footer for public pages. */
export function SiteFooter() {
  const t = useTranslations("nav")
  const tCommon = useTranslations("common")
  const tFooter = useTranslations("footer")

  return (
    <footer className="border-t bg-muted/50">
      <div className="container mx-auto flex flex-col gap-4 py-8 md:flex-row md:items-center md:justify-between">
        <div className="flex items-center gap-2 font-semibold">
          <span className="size-5 rounded-md bg-primary" />
          {tCommon("appName")}
        </div>
        <p className="text-sm text-muted-foreground">
          {tFooter("copyright", { year: new Date().getFullYear() })}
        </p>
        <nav className="flex gap-4 text-sm text-muted-foreground">
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
    </footer>
  )
}
