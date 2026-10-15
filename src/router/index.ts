/**
 * 路由表与守卫（docs/decision-map-frontend「页面与路由」）：
 * - history 模式、路由级懒加载（首屏只含 P01）
 * - /learn → /library；登录/注册在已登录时转 /account
 * - /preview/* 为管理员预览（meta.bare：不渲染 AppShell 账号入口）
 * - 锚点 #quiz/#practice/#record/#step-{id} 滚动
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useContextStore } from '@/stores/context'

declare module 'vue-router' {
  interface RouteMeta {
    /** 页面编号（P01–P11）；preview 与 NotFound 为空 */
    pageCode?: string
    /** 预览等不套 AppShell 的页面 */
    bare?: boolean
    title?: string
  }
}

const routes: RouteRecordRaw[] = [
  // P01 首页：首屏包（静态导入）
  { path: '/', name: 'home', component: () => import('@/pages/HomePage.vue'), meta: { pageCode: 'P01', title: '首页' } },

  // P02 搜索：q 写入 URL，可刷新、可后退
  { path: '/search', name: 'search', component: () => import('@/pages/SearchPage.vue'), meta: { pageCode: 'P02', title: '搜索' } },

  // P03 发音地图：?compare= 打开比较
  { path: '/map', name: 'map', component: () => import('@/pages/MapPage.vue'), meta: { pageCode: 'P03', title: '发音地图' } },

  // P04 原理子站：目录 + 文章
  { path: '/principles', name: 'principles', component: () => import('@/pages/PrinciplesPage.vue'), meta: { pageCode: 'P04', title: '发音原理' } },
  { path: '/principles/:slug', name: 'article', component: () => import('@/pages/ArticlePage.vue'), meta: { pageCode: 'P04', title: '文章' } },

  // P05 关卡页：/learn 重定向 /library；#record 等锚点由页面处理
  { path: '/learn', redirect: '/library' },
  { path: '/learn/:id', name: 'level', component: () => import('@/pages/LevelPage.vue'), meta: { pageCode: 'P05', title: '关卡' } },

  // P06 发音库
  { path: '/library', name: 'library', component: () => import('@/pages/LibraryPage.vue'), meta: { pageCode: 'P06', title: '发音库' } },

  // P08 检测中心：无 levelId 先选关
  { path: '/test', name: 'test', component: () => import('@/pages/TestPage.vue'), meta: { pageCode: 'P08', title: '检测中心' } },
  { path: '/test/:levelId', name: 'test-task', component: () => import('@/pages/TestPage.vue'), meta: { pageCode: 'P08', title: '录音检测' } },

  // P09 结果
  { path: '/result/:id', name: 'result', component: () => import('@/pages/ResultPage.vue'), meta: { pageCode: 'P09', title: '检测结果' } },

  // P10 声音档案 + 同关比较
  { path: '/archive', name: 'archive', component: () => import('@/pages/ArchivePage.vue'), meta: { pageCode: 'P10', title: '声音档案' } },
  { path: '/archive/compare', name: 'archive-compare', component: () => import('@/pages/ArchiveComparePage.vue'), meta: { pageCode: 'P10', title: '同关比较' } },

  // P11 账号：已登录访问 login/register 转到 /account
  { path: '/account', name: 'account', component: () => import('@/pages/AccountPage.vue'), meta: { pageCode: 'P11', title: '账号' } },
  {
    path: '/account/login',
    name: 'account-login',
    component: () => import('@/pages/AccountLoginPage.vue'),
    meta: { pageCode: 'P11', title: '登录' },
  },
  {
    path: '/account/register',
    name: 'account-register',
    component: () => import('@/pages/AccountRegisterPage.vue'),
    meta: { pageCode: 'P11', title: '注册' },
  },

  // 管理员草稿预览（不计入大众端页面；meta.bare 不渲染 AppShell）
  {
    path: '/preview/levels/:id',
    name: 'preview-level',
    component: () => import('@/pages/PreviewLevelPage.vue'),
    meta: { bare: true, title: '草稿预览' },
  },
  {
    path: '/preview/articles/:slug',
    name: 'preview-article',
    component: () => import('@/pages/PreviewArticlePage.vue'),
    meta: { bare: true, title: '文章草稿预览' },
  },

  // 其余路径统一 NotFound
  { path: '/:pathMatch(.*)*', name: 'not-found', component: () => import('@/pages/NotFoundPage.vue'), meta: { title: '页面不存在' } },
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, behavior: 'smooth', top: 80 }
    return { top: 0 }
  },
})

router.beforeEach((to) => {
  if (to.name === 'account-login' || to.name === 'account-register') {
    const context = useContextStore()
    if (context.isAuthenticated) return { name: 'account', replace: true }
  }
  return true
})

router.afterEach((to) => {
  const title = to.meta.title ? `${to.meta.title} · 看得见的声音` : '看得见的声音 · 普通话发音学习'
  document.title = title
})

export default router
