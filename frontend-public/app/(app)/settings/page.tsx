"use client"

import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import { logout, getCurrentSession, type UserSession } from "@/lib/api/auth"

export default function SettingsPage() {
  const router = useRouter()
  const [user, setUser] = useState<UserSession | null>(null)

  useEffect(() => {
    getCurrentSession().then(setUser).catch(() => router.replace("/login"))
  }, [router])

  async function handleLogout() {
    await logout()
    router.replace("/")
  }

  if (!user) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        加载中…
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold">账号设置</h1>
        <p className="text-muted-foreground">
          {user.display_name} · {user.email}
        </p>
      </div>
      <Button variant="destructive" onClick={handleLogout}>
        退出登录
      </Button>
    </div>
  )
}
