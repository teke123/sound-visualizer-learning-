/** identity 模块端点：context、注册登录、同意、注销（docs/decision-map-backend.md） */
import { apiRequest } from '../client'
import type {
  AuthLoginResponse,
  ConsentPostResponse,
  ConsentStateResponse,
  MeContext,
  MeProgress,
  TransferResult,
} from '../generated/types'

export const identityApi = {
  context() {
    return apiRequest<MeContext>('/me/context')
  },
  register(payload: { username: string; password: string }) {
    return apiRequest<{ created: boolean }>('/auth/register', { method: 'POST', body: payload })
  },
  /** 成功响应直接携带替换后的 context；已有同意时附 transfer */
  login(payload: { username: string; password: string }) {
    return apiRequest<AuthLoginResponse>('/auth/login', { method: 'POST', body: payload })
  },
  logout() {
    return apiRequest<{ loggedOut: boolean }>('/auth/logout', { method: 'POST' })
  },

  consentState() {
    return apiRequest<ConsentStateResponse>('/me/consent')
  },
  /** 版本须等于现行版本；已是 granted 时再次 granted 只重跑转存（转存重试入口） */
  postConsent(payload: { decision: 'granted' | 'rejected'; consentTextVersion: string }) {
    return apiRequest<ConsentPostResponse>('/me/consent', { method: 'POST', body: payload })
  },
  /** 撤回：dataEpoch 递增，按 D-17 删除；重复调用幂等 */
  revokeConsent() {
    return apiRequest<{ consent: { status: 'revoked' } ; transfer?: TransferResult }>('/me/consent', {
      method: 'DELETE',
    })
  },
  /** 注销：按撤回范围清理并失效全部会话 */
  deleteAccount(payload: { password: string }) {
    return apiRequest<{ deleted: boolean }>('/me/account', { method: 'DELETE', body: payload })
  },

  /** 登录且同意；按 D-24 派生 */
  progress() {
    return apiRequest<MeProgress>('/me/progress')
  },
}
