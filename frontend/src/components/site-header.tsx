
import { Bell, Search } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";

type Crumb = { label: string; href?: string };

type SiteHeaderProps = {
  title?: string;
  description?: string;
  crumbs?: Crumb[];
  actions?: React.ReactNode;
};

export function SiteHeader({
  title = "概览",
  description,
  crumbs,
  actions,
}: SiteHeaderProps) {
  return (
    <header className="flex h-auto shrink-0 flex-col gap-3 border-b bg-background/80 px-4 py-3 backdrop-blur-md transition-[width,height] ease-linear lg:px-6 lg:py-4">
      <div className="flex w-full items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <SidebarTrigger className="-ml-1" />
          <Separator
            orientation="vertical"
            className="mx-1 data-[orientation=vertical]:h-4"
          />
          <Breadcrumb>
            <BreadcrumbList>
              {(crumbs ?? [{ label: "工作台" }, { label: title }]).map(
                (crumb, index, array) => {
                  const isLast = index === array.length - 1;
                  return (
                    <BreadcrumbItem key={`${crumb.label}-${index}`}>
                      {isLast || !crumb.href ? (
                        <BreadcrumbPage>{crumb.label}</BreadcrumbPage>
                      ) : (
                        <BreadcrumbLink href={crumb.href}>
                          {crumb.label}
                        </BreadcrumbLink>
                      )}
                      {!isLast ? <BreadcrumbSeparator /> : null}
                    </BreadcrumbItem>
                  );
                },
              )}
            </BreadcrumbList>
          </Breadcrumb>
        </div>

        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="sm"
            className="hidden h-8 gap-2 text-muted-foreground md:inline-flex"
            aria-label="搜索（占位）"
          >
            <Search className="size-3.5" />
            <span>搜索…</span>
            <kbd className="pointer-events-none ml-3 hidden rounded border border-border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:inline-block">
              ⌘K
            </kbd>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            aria-label="通知（占位）"
            className="relative"
          >
            <Bell className="size-4" />
            <span className="absolute top-1.5 right-1.5 size-1.5 rounded-full bg-primary" />
          </Button>
          <ThemeToggle />
        </div>
      </div>

      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold tracking-tight lg:text-2xl">
            {title}
          </h1>
          {description ? (
            <p className="text-sm text-muted-foreground">{description}</p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        ) : null}
      </div>
    </header>
  );
}
