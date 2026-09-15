"use client"

import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { useTranslations } from "next-intl"
import { AppShell } from "@/components/layout/app-shell"
import { getCurrentSession } from "@/lib/api/auth"

/** Root layout for the app section. */
export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const t = useTranslations("common")
  const [authenticated, setAuthenticated] = useState(false)

  useEffect(() => {
    getCurrentSession()
      .then(() => setAuthenticated(true))
      .catch(() => router.replace("/login"))
  }, [router])

  if (!authenticated) {
    return (
      <div className="flex min-h-svh items-center justify-center text-muted-foreground">
        {t("loading")}
      </div>
    )
  }

  return <AppShell>{children}</AppShell>
}
