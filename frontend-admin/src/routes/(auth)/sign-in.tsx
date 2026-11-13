import { z } from 'zod'
import { createFileRoute } from '@tanstack/react-router'
import { SignIn } from '@/features/auth/sign-in'

const searchSchema = z.object({
  redirect: z.string().optional(),
  sso_error: z.preprocess(
    (value) =>
      typeof value === 'string' || typeof value === 'number'
        ? value
        : undefined,
    z.union([z.string(), z.number()]).optional()
  ),
})

export const Route = createFileRoute('/(auth)/sign-in')({
  component: SignIn,
  validateSearch: searchSchema,
})
