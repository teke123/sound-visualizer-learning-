/**
 * levels store：公开关卡摘要、骨架、易混对、availability（带新鲜度校验，NFR-11）
 * 与关卡详情缓存（关卡页 / 比较面板 / 结果页专业说明共用，避免重复请求）。
 * 路由切换与窗口可见时后台重新校验；先用缓存渲染，不阻塞（§6.9）。
 */
import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { contentApi, type ConfusablePair, type LevelDetail, type LevelSkeleton, type LevelSummary, type LevelsResponse } from '@/api'

export const useLevelsStore = defineStore('levels', () => {
  const levels = ref<LevelSummary[]>([])
  const skeletons = ref<LevelSkeleton[]>([])
  const confusablePairs = ref<ConfusablePair[]>([])
  const loaded = ref(false)
  const loading = ref(false)
  const error = ref<unknown>(null)
  let lastFetchAt = 0

  /** 关卡详情缓存：命中即可渲染，新鲜度由各调用方的刷新策略保证 */
  const detailCache = new Map<string, LevelDetail>()

  const byId = computed(() => {
    const map = new Map<string, LevelSummary>()
    levels.value.forEach((level) => map.set(level.id, level))
    return map
  })

  /** 按公开顺序排列的已开放关（P01/P02/P05/P06 使用，过滤骨架） */
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

  /* ------------------------ 关卡详情缓存与加载 ------------------------ */

  /** 读详情缓存（不发请求）：关卡页进入时先展示用 */
  function getCachedDetail(levelId: string): LevelDetail | undefined {
    return detailCache.get(levelId)
  }

  /** 写详情缓存：网络刷新成功后由 loadLevelDetail / 调用方写入 */
  function setCachedDetail(levelId: string, detail: LevelDetail): void {
    detailCache.set(levelId, detail)
  }

  /**
   * 关卡详情加载：
   * - 默认命中缓存即返回、不发请求（比较面板两关并拉、结果页专业说明等复用场景）；
   * - force = true 时总是请求网络并刷新缓存（关卡页「先缓存展示随后强制刷新」），
   *   请求失败向上抛出且不破坏已有缓存。
   */
  async function loadLevelDetail(levelId: string, options: { force?: boolean } = {}): Promise<LevelDetail> {
    if (!options.force) {
      const cached = detailCache.get(levelId)
      if (cached) return cached
    }
    const res = await contentApi.level(levelId)
    detailCache.set(levelId, res.data)
    return res.data
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
    getCachedDetail,
    setCachedDetail,
    loadLevelDetail,
  }
})
