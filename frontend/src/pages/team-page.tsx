import { Mail, MoreHorizontal, Plus, UsersRound } from "lucide-react";

import { SiteHeader } from "@/components/site-header";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type TeamRole = "管理员" | "产品经理" | "设计师" | "开发工程师";

type TeamMember = {
  id: string;
  name: string;
  initials: string;
  role: TeamRole;
  email: string;
  status: "在线" | "离线" | "忙碌";
};

const teamMembers: TeamMember[] = [
  {
    id: "1",
    name: "王雪",
    initials: "WX",
    role: "产品经理",
    email: "wangxue@example.com",
    status: "在线",
  },
  {
    id: "2",
    name: "李明",
    initials: "LM",
    role: "开发工程师",
    email: "liming@example.com",
    status: "忙碌",
  },
  {
    id: "3",
    name: "陈航",
    initials: "CH",
    role: "开发工程师",
    email: "chenhang@example.com",
    status: "在线",
  },
  {
    id: "4",
    name: "张琳",
    initials: "ZL",
    role: "设计师",
    email: "zhanglin@example.com",
    status: "离线",
  },
  {
    id: "5",
    name: "刘强",
    initials: "LQ",
    role: "管理员",
    email: "liuqiang@example.com",
    status: "在线",
  },
];

const statusTone: Record<TeamMember["status"], string> = {
  在线: "bg-emerald-500",
  忙碌: "bg-amber-500",
  离线: "bg-slate-400",
};

export function TeamPage() {
  return (
    <div className="flex flex-col">
      <SiteHeader
        title="团队"
        description="管理团队成员、角色与联系方式。"
        crumbs={[{ label: "工作台", href: "/dashboard" }, { label: "团队" }]}
        actions={
          <Button size="sm" className="gap-1.5">
            <Plus className="size-3.5" />
            邀请成员
          </Button>
        }
      />

      <div className="flex flex-1 flex-col gap-6 p-4 lg:p-6">
        <section aria-label="成员列表">
          <Card className="border-border/60">
            <CardHeader>
              <div className="flex items-center gap-2">
                <UsersRound className="size-4 text-primary" />
                <CardTitle>团队成员</CardTitle>
              </div>
              <CardDescription>当前工作空间的全部成员</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {teamMembers.map((member) => (
                <div
                  key={member.id}
                  className="flex items-center gap-3 rounded-lg border border-border/60 p-3 transition-colors hover:bg-accent/40"
                >
                  <Avatar className="size-9">
                    <AvatarFallback className="text-xs">{member.initials}</AvatarFallback>
                  </Avatar>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">{member.name}</span>
                      <Badge
                        variant="outline"
                        className="border-border/60 text-[10px] font-normal text-muted-foreground"
                      >
                        {member.role}
                      </Badge>
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                      <Mail className="size-3" />
                      <span className="truncate">{member.email}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
                      <span
                        className={`size-2 rounded-full ${statusTone[member.status]}`}
                        aria-hidden
                      />
                      {member.status}
                    </span>
                    <Button variant="ghost" size="icon-sm" aria-label="更多操作">
                      <MoreHorizontal className="size-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </section>
      </div>
    </div>
  );
}
