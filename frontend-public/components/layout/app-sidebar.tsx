"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { cn } from "@/lib/utils"
import {
  Bot,
  GitBranch,
  LayoutDashboard,
  MessageSquare,
  Plug,
  Settings,
} from "lucide-react"

const navItems = [
  { href: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/app/agents", label: "Agents", icon: Bot },
  { href: "/app/chat", label: "Chat", icon: MessageSquare },
  { href: "/app/workflows", label: "Workflows", icon: GitBranch },
  { href: "/app/tools", label: "Tools", icon: Plug },
  { href: "/app/settings", label: "Settings", icon: Settings },
]

/** Sidebar navigation for authenticated pages. */
export function AppSidebar() {
  const pathname = usePathname()

  return (
    <aside className="flex w-64 flex-col border-r bg-sidebar">
      <div className="flex h-14 items-center gap-2 border-b px-4">
        <span className="size-6 rounded-md bg-primary" />
        <span className="font-semibold text-sidebar-foreground">Zata</span>
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
                {item.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>
    </aside>
  )
}
