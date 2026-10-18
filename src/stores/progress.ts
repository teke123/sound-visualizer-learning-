/**
 * progress 门面（FR-102 / D-24：进度与学习事件统一走登录账号）：
 * - 已登录：服务端 me/progress + outbox 未上传事件乐观合并
 * - 未登录：无进度（公开内容照常可看，事件不记录）
 * 统一给出完成状态与 nextLevelId（D-24，与后端同一规则）。
 */
import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { identityApi, type LevelSummary, type MeProgress } from '@/api'
import { uuid } from '@/utils'
import { useContextStore } from './context'
import { useLevelsStore } from './levels'
import { useOutboxStore } from './outbox'
import { computeNextLevelId, isLevelCompleted } from './completion'

export const useProgressStore = defineStore('progress', () => {
  const contextStore = useContextStore()
  const levelsStore = useLevelsStore()
  const outbox = useOutboxStore()

  /** 服务端进度（me/progress；未登录为 null） */
  const serverProgress = ref<MeProgress | null>(null)
  const serverLoading = ref(false)

  function entryOf(levelId: string): { quizPassed: Set<string>; practiceDone: Set<string> } {
    const entry = optimisticBucket()[levelId] ?? { quizPassed: [], practiceDone: [] }
    return { quizPassed: new Set(entry.quizPassed), practiceDone: new Set(entry.practiceDone) }
  }

  /** 服务端进度 + outbox 未上传事件的乐观合并（避免答题后进度短暂回退） */
  function optimisticBucket(): Record<string, { quizPassed: string[]; practiceDone: string[] }> {
    const merged: Record<string, { quizPassed: string[]; practiceDone: string[] }> = {}
    for (const item of serverProgress.value?.levels ?? []) {
      if (item.completed) {
        const summary = levelsStore.byId.get(item.levelId)
        merged[item.levelId] = {
          quizPassed: summary ? [...summary.completionKeys.quizIds] : [],
          practiceDone: summary ? [...summary.completionKeys.practiceStepIds] : [],
        }
      }
    }
    for (const [levelId, overlay] of outbox.overlay) {
      const entry = merged[levelId] ?? { quizPassed: [], practiceDone: [] }
      merged[levelId] = {
        quizPassed: [...new Set([...entry.quizPassed, ...overlay.quizPassed])],
        practiceDone: [...new Set([...entry.practiceDone, ...overlay.practiceDone])],
      }
    }
    return merged
  }

  /** D-24：本关是否已完成（服务端进度 + outbox 乐观合并，同一规则） */
  function isCompleted(level: LevelSummary): boolean {
    const done = serverProgress.value?.levels.find((item) => item.levelId === level.id)
    if (done) {
      if (done.completed) return true
      // 服务端已有部分进度：与 outbox 乐观合并后判定
      const overlay = outbox.overlay.get(level.id)
      if (!overlay) return false
      return isLevelCompleted(level.completionKeys, new Set(overlay.quizPassed), new Set(overlay.practiceDone))
    }
    // 服务端进度未覆盖该关（新开放）：仅以 outbox 判定
    const overlay = outbox.overlay.get(level.id)
    if (!overlay) return false
    return isLevelCompleted(level.completionKeys, overlay.quizPassed, overlay.practiceDone)
  }

  const completedIds = computed(() => {
    const ids = new Set<string>()
    for (const level of levelsStore.published) {
      if (isCompleted(level)) ids.add(level.id)
    }
    return ids
  })

  /** FR-205：下一关 = 顺序中第一个未完成的关卡（D-24）；全部完成时回落第一关 */
  const nextLevelId = computed<string | null>(() => {
    if (contextStore.isAuthenticated && contextStore.context.nextLevelId) {
      return contextStore.context.nextLevelId
    }
    return computeNextLevelId(levelsStore.published, (level) => completedIds.value.has(level.id))
  })

  /* ----------------------------- 事件记录 ----------------------------- */

  /** 听辨作答：listen_quiz {questionId, choiceIndex}；答对才计入 D-24；未登录不记录 */
  function recordQuizAnswer(payload: {
    levelId: string
    questionId: string
    choiceIndex: number
    correct: boolean
  }) {
    if (!contextStore.isAuthenticated) return
    outbox.enqueue({
      eventId: uuid(),
      levelId: payload.levelId,
      kind: 'listen_quiz',
      detail: { questionId: payload.questionId, choiceIndex: payload.choiceIndex },
    })
  }

  /** 标记练习步骤完成：practice_done {stepId}；未登录不记录 */
  function recordPracticeDone(payload: { levelId: string; stepId: string }) {
    if (!contextStore.isAuthenticated) return
    outbox.enqueue({
      eventId: uuid(),
      levelId: payload.levelId,
      kind: 'practice_done',
      detail: { stepId: payload.stepId },
    })
  }

  /* --------------------------- 服务端进度 --------------------------- */

  async function loadServerProgress(): Promise<void> {
    if (!contextStore.isAuthenticated) return
    serverLoading.value = true
    try {
      const res = await identityApi.progress()
      serverProgress.value = res.data
    } catch {
      // 失败时保留旧值；乐观合并继续用 outbox
    } finally {
      serverLoading.value = false
    }
  }

  /* ----------------------------- 身份切换 ----------------------------- */

  /** 启动 / context 刷新后校验 outbox 归属：与当前账号不符即清理 */
  function syncIdentity() {
    const ctx = contextStore.context
    if (!ctx.authenticated || !ctx.accountId) {
      outbox.bind(null)
      return
    }
    outbox.bind(ctx.accountId)
  }

  /** 登录成功：替换 context 后调用；拉取该账号的服务端进度 */
  function onIdentityEstablished() {
    syncIdentity()
    serverProgress.value = null
    void loadServerProgress()
  }

  /** 退出：清空 outbox 与服务端进度 */
  function onLogout() {
    outbox.clear()
    outbox.bind(null)
    serverProgress.value = null
  }

  /** 注销：清空该账号全部本地数据 */
  function onAccountErased() {
    outbox.clear()
    outbox.bind(null)
    serverProgress.value = null
  }

  // context 变化 → 自动同步身份（启动、登录、退出、注销统一入口）
  watch(
    () => contextStore.context.accountId,
    () => {
      syncIdentity()
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
    entryOf,
    recordQuizAnswer,
    recordPracticeDone,
    loadServerProgress,
    syncIdentity,
    onIdentityEstablished,
    onLogout,
    onAccountErased,
  }
})
