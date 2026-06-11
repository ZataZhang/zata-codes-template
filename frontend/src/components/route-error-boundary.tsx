import { AlertTriangle, RotateCw, ShieldAlert } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type RouteErrorBoundaryProps = {
  children: ReactNode;
};

type RouteErrorBoundaryState = {
  error: Error | null;
};

export class RouteErrorBoundary extends Component<
  RouteErrorBoundaryProps,
  RouteErrorBoundaryState
> {
  state: RouteErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): RouteErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("RouteErrorBoundary caught an error", error, info);
  }

  reset = (): void => {
    this.setState({ error: null });
  };

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-[70vh] flex-col items-center justify-center px-4">
          <Card className="w-full max-w-md border-border/60">
            <CardHeader className="space-y-2 text-center">
              <div className="mx-auto flex size-12 items-center justify-center rounded-xl bg-destructive/10 text-destructive ring-1 ring-destructive/20">
                <AlertTriangle className="size-6" />
              </div>
              <CardTitle>页面出错了</CardTitle>
              <CardDescription>
                渲染这个页面时出现了意外错误。你可以重试,或回到工作台继续。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <pre className="max-h-40 overflow-auto rounded-md border border-border/60 bg-muted/40 p-3 text-xs text-muted-foreground">
                {this.state.error.message}
              </pre>
              <div className="flex flex-wrap items-center justify-center gap-2">
                <Button onClick={this.reset} className="gap-1.5">
                  <RotateCw className="size-3.5" />
                  重试
                </Button>
                <Button
                  variant="outline"
                  onClick={() => {
                    window.location.assign("/dashboard");
                  }}
                  className="gap-1.5"
                >
                  <ShieldAlert className="size-3.5" />
                  回到工作台
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      );
    }
    return this.props.children;
  }
}
