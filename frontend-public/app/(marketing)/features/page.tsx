import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Cpu, GitBranch, Layers, Shield, Terminal, Zap } from "lucide-react"

const features = [
  {
    icon: Layers,
    title: "四层架构",
    description: "api / core / engines / infrastructure，依赖向内，跨层接口解耦。",
  },
  {
    icon: Shield,
    title: "双认证域",
    description: "public 与 admin 物理隔离，HttpOnly Session + Redis 会话存储。",
  },
  {
    icon: GitBranch,
    title: "双前端骨架",
    description: "管理后台（Vite + React）与公开官网（Next.js），即开即用。",
  },
  {
    icon: Terminal,
    title: "统一配置",
    description: "环境变量 / config.toml / 默认值三层配置源，敏感值只进 .env。",
  },
  {
    icon: Zap,
    title: "可观测性",
    description: "请求 ID、结构化日志与 Prometheus 指标，按开关装配。",
  },
  {
    icon: Cpu,
    title: "工程化完整",
    description: "just 任务、pre-commit + Ruff、Alembic 迁移守卫、模板同步。",
  },
]

/** Render the features page. */
export default function FeaturesPage() {
  return (
    <div className="container mx-auto py-16">
      <div className="mx-auto max-w-5xl">
        <div className="mb-10 text-center">
          <h1 className="text-4xl font-bold">模板能力</h1>
          <p className="mt-3 text-muted-foreground">
            只提供工程化骨架，不内置任何业务域
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
    </div>
  )
}
