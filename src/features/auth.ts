/**
 * 账号流程：注册、登录、退出、注销（FR-102–108）。
 * 注册 / 登录即默认同意服务条款；登录响应携带替换后的 context；
 * 退出 / 注销按身份切换表清除本地数据。
 */
import { ref } from 'vue'
import { identityApi } from '@/api'
import { useContextStore } from '@/stores/context'
import { useProgressStore } from '@/stores/progress'
import { useOutboxStore } from '@/stores/outbox'
import { useRecorderStore } from '@/stores/recorder'

export const USERNAME_PATTERN = /^[\w\u4e00-\u9fa5]{3,32}$/
export const PASSWORD_MIN_LENGTH = 8

export function validateUsername(username: string): string | null {
  if (!USERNAME_PATTERN.test(username)) {
    return '用户名需 3–32 个字符，可用字母、数字、下划线或中文'
  }
  return null
}

export function validatePassword(password: string): string | null {
  if (password.length < PASSWORD_MIN_LENGTH) return '密码至少 8 位'
  return null
}

export function useAuth() {
  const contextStore = useContextStore()
  const progressStore = useProgressStore()
  const outbox = useOutboxStore()
  const recorder = useRecorderStore()

  const busy = ref(false)
  const error = ref<unknown>(null)

  async function register(payload: { username: string; password: string }): Promise<boolean> {
    busy.value = true
    error.value = null
    try {
      // 注册不自动登录（后端契约）
      await identityApi.register(payload)
      return true
    } catch (err) {
      error.value = err
      return false
    } finally {
      busy.value = false
    }
  }

  /** 登录：成功后用响应 context 替换并拉取全量（标定 / 进度） */
  async function login(payload: { username: string; password: string }): Promise<boolean> {
    busy.value = true
    error.value = null
    try {
      const res = await identityApi.login(payload)
      // 登录成功：清除上一账号内存状态，替换 context。
      // 后端 login 响应只携带部分身份字段（authenticated/accountId/username），
      // 先合并避免 context 出现空洞，再拉取全量。
      progressStore.onLogout()
      recorder.release()
      contextStore.apply({ ...contextStore.context, ...res.data.context })
      await contextStore.refresh()
      progressStore.onIdentityEstablished()
      return true
    } catch (err) {
      error.value = err
      return false
    } finally {
      busy.value = false
    }
  }

  /** 退出：清除 outbox 与账号内存状态；重新拉 context */
  async function logout(): Promise<void> {
    busy.value = true
    try {
      await identityApi.logout()
    } catch {
      // 会话已失效也按退出处理
    } finally {
      busy.value = false
    }
    recorder.release()
    progressStore.onLogout()
    await contextStore.refresh()
  }

  /** 注销：清空该账号全部数据；全部会话失效；注销后回到首页 */
  async function deleteAccount(password: string): Promise<boolean> {
    busy.value = true
    error.value = null
    try {
      await identityApi.deleteAccount({ password })
      return true
    } catch (err) {
      error.value = err
      return false
    } finally {
      busy.value = false
    }
  }

  function finishAccountDeletion() {
    recorder.release()
    progressStore.onAccountErased()
    void outbox.clear()
    void contextStore.refresh()
  }

  return { busy, error, register, login, logout, deleteAccount, finishAccountDeletion }
}
