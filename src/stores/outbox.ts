/**
 * learningEvents outbox：同意后学习事件的本地队列、批量上传与重试（docs/architecture/04 §6.5）。
 * localStorage 键含 accountId 与 dataEpoch；联网、可见、路由切换时尝试上传；
 * 被 rejected 的事件丢弃；上传成功后刷新服务端进度。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { learningApi, type LearningEvent } from '@/api'
import { safeStorage } from '@/utils'

const KEY_PREFIX = 'vv.outbox'
/** 单批上传上限（后端契约：单批 ≤50） */
const BATCH_LIMIT = 50

function outboxKey(accountId: string, dataEpoch: number | undefined): string {
  return `${KEY_PREFIX}.${accountId}.${dataEpoch ?? 0}`
}

export const useOutboxStore = defineStore('outbox', () => {
  const events = ref<LearningEvent[]>([])
  /** 当前队列归属（accountId, dataEpoch）；身份变化时整队换血或清空 */
  const owner = ref<{ accountId: string; dataEpoch: number | undefined } | null>(null)
  const flushing = ref(false)
  const lastError = ref<unknown>(null)

  const pendingCount = computed(() => events.value.length)

  /** 未上传事件的乐观合并视图：levelId → {quizPassed, practiceDone} */
  const overlay = computed(() => {
    const map = new Map<string, { quizPassed: Set<string>; practiceDone: Set<string> }>()
    for (const event of events.value) {
      const entry = map.get(event.levelId) ?? { quizPassed: new Set<string>(), practiceDone: new Set<string>() }
      if (event.kind === 'listen_quiz') {
        entry.quizPassed.add(event.detail.questionId)
      } else {
        entry.practiceDone.add(event.detail.stepId)
      }
      map.set(event.levelId, entry)
    }
    return map
  })

  function bind(nextOwner: { accountId: string; dataEpoch: number | undefined } | null) {
    if (owner.value?.accountId === nextOwner?.accountId && owner.value?.dataEpoch === nextOwner?.dataEpoch) return
    owner.value = nextOwner ? { ...nextOwner } : null
    if (!nextOwner) {
      events.value = []
      return
    }
    const raw = safeStorage.get(outboxKey(nextOwner.accountId, nextOwner.dataEpoch))
    if (raw) {
      try {
        events.value = JSON.parse(raw) as LearningEvent[]
      } catch {
        events.value = []
      }
    } else {
      events.value = []
    }
  }

  function persist() {
    if (!owner.value) return
    const key = outboxKey(owner.value.accountId, owner.value.dataEpoch)
    if (events.value.length === 0) safeStorage.remove(key)
    else safeStorage.set(key, JSON.stringify(events.value))
  }

  function enqueue(event: LearningEvent) {
    // eventId 去重：同一事件重试沿用同一 eventId，不重复入队
    if (events.value.some((e) => e.eventId === event.eventId)) return
    events.value.push(event)
    persist()
  }

  /**
   * 批量上传。响应 accepted / duplicates 为计数、rejected 携带 eventId：
   * 200 即视为本批已处理——移除除 rejected 以外的全部事件；
   * 网络或服务失败时保留，等待下一次触发。
   */
  async function flush(): Promise<boolean> {
    if (flushing.value || events.value.length === 0 || !owner.value) return false
    flushing.value = true
    const batch = events.value.slice(0, BATCH_LIMIT)
    try {
      const res = await learningApi.postEvents(batch)
      const rejectedIds = new Set((res.data.rejected ?? []).map((item) => item.eventId))
      const handled = new Set(batch.filter((event) => !rejectedIds.has(event.eventId)).map((event) => event.eventId))
      events.value = events.value.filter((event) => !handled.has(event.eventId))
      persist()
      lastError.value = null
      return true
    } catch (error) {
      lastError.value = error
      return false
    } finally {
      flushing.value = false
    }
  }

  /** dataEpoch 变化 / 撤回 / 注销 / 退出：按调用方语义整队清除 */
  function clear() {
    if (owner.value) safeStorage.remove(outboxKey(owner.value.accountId, owner.value.dataEpoch))
    events.value = []
  }

  /** 清理旧代次（dataEpoch 递增后，旧键不再有效） */
  function clearLegacy(accountId: string) {
    safeStorage.removeByPrefix(`${KEY_PREFIX}.${accountId}.`)
  }

  return { events, owner, flushing, lastError, pendingCount, overlay, bind, enqueue, flush, clear, clearLegacy }
})
