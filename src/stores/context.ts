/**
 * context store：/api/me/context 的唯一持有者
 * （身份、同意、标定、dataEpoch、pendingTransfer、nextLevelId）
 * 刷新时机：启动、登录、退出、同意变化、注销、标定完成、窗口重新可见、
 * 收到 401 或 403 CONSENT_REQUIRED（docs/architecture/04 §5）。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ApiError, identityApi, type MeContext } from '@/api'

const GUEST_CONTEXT: MeContext = {
  authenticated: false,
  consent: { status: 'none', consentTextVersion: '' },
  currentConsentTextVersion: '',
  calibration: { status: 'none' },
}

export const useContextStore = defineStore('context', () => {
  const context = ref<MeContext>({ ...GUEST_CONTEXT })
  const loaded = ref(false)
  const loading = ref(false)
  /** context 请求失败时以访客态渲染公开内容（§6.1 启动） */
  const degraded = ref(false)

  const isAuthenticated = computed(() => context.value.authenticated === true)
  const consentStatus = computed<MeContext['consent']['status']>(() =>
    context.value.authenticated ? (context.value.consent?.status ?? 'none') : 'none',
  )
  /** 登录且已同意：学习事件与录音走服务端 */
  const consentGranted = computed(
    () => context.value.authenticated && context.value.consent?.status === 'granted',
  )
  /** 未处理同意的账号登录后立即弹出 ConsentDialog（FD-07） */
  const needsConsentDialog = computed(
    () => context.value.authenticated && context.value.consent?.status === 'none',
  )

  /** 音域是否可用于检测（个人，或未到期的会话临时标定；D-20） */
  const calibrationValid = computed(() => {
    const cal = context.value.calibration
    if (!cal || cal.status === 'none') return false
    if (cal.status === 'personal') return true
    if (cal.status === 'session') {
      if (!cal.expiresAt) return true
      return new Date(cal.expiresAt).getTime() > Date.now()
    }
    return false
  })

  function apply(next: MeContext) {
    context.value = next
    degraded.value = false
    loaded.value = true
  }

  async function refresh(): Promise<MeContext> {
    loading.value = true
    try {
      const res = await identityApi.context()
      apply(res.data)
      return res.data
    } catch (error) {
      degraded.value = true
      loaded.value = true
      if (error instanceof ApiError && error.status === 0) {
        // 网络失败：保持现有（或访客）状态渲染公开内容
        return context.value
      }
      throw error
    } finally {
      loading.value = false
    }
  }

  function resetGuest() {
    context.value = { ...GUEST_CONTEXT }
  }

  /** 401 / 403 CONSENT_REQUIRED 时的统一处理入口 */
  function onAuthError(error: ApiError) {
    if (error.code === 'AUTH_REQUIRED' || error.code === 'CONSENT_REQUIRED') {
      void refresh()
    }
  }

  return {
    context,
    loaded,
    loading,
    degraded,
    isAuthenticated,
    consentStatus,
    consentGranted,
    needsConsentDialog,
    calibrationValid,
    apply,
    refresh,
    resetGuest,
    onAuthError,
  }
})
