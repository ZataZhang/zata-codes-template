import { useTranslations } from "next-intl"
import {
  Card,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Cpu, GitBranch, Layers, Shield, Terminal, Zap } from "lucide-react"

/** 能力卡片：图标与 `marketing.featuresPage.items` 下的文案 key 一一对应。 */
const FEATURE_ITEMS = [
  { icon: Layers, key: "architecture" },
  { icon: Shield, key: "authDomains" },
  { icon: GitBranch, key: "frontends" },
  { icon: Terminal, key: "config" },
  { icon: Zap, key: "observability" },
  { icon: Cpu, key: "tooling" },
] as const

/** Render the features page. */
export default function FeaturesPage() {
  const t = useTranslations("marketing.featuresPage")

  return (
    <div className="container mx-auto py-16">
      <div className="mx-auto max-w-5xl">
        <div className="mb-10 text-center">
          <h1 className="text-4xl font-bold">{t("title")}</h1>
          <p className="mt-3 text-muted-foreground">{t("subtitle")}</p>
        </div>
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {FEATURE_ITEMS.map((item) => (
            <Card key={item.key} className="bg-card/50">
              <CardHeader>
                <item.icon className="size-8 text-primary" />
                <CardTitle className="mt-2">{t(`items.${item.key}.title`)}</CardTitle>
                <CardDescription>{t(`items.${item.key}.description`)}</CardDescription>
              </CardHeader>
            </Card>
          ))}
        </div>
      </div>
    </div>
  )
}
