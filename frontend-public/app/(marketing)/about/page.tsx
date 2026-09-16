import { useTranslations } from "next-intl"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Heart, Lightbulb, Shield } from "lucide-react"

/** 理念卡片：图标与 `marketing.aboutPage.principles` 下的文案 key 一一对应。 */
const PRINCIPLE_ITEMS = [
  { icon: Lightbulb, key: "simple" },
  { icon: Shield, key: "security" },
  { icon: Heart, key: "evolution" },
] as const

/** Render the about page. */
export default function AboutPage() {
  const t = useTranslations("marketing.aboutPage")

  return (
    <div className="container mx-auto py-16">
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-3xl font-bold md:text-5xl">{t("title")}</h1>
        <p className="mt-4 text-muted-foreground">{t("description")}</p>
      </div>

      <div className="mx-auto mt-12 grid max-w-4xl gap-6 md:grid-cols-3">
        {PRINCIPLE_ITEMS.map((item) => (
          <Card key={item.key}>
            <CardHeader>
              <item.icon className="size-8 text-primary" />
              <CardTitle className="mt-2">{t(`principles.${item.key}.title`)}</CardTitle>
              <CardDescription>
                {t(`principles.${item.key}.description`)}
              </CardDescription>
            </CardHeader>
            <CardContent />
          </Card>
        ))}
      </div>
    </div>
  )
}
