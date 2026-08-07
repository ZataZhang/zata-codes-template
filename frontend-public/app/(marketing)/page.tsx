import Link from "next/link"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ArrowRight,
  CheckCircle2,
  Cpu,
  GitBranch,
  Layers,
  Shield,
  Sparkles,
  Terminal,
  Users,
} from "lucide-react"

const features = [
  {
    icon: Layers,
    title: "四层后端架构",
    description:
      "api / core / engines / infrastructure 依赖向内，跨层通过抽象接口协作，业务与基础设施解耦。",
  },
  {
    icon: Shield,
    title: "双认证域",
    description:
      "public 自助注册域与 admin 种子创建域物理隔离，各自独立 Cookie、会话命名空间与用户表。",
  },
  {
    icon: GitBranch,
    title: "双前端骨架",
    description:
      "管理后台（Vite + React）与公开官网（Next.js）开箱即用，与后端仅通过 /api/* HTTP 通信。",
  },
  {
    icon: Terminal,
    title: "可观测性",
    description:
      "请求 ID、结构化日志与 Prometheus 指标按开关装配，日志与指标格式平台无关。",
  },
  {
    icon: Cpu,
    title: "统一配置",
    description:
      "pydantic-settings 三层配置源：环境变量 / config.toml / 代码默认值，敏感值只进 .env。",
  },
  {
    icon: Users,
    title: "团队工程化",
    description:
      "just 任务驱动、pre-commit + Ruff、Alembic 迁移链守卫、模板同步脚本，开箱即用。",
  },
]

const stats = [
  { value: "4", label: "后端分层" },
  { value: "2", label: "认证域" },
  { value: "2", label: "前端骨架" },
]

const faqs = [
  {
    question: "这个模板适合什么项目？",
    answer:
      "适合需要长期维护的 Python Web 项目：先有清晰的分层骨架与工程化设施，再按业务添加模块。",
  },
  {
    question: "模板内置业务代码吗？",
    answer:
      "不内置任何业务域。认证、配置、可观测性与持久化是唯一骨架，业务模块由派生项目自行添加。",
  },
  {
    question: "如何用模板创建新项目？",
    answer:
      "使用 just copy <name> 复制为独立项目，再按 README 配置环境变量与数据库即可启动。",
  },
]

/** Render the home page. */
export default function HomePage() {
  return (
    <div className="flex flex-col gap-20 pb-20">
      {/* Hero */}
      <section className="container mx-auto pt-16 md:pt-24">
        <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
          <div className="flex flex-col gap-6">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border bg-muted/50 px-3 py-1 text-xs font-medium">
              <Sparkles className="size-4 text-primary" />
              面向长期演进的项目模板
            </div>
            <h1
              data-testid="public-hero-heading"
              className="text-4xl font-bold tracking-tight md:text-6xl"
            >
              干净的骨架，
              <span className="text-primary">只留工程化</span>
            </h1>
            <p className="text-lg text-muted-foreground md:text-xl">
              四层模块化单体 + 双认证域 + 可观测性。不内置业务域，
              让每个派生项目从零开始搭建自己的业务。
            </p>
            <div className="flex flex-wrap gap-4">
              <Button size="lg" asChild>
                <Link href="/register">
                  免费开始
                  <ArrowRight className="ml-2 size-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/features">了解骨架</Link>
              </Button>
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-1">
                <CheckCircle2 className="size-4 text-primary" />
                无业务域残留
              </div>
              <div className="flex items-center gap-1">
                <CheckCircle2 className="size-4 text-primary" />
                认证开箱即用
              </div>
              <div className="flex items-center gap-1">
                <CheckCircle2 className="size-4 text-primary" />
                工程化完整
              </div>
            </div>
          </div>
          <div className="relative hidden lg:block">
            <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-primary/30 via-accent/20 to-muted opacity-60 blur-3xl" />
            <div className="relative rounded-2xl border bg-card/80 p-6 shadow-xl backdrop-blur">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="size-3 rounded-full bg-red-500" />
                  <div className="size-3 rounded-full bg-yellow-500" />
                  <div className="size-3 rounded-full bg-green-500" />
                </div>
                <span className="text-xs text-muted-foreground">My App</span>
              </div>
              <div className="space-y-3">
                <div className="flex items-center gap-3 rounded-lg bg-muted p-4">
                  <Layers className="size-6 text-primary" />
                  <div className="flex-1">
                    <div className="h-2 w-24 rounded bg-primary/20" />
                    <div className="mt-2 h-2 w-full rounded bg-muted-foreground/20" />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="h-24 rounded-lg bg-muted" />
                  <div className="h-24 rounded-lg bg-muted" />
                </div>
                <div className="h-32 rounded-lg bg-muted" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Stats */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-5xl">
          <div className="grid gap-6 rounded-2xl border bg-muted/30 px-8 py-12 text-center md:grid-cols-3">
            {stats.map((stat) => (
              <div key={stat.label}>
                <div className="text-4xl font-bold text-primary">{stat.value}</div>
                <div className="mt-2 text-sm text-muted-foreground">{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-5xl">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold">核心骨架</h2>
            <p className="mt-3 text-muted-foreground">
              模板只承诺工程化能力，业务边界留给你
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {features.map((item) => (
              <Card key={item.title} className="bg-card/50">
                <CardHeader>
                  <item.icon className="size-8 text-primary" />
                  <CardTitle className="mt-2">{item.title}</CardTitle>
                  <CardDescription>{item.description}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-5xl">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold">三步开始</h2>
            <p className="mt-3 text-muted-foreground">
              复制模板、配置环境、启动服务
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {[
              {
                step: "01",
                title: "复制模板",
                description: "just copy <name> 创建新项目，不包含依赖与构建产物。",
              },
              {
                step: "02",
                title: "配置环境",
                description: "按 .env.example 填写数据库、Redis 与初始管理员。",
              },
              {
                step: "03",
                title: "启动服务",
                description: "just sync dev 安装依赖，just run 同时启动后端与两个前端。",
              },
            ].map((item) => (
              <Card key={item.step} className="relative overflow-hidden">
                <CardHeader>
                  <span className="text-4xl font-bold text-muted-foreground/30">
                    {item.step}
                  </span>
                  <CardTitle className="mt-2">{item.title}</CardTitle>
                  <CardDescription>{item.description}</CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-3xl">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold">常见问题</h2>
            <p className="mt-3 text-muted-foreground">
              关于这个模板你可能想知道的事
            </p>
          </div>
          <div className="space-y-4">
            {faqs.map((faq) => (
              <Card key={faq.question}>
                <CardHeader>
                  <CardTitle className="text-base">{faq.question}</CardTitle>
                  <CardDescription className="text-sm leading-relaxed">
                    {faq.answer}
                  </CardDescription>
                </CardHeader>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-4xl rounded-2xl bg-primary px-6 py-16 text-center text-primary-foreground md:px-12">
          <h2 className="text-3xl font-bold">准备好开始了吗？</h2>
          <p className="mx-auto mt-4 max-w-xl text-primary-foreground/80">
            注册账号，进入受保护区域，从干净的后端骨架开始搭建你的业务。
          </p>
          <Button
            size="lg"
            variant="secondary"
            className="mt-8"
            asChild
          >
            <Link href="/register">免费注册</Link>
          </Button>
        </div>
      </section>
    </div>
  )
}
