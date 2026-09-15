"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useTranslations } from "next-intl"
import { cn } from "@/lib/utils"
import { LayoutDashboard, Settings } from "lucide-react"
import { LanguageSwitcher } from "@/components/language-switcher"

/** 侧边栏导航项：href 与 `nav` 命名空间下的文案 key 一一对应。 */
const navItems = [
  { href: "/app/dashboard", labelKey: "dashboard", icon: LayoutDashboard },
  { href: "/app/settings", labelKey: "settings", icon: Settings },
] as const

/** Sidebar navigation for authenticated pages. */
export function AppSidebar() {
  const pathname = usePathname()
  const t = useTranslations("nav")
  const tCommon = useTranslations("common")

  return (
    <aside className="flex w-64 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <span className="size-6 rounded-md bg-primary" />
        <span className="font-semibold text-sidebar-foreground">
          {tCommon("appName")}
        </span>
      </div>
      <nav className="flex-1 p-3">
        <ul className="space-y-1">
          {navItems.map((item) => (
            <li key={item.href}>
              <Link
                href={item.href}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  pathname === item.href || pathname?.startsWith(`${item.href}/`)
                    ? "bg-sidebar-primary text-sidebar-primary-foreground"
                    : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                )}
              >
                <item.icon className="size-4" />
                {t(item.labelKey)}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      <div className="border-t p-3">
        <LanguageSwitcher />
      </div>
    </aside>
  )
}
