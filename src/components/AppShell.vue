<script setup lang="ts">
/**
 * AppShell · V5（清透蓝 / 右侧竖导航）
 * 右侧固定竖导航（可收起）+ 内容滚动区 + 页脚；窄屏改为顶部品牌条 + 抽屉式导航。
 */
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import AppIcon from '@/components/ui/AppIcon.vue'

const route = useRoute()

interface RailItem {
  to: string
  label: string
  desc: string
  icon: string
}

const studyItems: RailItem[] = [
  { to: '/', label: '首页', desc: '面板与快捷入口', icon: 'home' },
  { to: '/map', label: '发音地图', desc: '单韵母 / 声母 / 拼读', icon: 'map' },
  { to: '/library', label: '发音库', desc: '按声母 / 韵母分册', icon: 'book' },
]

const toolItems: RailItem[] = [
  { to: '/principles', label: '专业资料', desc: '发音原理与依据', icon: 'doc' },
  { to: '/archive', label: '声音档案', desc: '练过的关与录音', icon: 'folder' },
  { to: '/account', label: '账号', desc: '资料、音域与数据', icon: 'user' },
]

const railHidden = ref(false)
const mobileOpen = ref(false)

function isActive(to: string): boolean {
  if (to === '/') return route.path === '/'
  if (to === '/library') return route.path === '/library' || route.path.startsWith('/learn')
  if (to === '/archive') return route.path === '/archive' || route.path.startsWith('/result')
  return route.path === to || route.path.startsWith(`${to}/`)
}

function isNarrow(): boolean {
  return typeof window !== 'undefined' && window.innerWidth <= 900
}

function toggleRail() {
  if (isNarrow()) {
    mobileOpen.value = !mobileOpen.value
    return
  }
  railHidden.value = !railHidden.value
}

function closeMobile() {
  mobileOpen.value = false
}

watch(
  () => route.fullPath,
  () => {
    closeMobile()
  },
)

function onResize() {
  if (!isNarrow()) mobileOpen.value = false
}

onMounted(() => {
  window.addEventListener('resize', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
})
</script>

<template>
  <div
    class="app-shell"
    :class="{ 'rail-hidden': railHidden, 'mobile-open': mobileOpen }"
  >
    <aside class="rail" aria-label="主导航">
      <RouterLink to="/" class="rail-brand" title="回到首页">
        <span class="mark"><AppIcon name="wave" size="sm" /></span>
        <div>
          <b>看得见的声音</b>
          <span>普通话发音学习</span>
        </div>
      </RouterLink>

      <p class="rail-sec">学习</p>
      <RouterLink
        v-for="item in studyItems"
        :key="item.to"
        :to="item.to"
        class="ritem"
        :class="{ on: isActive(item.to) }"
        @click="closeMobile"
      >
        <span class="ic"><AppIcon :name="item.icon" size="sm" /></span>
        <span class="tx"><b>{{ item.label }}</b><small>{{ item.desc }}</small></span>
      </RouterLink>

      <p class="rail-sec">家长与检测</p>
      <RouterLink
        v-for="item in toolItems"
        :key="item.to"
        :to="item.to"
        class="ritem"
        :class="{ on: isActive(item.to) }"
        @click="closeMobile"
      >
        <span class="ic"><AppIcon :name="item.icon" size="sm" /></span>
        <span class="tx"><b>{{ item.label }}</b><small>{{ item.desc }}</small></span>
      </RouterLink>
    </aside>

    <button
      type="button"
      class="rail-toggle"
      :aria-expanded="isNarrow() ? mobileOpen : !railHidden"
      :aria-label="isNarrow() ? '打开导航' : railHidden ? '展开导航' : '收起导航'"
      :title="isNarrow() ? '打开导航' : railHidden ? '展开导航' : '收起导航'"
      @click="toggleRail"
    >
      <AppIcon name="chev" size="sm" />
    </button>

    <div class="rail-scrim" aria-hidden="true" @click="closeMobile" />

    <div class="pane">
      <header class="app-header">
        <RouterLink to="/" class="logo" title="回到首页">
          <span class="mark"><AppIcon name="wave" size="sm" /></span>
          看得见的声音
        </RouterLink>
        <button type="button" class="btn-quiet" @click="toggleRail">
          <span>更多</span>
          <AppIcon name="chev" size="sm" />
        </button>
      </header>

      <main class="pane-main">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped lang="sass">
.app-shell
  min-height: 100%

/* ============================ 右侧竖导航 ============================ */

.rail
  position: fixed
  top: 16px
  right: 16px
  bottom: 16px
  width: 236px
  z-index: 58
  display: flex
  flex-direction: column
  background: linear-gradient(178deg, #2596da 0%, #1a79c0 46%, #0e528c 100%)
  color: rgba(255, 255, 255, 0.92)
  padding: 16px 12px 12px
  border-radius: 22px
  border: 1px solid rgba(255, 255, 255, 0.22)
  overflow-y: auto
  overscroll-behavior: contain
  box-shadow: 0 28px 64px rgba(10, 45, 80, 0.26), 0 6px 18px rgba(10, 45, 80, 0.12)
  transition: transform 0.42s var(--vs-ease), opacity 0.3s var(--vs-ease)

.rail::-webkit-scrollbar
  width: 0

.rail::before
  content: ''
  position: absolute
  left: 0
  right: 0
  top: 0
  height: 240px
  pointer-events: none
  background: radial-gradient(120% 100% at 82% 0%, rgba(255, 255, 255, 0.2), rgba(255, 255, 255, 0) 68%)

.rail > *
  position: relative

.rail-hidden .rail
  transform: translateX(calc(100% + 30px))
  opacity: 0
  pointer-events: none

.rail-brand
  display: flex
  align-items: center
  gap: 10px
  padding: 2px 8px 14px
  border-bottom: 1px solid rgba(255, 255, 255, 0.2)
  color: #fff
  text-decoration: none

.rail-brand .mark
  width: 36px
  height: 36px
  border-radius: 12px
  flex: none
  color: #fff
  display: flex
  align-items: center
  justify-content: center
  background: linear-gradient(135deg, #52b0ec, #22a7d8)
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.34)

.rail-brand b
  display: block
  font-size: 14.5px
  font-weight: 800
  letter-spacing: 0.4px
  line-height: 1.35

.rail-brand span
  display: block
  font-size: 10.5px
  color: rgba(255, 255, 255, 0.88)
  margin-top: 1px

.rail-sec
  margin: 16px 9px 6px
  font-size: 10.5px
  font-weight: 800
  letter-spacing: 1.6px
  color: rgba(255, 255, 255, 0.7)

.ritem
  display: flex
  align-items: center
  gap: 10px
  width: 100%
  border: none
  background: transparent
  cursor: pointer
  font-family: inherit
  text-align: left
  color: #eaf6ff
  padding: 7px 9px
  border-radius: 12px
  margin-bottom: 2px
  text-decoration: none
  transition: background 0.2s var(--vs-ease), color 0.2s var(--vs-ease), box-shadow 0.2s var(--vs-ease)

.ritem .ic
  flex: none
  width: 30px
  height: 30px
  border-radius: 9px
  display: flex
  align-items: center
  justify-content: center
  background: rgba(255, 255, 255, 0.17)
  color: #eaf6ff
  transition: background 0.2s var(--vs-ease), color 0.2s var(--vs-ease)

.ritem .tx
  min-width: 0

.ritem b
  display: block
  font-size: 13px
  font-weight: 600
  color: #fff

.ritem small
  display: block
  font-size: 10.5px
  color: rgba(255, 255, 255, 0.88)
  margin-top: 1px
  white-space: nowrap
  overflow: hidden
  text-overflow: ellipsis

.ritem:hover
  background: rgba(255, 255, 255, 0.15)

.ritem:hover .ic
  background: rgba(255, 255, 255, 0.26)
  color: #fff

.ritem.on
  background: linear-gradient(135deg, #ffffff 0%, #eaf5fe 100%)
  box-shadow: 0 10px 24px rgba(8, 58, 98, 0.3)

.ritem.on b
  color: #0f63a8

.ritem.on small
  color: #4a87b2

.ritem.on .ic
  background: rgba(30, 147, 232, 0.12)
  color: #1573bc

/* 导航收起开关：贴在导航左侧中缝 */
.rail-toggle
  position: fixed
  top: 50%
  right: 254px
  transform: translateY(-50%)
  z-index: 59
  width: 30px
  height: 70px
  padding: 0
  border: 1px solid rgba(20, 38, 57, 0.08)
  cursor: pointer
  border-radius: 16px
  display: flex
  align-items: center
  justify-content: center
  background: rgba(255, 255, 255, 0.94)
  color: #1467a8
  box-shadow: 0 10px 26px rgba(10, 45, 80, 0.16), 0 2px 8px rgba(10, 45, 80, 0.08)
  transition: right 0.42s var(--vs-ease), opacity 0.25s var(--vs-ease)

.rail-toggle .vs-ico
  transform: rotate(-90deg)
  transition: transform 0.42s var(--vs-ease)

.rail-hidden .rail-toggle
  right: 10px
  opacity: 0.6

.rail-hidden .rail-toggle .vs-ico
  transform: rotate(90deg)

.rail-scrim
  display: none

/* ============================ 内容区 ============================ */

.pane
  margin-right: 288px
  transition: margin-right 0.42s var(--vs-ease)

.rail-hidden .pane
  margin-right: 0

.pane-main
  max-width: 1040px
  margin: 0 auto
  padding: 24px 32px 40px

.app-header
  display: none

/* ============================ 窄屏 ============================ */

@media (max-width: 1280px)
  .pane-main
    padding-left: 24px
    padding-right: 24px

@media (max-width: 900px)
  .rail
    top: 10px
    right: 10px
    bottom: 10px
    width: 264px
    border-radius: 20px
    z-index: 70
    transform: translateX(calc(100% + 30px))
    opacity: 0
    pointer-events: none

  .mobile-open .rail
    transform: translateX(0)
    opacity: 1
    pointer-events: auto

  .pane
    margin-right: 0

  .rail-toggle
    z-index: 71
    width: 28px
    height: 62px
    right: 10px
    opacity: 0.6

  .mobile-open .rail-toggle
    right: 278px
    opacity: 1

  .rail-scrim
    display: block
    position: fixed
    inset: 0
    z-index: 57
    background: rgba(20, 38, 57, 0.38)
    opacity: 0
    pointer-events: none
    transition: opacity 0.3s var(--vs-ease)

  .mobile-open .rail-scrim
    opacity: 1
    pointer-events: auto

  .app-header
    position: sticky
    top: 0
    z-index: 50
    display: flex
    align-items: center
    justify-content: space-between
    gap: 12px
    padding: 12px 14px
    background: rgba(247, 250, 252, 0.82)
    backdrop-filter: blur(14px)
    -webkit-backdrop-filter: blur(14px)
    border-radius: 0 0 20px 20px
    box-shadow: 0 1px 0 rgba(228, 238, 247, 0.9)

  .logo
    display: flex
    align-items: center
    gap: 8px
    font-size: 17px
    font-weight: 800
    color: var(--vs-ink)
    text-decoration: none
    white-space: nowrap

  .logo .mark
    width: 34px
    height: 34px
    border-radius: 11px
    flex: none
    color: #fff
    display: flex
    align-items: center
    justify-content: center
    background: linear-gradient(135deg, #52b0ec, #22a7d8)

  .btn-quiet
    border: none
    cursor: pointer
    border-radius: 999px
    padding: 8px 16px
    min-height: 44px
    background: var(--vs-card)
    color: var(--vs-ink)
    font-size: 13px
    font-weight: 600
    box-shadow: var(--vs-sh-1)
    display: flex
    align-items: center
    justify-content: center
    gap: 8px
    font-family: inherit

  .btn-quiet:hover
    background: var(--vs-brand-soft)

  .pane-main
    padding: 16px 20px 32px

</style>
