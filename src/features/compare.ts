/**
 * 关卡比较（FD-05）：单一 ComparePanel；P03/P05 易混入口直达（?compare=L13,L14 可分享），
 * P06 任选两关；易混对作快捷项。后退即关闭（打开比较写入 URL query 产生历史记录）。
 * 只负责比较面板的 URL 与面板状态；关卡详情经 levels store 缓存加载。
 */
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import type { LevelDetail } from '@/api'
import { useLevelsStore } from '@/stores/levels'

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
    // 写入 URL query 产生历史记录 → 后退即关闭
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
        const [a, b] = await Promise.all([
          levelsStore.loadLevelDetail(ids[0]),
          levelsStore.loadLevelDetail(ids[1]),
        ])
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

  return {
    pair,
    detailA,
    detailB,
    loading,
    error,
    open,
    close,
  }
}
