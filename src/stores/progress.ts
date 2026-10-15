/**
 * progress 门面（docs/architecture/04 §5、decision-map-frontend「进度与学习事件」）：
 * - 访客：本地访客桶（guest，退出登录后继续使用）
 * - 已登录未同意（含已拒绝、已撤回）：本地账号桶 (accountId, dataEpoch)，退出时清除
 * - 已登录已同意：服务端 me/progress + outbox 未上传事件乐观合并
 * 统一给出完成状态与 nextLevelId（D-24，与后端同一规则）。
 */
import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { identityApi, type LevelSummary, type MeProgress } from '@/api'
import { safeStorage, uuid } from '@/utils'
import { useContextStore } from './context'
import { useLevelsStore } from './levels'
import { useOutboxStore } from './outbox'
import { computeNextLevelId, isLevelCompleted } from './completion'

const GUEST_KEY = 'vv.progress.guest'
const ACCOUNT_KEY_PREFIX = 'vv.progress.acct'

interface LocalLevelEntry {
  quizPassed: string[]
  practiceDone: string[]
}
type LocalBucket = Record<string, LocalLevelEntry>

function emptyEntry(): LocalLevelEntry {
  return { quizPassed: [], practiceDone: [] }
}

function readBucket(key: string): LocalBucket {
  const raw = safeStorage.get(key)
  if (!raw) return {}
  try {
    return JSON.parse(raw) as LocalBucket
  } catch {
    return {}
  }
}

function writeBucket(key: string, bucket: LocalBucket) {
  safeStorage.set(key, JSON.stringify(bucket))
}

function accountKey(accountId: string, dataEpoch: number | undefined): string {
  return `${ACCOUNT_KEY_PREFIX}.${accountId}.${dataEpoch ?? 0}`
}

export type ProgressMode = 'guest' | 'local-account' | 'server'

export const useProgressStore = defineStore('progress', () => {
  const contextStore = useContextStore()
  const levelsStore = useLevelsStore()
  const outbox = useOutboxStore()

  const guestBucket = ref<LocalBucket>(readBucket(GUEST_KEY))
  const accountBucket = ref<LocalBucket>({})
  /** 已同意：服务端进度（me/progress） */
  const serverProgress = ref<MeProgress | null>(null)
  const serverLoading = ref(false)

  const mode = computed<ProgressMode>(() => {
    if (!contextStore.isAuthenticated) return 'guest'
    return contextStore.consentGranted ? 'server' : 'local-account'
  })

  /** 当前生效的本地桶（server 模式下本地桶不再代表进度，仅作 outbox 乐观源） */
  const activeBucket = computed<LocalBucket>(() =>
    mode.value === 'guest' ? guestBucket.value : accountBucket.value,
  )

  function entryOf(levelId: string): { quizPassed: Set<string>; practiceDone: Set<string> } {
    const source =
      mode.value === 'server'
        ? optimisticBucket()
        : activeBucket.value
    const entry = source[levelId] ?? emptyEntry()
    return { quizPassed: new Set(entry.quizPassed), practiceDone: new Set(entry.practiceDone) }
  }

  /** 服务端进度 + outbox 未上传事件的乐观合并（避免答题后进度短暂回退，§6.5） */
  function optimisticBucket(): LocalBucket {
    const merged: LocalBucket = {}
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
      const entry = merged[levelId] ?? emptyEntry()
      merged[levelId] = {
        quizPassed: [...new Set([...entry.quizPassed, ...overlay.quizPassed])],
        practiceDone: [...new Set([...entry.practiceDone, ...overlay.practiceDone])],
      }
    }
    return merged
  }

  /** D-24：本关是否已完成（本地桶 / 服务端+outbox 同一规则） */
  function isCompleted(level: LevelSummary): boolean {
    if (mode.value === 'server') {
      const done = serverProgress.value?.levels.find((item) => item.levelId === level.id)
      if (done) {
        if (done.completed) return true
        // 服务端已有部分进度：与 outbox 乐观合并后判定
        const overlay = outbox.overlay.get(level.id)
        if (!overlay) return false
        const quizPassed = new Set(overlay.quizPassed)
        const practiceDone = new Set(overlay.practiceDone)
        return isLevelCompleted(level.completionKeys, quizPassed, practiceDone)
      }
      // 服务端进度未覆盖该关（新发布）：仅以 outbox 判定
      const overlay = outbox.overlay.get(level.id)
      if (!overlay) return false
      return isLevelCompleted(level.completionKeys, overlay.quizPassed, overlay.practiceDone)
    }
    const entry = activeBucket.value[level.id] ?? emptyEntry()
    return isLevelCompleted(
      level.completionKeys,
      new Set(entry.quizPassed),
      new Set(entry.practiceDone),
    )
  }

  const completedIds = computed(() => {
    const ids = new Set<string>()
    for (const level of levelsStore.published) {
      if (isCompleted(level)) ids.add(level.id)
    }
    return ids
  })

  /** FR-205：访客/未同意按本地进度；已同意优先服务端 context.nextLevelId */
  const nextLevelId = computed<string | null>(() => {
    if (mode.value === 'server' && contextStore.context.nextLevelId) {
      return contextStore.context.nextLevelId
    }
    return computeNextLevelId(levelsStore.published, (level) => completedIds.value.has(level.id))
  })

  /* ----------------------------- 事件记录 ----------------------------- */

  function ensureEntry(bucket: LocalBucket, levelId: string): LocalLevelEntry {
    return (bucket[levelId] ??= emptyEntry())
  }

  /** 听辨作答：listen_quiz {questionId, choiceIndex}；答对才计入 D-24 */
  function recordQuizAnswer(payload: {
    levelId: string
    questionId: string
    choiceIndex: number
    correct: boolean
    contentVersion: number
  }) {
    if (mode.value === 'server') {
      outbox.enqueue({
        eventId: uuid(),
        levelId: payload.levelId,
        contentVersion: payload.contentVersion,
        kind: 'listen_quiz',
        detail: { questionId: payload.questionId, choiceIndex: payload.choiceIndex },
      })
      return
    }
    const bucket = mode.value === 'guest' ? guestBucket.value : accountBucket.value
    const entry = ensureEntry(bucket, payload.levelId)
    if (payload.correct && !entry.quizPassed.includes(payload.questionId)) {
      entry.quizPassed.push(payload.questionId)
    }
    if (mode.value === 'guest') writeBucket(GUEST_KEY, guestBucket.value)
    else if (contextStore.context.accountId) {
      writeBucket(
        accountKey(contextStore.context.accountId, contextStore.context.dataEpoch),
        accountBucket.value,
      )
    }
  }

  /** 标记练习步骤完成：practice_done {stepId} */
  function recordPracticeDone(payload: { levelId: string; stepId: string; contentVersion: number }) {
    if (mode.value === 'server') {
      outbox.enqueue({
        eventId: uuid(),
        levelId: payload.levelId,
        contentVersion: payload.contentVersion,
        kind: 'practice_done',
        detail: { stepId: payload.stepId },
      })
      return
    }
    const bucket = mode.value === 'guest' ? guestBucket.value : accountBucket.value
    const entry = ensureEntry(bucket, payload.levelId)
    if (!entry.practiceDone.includes(payload.stepId)) {
      entry.practiceDone.push(payload.stepId)
    }
    if (mode.value === 'guest') writeBucket(GUEST_KEY, guestBucket.value)
    else if (contextStore.context.accountId) {
      writeBucket(
        accountKey(contextStore.context.accountId, contextStore.context.dataEpoch),
        accountBucket.value,
      )
    }
  }

  /* --------------------------- 服务端进度 --------------------------- */

  async function loadServerProgress(): Promise<void> {
    if (mode.value !== 'server') return
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

  /* ------------------------- 身份切换（§5 表） ------------------------- */

  /** 启动 / context 刷新后校验本地存储：清理与当前账号、dataEpoch 不符的数据 */
  function syncIdentity() {
    const ctx = contextStore.context
    if (!ctx.authenticated || !ctx.accountId) {
      accountBucket.value = {}
      outbox.bind(null)
      return
    }
    outbox.bind({ accountId: ctx.accountId, dataEpoch: ctx.dataEpoch })
    outbox.clearLegacy(ctx.accountId)
    accountBucket.value = readBucket(accountKey(ctx.accountId, ctx.dataEpoch))
  }

  /** 登录成功：替换 context 后调用；切换到该账号的本地桶/服务端进度 */
  function onIdentityEstablished() {
    syncIdentity()
    serverProgress.value = null
    if (mode.value === 'server') void loadServerProgress()
  }

  /** 授予同意：清除账号桶（不导入，D-16），转服务端进度 */
  function onConsentGranted() {
    if (contextStore.context.accountId) {
      safeStorage.remove(accountKey(contextStore.context.accountId, contextStore.context.dataEpoch))
    }
    accountBucket.value = {}
    void loadServerProgress()
  }

  /** 退出：清除账号桶与 outbox，回到访客桶 */
  function onLogout() {
    outbox.clear()
    outbox.bind(null)
    accountBucket.value = {}
    serverProgress.value = null
  }

  /** 撤回 / 注销：清除该账号全部本地数据 */
  function onAccountErased() {
    if (contextStore.context.accountId) {
      safeStorage.removeByPrefix(`${ACCOUNT_KEY_PREFIX}.${contextStore.context.accountId}.`)
    }
    outbox.clear()
    outbox.bind(null)
    accountBucket.value = {}
    serverProgress.value = null
  }

  // context 变化 → 自动同步身份（启动、登录、退出、同意、撤回、注销统一入口）
  watch(
    () => [contextStore.context.accountId, contextStore.context.dataEpoch, mode.value] as const,
    () => {
      syncIdentity()
      if (mode.value === 'server' && !serverProgress.value) void loadServerProgress()
    },
    { immediate: true },
  )

  return {
    mode,
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
    onConsentGranted,
    onLogout,
    onAccountErased,
  }
})
