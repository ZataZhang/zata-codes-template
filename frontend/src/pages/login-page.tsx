import { useEffect, useState, type FormEvent } from "react";
import { Eye, EyeOff, Loader2, ShieldCheck, Sparkles } from "lucide-react";
import { useNavigate, useSearchParams } from "react-router";

import { ApiRequestError } from "@shared/api/client";
import { ThemeToggle } from "@/components/theme-toggle";
import { useSession } from "@/auth/SessionProvider";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const redirectTarget = searchParams.get("to") || "/dashboard";

  const { signIn, status, sessionRestoreErrorMessage } = useSession();

  const [identifierValue, setIdentifierValue] = useState("");
  const [passwordValue, setPasswordValue] = useState("");
  const [rememberMe, setRememberMe] = useState(true);
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (status === "authenticated") {
      void navigate(redirectTarget, { replace: true });
    }
  }, [navigate, redirectTarget, status]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setErrorMessage(null);
    setIsSubmitting(true);

    try {
      await signIn({
        identifier: identifierValue.trim(),
        password: passwordValue,
      });
    } catch (error) {
      if (error instanceof ApiRequestError) {
        setErrorMessage(error.message);
      } else if (error instanceof Error) {
        setErrorMessage(error.message);
      } else {
        setErrorMessage("登录失败，请重试。");
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="grid min-h-screen w-full lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-sidebar p-10 text-sidebar-foreground lg:flex">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_top_left,hsl(var(--primary)/0.45),transparent_55%),radial-gradient(circle_at_bottom_right,hsl(var(--chart-2)/0.45),transparent_55%)]" />
        <div className="absolute inset-0 -z-10 opacity-60 [mask-image:radial-gradient(circle_at_center,black,transparent_70%)]">
          <div className="absolute inset-0 bg-[linear-gradient(to_right,hsl(var(--sidebar-border)/0.4)_1px,transparent_1px),linear-gradient(to_bottom,hsl(var(--sidebar-border)/0.4)_1px,transparent_1px)] bg-[size:48px_48px]" />
        </div>

        <div className="flex items-center gap-2 text-base font-semibold">
          <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
            <Sparkles className="size-4" />
          </span>
          My App
        </div>

        <div className="space-y-6">
          <Badge
            variant="secondary"
            className="border border-sidebar-border bg-sidebar-accent text-sidebar-accent-foreground"
          >
            <ShieldCheck className="mr-1.5 size-3" />
            企业级安全登录
          </Badge>
          <h1 className="text-3xl font-semibold leading-tight tracking-tight lg:text-4xl">
            一站式的 <br />
            <span className="text-primary">业务协作空间</span>
          </h1>
          <p className="max-w-md text-sm leading-relaxed text-sidebar-foreground/80">
            统一管理团队、任务与项目进展。登录后即可进入个人工作台,
            实时查看关键指标与最近动态。
          </p>
          <div className="grid grid-cols-3 gap-4 pt-2">
            {[
              { label: "活跃团队", value: "32" },
              { label: "今日任务", value: "186" },
              { label: "SLA 达成", value: "99.9%" },
            ].map((metric) => (
              <div
                key={metric.label}
                className="rounded-lg border border-sidebar-border bg-sidebar/60 p-3 backdrop-blur"
              >
                <div className="text-xs text-sidebar-foreground/70">
                  {metric.label}
                </div>
                <div className="mt-1 text-lg font-semibold text-sidebar-foreground">
                  {metric.value}
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-sidebar-foreground/60">
          © {new Date().getFullYear()} My App · 保留所有权利
        </p>
      </div>

      <div className="relative flex items-center justify-center bg-background p-6 sm:p-10">
        <div className="absolute top-4 right-4">
          <ThemeToggle />
        </div>

        <Card className="w-full max-w-md border-border/60 shadow-xl shadow-primary/5">
          <CardHeader className="space-y-2">
            <CardTitle className="text-2xl tracking-tight">登录</CardTitle>
            <CardDescription>
              输入账号和密码以继续访问你的工作台
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-4"
              onSubmit={(event) => void handleSubmit(event)}
            >
              <div className="space-y-2">
                <Label htmlFor="identifier">用户名 / 邮箱</Label>
                <Input
                  id="identifier"
                  autoComplete="username"
                  placeholder="admin@example.com"
                  value={identifierValue}
                  onChange={(e) => setIdentifierValue(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label htmlFor="password">密码</Label>
                  <button
                    type="button"
                    className="text-xs font-medium text-primary hover:underline"
                    tabIndex={-1}
                  >
                    忘记密码？
                  </button>
                </div>
                <div className="relative">
                  <Input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    className="pr-10"
                    value={passwordValue}
                    onChange={(e) => setPasswordValue(e.target.value)}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    className="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-muted-foreground hover:text-foreground"
                    aria-label={showPassword ? "隐藏密码" : "显示密码"}
                    tabIndex={-1}
                  >
                    {showPassword ? (
                      <EyeOff className="size-4" />
                    ) : (
                      <Eye className="size-4" />
                    )}
                  </button>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Checkbox
                  id="remember-me"
                  checked={rememberMe}
                  onCheckedChange={(value) => setRememberMe(value === true)}
                />
                <Label
                  htmlFor="remember-me"
                  className="text-sm font-normal text-muted-foreground"
                >
                  7 天内保持登录
                </Label>
              </div>

              {errorMessage ? (
                <div className="rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
                  {errorMessage}
                </div>
              ) : null}

              {sessionRestoreErrorMessage ? (
                <div className="rounded-lg border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning-foreground">
                  {sessionRestoreErrorMessage}
                </div>
              ) : null}

              <Button
                className="w-full"
                size="lg"
                disabled={isSubmitting}
                type="submit"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    正在登录…
                  </>
                ) : (
                  "登录"
                )}
              </Button>

              <p className="text-center text-xs text-muted-foreground">
                登录即表示同意我们的{" "}
                <a className="text-primary hover:underline" href="#">
                  服务条款
                </a>{" "}
                与{" "}
                <a className="text-primary hover:underline" href="#">
                  隐私政策
                </a>
              </p>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
