import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Heart, Lightbulb, Shield } from "lucide-react"

export default function AboutPage() {
  return (
    <div className="container mx-auto py-16">
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-3xl font-bold md:text-5xl">关于 Zata</h1>
        <p className="mt-4 text-muted-foreground">
          我们致力于打造简洁、高效、可扩展的团队协作平台。
        </p>
      </div>

      <div className="mx-auto mt-12 grid max-w-4xl gap-6 md:grid-cols-3">
        <Card>
          <CardHeader>
            <Lightbulb className="size-8 text-primary" />
            <CardTitle className="mt-2">简洁至上</CardTitle>
            <CardDescription>
              去掉多余复杂度，让工具服务于工作本身。
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
            <CardTitle className="mt-2">持续迭代</CardTitle>
            <CardDescription>
              倾听用户反馈，快速迭代产品体验。
            </CardDescription>
          </CardHeader>
          <CardContent />
        </Card>
      </div>
    </div>
  )
}
