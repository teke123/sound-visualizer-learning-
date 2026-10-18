/** identity 模块端点：context、注册登录、注销（docs/decision-map-backend.md） */
import { apiRequest } from '../client'
import type {
  AuthLoginResponse,
  DeletedResponse,
  LoggedOutResponse,
  MeContext,
  MeProgress,
  RegisterResponse,
} from '../generated/types'

export const identityApi = {
  context() {
    return apiRequest<MeContext>('/me/context')
  },
  register(payload: { username: string; password: string }) {
    return apiRequest<RegisterResponse>('/auth/register', { method: 'POST', body: payload })
  },
  /** 成功响应直接携带替换后的 context */
  login(payload: { username: string; password: string }) {
    return apiRequest<AuthLoginResponse>('/auth/login', { method: 'POST', body: payload })
  },
  logout() {
    return apiRequest<LoggedOutResponse>('/auth/logout', { method: 'POST' })
  },
  /** 注销：清空该账号全部数据并失效全部会话 */
  deleteAccount(payload: { password: string }) {
    return apiRequest<DeletedResponse>('/me/account', { method: 'DELETE', body: payload })
  },
  /** 登录账号进度；按 D-24 派生 */
  progress() {
    return apiRequest<MeProgress>('/me/progress')
  },
}
