/**
 * 统一文案位取用
 * ---------------------------------------------------------------------------
 * 口径来源：src/data/pages.ts ——「页面只消费 PAGE_COPY[code]，
 * 不要在页面里散写提示语」。
 *
 * 用法：
 *   const { copy, code } = usePageCopy('P06')
 *   <PageState v-if="loading" state="loading" :copy="copy" />
 *
 * 页面里**不要**再出现「加载中 / 暂无数据 / 加载失败」这类字面量：
 * 文案统一在 pages.ts 定稿（口径 = docs/srs），改文案只改那一处。
 */
import { computed, type ComputedRef } from 'vue'
import { getPage, type PageCopySlots, type PageDef } from '@/data/pages'

export interface UsePageCopy {
  /** 页号 P01–P11（后台为 ADMIN） */
  code: string
  /** 页面登记项（标题、图标、路由等） */
  page: PageDef
  /** 六个文案位：subtitle / loading / empty / error / unopened / cta */
  copy: PageCopySlots
  /** 页面标题 */
  title: ComputedRef<string>
}

export function usePageCopy(code: string): UsePageCopy {
  const page = getPage(code)
  if (!page) {
    // 宁可在开发期直接报错，也不要让页面各写一套文案绕开登记处
    throw new Error(`[usePageCopy] 未登记的页号：${code}；请先在 src/data/pages.ts 登记`)
  }
  return {
    code,
    page,
    copy: page.copy,
    title: computed(() => page.title),
  }
}
