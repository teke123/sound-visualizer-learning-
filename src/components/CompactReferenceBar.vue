<script setup lang="ts">
/**
 * CompactReferenceBar：窄屏（<1024px）关卡页顶部紧凑参照栏
 * （docs/发音库与关卡页重构方案_修订版.md §3.1 响应式退化：滚动到 #record 录音检测区时出现）。
 * 左侧关卡身份（代表字 + 拼音 + IPA），右侧「听示范」（全局唯一播放）与「查看构形」入口。
 * 显隐完全由组件内部决定：matchMedia(max-width: 1023px) 与 #record 的 IntersectionObserver 相与。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { QBtn } from 'quasar'
import { mediaUrl, type LevelDetail } from '@/api'
import { matchLevel } from '@/phonology/mandarin'
import { usePlayerStore } from '@/stores/player'

const props = defineProps<{ level: LevelDetail }>()

const player = usePlayerStore()

/** 音系身份与 LevelView 头部同源（layer/targetSound/pinyin 兜底匹配），栏内 IPA 与页头徽章一致 */
const phonology = computed(() =>
  matchLevel({
    layer: props.level.layer,
    targetSound: props.level.targetSound,
    pinyin: props.level.pinyin,
  }),
)

/** 第一个正常语速示范；没有则不显示「听示范」按钮 */
const demo = computed(() => props.level.demos?.find((item) => item.speed === 'normal') ?? null)
/** 独立播放键（区别于 DemoPlayer 的 demo:<mediaId>，避免与页内示范按钮互相顶替状态） */
const demoKey = computed(() => `compact-demo:${props.level.id}`)

function toggleDemo() {
  const item = demo.value
  if (!item) return
  void player.play({
    key: demoKey.value,
    url: mediaUrl(item.mediaId),
    label: `${props.level.title} · 示范`,
  })
}

function gotoFigure() {
  document.getElementById('figure')?.scrollIntoView({ behavior: 'smooth' })
}

/* ------------------------- 显隐控制（组件内部自治） ------------------------- */
const visible = ref(false)

let narrowQuery: MediaQueryList | null = null
let observer: IntersectionObserver | null = null
let recordIntersecting = false

/**
 * 顶栏让位：AppShell 手机顶栏（≤760px 显示，sticky z-100）运行时实测高度；
 * 桌面 761–1023px 区间顶栏隐藏（高度 0）则贴顶 top: 0。
 */
const topOffsetPx = ref(0)

function readTopOffset() {
  const appTopBar = document.querySelector('.app-shell > .mobile-bar')
  const height = appTopBar ? appTopBar.getBoundingClientRect().height : 0
  topOffsetPx.value = height > 0 ? Math.round(height) : 0
}

function syncVisible() {
  visible.value = narrowQuery?.matches === true && recordIntersecting
}

function onNarrowChange() {
  // 跨 760px 断点时 AppShell 顶栏显隐变化，需重读让位高度
  readTopOffset()
  syncVisible()
}

onMounted(async () => {
  // nextTick 后 LevelView（含 #record / #figure 锚点）已完成首帧渲染；找不到 #record 则本栏永不出现
  await nextTick()
  const recordEl = document.getElementById('record')
  if (!recordEl || typeof IntersectionObserver === 'undefined') return

  observer = new IntersectionObserver(
    (entries) => {
      recordIntersecting = entries.some((entry) => entry.isIntersecting)
      syncVisible()
    },
    { threshold: 0 },
  )
  observer.observe(recordEl)

  narrowQuery = window.matchMedia('(max-width: 1023px)')
  narrowQuery.addEventListener('change', onNarrowChange)
  window.addEventListener('resize', readTopOffset)
  readTopOffset()
})

onBeforeUnmount(() => {
  observer?.disconnect()
  observer = null
  narrowQuery?.removeEventListener('change', onNarrowChange)
  narrowQuery = null
  window.removeEventListener('resize', readTopOffset)
})
</script>

<template>
  <div
    class="compact-ref"
    :class="{ shown: visible }"
    :style="topOffsetPx > 0 ? { top: `${topOffsetPx}px` } : undefined"
    role="region"
    aria-label="本关参照"
  >
    <div class="ref-identity">
      <span v-if="level.representativeChar" class="ref-char">{{ level.representativeChar }}</span>
      <span class="ref-meta">
        <span class="ref-pinyin">{{ level.pinyin }}</span>
        <span v-if="phonology.ipa" class="ref-ipa">[{{ phonology.ipa }}]</span>
      </span>
    </div>

    <div class="ref-actions">
      <QBtn
        v-if="demo"
        outline
        no-caps
        color="primary"
        text-color="teal-9"
        class="ref-demo-btn"
        @click="toggleDemo"
      >
        {{ player.isCurrent(demoKey) ? '⏸ 暂停示范' : '▶ 听示范' }}
      </QBtn>
      <QBtn flat no-caps color="primary" class="ref-figure-btn" label="查看构形" @click="gotoFigure" />
    </div>
  </div>
</template>

<style scoped lang="sass">
/*
 * 层叠：z-index 900 高于 AppShell 全局导航（侧栏/手机顶栏/底部标签均 z-100），
 * 低于 Quasar 遮罩体系（QDialog 根节点 .fullscreen z-6000、q-menu 6000、notify 9500、loading 9998），
 * 标定/比较对话框打开时参照栏必然被盖住，不产生层叠冲突。
 */
.compact-ref
  position: fixed
  left: 0
  right: 0
  top: 0
  z-index: 900
  display: flex
  align-items: center
  justify-content: space-between
  gap: 10px
  min-height: 60px
  padding: 6px 14px
  box-sizing: border-box
  background: #fff
  border-bottom: 1px solid #eceff1
  box-shadow: 0 4px 14px rgba(69, 90, 100, 0.1)
  transform: translateY(-100%)
  opacity: 0
  visibility: hidden
  pointer-events: none
  transition: transform 0.2s ease, opacity 0.2s ease, visibility 0.2s
  &.shown
    transform: translateY(0)
    opacity: 1
    visibility: visible
    pointer-events: auto

/* 761–1023px：AppShell 桌面侧栏（宽 240px 含边框，sticky z-100）仍在左侧，参照栏从其右侧起，避免遮住搜索/导航 */
@media (min-width: 761px)
  .compact-ref
    left: 240px

.ref-identity
  display: flex
  align-items: center
  gap: 10px
  min-width: 0

.ref-char
  font-size: 30px
  font-weight: 700
  line-height: 1.1
  color: #263238

.ref-meta
  display: flex
  flex-direction: column
  gap: 1px
  min-width: 0

.ref-pinyin
  font-size: 15px
  font-weight: 700
  color: #00695c
  white-space: nowrap
  overflow: hidden
  text-overflow: ellipsis

.ref-ipa
  font-size: 13px
  color: #546e7a
  white-space: nowrap

.ref-actions
  display: flex
  align-items: center
  gap: 8px
  flex-shrink: 0

/* 主操作「听示范」保持 ≥44px 触达标准；原版浅青底（#e0f2f1）由 scoped 补回
   （Quasar outline 底色为 transparent !important，覆盖需同为 important） */
.ref-demo-btn
  min-height: 44px
  white-space: nowrap
  background: #e0f2f1 !important

/* 次操作「查看构形」允许紧凑栏内的 40px */
.ref-figure-btn
  min-height: 40px
  font-size: 13px
  text-decoration: underline
  white-space: nowrap
</style>
