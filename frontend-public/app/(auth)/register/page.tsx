"use client"

import Link from "next/link"
import { useRouter } from "next/navigation"
import { useMemo, useState } from "react"
import { useTranslations } from "next-intl"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Loader2, UserPlus } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Form,
  FormControl,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from "@/components/ui/form"
import { Input } from "@/components/ui/input"
import { PasswordInput } from "@/components/ui/password-input"
import { register } from "@/lib/api/auth"

/** 注册表单字段类型，与 `buildFormSchema` 产出的 schema 保持一致。 */
type RegisterFormValues = {
  displayName: string
  email: string
  password: string
  confirmPassword: string
}

/** 注册密码的最短长度。 */
const PASSWORD_MIN_LENGTH = 6

/**
 * 构造注册表单校验 schema。
 *
 * 与登录表单同理：校验消息随 locale 变化，schema 必须在组件内基于当前 `t` 构造。
 *
 * @param t - `errors` 命名空间的翻译函数。
 * @returns 含"两次密码一致"校验的 zod schema。
 */
function buildFormSchema(t: (key: string) => string) {
  return z
    .object({
      displayName: z.string().min(1, t("displayNameRequired")),
      email: z.string().min(1, t("emailRequired")).email(t("emailInvalid")),
      password: z.string().min(PASSWORD_MIN_LENGTH, t("passwordTooShort")),
      confirmPassword: z.string().min(1, t("confirmPasswordRequired")),
    })
    .refine((data) => data.password === data.confirmPassword, {
      message: t("passwordMismatch"),
      path: ["confirmPassword"],
    })
}

/** Render the register page. */
export default function RegisterPage() {
  const router = useRouter()
  const t = useTranslations("auth")
  const tErrors = useTranslations("errors")
  const tToast = useTranslations("toast")
  const [isLoading, setIsLoading] = useState(false)

  const formSchema = useMemo(() => buildFormSchema(tErrors), [tErrors])

  const form = useForm<RegisterFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      displayName: "",
      email: "",
      password: "",
      confirmPassword: "",
    },
  })

  /** Submit the registration form. */
  async function onSubmit(data: RegisterFormValues) {
    setIsLoading(true)
    try {
      await register({
        displayName: data.displayName,
        email: data.email,
        password: data.password,
      })
      toast.success(tToast("registerSuccess"))
      router.replace("/app/dashboard")
    } catch (error) {
      const message =
        error instanceof Error ? error.message : tToast("registerFailed")
      toast.error(message)
    } finally {
      setIsLoading(false)
    }
  }

  const handleFormSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    void form.handleSubmit(onSubmit)(event)
  }

  return (
    <Card className="border shadow-lg">
      <CardHeader className="text-center">
        <CardTitle className="text-2xl">{t("registerTitle")}</CardTitle>
        <CardDescription>{t("registerSubtitle")}</CardDescription>
      </CardHeader>
      <CardContent>
        <Form {...form}>
          <form onSubmit={handleFormSubmit} className="grid gap-4">
            <FormField
              control={form.control}
              name="displayName"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("displayNameLabel")}</FormLabel>
                  <FormControl>
                    <Input placeholder={t("displayNamePlaceholder")} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="email"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("emailLabel")}</FormLabel>
                  <FormControl>
                    <Input placeholder={t("emailPlaceholder")} {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="password"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("passwordLabel")}</FormLabel>
                  <FormControl>
                    <PasswordInput placeholder="********" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <FormField
              control={form.control}
              name="confirmPassword"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>{t("confirmPasswordLabel")}</FormLabel>
                  <FormControl>
                    <PasswordInput placeholder="********" {...field} />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
            <Button type="submit" disabled={isLoading}>
              {isLoading ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <UserPlus className="mr-2 size-4" />
              )}
              {t("registerSubmit")}
            </Button>
          </form>
        </Form>
        <p className="mt-6 text-center text-sm text-muted-foreground">
          {t("haveAccount")}{" "}
          <Link
            href="/login"
            className="text-primary underline-offset-4 hover:underline"
          >
            {t("signInNow")}
          </Link>
        </p>
      </CardContent>
    </Card>
  )
}
