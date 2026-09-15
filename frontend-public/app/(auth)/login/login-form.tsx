"use client"

import Link from "next/link"
import { useRouter, useSearchParams } from "next/navigation"
import { useMemo, useState } from "react"
import { useTranslations } from "next-intl"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import { z } from "zod"
import { Loader2, LogIn } from "lucide-react"
import { toast } from "sonner"
import { Button } from "@/components/ui/button"
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
import { login } from "@/lib/api/auth"

/** 登录表单字段类型，与 `buildFormSchema` 产出的 schema 保持一致。 */
type LoginFormValues = {
  identifier: string
  password: string
}

/**
 * 构造登录表单校验 schema。
 *
 * 校验消息依赖当前 locale，因此 schema 必须在使用 `t` 的组件内构造，
 * 不能在模块顶层固化（否则语言切换后错误提示仍是旧语言）。
 *
 * @param t - `errors` 命名空间的翻译函数。
 * @returns 与该表单字段对应的 zod schema。
 */
function buildFormSchema(t: (key: string) => string) {
  return z.object({
    identifier: z.string().min(1, t("identifierRequired")),
    password: z.string().min(1, t("passwordRequired")),
  })
}

/** Render the LoginForm component. */
export function LoginForm() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const t = useTranslations("auth")
  const tErrors = useTranslations("errors")
  const tToast = useTranslations("toast")
  const [isLoading, setIsLoading] = useState(false)

  const formSchema = useMemo(() => buildFormSchema(tErrors), [tErrors])

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      identifier: "",
      password: "",
    },
  })

  /** Submit the login form. */
  async function onSubmit(data: LoginFormValues) {
    setIsLoading(true)
    try {
      await login(data)
      toast.success(tToast("loginSuccess"))
      const redirect = searchParams.get("redirect")
      router.replace(redirect || "/app/dashboard")
    } catch (error) {
      const message =
        error instanceof Error ? error.message : tToast("loginFailed")
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
    <Form {...form}>
      <form onSubmit={handleFormSubmit} className="grid gap-4">
        <FormField
          control={form.control}
          name="identifier"
          render={({ field }) => (
            <FormItem>
              <FormLabel>{t("identifierLabel")}</FormLabel>
              <FormControl>
                <Input
                  data-testid="login-identifier-input"
                  placeholder="admin@example.com"
                  {...field}
                />
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
              <div className="flex items-center justify-between">
                <FormLabel>{t("passwordLabel")}</FormLabel>
                <button
                  type="button"
                  className="text-xs text-muted-foreground underline-offset-4 hover:text-primary hover:underline"
                  onClick={() => toast.info(t("forgotPasswordHint"))}
                >
                  {t("forgotPassword")}
                </button>
              </div>
              <FormControl>
                <PasswordInput
                  data-testid="login-password-input"
                  placeholder="********"
                  {...field}
                />
              </FormControl>
              <FormMessage />
            </FormItem>
          )}
        />
        <Button
          data-testid="login-submit-button"
          type="submit"
          disabled={isLoading}
        >
          {isLoading ? (
            <Loader2 className="mr-2 size-4 animate-spin" />
          ) : (
            <LogIn className="mr-2 size-4" />
          )}
          {t("loginSubmit")}
        </Button>
      </form>
      <p className="mt-6 text-center text-sm text-muted-foreground">
        {t("noAccount")}{" "}
        <Link
          href="/register"
          className="text-primary underline-offset-4 hover:underline"
        >
          {t("signUpNow")}
        </Link>
      </p>
    </Form>
  )
}
