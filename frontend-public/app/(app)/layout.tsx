import Link from "next/link"
import { Button } from "@/components/ui/button"

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-svh flex-col">
      <header className="sticky top-0 z-50 w-full border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto flex h-14 items-center justify-between">
          <Link href="/" className="flex items-center gap-2 font-semibold">
            <span className="size-6 rounded-md bg-primary" />
            Zata
          </Link>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" asChild>
              <Link href="/dashboard">控制台</Link>
            </Button>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/">返回官网</Link>
            </Button>
          </div>
        </div>
      </header>
      <main className="flex-1 container py-8">{children}</main>
    </div>
  )
}
