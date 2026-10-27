/**
 * progress 门面（FR-102）：进度统一走登录账号。
 * - 已登录：服务端 me/progress（关卡完成 = 本关至少提交过一次录音检测）
 * - 未登录：无进度（公开内容照常可看）
 * 统一给出完成状态与 nextLevelId。
 */
import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { identityApi, type LevelSummary } from '@/api'
import { useContextStore } from './context'
import { useLevelsStore } from './levels'
import { computeNextLevelId } from './completion'

export const useProgressStore = defineStore('progress', () => {
  const contextStore = useContextStore()
  const levelsStore = useLevelsStore()

  /** 服务端进度（me/progress；未登录为 null） */
  const serverProgress = ref<{ levels: Array<{ levelId: string; completed: boolean }> } | null>(null)
  const serverLoading = ref(false)

  /** 本关是否已完成（以服务端进度为准） */
  function isCompleted(level: LevelSummary): boolean {
    return serverProgress.value?.levels.some((item) => item.levelId === level.id && item.completed) ?? false
  }

  const completedIds = computed(() => {
    const ids = new Set<string>()
    for (const level of levelsStore.published) {
      if (isCompleted(level)) ids.add(level.id)
    }
    return ids
  })

  /** FR-205：下一关 = 顺序中第一个未完成的关卡；全部完成时回落第一关 */
  const nextLevelId = computed<string | null>(() => {
    if (contextStore.isAuthenticated && contextStore.context.nextLevelId) {
      return contextStore.context.nextLevelId
    }
    return computeNextLevelId(levelsStore.published, (level) => completedIds.value.has(level.id))
  })

  /* --------------------------- 服务端进度 --------------------------- */

  async function loadServerProgress(): Promise<void> {
    if (!contextStore.isAuthenticated) return
    serverLoading.value = true
    try {
      const res = await identityApi.progress()
      serverProgress.value = res.data
    } catch {
      // 失败时保留旧值
    } finally {
      serverLoading.value = false
    }
  }

  /** 登录成功：替换 context 后调用；拉取该账号的服务端进度 */
  function onIdentityEstablished() {
    serverProgress.value = null
    void loadServerProgress()
  }

  /** 退出：清空服务端进度 */
  function onLogout() {
    serverProgress.value = null
  }

  /** 注销：清空该账号全部本地数据 */
  function onAccountErased() {
    serverProgress.value = null
  }

  // context 变化 → 自动加载服务端进度（启动、登录、退出、注销统一入口）
  watch(
    () => contextStore.context.accountId,
    () => {
      if (contextStore.isAuthenticated && !serverProgress.value) void loadServerProgress()
    },
    { immediate: true },
  )

  return {
    serverProgress,
    serverLoading,
    completedIds,
    nextLevelId,
    isCompleted,
    loadServerProgress,
    onIdentityEstablished,
    onLogout,
    onAccountErased,
  }
})
