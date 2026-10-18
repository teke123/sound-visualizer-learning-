/**
 * 声音档案：本人存档列表、删除、清空、同关比较（FR-1101–1103）。
 * 状态为模块级单例：ArchivePage 与 ArchiveList 共享同一份数据
 * （此前每个组件各建实例导致列表永远为空）。
 */
import { computed, ref } from 'vue'
import { archiveApi, detectionApi, type ArchiveCompareResponse, type ArchiveRecordingSummary } from '@/api'
import { useContextStore } from '@/stores/context'
import { useLevelsStore } from '@/stores/levels'

/* ------------------------- 全局单例状态 ------------------------- */

const items = ref<ArchiveRecordingSummary[]>([])
const loading = ref(false)
const error = ref<unknown>(null)
const nextCursor = ref<string | undefined>(undefined)
const loadingMore = ref(false)
const loadMoreError = ref<unknown>(null)
const compareData = ref<ArchiveCompareResponse | null>(null)
const compareLoading = ref(false)
const compareError = ref<unknown>(null)

/** 三种态：访客 / 未同意（无档案说明）/ 已同意（档案列表）—— P10 按 context 渲染 */
function viewOf(contextStore: ReturnType<typeof useContextStore>) {
  if (!contextStore.isAuthenticated) return 'guest' as const
  return contextStore.consentGranted ? ('archive' as const) : ('no-consent' as const)
}

export function useArchive() {
  const contextStore = useContextStore()
  const levelsStore = useLevelsStore()

  const view = computed(() => viewOf(contextStore))

  async function load(): Promise<void> {
    if (viewOf(contextStore) !== 'archive') return
    loading.value = true
    error.value = null
    try {
      const res = await archiveApi.listMine()
      items.value = res.data.recordings ?? []
      nextCursor.value = res.data.nextCursor ?? undefined
    } catch (err) {
      error.value = err
    } finally {
      loading.value = false
    }
  }

  async function loadMore(): Promise<void> {
    if (!nextCursor.value || loadingMore.value) return
    loadingMore.value = true
    loadMoreError.value = null
    try {
      const res = await archiveApi.listMine(undefined, nextCursor.value)
      items.value = [...items.value, ...(res.data.recordings ?? [])]
      nextCursor.value = res.data.nextCursor ?? undefined
    } catch (err) {
      loadMoreError.value = err
    } finally {
      loadingMore.value = false
    }
  }

  async function removeOne(recordingId: string): Promise<boolean> {
    try {
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

  /** 是否还有下一页（服务端按 (createdAt, id) 键集分页） */
  const hasMore = computed(() => nextCursor.value != null)

  return {
    view,
    items,
    loading,
    error,
    byLevel,
    hasMore,
    loadingMore,
    loadMoreError,
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
