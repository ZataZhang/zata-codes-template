import { Bell, Save, Shield, User } from "lucide-react";

import { SiteHeader } from "@/components/site-header";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";

export function SettingsPage() {
  return (
    <div className="flex flex-col">
      <SiteHeader
        title="设置"
        description="管理个人偏好、通知与安全选项。"
        crumbs={[{ label: "工作台", href: "/dashboard" }, { label: "设置" }]}
        actions={
          <Button size="sm" className="gap-1.5">
            <Save className="size-3.5" />
            保存更改
          </Button>
        }
      />

      <div className="flex flex-1 flex-col gap-6 p-4 lg:p-6">
        <section aria-label="个人资料" className="grid gap-6 lg:grid-cols-2">
          <Card className="border-border/60">
            <CardHeader>
              <div className="flex items-center gap-2">
                <User className="size-4 text-primary" />
                <CardTitle>个人资料</CardTitle>
              </div>
              <CardDescription>更新你的显示名称与联系信息</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="display-name">显示名称</Label>
                <Input id="display-name" defaultValue="王雪" />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">邮箱</Label>
                <Input id="email" type="email" defaultValue="wangxue@example.com" />
              </div>
            </CardContent>
          </Card>

          <Card className="border-border/60">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Bell className="size-4 text-primary" />
                <CardTitle>通知偏好</CardTitle>
              </div>
              <CardDescription>选择你希望接收的消息类型</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {[
                { id: "email-notify", label: "邮件通知", description: "接收每日摘要与重要提醒" },
                { id: "push-notify", label: "浏览器推送", description: "任务截止与提及消息实时推送" },
                { id: "weekly-report", label: "周报", description: "每周一发送团队周报" },
              ].map((item) => (
                <div key={item.id} className="flex items-start justify-between gap-4">
                  <div className="space-y-0.5">
                    <Label htmlFor={item.id} className="text-sm font-medium">
                      {item.label}
                    </Label>
                    <p className="text-xs text-muted-foreground">{item.description}</p>
                  </div>
                  <Switch id={item.id} defaultChecked={item.id !== "push-notify"} />
                </div>
              ))}
            </CardContent>
          </Card>
        </section>

        <Separator />

        <section aria-label="安全设置">
          <Card className="border-border/60">
            <CardHeader>
              <div className="flex items-center gap-2">
                <Shield className="size-4 text-primary" />
                <CardTitle>安全</CardTitle>
              </div>
              <CardDescription>管理密码与登录方式</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="current-password">当前密码</Label>
                <Input id="current-password" type="password" placeholder="••••••••" />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="new-password">新密码</Label>
                  <Input id="new-password" type="password" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirm-password">确认新密码</Label>
                  <Input id="confirm-password" type="password" />
                </div>
              </div>
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
