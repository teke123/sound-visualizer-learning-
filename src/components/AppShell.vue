<script setup lang="ts">
/**
 * AppShell：桌面左侧导航栏（标题下常驻搜索 + 一级页面 + 账号入口）与
 * 手机端顶部细栏 + 底部 5 标签（首页 / 地图 / 发音库 / 档案 / 我的）。
 */
import { useRoute, useRouter } from 'vue-router'
import { useContextStore } from '@/stores/context'
import SearchBox from './SearchBox.vue'

const route = useRoute()
const router = useRouter()
const contextStore = useContextStore()

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
  <div class="app-shell">
    <aside class="side-nav">
      <div class="side-head">
        <RouterLink to="/" class="brand">看得见的声音</RouterLink>
        <SearchBox @search="onSearch" />
      </div>
      <nav class="side-links" aria-label="一级导航">
        <RouterLink
          v-for="link in navLinks"
          :key="link.to"
          :to="link.to"
          class="side-link"
          :class="{ active: isActive(link.to) }"
        >
          {{ link.label }}
        </RouterLink>
      </nav>
      <div class="side-foot">
        <RouterLink to="/account" class="account-entry">
          {{ contextStore.isAuthenticated ? contextStore.context.username : '登录 / 注册' }}
        </RouterLink>
      </div>
    </aside>

    <header class="mobile-bar">
      <RouterLink to="/" class="brand">看得见的声音</RouterLink>
      <RouterLink to="/account" class="account-entry">
        {{ contextStore.isAuthenticated ? contextStore.context.username : '登录 / 注册' }}
      </RouterLink>
    </header>

    <main class="shell-main">
      <slot />
    </main>

    <nav class="bottom-tabs" aria-label="手机导航">
      <RouterLink v-for="tab in bottomTabs" :key="tab.to" :to="tab.to" :class="{ active: isActive(tab.to) }">
        {{ tab.label }}
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped lang="sass">
.app-shell
  min-height: 100vh
  display: flex
  background: #f7f9fa

/* —— 桌面左侧导航栏 —— */
.side-nav
  width: 240px
  flex-shrink: 0
  position: sticky
  top: 0
  height: 100vh
  display: flex
  flex-direction: column
  gap: 18px
  padding: 20px 14px 16px
  box-sizing: border-box
  background: #fff
  border-right: 1px solid #eceff1
  box-shadow: 4px 0 16px rgba(69, 90, 100, 0.04)
  overflow-y: auto
  z-index: 100

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

.side-link
  display: flex
  align-items: center
  padding: 10px 12px
  border-radius: 10px
  text-decoration: none
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

/* —— 手机顶部细栏 —— */
.mobile-bar
  display: none
  align-items: center
  justify-content: space-between
  gap: 12px
  padding: 10px 16px
  background: #fff
  border-bottom: 1px solid #eceff1
  position: sticky
  top: 0
  z-index: 100
  .brand
    padding: 0
    font-size: 17px
  .account-entry
    min-height: 40px

/* —— 主内容区 —— */
.shell-main
  flex: 1
  min-width: 0
  width: 100%
  max-width: 1080px
  margin: 0 auto
  padding: 24px 28px 56px
  box-sizing: border-box

/* —— 手机底部标签 —— */
.bottom-tabs
  display: none
  position: fixed
  bottom: 0
  left: 0
  right: 0
  background: #fff
  border-top: 1px solid #eceff1
  z-index: 100
  a
    flex: 1
    display: flex
    align-items: center
    justify-content: center
    padding: 10px 0 calc(10px + env(safe-area-inset-bottom))
    text-decoration: none
    color: #78909c
    font-size: 13px
    min-height: 52px
    white-space: nowrap
    &.active
      color: #00897b
      font-weight: 700

@media (max-width: 760px)
  .app-shell
    flex-direction: column
  .side-nav
    display: none
  .mobile-bar
    display: flex
  .bottom-tabs
    display: flex
  .shell-main
    padding: 16px 16px 96px
</style>
