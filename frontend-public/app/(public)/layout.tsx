import { PublicLayout } from "@/components/layout/public-layout"

export default function Layout({ children }: { children: React.ReactNode }) {
  return <PublicLayout>{children}</PublicLayout>
}
