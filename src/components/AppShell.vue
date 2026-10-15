<script setup lang="ts">
/**
 * AppShell：桌面顶部导航（全部一级页面 + 常驻搜索）与手机底部 5 标签
 * （首页 / 地图 / 检测 / 档案 / 我的；FD-10）；预览页不渲染账号入口。
 */
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useContextStore } from '@/stores/context'
import { useConsent } from '@/features/consent'
import SearchBox from './SearchBox.vue'

const route = useRoute()
const router = useRouter()
const contextStore = useContextStore()
const consent = useConsent()

const isPreview = computed(() => route.path.startsWith('/preview'))

const topLinks = [
  { to: '/', label: '首页' },
  { to: '/map', label: '发音地图' },
  { to: '/principles', label: '发音原理' },
  { to: '/library', label: '发音库' },
  { to: '/test', label: '检测中心' },
  { to: '/archive', label: '声音档案' },
]

const bottomTabs = [
  { to: '/', label: '首页', icon: '🏠' },
  { to: '/map', label: '地图', icon: '🗺️' },
  { to: '/test', label: '检测', icon: '🎤' },
  { to: '/archive', label: '档案', icon: '📁' },
  { to: '/account', label: '我的', icon: '👤' },
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
  <div class="app-shell" :class="{ 'with-bottom-tabs': !isPreview }">
    <header class="top-nav">
      <RouterLink to="/" class="brand">看得见的声音</RouterLink>
      <nav v-if="!isPreview" class="top-links" aria-label="一级导航">
        <RouterLink v-for="link in topLinks" :key="link.to" :to="link.to" :class="{ active: isActive(link.to) }">
          {{ link.label }}
        </RouterLink>
      </nav>
      <div class="top-right">
        <SearchBox v-if="!isPreview" class="top-search" @search="onSearch" />
        <RouterLink v-if="!isPreview" to="/account" class="account-entry">
          {{ contextStore.isAuthenticated ? contextStore.context.username : '登录 / 注册' }}
        </RouterLink>
      </div>
    </header>

    <main class="shell-main">
      <slot />
    </main>

    <nav v-if="!isPreview" class="bottom-tabs" aria-label="手机导航">
      <RouterLink v-for="tab in bottomTabs" :key="tab.to" :to="tab.to" :class="{ active: isActive(tab.to) }">
        <span class="tab-icon" aria-hidden="true">{{ tab.icon }}</span>
        <span class="tab-label">{{ tab.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped lang="sass">
.app-shell
  min-height: 100vh
  display: flex
  flex-direction: column
  background: #f7f9fa

.top-nav
  display: flex
  align-items: center
  gap: 18px
  padding: 10px 20px
  background: #fff
  border-bottom: 1px solid #eceff1
  position: sticky
  top: 0
  z-index: 100

.brand
  font-weight: 800
  font-size: 17px
  color: #00695c
  text-decoration: none
  white-space: nowrap

.top-links
  display: flex
  gap: 4px
  flex-wrap: wrap
  a
    padding: 8px 12px
    border-radius: 8px
    text-decoration: none
    color: #455a64
    font-size: 14px
    min-height: 40px
    display: inline-flex
    align-items: center
    &:hover
      background: #e0f2f1
    &.active
      background: #e0f2f1
      color: #00695c
      font-weight: 700

.top-right
  margin-left: auto
  display: flex
  align-items: center
  gap: 12px
  flex: 1
  justify-content: flex-end
  max-width: 620px

.top-search
  flex: 1
  max-width: 380px

.account-entry
  white-space: nowrap
  padding: 8px 14px
  border-radius: 999px
  background: #e0f2f1
  color: #00695c
  text-decoration: none
  font-size: 14px
  font-weight: 600
  min-height: 40px
  display: inline-flex
  align-items: center

.shell-main
  flex: 1
  width: 100%
  max-width: 1080px
  margin: 0 auto
  padding: 20px 16px 90px
  box-sizing: border-box

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
    flex-direction: column
    align-items: center
    gap: 2px
    padding: 8px 0 calc(8px + env(safe-area-inset-bottom))
    text-decoration: none
    color: #78909c
    font-size: 11px
    min-height: 56px
    &.active
      color: #00897b
      font-weight: 700

.tab-icon
  font-size: 20px

@media (max-width: 760px)
  .top-links
    display: none
  .top-search
    display: none
  .bottom-tabs
    display: flex
  .shell-main
    padding-bottom: 110px
</style>
