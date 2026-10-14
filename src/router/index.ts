import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { ElMessage } from 'element-plus'
import { PAGE_CODE_BY_ROUTE_NAME } from '@/data/pages'

/**
 * P01–P11 路由表（口径：docs/srs/02 4.1 页面清单）
 * ---------------------------------------------------------------------------
 * 页号登记处：src/data/pages.ts；每条路由的 meta.pageCode 由
 * PAGE_CODE_BY_ROUTE_NAME 自动写入，页面/验收清单不要再手写页号，
 * 避免「文档一套、代码一套」。
 */
function meta(name: string, title: string, extra: Record<string, unknown> = {}) {
  return { title, pageCode: PAGE_CODE_BY_ROUTE_NAME[name] ?? '', ...extra }
}

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'home', component: () => import('@/views/HomeView.vue'), meta: meta('home', '首页') },
  { path: '/search', name: 'search', component: () => import('@/views/SearchResultsView.vue'), meta: meta('search', '搜索结果') },
  { path: '/map', name: 'map', component: () => import('@/views/PronunciationMap.vue'), meta: meta('map', '发音地图') },
  { path: '/principles', name: 'principles', component: () => import('@/views/PronunciationPrinciples.vue'), meta: meta('principles', '发音原理') },
  { path: '/library', name: 'library', component: () => import('@/views/PronunciationLibrary.vue'), meta: meta('library', '发音库') },
  { path: '/materials', name: 'materials', component: () => import('@/views/ProfessionalMaterials.vue'), meta: meta('materials', '专业资料') },
  { path: '/test', name: 'test', component: () => import('@/views/TestCenterView.vue'), meta: meta('test', '检测中心') },
  // P05 关卡页：/learn 为 30 关总览骨架，/learn/:id 为单关骨架（同一页号）
  { path: '/learn', name: 'levels', component: () => import('@/views/LearningView.vue'), meta: meta('levels', '关卡页') },
  { path: '/learn/:id', name: 'level', component: () => import('@/views/LearningView.vue'), meta: meta('level', '关卡页') },
  { path: '/feedback/:id', name: 'feedback', component: () => import('@/views/FeedbackView.vue'), meta: meta('feedback', '检测结果') },
  { path: '/archive', name: 'archive', component: () => import('@/views/HistoryView.vue'), meta: meta('archive', '声音档案') },
  { path: '/account', name: 'account', component: () => import('@/views/AccountView.vue'), meta: meta('account', '账号') },
  // 后台（CMS）：不属于 P01–P11 页面
  { path: '/admin', name: 'admin', component: () => import('@/views/AdminView.vue'), meta: meta('admin', '后台管理') },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

/**
 * 路由组件是按需下载的。如果前端开发服务器（npm run dev）停了 / 崩了，点击菜单或按钮
 * 会出现「点了没反应」——因为代码下载失败，vue-router 会取消跳转，地址栏都不变。
 * 这类失败必须显性化，否则会被误判成页面 bug（2026-09-29 实测踩过一次）。
 */
router.onError((error, to) => {
  const message = String((error as Error)?.message ?? error)
  console.error('[router] 跳转失败：', to?.fullPath, error)
  if (/dynamically imported module|Importing a module script failed|Failed to fetch/i.test(message)) {
    ElMessage.error('页面代码没加载出来：前端开发服务器可能已停止，请重新运行 npm run dev:all 后刷新页面')
  } else {
    ElMessage.error(`页面打开失败：${message}`)
  }
})

export default router
