import { createFileRoute } from '@tanstack/react-router'
import { RegistrationSettings } from '@/features/registration'

export const Route = createFileRoute('/_authenticated/registration/')({
  component: RegistrationSettings,
})
