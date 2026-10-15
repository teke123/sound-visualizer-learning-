/**
 * 账号流程：注册、登录、退出、撤回、注销（docs/architecture/04 §5 身份切换表 / §6.6–6.7）。
 * 登录响应直接携带替换后的 context；未处理同意立即弹 ConsentDialog；
 * 已有同意账号登录触发转存提示。退出/撤回/注销按表清除本地数据。
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
      // 注册不自动登录、不认领（后端契约）
      await identityApi.register(payload)
      return true
    } catch (err) {
      error.value = err
      return false
    } finally {
      busy.value = false
    }
  }

  /** 登录：成功后用响应 context 替换；未处理同意由调用方弹出；transfer 由调用方展示 */
  async function login(
    payload: { username: string; password: string },
    hooks: {
      onNeedConsent?: () => void
      onTransfer?: (transfer: { status: string; transferredCount: number } | undefined) => void
    } = {},
  ): Promise<boolean> {
    busy.value = true
    error.value = null
    try {
      const res = await identityApi.login(payload)
      // 登录成功：清除上一账号内存状态，替换 context（§5 表）
      progressStore.onLogout()
      recorder.release()
      contextStore.apply(res.data.context)
      progressStore.onIdentityEstablished()
      if (res.data.context.consent.status === 'none') hooks.onNeedConsent?.()
      if (res.data.transfer) hooks.onTransfer?.(res.data.transfer)
      return true
    } catch (err) {
      error.value = err
      return false
    } finally {
      busy.value = false
    }
  }

  /** 退出：清除账号桶、outbox 与全部账号内存状态；重新拉 context；回到访客桶 */
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

  /** 撤回同意：dataEpoch 递增；清除本设备该账号本地数据并刷新 context */
  async function revokeConsent(): Promise<void> {
    busy.value = true
    error.value = null
    try {
      await identityApi.revokeConsent()
    } finally {
      busy.value = false
    }
    progressStore.onAccountErased()
    await contextStore.refresh()
  }

  /** 注销：按撤回范围清理；全部会话失效；注销后回到首页 */
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

  return { busy, error, register, login, logout, revokeConsent, deleteAccount, finishAccountDeletion }
}
