import Link from "next/link"
import { useTranslations } from "next-intl"
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

/** 特性卡片：图标与 `marketing.features` 下的文案 key 一一对应。 */
const FEATURE_ITEMS = [
  { icon: Layers, key: "architecture" },
  { icon: Shield, key: "authDomains" },
  { icon: GitBranch, key: "frontends" },
  { icon: Terminal, key: "observability" },
  { icon: Cpu, key: "config" },
  { icon: Users, key: "teamwork" },
] as const

/** 数字指标：数值固定，标签走 i18n key。 */
const STAT_ITEMS = [
  { value: "4", key: "backendLayers" },
  { value: "2", key: "authDomains" },
  { value: "2", key: "frontendSkeletons" },
] as const

/** 三步开始：序号固定，标题与说明走 i18n key。 */
const STEP_ITEMS = [
  { step: "01", key: "copy" },
  { step: "02", key: "configure" },
  { step: "03", key: "run" },
] as const

/** 常见问题：问题与答案都走 `marketing.faq` 下的 i18n key。 */
const FAQ_ITEMS = ["audience", "businessCode", "createProject"] as const

/** Render the home page. */
export default function HomePage() {
  const t = useTranslations("marketing")
  const tCommon = useTranslations("common")

  return (
    <div className="flex flex-col gap-20 pb-20">
      {/* Hero */}
      <section className="container mx-auto pt-16 md:pt-24">
        <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
          <div className="flex flex-col gap-6">
            <div className="inline-flex w-fit items-center gap-2 rounded-full border bg-muted/50 px-3 py-1 text-xs font-medium">
              <Sparkles className="size-4 text-primary" />
              {t("hero.badge")}
            </div>
            <h1
              data-testid="public-hero-heading"
              className="text-4xl font-bold tracking-tight md:text-6xl"
            >
              {t("hero.titleLine1")}
              <span className="text-primary">{t("hero.titleAccent")}</span>
            </h1>
            <p className="text-lg text-muted-foreground md:text-xl">
              {t("hero.subtitle")}
            </p>
            <div className="flex flex-wrap gap-4">
              <Button size="lg" asChild>
                <Link href="/register">
                  {t("hero.ctaPrimary")}
                  <ArrowRight className="ml-2 size-4" />
                </Link>
              </Button>
              <Button size="lg" variant="outline" asChild>
                <Link href="/features">{t("hero.ctaSecondary")}</Link>
              </Button>
            </div>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <div className="flex items-center gap-1">
                <CheckCircle2 className="size-4 text-primary" />
                {t("hero.highlightNoDomain")}
              </div>
              <div className="flex items-center gap-1">
                <CheckCircle2 className="size-4 text-primary" />
                {t("hero.highlightAuth")}
              </div>
              <div className="flex items-center gap-1">
                <CheckCircle2 className="size-4 text-primary" />
                {t("hero.highlightTooling")}
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
                <span className="text-xs text-muted-foreground">
                  {tCommon("appName")}
                </span>
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
            {STAT_ITEMS.map((stat) => (
              <div key={stat.key}>
                <div className="text-4xl font-bold text-primary">
                  {stat.value}
                </div>
                <div className="mt-2 text-sm text-muted-foreground">
                  {t(`stats.${stat.key}`)}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="container mx-auto">
        <div className="mx-auto max-w-5xl">
          <div className="mb-10 text-center">
            <h2 className="text-3xl font-bold">
              {t("features.sectionTitle")}
            </h2>
            <p className="mt-3 text-muted-foreground">
              {t("features.sectionSubtitle")}
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {FEATURE_ITEMS.map((item) => (
              <Card key={item.key} className="bg-card/50">
                <CardHeader>
                  <item.icon className="size-8 text-primary" />
                  <CardTitle className="mt-2">
                    {t(`features.${item.key}.title`)}
                  </CardTitle>
                  <CardDescription>
                    {t(`features.${item.key}.description`)}
                  </CardDescription>
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
            <h2 className="text-3xl font-bold">{t("steps.sectionTitle")}</h2>
            <p className="mt-3 text-muted-foreground">
              {t("steps.sectionSubtitle")}
            </p>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            {STEP_ITEMS.map((item) => (
              <Card key={item.step} className="relative overflow-hidden">
                <CardHeader>
                  <span className="text-4xl font-bold text-muted-foreground/30">
                    {item.step}
                  </span>
                  <CardTitle className="mt-2">
                    {t(`steps.${item.key}.title`)}
                  </CardTitle>
                  <CardDescription>
                    {t(`steps.${item.key}.description`)}
                  </CardDescription>
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
            <h2 className="text-3xl font-bold">{t("faq.sectionTitle")}</h2>
            <p className="mt-3 text-muted-foreground">
              {t("faq.sectionSubtitle")}
            </p>
          </div>
          <div className="space-y-4">
            {FAQ_ITEMS.map((key) => (
              <Card key={key}>
                <CardHeader>
                  <CardTitle className="text-base">
                    {t(`faq.${key}.question`)}
                  </CardTitle>
                  <CardDescription className="text-sm leading-relaxed">
                    {t(`faq.${key}.answer`)}
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
          <h2 className="text-3xl font-bold">{t("cta.title")}</h2>
          <p className="mx-auto mt-4 max-w-xl text-primary-foreground/80">
            {t("cta.body")}
          </p>
          <Button size="lg" variant="secondary" className="mt-8" asChild>
            <Link href="/register">{t("cta.button")}</Link>
          </Button>
        </div>
      </section>
    </div>
  )
}
