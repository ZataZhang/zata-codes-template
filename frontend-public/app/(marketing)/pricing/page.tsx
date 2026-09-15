import Link from "next/link"
import { useTranslations } from "next-intl"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Check } from "lucide-react"

/** 授权条款条目：与 `marketing.pricingPage.items` 下的文案 key 一一对应。 */
const LICENSE_ITEM_KEYS = ["copy", "deploy", "modify", "license"] as const

/** Render the license page. */
export default function LicensePage() {
  const t = useTranslations("marketing.pricingPage")

  return (
    <div className="container mx-auto py-16">
      <div className="mx-auto max-w-3xl text-center">
        <h1 className="text-3xl font-bold md:text-5xl">{t("title")}</h1>
        <p className="mt-4 text-muted-foreground">{t("description")}</p>
      </div>
      <div className="mx-auto mt-12 max-w-3xl">
        <Card>
          <CardHeader>
            <CardTitle>{t("cardTitle")}</CardTitle>
            <CardDescription>{t("cardDescription")}</CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {LICENSE_ITEM_KEYS.map((itemKey) => (
                <li key={itemKey} className="flex items-center gap-2 text-sm">
                  <Check className="size-4 text-primary" />
                  {t(`items.${itemKey}`)}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
        <div className="mt-8 text-center">
          <Button asChild>
            <Link href="/register">{t("cta")}</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
