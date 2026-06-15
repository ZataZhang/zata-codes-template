"use client"

import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { getCurrentSession, type UserSession } from "@/lib/api/auth"

export default function TasksPage() {
  const router = useRouter()
  const [user, setUser] = useState<UserSession | null>(null)

  useEffect(() => {
    getCurrentSession().then(setUser).catch(() => router.replace("/login"))
  }, [router])

  if (!user) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        加载中…
      </div>
    )
  }

  return (
    <div>
      <h1 className="text-3xl font-bold">我的任务</h1>
      <p className="mt-2 text-muted-foreground">
        这里是登录后才能看到的任务列表。后续可以接入后端 API 展示真实数据。
      </p>
    </div>
  )
}
