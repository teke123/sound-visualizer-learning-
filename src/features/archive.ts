/** 声音档案：本人存档列表、删除、清空、同关比较（FR-1101–1103） */
import { computed, ref } from 'vue'
import { archiveApi, type ArchiveCompareResponse, type ArchiveRecordingSummary } from '@/api'
import { useContextStore } from '@/stores/context'
import { useLevelsStore } from '@/stores/levels'

export function useArchive() {
  const contextStore = useContextStore()
  const levelsStore = useLevelsStore()

  const items = ref<ArchiveRecordingSummary[]>([])
  const loading = ref(false)
  const error = ref<unknown>(null)
  const nextCursor = ref<string | undefined>(undefined)

  /** 三种态：访客 / 未同意（无档案说明）/ 已同意（档案列表）—— P10 按 context 渲染 */
  const view = computed<'guest' | 'no-consent' | 'archive'>(() => {
    if (!contextStore.isAuthenticated) return 'guest'
    return contextStore.consentGranted ? 'archive' : 'no-consent'
  })

  async function load(): Promise<void> {
    if (view.value !== 'archive') return
    loading.value = true
    error.value = null
    try {
      const res = await archiveApi.listMine()
      items.value = res.data.items
      nextCursor.value = res.data.nextCursor
    } catch (err) {
      error.value = err
    } finally {
      loading.value = false
    }
  }

  async function loadMore(): Promise<void> {
    if (!nextCursor.value) return
    const res = await archiveApi.listMine(undefined, nextCursor.value)
    items.value = [...items.value, ...res.data.items]
    nextCursor.value = res.data.nextCursor
  }

  async function removeOne(recordingId: string): Promise<boolean> {
    try {
      const { detectionApi } = await import('@/api')
      await detectionApi.deleteRecording(recordingId)
      items.value = items.value.filter((item) => item.recordingId !== recordingId)
      return true
    } catch (err) {
      error.value = err
      return false
    }
  }

  async function clearAll(): Promise<boolean> {
    try {
      await archiveApi.clearMine()
      items.value = []
      return true
    } catch (err) {
      error.value = err
      return false
    }
  }

  /** 按关卡分组（同一关至少两条可比较） */
  const byLevel = computed(() => {
    const groups = new Map<string, ArchiveRecordingSummary[]>()
    for (const item of items.value) {
      const list = groups.get(item.levelId) ?? []
      list.push(item)
      groups.set(item.levelId, list)
    }
    return groups
  })

  const compareData = ref<ArchiveCompareResponse | null>(null)
  const compareLoading = ref(false)
  const compareError = ref<unknown>(null)

  async function compare(a: string, b: string): Promise<boolean> {
    compareLoading.value = true
    compareError.value = null
    try {
      const res = await archiveApi.compare(a, b)
      compareData.value = res.data
      return true
    } catch (err) {
      compareError.value = err
      compareData.value = null
      return false
    } finally {
      compareLoading.value = false
    }
  }

  function levelTitle(levelId: string): string {
    return levelsStore.byId.get(levelId)?.title ?? levelId
  }

  return {
    view,
    items,
    loading,
    error,
    byLevel,
    compareData,
    compareLoading,
    compareError,
    load,
    loadMore,
    removeOne,
    clearAll,
    compare,
    levelTitle,
  }
}
