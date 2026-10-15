/**
 * 草稿预览（FD-12 / #21 / docs/architecture/04 §6.8）：
 * token 从 query 读取，所有预览请求与媒体地址带同一 token；
 * 预览容器向 LevelView/ArticleView 传入只读能力；
 * 401/403/404 统一显示「预览已失效，请回后台重新打开」。
 */
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import { contentApi, mediaUrl, type ArticleDetail, type LevelDetail } from '@/api'

export function usePreview() {
  const route = useRoute()
  const token = computed(() => {
    const raw = route.query.token
    return typeof raw === 'string' ? raw : ''
  })
  const invalid = ref(false)
  const notFoundNotice = computed(() => '预览已失效，请回后台重新打开')

  function markError(error: unknown): void {
    const status = (error as { status?: number })?.status
    if (status === 401 || status === 403 || status === 404) invalid.value = true
  }

  const level = ref<LevelDetail | null>(null)
  const article = ref<ArticleDetail | null>(null)
  const loading = ref(false)
  const error = ref<unknown>(null)

  async function loadLevel(id: string): Promise<void> {
    if (!token.value) {
      invalid.value = true
      return
    }
    loading.value = true
    try {
      const res = await contentApi.previewLevel(id, token.value)
      level.value = res.data
    } catch (err) {
      error.value = err
      markError(err)
    } finally {
      loading.value = false
    }
  }

  async function loadArticle(slug: string): Promise<void> {
    if (!token.value) {
      invalid.value = true
      return
    }
    loading.value = true
    try {
      const res = await contentApi.previewArticle(slug, token.value)
      article.value = res.data
    } catch (err) {
      error.value = err
      markError(err)
    } finally {
      loading.value = false
    }
  }

  /** 预览态媒体地址改写 */
  function previewMediaUrl(mediaId: string): string {
    return mediaUrl(mediaId, { previewToken: token.value })
  }

  return { token, invalid, notFoundNotice, level, article, loading, error, loadLevel, loadArticle, previewMediaUrl }
}
