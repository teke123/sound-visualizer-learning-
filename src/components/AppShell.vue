<script setup lang="ts">
/**
 * AppShell · V4（编辑感）
 * 顶部：悬浮胶囊导航（品牌 / 一级导航 / 搜索 / 开始练 / 账号）
 * 底部：深色页脚（站内导航 + 说明 + 超大字号品牌）
 * 原来的底部悬浮导航与主题切换按钮已移除，导航统一放在顶部。
 */
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useContextStore } from '@/stores/context'
import AppIcon from '@/components/ui/AppIcon.vue'

const route = useRoute()
const router = useRouter()
const contextStore = useContextStore()

const navItems = [
  { to: '/', label: '首页' },
  { to: '/map', label: '发音地图' },
  { to: '/library', label: '发音库' },
  { to: '/principles', label: '专业资料' },
  { to: '/archive', label: '声音档案' },
]

const searchTerm = ref('')

const accountLabel = computed(
  () => (contextStore.isAuthenticated && contextStore.context.username) || '登录',
)

/** 首页把产品名放进英雄区大字，导航里不再重复 */
const isHome = computed(() => route.name === 'home')

function isActive(to: string): boolean {
  if (to === '/') return route.path === '/'
  if (to === '/library') return route.path === '/library' || route.path.startsWith('/learn')
  return route.path === to || route.path.startsWith(`${to}/`)
}

function submitSearch() {
  const q = searchTerm.value.trim()
  if (!q) return
  void router.push({ path: '/search', query: { q } })
  searchTerm.value = ''
}
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="topbar-in">
        <RouterLink to="/" class="brand" aria-label="看得见的声音 · 回到首页">
          <span class="brand-mark"><AppIcon name="wave" size="sm" /></span>
          <span v-if="!isHome" class="brand-name">看得见的声音</span>
        </RouterLink>

        <nav class="nav" aria-label="主导航">
          <RouterLink
            v-for="item in navItems"
            :key="item.to"
            :to="item.to"
            class="nav-link"
            :class="{ on: isActive(item.to) }"
            :aria-current="isActive(item.to) ? 'page' : undefined"
          >
            {{ item.label }}
          </RouterLink>
        </nav>

        <div class="nav-right">
          <form class="nav-search" role="search" @submit.prevent="submitSearch">
            <AppIcon name="search" size="sm" />
            <input
              v-model="searchTerm"
              type="search"
              placeholder="搜拼音 / 汉字"
              aria-label="搜索关卡"
              enterkeyhint="search"
            />
          </form>

          <RouterLink to="/account" class="account">{{ accountLabel }}</RouterLink>

          <RouterLink to="/map" class="nav-cta">
            开始练
            <AppIcon name="arrow" size="sm" />
          </RouterLink>
        </div>
      </div>
    </header>

    <main class="shell-main">
      <slot />
    </main>

    <footer class="site-foot">
      <div class="foot-in">
        <div class="foot-brand">
          <span class="brand-mark"><AppIcon name="wave" size="sm" /></span>
          <span class="foot-brand-name">看得见的声音</span>
        </div>

        <nav class="foot-links" aria-label="页脚导航">
          <RouterLink to="/map">发音地图</RouterLink>
          <RouterLink to="/library">发音库</RouterLink>
          <RouterLink to="/principles">专业资料</RouterLink>
          <RouterLink to="/archive">声音档案</RouterLink>
          <RouterLink to="/search">搜索</RouterLink>
          <RouterLink to="/account">账号</RouterLink>
        </nav>
      </div>
    </footer>
  </div>
</template>

<style scoped lang="sass">
.app-shell
  overflow-x: clip
  background: var(--vs-bg)

/* ============================ 顶部导航 ============================ */

.topbar
  position: sticky
  top: 0
  z-index: 60
  padding: 16px 24px 0
  background: linear-gradient(180deg, var(--vs-bg) 60%, rgba(var(--vs-bg-rgb), 0.86))
  -webkit-backdrop-filter: blur(12px)
  backdrop-filter: blur(12px)

.topbar-in
  max-width: 1180px
  margin: 0 auto
  height: 64px
  padding: 0 10px 0 18px
  display: flex
  align-items: center
  gap: 24px
  background: var(--vs-card)
  border: 1px solid var(--vs-line)
  border-radius: 999px
  box-shadow: 0 10px 30px rgba(var(--vs-shadow-rgb), 0.08)

.brand
  display: flex
  align-items: center
  gap: 10px
  flex: none
  text-decoration: none

.brand-mark
  width: 32px
  height: 32px
  border-radius: 10px
  flex: none
  color: var(--vs-on-coffee)
  display: flex
  align-items: center
  justify-content: center
  background: var(--vs-brand)

.brand-name
  font-family: var(--vs-font-display)
  font-size: 21px
  font-weight: 600
  letter-spacing: -0.01em
  color: var(--vs-ink)
  white-space: nowrap

.nav
  display: flex
  align-items: center
  gap: 4px
  flex: 1
  min-width: 0

.nav-link
  position: relative
  padding: 8px 12px
  border-radius: 999px
  font-size: 13.5px
  font-weight: 500
  color: var(--vs-sub)
  text-decoration: none
  white-space: nowrap
  transition: color 0.16s var(--vs-ease), background 0.16s var(--vs-ease)

.nav-link:hover
  color: var(--vs-ink)
  background: var(--vs-soft-2)

.nav-link.on
  color: var(--vs-brand)
  font-weight: 600

.nav-link.on::after
  content: ''
  position: absolute
  left: 12px
  right: 12px
  bottom: 2px
  height: 2px
  border-radius: 2px
  background: var(--vs-brand)

.nav-right
  display: flex
  align-items: center
  gap: 10px
  flex: none

.nav-search
  display: flex
  align-items: center
  gap: 6px
  width: 180px
  height: 40px
  padding: 0 12px
  border-radius: 999px
  background: var(--vs-soft-2)
  color: var(--vs-mute)

.nav-search input
  flex: 1
  min-width: 0
  border: none
  outline: none
  background: transparent
  font-family: inherit
  font-size: 13px
  color: var(--vs-ink)

.nav-search input::placeholder
  color: var(--vs-mute)

.account
  font-size: 13.5px
  font-weight: 500
  color: var(--vs-sub)
  text-decoration: none
  white-space: nowrap
  max-width: 90px
  overflow: hidden
  text-overflow: ellipsis

.account:hover
  color: var(--vs-brand)

.nav-cta
  display: inline-flex
  align-items: center
  gap: 6px
  height: 42px
  padding: 0 18px
  border-radius: 999px
  background: var(--vs-coffee)
  color: var(--vs-on-coffee)
  font-size: 13.5px
  font-weight: 600
  text-decoration: none
  white-space: nowrap
  transition: background 0.16s var(--vs-ease)

.nav-cta:hover
  background: var(--vs-coffee-2)

/* ============================ 内容区 ============================ */

.shell-main
  max-width: 1180px
  margin: 0 auto
  padding: 40px 24px 96px

/* ============================ 页脚 ============================ */

.site-foot
  margin-top: 40px
  background: var(--vs-band)
  color: var(--vs-band-ink)
  overflow: hidden

.foot-in
  max-width: 1180px
  margin: 0 auto
  padding: 40px 24px
  display: flex
  align-items: center
  justify-content: space-between
  gap: 24px
  flex-wrap: wrap

.foot-brand
  display: flex
  align-items: center
  gap: 10px
  .brand-mark
    background: var(--vs-brand-soft)
    color: var(--vs-band)

.foot-brand-name
  font-family: var(--vs-font-display)
  font-size: 16px
  font-weight: 600
  color: var(--vs-band-ink)

.foot-links
  display: flex
  align-items: center
  gap: 24px
  flex-wrap: wrap
  a
    font-size: 13.5px
    color: var(--vs-band-sub)
    text-decoration: none
  a:hover
    color: var(--vs-band-ink)

/* ============================ 响应式 ============================ */

@media (max-width: 1080px)
  .nav-search
    display: none

  .nav-link
    padding: 8px 9px

@media (max-width: 900px)
  .topbar
    padding: 12px 12px 0

  .topbar-in
    height: auto
    flex-wrap: wrap
    padding: 10px 12px
    border-radius: 20px
    gap: 10px

  .brand-name
    font-size: 19px

  .nav
    order: 3
    flex: 1 1 100%
    width: 100%
    overflow-x: auto
    padding-bottom: 2px
    scrollbar-width: none

  .nav::-webkit-scrollbar
    display: none

  .nav-right
    margin-left: auto

  .account
    display: none

  .shell-main
    padding: 24px 16px 64px

  .foot-top
    grid-template-columns: 1fr 1fr
    gap: 28px

  .foot-in
    padding: 40px 20px 24px
</style>
