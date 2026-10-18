/** content 模块端点：关卡、搜索、文章（docs/decision-map-backend.md） */
import { apiRequest } from '../client'
import type {
  ArticleCategoriesResponse,
  ArticleDetail,
  ArticlesResponse,
  LevelDetail,
  LevelsResponse,
  SearchResponse,
} from '../generated/types'

export const contentApi = {
  levels() {
    return apiRequest<LevelsResponse>('/levels')
  },
  level(id: string, options: { signal?: AbortSignal } = {}) {
    return apiRequest<LevelDetail>(`/levels/${encodeURIComponent(id)}`, { signal: options.signal })
  },
  search(q: string, options: { signal?: AbortSignal } = {}) {
    return apiRequest<SearchResponse>(`/search?q=${encodeURIComponent(q)}`, { signal: options.signal })
  },
  articleCategories() {
    return apiRequest<ArticleCategoriesResponse>('/article-categories')
  },
  articles(category?: string) {
    const query = category ? `?category=${encodeURIComponent(category)}` : ''
    return apiRequest<ArticlesResponse>(`/articles${query}`)
  },
  article(slug: string, options: { signal?: AbortSignal } = {}) {
    return apiRequest<ArticleDetail>(`/articles/${encodeURIComponent(slug)}`, { signal: options.signal })
  },
}
