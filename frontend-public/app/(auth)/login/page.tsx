import { Suspense } from "react"
import { useTranslations } from "next-intl"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { LoginForm } from "./login-form"

/** Render the login page. */
export default function LoginPage() {
  const t = useTranslations("auth")
  const tCommon = useTranslations("common")

  return (
    <Card className="border shadow-lg">
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">{t("loginTitle")}</CardTitle>
        <CardDescription>{t("loginSubtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        <Suspense
          fallback={
            <div className="py-8 text-center text-sm text-muted-foreground">
              {tCommon("loading")}
            </div>
          }
        >
          <LoginForm />
        </Suspense>
      </CardContent>
    </Card>
  )
}
