import Link from "next/link"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Check } from "lucide-react"

const licenseItems = [
  "复制为独立项目并自由开发",
  "私有部署或云托管，无强制开源要求",
  "按需修改骨架代码与配置",
  "保留原始版权与许可声明",
]

/** Render the license page. */
export default function LicensePage() {
  return (
    <div className="container mx-auto py-16">
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-3xl font-bold md:text-5xl">开源授权</h1>
        <p className="mt-4 text-muted-foreground">
          本模板作为开源项目提供，派生项目完全自由，无商业限制。
        </p>
      </div>
      <div className="mx-auto mt-12 max-w-3xl">
        <Card>
          <CardHeader>
            <CardTitle>你可以</CardTitle>
            <CardDescription>
              使用模板启动任意项目，业务代码归你所有。
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {licenseItems.map((item) => (
                <li key={item} className="flex items-center gap-2 text-sm">
                  <Check className="size-4 text-primary" />
                  {item}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <div className="mt-8 text-center">
          <Button asChild>
            <Link href="/register">免费开始</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
