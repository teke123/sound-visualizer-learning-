/** 当前会话临时记录：查看、单删、清空并重新开始（FR-110 / FD-09） */
import { ref } from 'vue'
import { detectionApi, sessionApi, type SessionRecordingSummary } from '@/api'
import { useContextStore } from '@/stores/context'

export function useSessionRecords() {
  const contextStore = useContextStore()
  const items = ref<SessionRecordingSummary[]>([])
  const transferableCount = ref(0)
  const loading = ref(false)
  const error = ref<unknown>(null)

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const res = await sessionApi.recordings()
      items.value = res.data.recordings
      transferableCount.value = res.data.transferableCount
    } catch (err) {
      error.value = err
    } finally {
      loading.value = false
    }
  }

  async function removeOne(recordingId: string): Promise<boolean> {
    try {
      await detectionApi.deleteRecording(recordingId)
      items.value = items.value.filter((item) => item.recordingId !== recordingId)
      transferableCount.value = Math.max(0, transferableCount.value - 1)
      return true
    } catch (err) {
      error.value = err
      return false
    }
  }

  /** 清空并重新开始会话：访客轮换 sid；已登录者保留登录，不触及已存档 */
  async function resetSession(): Promise<boolean> {
    try {
      await sessionApi.reset()
      items.value = []
      transferableCount.value = 0
      await contextStore.refresh()
      return true
    } catch (err) {
      error.value = err
      return false
    }
  }

  return { items, transferableCount, loading, error, load, removeOne, resetSession }
}
