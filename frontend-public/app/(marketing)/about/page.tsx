import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Heart, Lightbulb, Shield } from "lucide-react"

/** Render the about page. */
export default function AboutPage() {
  return (
    <div className="container mx-auto py-16">
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-3xl font-bold md:text-5xl">关于本模板</h1>
        <p className="mt-4 text-muted-foreground">
          这是一个用于启动新项目的 Python 模板：提供四层后端骨架、双认证域与
          完整工程化设施，同时刻意不内置任何业务域，让每个派生项目从干净的
          起点开始搭建自己的业务。
        </p>
      </div>

      <div className="mx-auto mt-12 grid max-w-4xl gap-6 md:grid-cols-3">
        <Card>
          <CardHeader>
            <Lightbulb className="size-8 text-primary" />
            <CardTitle className="mt-2">简洁至上</CardTitle>
            <CardDescription>
              去掉多余复杂度，只保留真正可复用的骨架。
            </CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
        <Card>
          <CardHeader>
            <Shield className="size-8 text-primary" />
            <CardTitle className="mt-2">安全优先</CardTitle>
            <CardDescription>
              从认证到数据存储，安全始终是第一优先级。
            </CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
        <Card>
          <CardHeader>
            <Heart className="size-8 text-primary" />
            <CardTitle className="mt-2">持续演进</CardTitle>
            <CardDescription>
              骨架能力持续打磨，业务边界始终留给派生项目。
            </CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
      </div>
    </div>
  )
}
