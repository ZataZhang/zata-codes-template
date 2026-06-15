import { MoreHorizontal, Plus, Sparkles } from "lucide-react";

import { SiteHeader } from "@/components/site-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";

type ProjectStatus = "进行中" | "审核中" | "已规划";

type ProjectItem = {
  id: string;
  name: string;
  description: string;
  owner: string;
  progress: number;
  status: ProjectStatus;
  tone: string;
};

const projectsList: ProjectItem[] = [
  {
    id: "1",
    name: "体验改版 V3",
    description: "重构核心用户流程，提升关键路径转化率。",
    owner: "王雪",
    progress: 72,
    status: "进行中",
    tone: "bg-violet-500",
  },
  {
    id: "2",
    name: "海外支付接入",
    description: "集成多渠道支付网关，支持 12 个新区域。",
    owner: "李明",
    progress: 45,
    status: "审核中",
    tone: "bg-amber-500",
  },
  {
    id: "3",
    name: "数据看板重构",
    description: "统一指标口径，支持自定义报表与实时刷新。",
    owner: "陈航",
    progress: 30,
    status: "已规划",
    tone: "bg-sky-500",
  },
  {
    id: "4",
    name: "AI Copilot",
    description: "基于大模型的智能助手，覆盖研发与运营场景。",
    owner: "张琳",
    progress: 88,
    status: "审核中",
    tone: "bg-fuchsia-500",
  },
  {
    id: "5",
    name: "权限中心",
    description: "细粒度 RBAC 与资源级权限策略管理。",
    owner: "陈航",
    progress: 60,
    status: "进行中",
    tone: "bg-emerald-500",
  },
];

export function ProjectsPage() {
  return (
    <div className="flex flex-col">
      <SiteHeader
        title="热门项目"
        description="按时间窗口排名的进行中项目，可查看进度与负责人。"
        crumbs={[{ label: "工作台", href: "/dashboard" }, { label: "热门项目" }]}
        actions={
          <Button size="sm" className="gap-1.5">
            <Plus className="size-3.5" />
            新建项目
          </Button>
        }
      />

      <div className="flex flex-1 flex-col gap-6 p-4 lg:p-6">
        <section aria-label="项目列表">
          <Card className="border-border/60">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Sparkles className="size-4 text-primary" />
                <CardTitle>全部项目</CardTitle>
              </div>
              <CardDescription>当前团队正在推进的项目清单</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {projectsList.map((project) => (
                <div
                  key={project.id}
                  className="flex items-center gap-3 rounded-lg border border-border/60 p-3 transition-colors hover:bg-accent/40"
                >
                  <span
                    className={`size-2.5 shrink-0 rounded-full ${project.tone}`}
                    aria-hidden
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">
                        {project.name}
                      </span>
                      <Badge
                        variant="outline"
                        className="border-border/60 text-[10px] font-normal text-muted-foreground"
                      >
                        {project.status}
                      </Badge>
                    </div>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {project.description}
                    </p>
                    <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
                      <span>负责人 · {project.owner}</span>
                      <Separator orientation="vertical" className="h-3" />
                      <span className="flex-1 truncate">进度 {project.progress}%</span>
                    </div>
                    <Progress value={project.progress} className="mt-2 h-1.5" />
                  </div>
                  <Button variant="ghost" size="icon-sm" aria-label="更多操作">
                    <MoreHorizontal className="size-4" />
                  </Button>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
