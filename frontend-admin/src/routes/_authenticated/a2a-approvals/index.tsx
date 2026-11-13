import { createFileRoute } from '@tanstack/react-router'
import { A2AApprovals } from '@/features/a2a-approvals'

export const Route = createFileRoute('/_authenticated/a2a-approvals/')({
  component: A2AApprovals,
})
