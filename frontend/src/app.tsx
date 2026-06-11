import { BrowserRouter } from "react-router";

import { ThemeProvider } from "@/components/theme-provider";
import { SessionProvider } from "@/auth/SessionProvider";
import { MainApp } from "@/main-app";
import { Toaster } from "@/components/ui/sonner";

export function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="my-app-theme">
      <BrowserRouter>
        <SessionProvider>
          <MainApp />
          <Toaster position="top-right" richColors />
        </SessionProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
