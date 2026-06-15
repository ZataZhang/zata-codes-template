import { Box, CheckCircle2, Circle, Clock, Plus } from "lucide-react";

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
import { Checkbox } from "@/components/ui/checkbox";

type TaskPriority = "高" | "中" | "低";
type TaskStatus = "待处理" | "进行中" | "已完成";

type TaskItem = {
  id: string;
  title: string;
  project: string;
  dueDate: string;
  priority: TaskPriority;
  status: TaskStatus;
};

const tasksList: TaskItem[] = [
  {
    id: "1",
    title: "完成登录流程可用性测试",
    project: "体验改版 V3",
    dueDate: "今天",
    priority: "高",
    status: "进行中",
  },
  {
    id: "2",
    title: "整理海外支付渠道对接文档",
    project: "海外支付接入",
    dueDate: "明天",
    priority: "中",
    status: "待处理",
  },
  {
    id: "3",
    title: "更新数据看板指标口径说明",
    project: "数据看板重构",
    dueDate: "本周五",
    priority: "低",
    status: "待处理",
  },
  {
    id: "4",
    title: "AI Copilot 提示词调优",
    project: "AI Copilot",
    dueDate: "昨天",
    priority: "高",
    status: "已完成",
  },
  {
    id: "5",
    title: "权限中心角色分配策略评审",
    project: "权限中心",
    dueDate: "下周一",
    priority: "中",
    status: "进行中",
  },
];

const priorityTone: Record<TaskPriority, string> = {
  高: "bg-rose-500/10 text-rose-700 dark:text-rose-300 border-rose-500/20",
  中: "bg-amber-500/10 text-amber-700 dark:text-amber-300 border-amber-500/20",
  低: "bg-sky-500/10 text-sky-700 dark:text-sky-300 border-sky-500/20",
};

const statusIcon: Record<TaskStatus, typeof Circle> = {
  待处理: Circle,
  进行中: Clock,
  已完成: CheckCircle2,
};

export function TasksPage() {
  return (
    <div className="flex flex-col">
      <SiteHeader
        title="任务"
        description="查看和跟进你的待办任务与团队分配。"
        crumbs={[{ label: "工作台", href: "/dashboard" }, { label: "任务" }]}
        actions={
          <Button size="sm" className="gap-1.5">
            <Plus className="size-3.5" />
            新建任务
          </Button>
        }
      />

      <div className="flex flex-1 flex-col gap-6 p-4 lg:p-6">
        <section aria-label="任务列表">
          <Card className="border-border/60">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Box className="size-4 text-primary" />
                <CardTitle>我的任务</CardTitle>
              </div>
              <CardDescription>按截止时间排序的待办与进行中任务</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              {tasksList.map((task) => {
                const StatusIcon = statusIcon[task.status];
                return (
                  <div
                    key={task.id}
                    className="flex items-start gap-3 rounded-lg border border-border/60 p-3 transition-colors hover:bg-accent/40"
                  >
                    <Checkbox
                      id={`task-${task.id}`}
                      checked={task.status === "已完成"}
                      aria-label={`标记 ${task.title}`}
                      className="mt-0.5"
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <label
                          htmlFor={`task-${task.id}`}
                          className={`text-sm font-medium ${
                            task.status === "已完成"
                              ? "text-muted-foreground line-through"
                              : ""
                          }`}
                        >
                          {task.title}
                        </label>
                        <Badge
                          variant="outline"
                          className={`text-[10px] font-normal ${priorityTone[task.priority]}`}
                        >
                          {task.priority}
                        </Badge>
                      </div>
                      <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                        <StatusIcon className="size-3" />
                        <span>{task.status}</span>
                        <span>·</span>
                        <span>{task.project}</span>
                        <span>·</span>
                        <span>截止 {task.dueDate}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
