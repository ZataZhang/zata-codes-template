import { ArrowLeft, Compass, Home } from "lucide-react";
import { useNavigate } from "react-router";

import { Button } from "@/components/ui/button";

export function NotFoundPage() {
  const navigate = useNavigate();

  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center px-4 text-center">
      <div className="relative">
        <div className="absolute inset-0 -z-10 mx-auto size-40 rounded-full bg-primary/10 blur-2xl" />
        <div className="flex size-20 items-center justify-center rounded-2xl bg-primary/10 text-primary ring-1 ring-primary/20">
          <Compass className="size-10" />
        </div>
      </div>
      <div className="mt-6 space-y-2">
        <p className="text-sm font-medium text-primary">404</p>
        <h1 className="text-2xl font-semibold tracking-tight">页面走丢了</h1>
        <p className="max-w-md text-sm text-muted-foreground">
          你访问的页面不存在、被移动,或者你输入的链接有误。回到工作台继续你的工作吧。
        </p>
      </div>
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        <Button onClick={() => void navigate(-1)} variant="outline" className="gap-1.5">
          <ArrowLeft className="size-3.5" />
          返回上一页
        </Button>
        <Button onClick={() => void navigate("/dashboard")} className="gap-1.5">
          <Home className="size-3.5" />
          回到工作台
        </Button>
      </div>
    </div>
  );
}
