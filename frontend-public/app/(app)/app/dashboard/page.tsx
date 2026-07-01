"use client"

import Link from "next/link"
import { useEffect, useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { listAgents } from "@/lib/api/agents"
import { listSessions } from "@/lib/api/sessions"
import { listWorkflows } from "@/lib/api/workflows"
import type { Agent } from "@/lib/types/agent"
import type { ChatSession } from "@/lib/types/session"
import type { Workflow } from "@/lib/types/workflow"
import { Bot, GitBranch, Loader2, MessageSquare, Plus } from "lucide-react"

/** Render the dashboard page. */
export default function DashboardPage() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [workflows, setWorkflows] = useState<Workflow[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([listAgents(), listSessions(), listWorkflows()])
      .then(([agentsData, sessionsData, workflowsData]) => {
        setAgents(agentsData)
        setSessions(sessionsData)
        setWorkflows(workflowsData)
      })
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="size-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-8">
      <div>
        <h1 className="text-3xl font-bold">工作区</h1>
        <p className="text-muted-foreground">概览你的 Agent、会话和工作流</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-2xl">{agents.length}</CardTitle>
            <CardDescription>我的 Agent</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" size="sm" asChild>
              <Link href="/app/agents/new">
                <Plus className="mr-1 size-4" />
                新建 Agent
              </Link>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-2xl">{sessions.length}</CardTitle>
            <CardDescription>最近会话</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" size="sm" asChild>
              <Link href="/app/chat">
                <MessageSquare className="mr-1 size-4" />
                查看会话
              </Link>
            </Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-2xl">{workflows.length}</CardTitle>
            <CardDescription>工作流</CardDescription>
          </CardHeader>
          <CardContent>
            <Button variant="outline" size="sm" asChild>
              <Link href="/app/workflows/new">
                <GitBranch className="mr-1 size-4" />
                新建工作流
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-8 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Bot className="size-5 text-primary" />
              最近 Agent
            </CardTitle>
          </CardHeader>
          <CardContent>
            {agents.length === 0 ? (
              <p className="text-sm text-muted-foreground">还没有创建 Agent</p>
            ) : (
              <ul className="space-y-3">
                {agents.slice(0, 5).map((agent) => (
                  <li key={agent.id}>
                    <Link
                      href={`/app/agents/${agent.id}`}
                      className="block rounded-lg border p-3 hover:bg-muted/50"
                    >
                      <div className="font-medium">{agent.name}</div>
                      <div className="text-sm text-muted-foreground">
                        {agent.description || "暂无描述"}
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="size-5 text-primary" />
              最近会话
            </CardTitle>
          </CardHeader>
          <CardContent>
            {sessions.length === 0 ? (
              <p className="text-sm text-muted-foreground">还没有会话记录</p>
            ) : (
              <ul className="space-y-3">
                {sessions.slice(0, 5).map((session) => (
                  <li key={session.id}>
                    <Link
                      href={`/app/chat/${session.id}`}
                      className="block rounded-lg border p-3 hover:bg-muted/50"
                    >
                      <div className="font-medium">{session.title}</div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
