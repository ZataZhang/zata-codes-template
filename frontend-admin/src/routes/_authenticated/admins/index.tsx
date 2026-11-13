import { createFileRoute } from '@tanstack/react-router'
import { Admins } from '@/features/admins'

export const Route = createFileRoute('/_authenticated/admins/')({
  component: Admins,
})
