"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { useTranslations } from "next-intl"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { getCurrentSession, type UserSession } from "@/lib/api/auth"
import { Settings } from "lucide-react"

/** Render the dashboard page. */
export default function DashboardPage() {
  const t = useTranslations("dashboard")
  const tCommon = useTranslations("common")
  const [user, setUser] = useState<UserSession | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getCurrentSession()
      .then(setUser)
      .catch(() => setUser(null))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
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
          {user ? `${user.display_name} · ${user.email}` : t("signedIn")}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="size-5 text-primary" />
            {t("gettingStartedTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          {t("gettingStartedBody")}
        </CardContent>
      </Card>

      <div>
        <Button asChild variant="outline" size="sm">
          <Link href="/app/settings">{t("accountSettings")}</Link>
        </Button>
      </div>
    </div>
  )
}
