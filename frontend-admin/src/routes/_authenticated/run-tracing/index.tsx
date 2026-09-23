import { createFileRoute } from '@tanstack/react-router'
import { RunTracing } from '@/features/run-tracing'

export const Route = createFileRoute('/_authenticated/run-tracing/')({
  component: RunTracing,
})
