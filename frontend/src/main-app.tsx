import { Suspense, lazy } from "react";
import { Navigate, Route, Routes } from "react-router";

import { RequireSession } from "@/auth/RequireSession";
import { AppSidebar } from "@/components/app-sidebar";
import { RouteErrorBoundary } from "@/components/route-error-boundary";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

const LoginPage = lazy(async () => ({
  default: (await import("@/pages/login-page")).LoginPage,
}));

const DashboardPage = lazy(async () => ({
  default: (await import("@/pages/dashboard-page")).DashboardPage,
}));

const ProjectsPage = lazy(async () => ({
  default: (await import("@/pages/projects-page")).ProjectsPage,
}));

const TasksPage = lazy(async () => ({
  default: (await import("@/pages/tasks-page")).TasksPage,
}));

const TeamPage = lazy(async () => ({
  default: (await import("@/pages/team-page")).TeamPage,
}));

const SettingsPage = lazy(async () => ({
  default: (await import("@/pages/settings-page")).SettingsPage,
}));

const NotFoundPage = lazy(async () => ({
  default: (await import("@/pages/not-found-page")).NotFoundPage,
}));

function PageLoadingFallback() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center text-sm text-muted-foreground">
      加载中...
    </div>
  );
}

function AppShell() {
  return (
    <SidebarProvider>
      <AppSidebar />
      <SidebarInset>
        <RouteErrorBoundary>
          <Suspense fallback={<PageLoadingFallback />}>
            <Routes>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<DashboardPage />} />
              <Route path="projects" element={<ProjectsPage />} />
              <Route path="tasks" element={<TasksPage />} />
              <Route path="team" element={<TeamPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </RouteErrorBoundary>
      </SidebarInset>
    </SidebarProvider>
  );
}

export function MainApp() {
  return (
    <Routes>
      <Route
        path="login"
        element={
          <Suspense fallback={<PageLoadingFallback />}>
            <LoginPage />
          </Suspense>
        }
      />
      <Route element={<RequireSession />}>
        <Route path="/*" element={<AppShell />} />
      </Route>
    </Routes>
  );
}
