"use client"

import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import { logout, getCurrentSession, type UserSession } from "@/lib/api/auth"

/** Render the settings page. */
export default function SettingsPage() {
  const router = useRouter()
  const t = useTranslations("settings")
  const tCommon = useTranslations("common")
  const [user, setUser] = useState<UserSession | null>(null)

  useEffect(() => {
    getCurrentSession().then(setUser).catch(() => router.replace("/login"))
  }, [router])

  /** Handle logout and redirect to the home page. */
  async function handleLogout() {
    await logout()
    router.replace("/")
  }

  if (!user) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        {tCommon("loading")}
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold">{t("title")}</h1>
        <p className="text-muted-foreground">
          {user.display_name} · {user.email}
        </p>
      </div>
      <div className="rounded-2xl border bg-muted/30 p-6">
        <h2 className="mb-2 text-lg font-semibold">{t("aboutTitle")}</h2>
        <p className="text-sm text-muted-foreground">{t("aboutBody")}</p>
      </div>
      <Button variant="destructive" onClick={handleLogout}>
        {t("signOut")}
      </Button>
    </div>
  )
}
