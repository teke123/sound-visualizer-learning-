/**
 * 关卡比较（FD-05）：单一 ComparePanel；P03/P05 易混入口直达（?compare=L13,L14 可分享），
 * P06 任选两关；易混对作快捷项。后退即关闭（打开比较写入 URL query 产生历史记录）。
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { contentApi, type LevelDetail } from '@/api'
import { useLevelsStore } from '@/stores/levels'

/** 关卡详情缓存（比较面板 / 关卡页共用，避免重复请求） */
const detailCache = new Map<string, LevelDetail>()
export const levelDetailCache = {
  get(id: string) {
    return detailCache.get(id)
  },
  set(id: string, detail: LevelDetail) {
    detailCache.set(id, detail)
  },
  clear(id?: string) {
    if (id) detailCache.delete(id)
    else detailCache.clear()
  },
}

export async function loadLevelDetail(id: string): Promise<LevelDetail> {
  const cached = detailCache.get(id)
  if (cached) return cached
  const res = await contentApi.level(id)
  detailCache.set(id, res.data)
  return res.data
}

export function useComparePanel() {
  const route = useRoute()
  const router = useRouter()
  const levelsStore = useLevelsStore()

  const detailA = ref<LevelDetail | null>(null)
  const detailB = ref<LevelDetail | null>(null)
  const loading = ref(false)
  const error = ref<unknown>(null)

  const pair = computed<[string, string] | null>(() => {
    const raw = route.query.compare
    if (typeof raw !== 'string' || !raw) return null
    const [a, b] = raw.split(',')
    if (!a || !b || a === b) return null
    return [a, b]
  })

  async function open(aId: string, bId: string) {
    // 写入 URL query 产生历史记录 → 后退即关闭（decision-map-frontend 路由表）
    await router.push({ query: { ...route.query, compare: `${aId},${bId}` } })
  }

  async function close() {
    if (!pair.value) return
    if (window.history.state?.back != null) {
      await router.back()
    } else {
      const query = { ...route.query }
      delete query.compare
      await router.replace({ query })
    }
  }

  watch(
    pair,
    async (ids) => {
      if (!ids) {
        detailA.value = null
        detailB.value = null
        return
      }
      loading.value = true
      error.value = null
      try {
        const [a, b] = await Promise.all([loadLevelDetail(ids[0]), loadLevelDetail(ids[1])])
        detailA.value = a
        detailB.value = b
      } catch (err) {
        error.value = err
        detailA.value = null
        detailB.value = null
      } finally {
        loading.value = false
      }
    },
    { immediate: true },
  )

  /** P06 任选两关的选择状态 */
  const selected = ref<string[]>([])
  function toggleSelect(levelId: string) {
    if (selected.value.includes(levelId)) {
      selected.value = selected.value.filter((id) => id !== levelId)
    } else {
      selected.value = [...selected.value.slice(-1), levelId]
    }
  }
  const canCompare = computed(() => selected.value.length === 2)

  /** 易混对快捷项（仅双方已开放） */
  const quickPairs = computed(() => levelsStore.confusablePairs)

  return {
    pair,
    detailA,
    detailB,
    loading,
    error,
    open,
    close,
    selected,
    toggleSelect,
    canCompare,
    quickPairs,
  }
}
