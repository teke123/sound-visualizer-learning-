/**
 * 发音单元 store（重构占位）
 * ---------------------------------------------------------------------------
 * 意图：大众端单元数据源——从 GET /api/units（已发布只读）拉取并缓存，
 * 为发音库/搜索提供列表与筛选；搜索匹配由后端或 CMS 数据驱动。
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useUnitsStore = defineStore('units', () => {
  const publishedUnits = ref<unknown[]>([])
  const loading = ref(false)
  const error = ref('')

  async function fetchPublished(): Promise<void> {
    // TODO(重构): 拉取已发布单元列表，维护 loading/error
  }
  return { publishedUnits, loading, error, fetchPublished }
})
