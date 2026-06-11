import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Download,
  FileText,
  MessageSquare,
  MoreHorizontal,
  PencilLine,
  Plus,
  Sparkles,
  TrendingUp,
  Users,
  Zap,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, XAxis } from "recharts";

import { SiteHeader } from "@/components/site-header";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const trendUp = "text-emerald-600 dark:text-emerald-400";
const trendDown = "text-rose-600 dark:text-rose-400";

type Stat = {
  label: string;
  value: string;
  change: string;
  changeDirection: "up" | "down";
  hint: string;
  icon: typeof Users;
  accent: string;
};

const stats: Stat[] = [
  {
    label: "总用户数",
    value: "12,480",
    change: "+8.2%",
    changeDirection: "up",
    hint: "对比上周",
    icon: Users,
    accent: "from-violet-500/20 to-violet-500/0 text-violet-700 dark:text-violet-300",
  },
  {
    label: "今日请求",
    value: "184,623",
    change: "+12.4%",
    changeDirection: "up",
    hint: "对比昨日同时段",
    icon: Zap,
    accent: "from-fuchsia-500/20 to-fuchsia-500/0 text-fuchsia-700 dark:text-fuchsia-300",
  },
  {
    label: "活跃会话",
    value: "3,142",
    change: "-1.8%",
    changeDirection: "down",
    hint: "对比上周平均",
    icon: MessageSquare,
    accent: "from-sky-500/20 to-sky-500/0 text-sky-700 dark:text-sky-300",
  },
  {
    label: "SLA 达成率",
    value: "99.92%",
    change: "+0.06%",
    changeDirection: "up",
    hint: "近 30 天",
    icon: CheckCircle2,
    accent: "from-emerald-500/20 to-emerald-500/0 text-emerald-700 dark:text-emerald-300",
  },
];

type Range = "7d" | "30d" | "90d";

const chartData: Record<Range, Array<{ label: string; value: number }>> = {
  "7d": [
    { label: "周一", value: 1820 },
    { label: "周二", value: 1980 },
    { label: "周三", value: 2340 },
    { label: "周四", value: 2120 },
    { label: "周五", value: 2680 },
    { label: "周六", value: 1980 },
    { label: "周日", value: 2240 },
  ],
  "30d": Array.from({ length: 30 }, (_, i) => ({
    label: `${i + 1} 日`,
    value: 1500 + Math.round(Math.sin(i / 3) * 600 + Math.random() * 300),
  })),
  "90d": Array.from({ length: 90 }, (_, i) => ({
    label: `D${i + 1}`,
    value: 1200 + Math.round(Math.cos(i / 6) * 500 + Math.random() * 400),
  })),
};

const chartConfig = {
  value: {
    label: "请求量",
    color: "hsl(var(--chart-1))",
  },
} satisfies ChartConfig;

const recentActivities = [
  {
    id: "1",
    actor: "王雪",
    initials: "WX",
    action: "完成了里程碑",
    target: "M3 体验优化方案",
    time: "12 分钟前",
    icon: CheckCircle2,
    tone: "text-emerald-600 dark:text-emerald-400",
  },
  {
    id: "2",
    actor: "李明",
    initials: "LM",
    action: "上传了新版本",
    target: "design-system@2.4.1",
    time: "1 小时前",
    icon: Download,
    tone: "text-sky-600 dark:text-sky-400",
  },
  {
    id: "3",
    actor: "陈航",
    initials: "CH",
    action: "在评论中回复了",
    target: "关于登录流程的反馈",
    time: "今天 09:42",
    icon: MessageSquare,
    tone: "text-violet-600 dark:text-violet-400",
  },
  {
    id: "4",
    actor: "张琳",
    initials: "ZL",
    action: "编辑了文档",
    target: "API v2 迁移指南",
    time: "昨天 18:05",
    icon: PencilLine,
    tone: "text-amber-600 dark:text-amber-400",
  },
  {
    id: "5",
    actor: "系统",
    initials: "SYS",
    action: "已自动备份",
    target: "夜间任务 · 18 GB",
    time: "昨天 03:00",
    icon: FileText,
    tone: "text-muted-foreground",
  },
];

type ProjectStatus = "进行中" | "审核中" | "已规划";
type Project = {
  name: string;
  owner: string;
  progress: number;
  status: ProjectStatus;
  tone: string;
};

const popularProjects: Record<"today" | "week" | "month", Project[]> = {
  today: [
    { name: "体验改版 V3", owner: "王雪", progress: 72, status: "进行中", tone: "bg-violet-500" },
    { name: "海外支付接入", owner: "李明", progress: 45, status: "审核中", tone: "bg-amber-500" },
    { name: "数据看板重构", owner: "陈航", progress: 30, status: "已规划", tone: "bg-sky-500" },
  ],
  week: [
    { name: "体验改版 V3", owner: "王雪", progress: 72, status: "进行中", tone: "bg-violet-500" },
    { name: "AI Copilot", owner: "张琳", progress: 88, status: "审核中", tone: "bg-fuchsia-500" },
    { name: "权限中心", owner: "陈航", progress: 60, status: "进行中", tone: "bg-emerald-500" },
  ],
  month: [
    { name: "AI Copilot", owner: "张琳", progress: 88, status: "审核中", tone: "bg-fuchsia-500" },
    { name: "全链路监控", owner: "李明", progress: 65, status: "进行中", tone: "bg-sky-500" },
    { name: "海外多语言", owner: "王雪", progress: 50, status: "已规划", tone: "bg-violet-500" },
  ],
};

export function DashboardPage() {
  const [range, setRange] = useState<Range>("7d");
  const series = useMemo(() => chartData[range], [range]);

  return (
    <div className="flex flex-col">
      <SiteHeader
        title="工作台"
        description="周一早上好,王雪。这里是过去 7 天的关键指标。"
        crumbs={[{ label: "工作台", href: "/dashboard" }, { label: "概览" }]}
        actions={
          <>
            <Button variant="outline" size="sm" className="gap-1.5">
              <Download className="size-3.5" />
              导出
            </Button>
            <Button size="sm" className="gap-1.5">
              <Plus className="size-3.5" />
              新建项目
            </Button>
          </>
        }
      />

      <div className="flex flex-1 flex-col gap-6 p-4 lg:p-6">
        <section
          aria-label="关键指标"
          className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
        >
          {stats.map((stat) => {
            const Icon = stat.icon;
            const isUp = stat.changeDirection === "up";
            return (
              <Card
                key={stat.label}
                className="relative overflow-hidden border-border/60"
              >
                <div
                  className={`pointer-events-none absolute inset-0 bg-gradient-to-br ${stat.accent} opacity-60`}
                  aria-hidden
                />
                <CardHeader className="relative pb-2">
                  <div className="flex items-start justify-between">
                    <CardDescription className="text-sm font-medium">
                      {stat.label}
                    </CardDescription>
                    <span className="rounded-md bg-background/80 p-1.5 shadow-sm ring-1 ring-border/40 backdrop-blur">
                      <Icon className="size-3.5" />
                    </span>
                  </div>
                </CardHeader>
                <CardContent className="relative">
                  <div className="text-2xl font-semibold tracking-tight tabular-nums lg:text-3xl">
                    {stat.value}
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-xs">
                    <Badge
                      variant="secondary"
                      className={`border-0 px-1.5 py-0 ${isUp ? trendUp : trendDown}`}
                    >
                      {isUp ? (
                        <ArrowUpRight className="mr-0.5 size-3" />
                      ) : (
                        <ArrowDownRight className="mr-0.5 size-3" />
                      )}
                      {stat.change}
                    </Badge>
                    <span className="text-muted-foreground">{stat.hint}</span>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </section>

        <section
          aria-label="请求趋势与亮点"
          className="grid gap-4 lg:grid-cols-3"
        >
          <Card className="border-border/60 lg:col-span-2">
            <CardHeader className="flex flex-row items-start justify-between space-y-0">
              <div>
                <CardTitle>请求趋势</CardTitle>
                <CardDescription>
                  按所选时间窗口聚合的请求量（占位数据，接入后端后展示真实指标）
                </CardDescription>
              </div>
              <Tabs
                value={range}
                onValueChange={(value) => setRange(value as Range)}
                className="hidden sm:block"
              >
                <TabsList>
                  <TabsTrigger value="7d">7 天</TabsTrigger>
                  <TabsTrigger value="30d">30 天</TabsTrigger>
                  <TabsTrigger value="90d">90 天</TabsTrigger>
                </TabsList>
              </Tabs>
            </CardHeader>
            <CardContent>
              <ChartContainer
                config={chartConfig}
                className="aspect-auto h-[260px] w-full"
              >
                <AreaChart
                  data={series}
                  margin={{ left: 0, right: 12, top: 8, bottom: 0 }}
                >
                  <defs>
                    <linearGradient
                      id="dashboardAreaFill"
                      x1="0"
                      y1="0"
                      x2="0"
                      y2="1"
                    >
                      <stop
                        offset="5%"
                        stopColor="var(--color-value)"
                        stopOpacity={0.5}
                      />
                      <stop
                        offset="95%"
                        stopColor="var(--color-value)"
                        stopOpacity={0.02}
                      />
                    </linearGradient>
                  </defs>
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="hsl(var(--border))"
                    vertical={false}
                  />
                  <XAxis
                    dataKey="label"
                    tickLine={false}
                    axisLine={false}
                    tickMargin={8}
                    interval="preserveStartEnd"
                    className="fill-muted-foreground text-xs"
                  />
                  <ChartTooltip
                    cursor={{ stroke: "hsl(var(--primary))", strokeWidth: 1 }}
                    content={
                      <ChartTooltipContent
                        indicator="line"
                        labelFormatter={(value) => `${value}`}
                      />
                    }
                  />
                  <Area
                    dataKey="value"
                    type="monotone"
                    fill="url(#dashboardAreaFill)"
                    stroke="var(--color-value)"
                    strokeWidth={2}
                  />
                </AreaChart>
              </ChartContainer>
            </CardContent>
          </Card>

          <Card className="border-border/60">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Sparkles className="size-4 text-primary" />
                <CardTitle>本周亮点</CardTitle>
              </div>
              <CardDescription>系统自动汇总的值得关注的变化</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                {
                  title: "海外支付成功率提升",
                  detail: "从 92.1% 提升至 96.4%，建议继续保持当前路由策略。",
                  tone: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
                  icon: TrendingUp,
                },
                {
                  title: "夜间批处理耗时 +18%",
                  detail: "建议检查数据库慢查询与索引使用情况。",
                  tone: "bg-amber-500/10 text-amber-700 dark:text-amber-300",
                  icon: Clock,
                },
                {
                  title: "新接入 3 个数据源",
                  detail: "已通过校验，可用于 BI 看板的实时指标聚合。",
                  tone: "bg-violet-500/10 text-violet-700 dark:text-violet-300",
                  icon: Zap,
                },
              ].map((highlight) => {
                const Icon = highlight.icon;
                return (
                  <div key={highlight.title} className="flex items-start gap-3">
                    <span
                      className={`mt-0.5 inline-flex size-8 shrink-0 items-center justify-center rounded-md ${highlight.tone}`}
                    >
                      <Icon className="size-4" />
                    </span>
                    <div className="space-y-0.5">
                      <div className="text-sm font-medium leading-snug">
                        {highlight.title}
                      </div>
                      <div className="text-xs leading-relaxed text-muted-foreground">
                        {highlight.detail}
                      </div>
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </section>

        <section
          aria-label="项目与活动"
          className="grid gap-4 lg:grid-cols-3"
        >
          <Card className="border-border/60 lg:col-span-2">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>热门项目</CardTitle>
                  <CardDescription>按当前时间窗口排名的进行中项目</CardDescription>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="gap-1 text-muted-foreground"
                >
                  全部项目
                  <ArrowRight className="size-3.5" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="today">
                <TabsList>
                  <TabsTrigger value="today">今日</TabsTrigger>
                  <TabsTrigger value="week">本周</TabsTrigger>
                  <TabsTrigger value="month">本月</TabsTrigger>
                </TabsList>
                {(["today", "week", "month"] as const).map((key) => (
                  <TabsContent key={key} value={key} className="mt-4 space-y-3">
                    {popularProjects[key].map((project) => (
                      <div
                        key={project.name}
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
                          <div className="mt-1.5 flex items-center gap-3 text-xs text-muted-foreground">
                            <span>负责人 · {project.owner}</span>
                            <Separator orientation="vertical" className="h-3" />
                            <span className="flex-1 truncate">截止 12 月 24 日</span>
                          </div>
                          <Progress value={project.progress} className="mt-2 h-1.5" />
                        </div>
                        <Button variant="ghost" size="icon-sm" aria-label="更多操作">
                          <MoreHorizontal className="size-4" />
                        </Button>
                      </div>
                    ))}
                  </TabsContent>
                ))}
              </Tabs>
            </CardContent>
          </Card>

          <Card className="border-border/60">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle>最近动态</CardTitle>
                  <CardDescription>团队成员的操作流水</CardDescription>
                </div>
                <Avatar className="size-7 ring-2 ring-background">
                  <AvatarFallback className="text-[10px]">你</AvatarFallback>
                </Avatar>
              </div>
            </CardHeader>
            <CardContent>
              <ol className="relative space-y-4 border-l border-border/60 pl-5">
                {recentActivities.map((activity) => {
                  const Icon = activity.icon;
                  return (
                    <li key={activity.id} className="relative">
                      <span
                        className={`absolute -left-[27px] top-0.5 flex size-5 items-center justify-center rounded-full bg-background ring-2 ring-background ${activity.tone}`}
                        aria-hidden
                      >
                        <Icon className="size-3" />
                      </span>
                      <div className="text-sm">
                        <span className="font-medium">{activity.actor}</span>
                        <span className="text-muted-foreground"> {activity.action} </span>
                        <span className="font-medium">{activity.target}</span>
                      </div>
                      <div className="mt-0.5 text-xs text-muted-foreground">
                        {activity.time}
                      </div>
                    </li>
                  );
                })}
              </ol>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
