import { apiGet, apiPut } from './client'

/** 注册策略模式。 */
export type RegistrationMode = 'both' | 'oidc_only' | 'closed'

/** 管理端可读取和更新的注册策略。 */
export type RegistrationPolicy = {
  registration_mode: RegistrationMode
  allowed_email_domains: string[]
}

/** 获取当前注册策略。 */
export async function getRegistrationPolicy(): Promise<RegistrationPolicy> {
  return apiGet<RegistrationPolicy>('/admin/settings/registration-policy')
}

/** 保存注册策略。 */
export async function updateRegistrationPolicy(
  policy: RegistrationPolicy
): Promise<RegistrationPolicy> {
  return apiPut<RegistrationPolicy>(
    '/admin/settings/registration-policy',
    policy
  )
}
