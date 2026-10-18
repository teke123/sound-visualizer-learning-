/**
 * context store：/api/me/context 的唯一持有者
 * （身份、标定、nextLevelId）
 * 刷新时机：启动、登录、退出、注销、标定完成、窗口重新可见、收到 401。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { ApiError, identityApi, type MeContext } from '@/api'

const GUEST_CONTEXT: MeContext = {
  authenticated: false,
  calibration: { status: 'none' },
}

export const useContextStore = defineStore('context', () => {
  const context = ref<MeContext>({ ...GUEST_CONTEXT })
  const loaded = ref(false)
  const loading = ref(false)
  /** context 请求失败时以未登录态渲染公开内容（启动兜底） */
  const degraded = ref(false)

  const isAuthenticated = computed(() => context.value.authenticated === true)

  /** 音域是否已标定（个人音域；用于结果对比换算与录音前标定引导，D-20） */
  const calibrationValid = computed(() => context.value.calibration?.status === 'personal')

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
        // 网络失败：保持现有（或未登录）状态渲染公开内容
        return context.value
      }
      throw error
    } finally {
      loading.value = false
    }
  }

  /** 401 时的统一处理入口 */
  function onAuthError(error: ApiError) {
    if (error.code === 'AUTH_REQUIRED') {
      void refresh()
    }
  }

  return {
    context,
    loaded,
    loading,
    degraded,
    isAuthenticated,
    calibrationValid,
    apply,
    refresh,
    onAuthError,
  }
})
