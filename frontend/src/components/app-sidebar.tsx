import * as React from "react";
import {
  Box,
  LayoutDashboard,
  Settings,
  Sparkles,
  UsersRound,
  type LucideIcon,
} from "lucide-react";

import { NavMain } from "@/components/nav-main";
import { NavUser } from "@/components/nav-user";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar";

type NavItem = { title: string; url: string; icon: LucideIcon };
type NavGroup = { label: string; items: NavItem[] };

const navGroups: NavGroup[] = [
  {
    label: "工作台",
    items: [
      { title: "概览", url: "/dashboard", icon: LayoutDashboard },
      { title: "热门项目", url: "/projects", icon: Sparkles },
      { title: "任务", url: "/tasks", icon: Box },
    ],
  },
  {
    label: "管理",
    items: [
      { title: "团队", url: "/team", icon: UsersRound },
      { title: "设置", url: "/settings", icon: Settings },
    ],
  },
];

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  return (
    <Sidebar collapsible="offcanvas" {...props}>
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              asChild
              className="data-[slot=sidebar-menu-button]:p-1.5!"
            >
              <a href="/dashboard">
                <span className="flex size-5 items-center justify-center rounded-md bg-primary text-primary-foreground">
                  <Sparkles className="size-3.5" />
                </span>
                <span className="text-base font-semibold tracking-tight">
                  My App
                </span>
              </a>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        {navGroups.map((group) => (
          <NavMain key={group.label} label={group.label} items={group.items} />
        ))}
      </SidebarContent>
      <SidebarFooter>
        <NavUser />
      </SidebarFooter>
    </Sidebar>
  );
}
