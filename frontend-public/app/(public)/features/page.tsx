import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { BarChart3, Layers, Lock, Rocket, Users, Zap } from "lucide-react"

const features = [
  {
    icon: Layers,
    title: "项目管理",
    description: "创建项目、设定里程碑、跟踪进度，让复杂交付变得清晰可控。",
  },
  {
    icon: Zap,
    title: "任务协作",
    description: "分配任务、设置优先级、记录状态，确保每个人都在正确的轨道上。",
  },
  {
    icon: Users,
    title: "团队管理",
    description: "邀请成员、分配角色、控制权限，构建安全的协作空间。",
  },
  {
    icon: BarChart3,
    title: "数据洞察",
    description: "通过可视化数据了解项目健康度，及时调整资源分配。",
  },
  {
    icon: Lock,
    title: "安全合规",
    description: "基于 HttpOnly Session 的认证机制，保护用户数据安全。",
  },
  {
    icon: Rocket,
    title: "快速上手",
    description: "简洁直观的界面设计，无需培训即可开始使用。",
  },
]

export default function FeaturesPage() {
  return (
    <div className="container mx-auto py-16">
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-3xl font-bold md:text-5xl">核心功能</h1>
        <p className="mt-4 text-muted-foreground">
          Zata 提供一站式的项目与团队管理体验，帮助团队聚焦真正重要的事情。
        </p>
      </div>
      <div className="mx-auto mt-12 grid max-w-5xl gap-6 md:grid-cols-2 lg:grid-cols-3">
        {features.map((feature) => (
          <Card key={feature.title}>
            <CardHeader>
              <feature.icon className="size-8 text-primary" />
              <CardTitle className="mt-2">{feature.title}</CardTitle>
              <CardDescription>{feature.description}</CardDescription>
            </CardHeader>
            <CardContent />
          </Card>
        ))}
      </div>
    </div>
  )
}
