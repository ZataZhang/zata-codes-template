"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { getCurrentSession, type UserSession } from "@/lib/api/auth"

export default function DashboardPage() {
  const router = useRouter()
  const [user, setUser] = useState<UserSession | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    getCurrentSession()
      .then(setUser)
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false))
  }, [router])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-muted-foreground">
        加载中…
      </div>
    )
  }

  if (!user) {
    return null
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-3xl font-bold">控制台</h1>
        <p className="text-muted-foreground">
          欢迎回来，{user.display_name}（{user.email}）
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>我的项目</CardTitle>
            <CardDescription>查看和管理参与的项目</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" asChild>
              <Link href="/app/projects">进入项目</Link>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>我的任务</CardTitle>
            <CardDescription>跟踪待办任务</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" asChild>
              <Link href="/app/tasks">查看任务</Link>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>账号设置</CardTitle>
            <CardDescription>管理个人资料与安全</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" asChild>
              <Link href="/app/settings">进入设置</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
