<script setup lang="ts">
/**
 * AppShell（Quasar QLayout 外壳）：桌面左侧常驻 QDrawer（标题下常驻搜索 + 一级页面 + 账号入口）与
 * 手机端 QHeader 细栏 + QFooter 底部 5 标签（首页 / 地图 / 发音库 / 档案 / 我的）。
 * 断点沿用旧版的 760px：useMediaQuery 控制 QHeader / QFooter / QDrawer 显隐
 * （不用 $q.screen，Quasar 默认断点 1024/768 会造成观感漂移）。
 * view 用 hHh…fFf：大写 H/F 让手机端 QHeader/QFooter 视口固定（对应旧版 sticky / fixed），
 * 大写 L 让桌面 QDrawer 视口固定（position: fixed）——侧栏不随页面滚动，
 * 底部登录入口常驻可见；页面让位仍由 QPageContainer 的 padding 负责，不受大小写影响。
 */
import { useRoute, useRouter } from 'vue-router'
import { useMediaQuery } from '@vueuse/core'
import {
  QLayout,
  QHeader,
  QToolbar,
  QDrawer,
  QPageContainer,
  QFooter,
  QTabs,
  QRouteTab,
  QList,
  QItem,
  QItemSection,
} from 'quasar'
import { useContextStore } from '@/stores/context'
import SearchBox from './SearchBox.vue'

const route = useRoute()
const router = useRouter()
const contextStore = useContextStore()

/** ≤760px 判定为手机端（与下方 CSS media query 断点一致） */
const isMobile = useMediaQuery('(max-width: 760px)')

const navLinks = [
  { to: '/', label: '首页' },
  { to: '/map', label: '发音地图' },
  { to: '/principles', label: '发音原理' },
  { to: '/library', label: '发音库' },
  { to: '/archive', label: '声音档案' },
]

const bottomTabs = [
  { to: '/', label: '首页' },
  { to: '/map', label: '地图' },
  { to: '/library', label: '发音库' },
  { to: '/archive', label: '档案' },
  { to: '/account', label: '我的' },
]

function onSearch(q: string) {
  void router.push({ path: '/search', query: { q } })
}

function isActive(to: string): boolean {
  if (to === '/') return route.path === '/'
  return route.path === to || route.path.startsWith(`${to}/`)
}
</script>

<template>
  <QLayout view="hHh LpR fFf" class="app-shell">
    <!-- 桌面左侧 240px 常驻侧栏（非覆盖式；≤760px 整体不渲染） -->
    <QDrawer v-if="!isMobile" :model-value="true" :width="240" :breakpoint="0">
      <div class="side-nav">
        <div class="side-head">
          <RouterLink to="/" class="brand">看得见的声音</RouterLink>
          <SearchBox @search="onSearch" />
        </div>
        <!-- QList 渲染为 nav（默认 role=list 会顶掉 nav 地标语义，断言传 null 抹掉该属性；QItem 带 to 渲染为链接、不依赖 listitem） -->
        <QList tag="nav" :role="(null as unknown as string)" class="side-links" aria-label="一级导航">
          <QItem
            v-for="link in navLinks"
            :key="link.to"
            :to="link.to"
            class="side-link"
            :class="{ active: isActive(link.to) }"
          >
            <QItemSection>{{ link.label }}</QItemSection>
          </QItem>
        </QList>
        <div class="side-foot">
          <RouterLink to="/account" class="account-entry">
            {{ contextStore.isAuthenticated ? contextStore.context.username : '登录 / 注册' }}
          </RouterLink>
        </div>
      </div>
    </QDrawer>

    <!-- 手机顶部细栏（>760px 不渲染） -->
    <QHeader v-if="isMobile" class="mobile-bar">
      <QToolbar class="mobile-toolbar">
        <RouterLink to="/" class="brand">看得见的声音</RouterLink>
        <RouterLink to="/account" class="account-entry">
          {{ contextStore.isAuthenticated ? contextStore.context.username : '登录 / 注册' }}
        </RouterLink>
      </QToolbar>
    </QHeader>

    <!-- QPageContainer 依据 header/footer/drawer 尺寸自动让位，内部仍是普通容器 div -->
    <QPageContainer>
      <main class="shell-main">
        <slot />
      </main>
    </QPageContainer>

    <!-- 手机底部固定 5 标签（>760px 不渲染） -->
    <QFooter v-if="isMobile" class="bottom-tabs">
      <nav aria-label="手机导航">
        <QTabs align="justify">
          <QRouteTab
            v-for="tab in bottomTabs"
            :key="tab.to"
            :to="tab.to"
            :label="tab.label"
            no-caps
            :ripple="false"
            :class="{ active: isActive(tab.to) }"
          />
        </QTabs>
      </nav>
    </QFooter>
  </QLayout>
</template>

<style scoped lang="sass">
.app-shell
  background: #f7f9fa
  /* QDrawer 会把外部 class 挂到滚动内容层，白底侧栏本体需 :deep 定位 aside */
  > :deep(aside.q-drawer)
    background: #fff
    border-right: 1px solid #eceff1
    box-shadow: 4px 0 16px rgba(69, 90, 100, 0.04)

/* —— 桌面左侧导航栏 —— */
.side-nav
  min-height: 100%
  display: flex
  flex-direction: column
  gap: 18px
  padding: 20px 14px 16px
  box-sizing: border-box

/* 标题与搜索组成一组，置于导航链接上方 */
.side-head
  display: flex
  flex-direction: column
  gap: 14px
  padding-bottom: 16px
  border-bottom: 1px solid #f1f4f5

.brand
  display: block
  padding: 2px 2px 0
  font-weight: 800
  font-size: 18px
  color: #00695c
  text-decoration: none
  white-space: nowrap

.side-links
  display: flex
  flex-direction: column
  gap: 4px

/* QItem 默认 padding 8px 16px / min-height 48px，对齐旧版 10px 12px / 42px */
.side-link
  padding: 10px 12px
  border-radius: 10px
  color: #455a64
  font-size: 14px
  min-height: 42px
  transition: background 0.15s ease, color 0.15s ease
  &:hover
    background: #e0f2f1
  &.active
    background: #e0f2f1
    color: #00695c
    font-weight: 700
  /* 隐藏 Quasar focus-helper 悬停遮罩，保留旧版纯浅青底悬停 + 浏览器默认焦点圈 */
  :deep(.q-focus-helper)
    display: none
  &:focus-visible
    outline: auto

.side-foot
  margin-top: auto
  border-top: 1px solid #f1f4f5
  padding-top: 14px

.account-entry
  display: flex
  align-items: center
  justify-content: center
  white-space: nowrap
  padding: 10px 14px
  border-radius: 999px
  background: #e0f2f1
  color: #00695c
  text-decoration: none
  font-size: 14px
  font-weight: 600
  min-height: 42px
  overflow: hidden
  text-overflow: ellipsis

/* —— 手机顶部细栏（QHeader 默认 primary 底，对齐旧版白底） —— */
.mobile-bar
  background: #fff
  border-bottom: 1px solid #eceff1

/* QToolbar 默认 padding 0 12px，对齐旧版 10px 16px */
.mobile-toolbar
  padding: 10px 16px
  justify-content: space-between
  gap: 12px
  .brand
    padding: 0
    font-size: 17px
  .account-entry
    min-height: 40px

/* —— 主内容区 —— */
.shell-main
  max-width: 1080px
  margin: 0 auto
  padding: 24px 28px 56px
  box-sizing: border-box

/* —— 手机底部标签（QFooter 默认 primary 底，对齐旧版白底） —— */
.bottom-tabs
  background: #fff
  border-top: 1px solid #eceff1
  /* 安全区内衬与旧版逐项 padding 等效，白底延伸覆盖 home indicator */
  padding-bottom: env(safe-area-inset-bottom)
  color: #78909c
  :deep(.q-tab)
    min-height: 52px
    padding: 10px 0
    opacity: 1
    transition: none
    &:focus-visible
      outline: auto
  :deep(.q-tab .q-focus-helper)
    display: none
  :deep(.q-tab .q-tab__content)
    padding: 0
  :deep(.q-tab .q-tab__indicator)
    display: none
  :deep(.q-tab .q-tab__label)
    font-size: 13px
    font-weight: 400
  :deep(.q-tab.active)
    color: #00897b
    .q-tab__label
      font-weight: 700

@media (max-width: 760px)
  .shell-main
    padding: 16px 16px 96px
</style>
