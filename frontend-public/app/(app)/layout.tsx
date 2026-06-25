"use client"

import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { AppShell } from "@/components/layout/app-shell"
import { getCurrentSession } from "@/lib/api/auth"

export default function AppLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const [authenticated, setAuthenticated] = useState(false)

  useEffect(() => {
    getCurrentSession()
      .then(() => setAuthenticated(true))
      .catch(() => router.replace("/login"))
  }, [router])

  if (!authenticated) {
    return (
      <div className="flex min-h-svh items-center justify-center text-muted-foreground">
        加载中…
      </div>
    )
  }

  return <AppShell>{children}</AppShell>
}
