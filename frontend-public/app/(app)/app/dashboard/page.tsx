"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { getCurrentSession, type UserSession } from "@/lib/api/auth"
import { Settings } from "lucide-react"

/** Render the dashboard page. */
export default function DashboardPage() {
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
        加载中…
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold">工作区</h1>
        <p className="text-muted-foreground">
          {user ? `${user.display_name} · ${user.email}` : "已登录"}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="size-5 text-primary" />
            开始搭建你的业务
          </CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          本模板仅保留认证与基础设施骨架，不内置任何业务域。请根据你的项目在四层架构
          上添加业务模块，例如在 <code>src/backend/core/</code> 定义用例与领域契约、
          在 <code>src/backend/engines/</code> 实现平台能力、在
          <code>src/backend/api/</code> 暴露 HTTP 入口。
        </CardContent>
      </Card>

      <div>
        <Button asChild variant="outline" size="sm">
          <Link href="/app/settings">账户设置</Link>
        </Button>
      </div>
    </div>
  )
}
