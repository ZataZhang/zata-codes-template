import Link from "next/link"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  ArrowRight,
  CheckCircle2,
  Layers,
  Users,
  Zap,
  BarChart3,
  Shield,
  Rocket,
  MessageSquare,
} from "lucide-react"

const stats = [
  { value: "10k+", label: "活跃用户" },
  { value: "50k+", label: "管理任务" },
  { value: "99.9%", label: "服务可用性" },
]

const steps = [
  {
    step: "01",
    title: "创建项目",
    description: "几分钟内建立团队工作空间，定义目标与里程碑。",
  },
  {
    step: "02",
    title: "分配任务",
    description: "将工作拆分为可执行的任务，分配给团队成员并设定优先级。",
  },
  {
    step: "03",
    title: "实时协作",
    description: "跟踪进度、更新状态，让所有人保持同步。",
  },
  {
    step: "04",
    title: "数据驱动",
    description: "通过报表与洞察持续优化团队效率。",
  },
]

const testimonials = [
  {
    content:
      "Zata 让我们的项目管理效率提升了至少 30%，界面简洁但功能非常完整。",
    author: "李明",
    role: "某科技公司 CTO",
  },
  {
    content:
      "从任务分配到进度跟踪，一切都变得透明可控，团队沟通成本大大降低。",
    author: "王芳",
    role: "产品经理",
  },
]

const faqs = [
  {
    question: "Zata 适合什么规模的团队？",
    answer:
      "从初创团队到大型企业都可以使用。免费版支持小团队试用，专业版和企业版提供更多成员与高级功能。",
  },
  {
    question: "注册后是否需要绑定信用卡？",
    answer:
      "免费版无需绑定信用卡即可开始使用。升级到付费方案时才会需要支付信息。",
  },
  {
    question: "数据安全如何保障？",
    answer:
      "我们使用 HttpOnly Session 进行身份认证，所有传输均通过加密连接，并定期备份关键数据。",
  },
]

export default function HomePage() {
  return (
    <div className="flex flex-col gap-20 pb-20">
      {/* Hero */}
      <section className="container mx-auto pt-16 md:pt-24">
        <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
          <div className="flex flex-col gap-6">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border bg-muted/50 px-3 py-1 text-xs font-medium">
              <span className="size-2 rounded-full bg-primary" />
              新一代团队协作平台
            </div>
            <h1 className="text-4xl font-bold tracking-tight md:text-6xl">
              让团队协作
              <span className="text-primary">更简单</span>
            </h1>
            <p className="text-lg text-muted-foreground md:text-xl">
              Zata 是统一项目、任务与团队协作的现代化平台。
              无需登录即可了解我们，注册后即可开始高效工作。
            </p>
            <div className="flex flex-wrap gap-4">
              <Button size="lg" asChild>
                <Link href="/register">
                  免费开始
                  <ArrowRight className="ml-2 size-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/features">了解功能</Link>
              </Button>
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-1">
                <CheckCircle2 className="size-4 text-primary" />
                免费试用
              </div>
              <div className="flex items-center gap-1">
                <CheckCircle2 className="size-4 text-primary" />
                无需信用卡
              </div>
              <div className="flex items-center gap-1">
                <CheckCircle2 className="size-4 text-primary" />
                即时开通
              </div>
            </div>
          </div>
          <div className="relative hidden lg:block">
            <div className="absolute inset-0 rounded-3xl bg-gradient-to-br from-primary/20 to-muted opacity-50 blur-3xl" />
            <div className="relative rounded-2xl border bg-card p-6 shadow-xl">
              <div className="mb-4 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <div className="size-3 rounded-full bg-red-500" />
                  <div className="size-3 rounded-full bg-yellow-500" />
                  <div className="size-3 rounded-full bg-green-500" />
                </div>
                <span className="text-xs text-muted-foreground">Zata Dashboard</span>
              </div>
              <div className="space-y-3">
                <div className="h-24 rounded-lg bg-muted" />
                <div className="grid grid-cols-3 gap-3">
                  <div className="h-20 rounded-lg bg-muted" />
                  <div className="h-20 rounded-lg bg-muted" />
                  <div className="h-20 rounded-lg bg-muted" />
                </div>
                <div className="h-32 rounded-lg bg-muted" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Logos */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-5xl rounded-2xl border bg-muted/30 px-8 py-8">
          <p className="mb-6 text-center text-sm text-muted-foreground">
            受到以下团队信赖
          </p>
          <div className="flex flex-wrap items-center justify-center gap-8 opacity-60">
            {["Acme", "Globex", "Hooli", "Initech", "Umbrella"].map((name) => (
              <span
                key={name}
                className="text-lg font-semibold tracking-tight text-muted-foreground"
              >
                {name}
              </span>
            ))}
          </div>
        </div>
      </section>

      {/* Features preview */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-5xl">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold">核心能力</h2>
            <p className="mt-3 text-muted-foreground">
              一站式解决项目、任务与团队协作的核心需求
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            <Card>
              <CardHeader>
                <Layers className="size-8 text-primary" />
                <CardTitle className="mt-2">项目管理</CardTitle>
                <CardDescription>
                  清晰的项目看板，实时掌握进度与状态。
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-primary" />
                    多项目并行跟踪
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-primary" />
                    状态与负责人一目了然
                  </li>
                </ul>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <Zap className="size-8 text-primary" />
                <CardTitle className="mt-2">任务协作</CardTitle>
                <CardDescription>
                  将大目标拆解为可执行的小任务。
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-primary" />
                    优先级与截止日期
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-primary" />
                    筛选与批量操作
                  </li>
                </ul>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <Users className="size-8 text-primary" />
                <CardTitle className="mt-2">团队权限</CardTitle>
                <CardDescription>
                  灵活的成员管理与角色控制。
                </CardDescription>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2 text-sm text-muted-foreground">
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-primary" />
                    角色与权限分配
                  </li>
                  <li className="flex items-center gap-2">
                    <CheckCircle2 className="size-4 text-primary" />
                    安全的会话管理
                  </li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* How it works */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-5xl">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold">使用流程</h2>
            <p className="mt-3 text-muted-foreground">
              四步上手，快速建立高效协作节奏
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-4">
            {steps.map((item) => (
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

      {/* Testimonials */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-5xl">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold">用户评价</h2>
            <p className="mt-3 text-muted-foreground">
              来自真实用户的使用反馈
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            {testimonials.map((item) => (
              <Card key={item.author}>
                <CardHeader>
                  <MessageSquare className="size-6 text-primary" />
                  <CardDescription className="pt-2 text-base leading-relaxed text-foreground">
                    &ldquo;{item.content}&rdquo;
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="font-medium">{item.author}</div>
                  <div className="text-sm text-muted-foreground">{item.role}</div>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* More features */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-5xl">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold">更多功能</h2>
            <p className="mt-3 text-muted-foreground">
              为团队提供全方位的支持
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            <Card>
              <CardHeader>
                <BarChart3 className="size-8 text-primary" />
                <CardTitle className="mt-2">数据洞察</CardTitle>
                <CardDescription>
                  通过可视化数据了解项目健康度，及时调整资源分配。
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <Shield className="size-8 text-primary" />
                <CardTitle className="mt-2">安全合规</CardTitle>
                <CardDescription>
                  基于 HttpOnly Session 的认证机制，保护用户数据安全。
                </CardDescription>
              </CardHeader>
            </Card>
            <Card>
              <CardHeader>
                <Rocket className="size-8 text-primary" />
                <CardTitle className="mt-2">快速上手</CardTitle>
                <CardDescription>
                  简洁直观的界面设计，无需培训即可开始使用。
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
        </div>
      </section>

      {/* FAQ */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-3xl">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold">常见问题</h2>
            <p className="mt-3 text-muted-foreground">
              关于 Zata 你可能想知道的事
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
          <h2 className="text-3xl font-bold">准备好开始了？</h2>
          <p className="mx-auto mt-4 max-w-xl text-primary-foreground/80">
            注册账号，立即体验 Zata 的完整功能。免费版支持小团队无门槛试用。
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
