/**
 * levels store：公开关卡摘要、骨架、易混对、availability（带新鲜度校验，NFR-11）。
 * 路由切换与窗口可见时后台重新校验；先用缓存渲染，不阻塞（§6.9）。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { contentApi, type ConfusablePair, type LevelSkeleton, type LevelSummary, type LevelsResponse } from '@/api'

export const useLevelsStore = defineStore('levels', () => {
  const levels = ref<LevelSummary[]>([])
  const skeletons = ref<LevelSkeleton[]>([])
  const confusablePairs = ref<ConfusablePair[]>([])
  const loaded = ref(false)
  const loading = ref(false)
  const error = ref<unknown>(null)
  let lastFetchAt = 0

  const byId = computed(() => {
    const map = new Map<string, LevelSummary>()
    levels.value.forEach((level) => map.set(level.id, level))
    return map
  })

  /** 按公开顺序排列的已发布关（P01/P02/P06/P08 一律使用，过滤骨架） */
  const published = computed(() =>
    [...levels.value].sort((a, b) => a.order - b.order).filter((l) => l.availability !== 'closed'),
  )

  const firstPublishedId = computed(() => published.value[0]?.id ?? null)

  function apply(data: LevelsResponse) {
    levels.value = data.levels
    skeletons.value = data.skeleton
    confusablePairs.value = data.confusablePairs
    loaded.value = true
    error.value = null
    lastFetchAt = Date.now()
  }

  async function refresh(options: { background?: boolean } = {}): Promise<void> {
    if (loading.value) return
    if (options.background && Date.now() - lastFetchAt < 15_000) return
    loading.value = true
    try {
      const res = await contentApi.levels()
      apply(res.data)
    } catch (err) {
      if (!options.background) error.value = err
      // 后台校验失败：保持缓存继续渲染
    } finally {
      loading.value = false
    }
  }

  /** 详情/媒体 404 时立即刷新（LEVEL_NOT_PUBLISHED / 下架同步） */
  function invalidate() {
    lastFetchAt = 0
  }

  function getSummary(levelId: string): LevelSummary | undefined {
    return byId.value.get(levelId)
  }

  return {
    levels,
    skeletons,
    confusablePairs,
    loaded,
    loading,
    error,
    byId,
    published,
    firstPublishedId,
    apply,
    refresh,
    invalidate,
    getSummary,
  }
})
