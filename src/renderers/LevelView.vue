<script setup lang="ts">
/**
 * LevelView：关卡页纯展示组件（FR-601 统一结构；docs §3.1 桌面双栏工作台）。
 * 头部冻结在页面顶部（sticky）：滚动时标题与拼音一直可见；
 * 头部只保留标题 + 拼音 + IPA 徽章（不显示关卡编号、示例汉字与语音学特征标签）。
 * ≥1024px：左栏为主（更宽，构形 / 示范常驻参照，sticky），
 *          右栏训练与检测流（跟练 → 录音 → 页内结果）。
 * <1024px：单列认知顺序：构形 → 示范 → 发音要领 → 录音 → 结果。
 * 头部 IPA 徽章由音系数据（matchLevel）补齐。
 * 听辨练习模块暂不在关卡页展示（组件保留待后续启用）；
 * 误区与专业说明已按需求调整移出关卡页（专业说明移至完整检测结果页）。
 * 录音区（#assessment slot）与结果区（#result slot）由页面挂载；
 * 结果区仅在页面提交检测后（hasResult）出现，避免空标题。
 */
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import type { LevelDetail } from '@/api'
import { matchLevel } from '@/phonology/mandarin'
import ArticulationFigure from './ArticulationFigure.vue'
import DemoPlayer from '@/components/DemoPlayer.vue'
import PracticeTextList from '@/components/PracticeTextList.vue'

const props = withDefaults(
  defineProps<{
    level: LevelDetail
    mediaResolver: (mediaId: string) => string
    /** 页内检测结果是否已产生（提交成功后置真）：控制「本次检测结果」区显隐 */
    hasResult?: boolean
  }>(),
  { hasResult: false },
)

/** 关卡 → 音系单元格（IPA 徽章与语音学特征标签的兜底数据源，§5.1） */
const phonology = computed(() =>
  matchLevel({
    layer: props.level.layer,
    targetSound: props.level.targetSound,
    pinyin: props.level.pinyin,
  }),
)

/* ------------------- 粘性头部的让位测量（运行时实测） ------------------- */
const headerEl = ref<HTMLElement | null>(null)

/** 顶部让位：AppShell 手机顶栏（≤760px 显示，sticky）实测高度；桌面为 0 */
const topOffsetPx = ref(0)
/** 头部实际高度：sticky 冻结后，左栏参照区的让位距离 */
const headerHeightPx = ref(0)

function readOffsets() {
  const appTopBar = document.querySelector('.app-shell > .topbar')
  const barH = appTopBar ? appTopBar.getBoundingClientRect().height : 0
  topOffsetPx.value = barH > 0 ? Math.round(barH) : 0
  headerHeightPx.value = headerEl.value
    ? Math.round(headerEl.value.getBoundingClientRect().height)
    : 0
}

const cssVars = computed(() => ({
  '--lv-top': `${topOffsetPx.value}px`,
  '--lv-head-h': `${headerHeightPx.value}px`,
}))

let headerObserver: ResizeObserver | null = null

onMounted(() => {
  readOffsets()
  window.addEventListener('resize', readOffsets)
  if (headerEl.value && typeof ResizeObserver !== 'undefined') {
    headerObserver = new ResizeObserver(readOffsets)
    headerObserver.observe(headerEl.value)
  }
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', readOffsets)
  headerObserver?.disconnect()
  headerObserver = null
})
</script>

<template>
  <article class="level-view" :style="cssVars">
    <!-- 关卡头部：类型 / 拼音 / IPA；冻结于页面顶部，滚动可见 -->
    <header ref="headerEl" class="level-header">
      <div class="level-identity">
        <span class="vs-tag">{{ level.type }}</span>
        <h1>{{ level.title }}</h1>
        <span class="level-pinyin">{{ level.pinyin }}</span>
        <span v-if="phonology.ipa" class="ipa-badge">[{{ phonology.ipa }}]</span>
      </div>
    </header>

    <aside class="level-aside">
      <!-- 看得见的构形（FR-603）：内容媒体 / 三维模型多视图 -->
      <section id="figure" class="level-section sec-figure" aria-label="构形">
        <ArticulationFigure :articulation="level.articulation" :media-resolver="mediaResolver" />
      </section>

      <!-- 示范音（FR-604）：小标题省略，发音人按钮即标识 -->
      <section id="demo" class="level-section sec-demo" aria-label="示范">
        <DemoPlayer :items="level.demos ?? []" :media-resolver="mediaResolver" />
      </section>
    </aside>

    <main class="level-main">
      <!-- 1 发音要领（FR-605 改版）：发音步骤与方法的纯文本列表 -->
      <section id="practice" class="level-section sec-practice" aria-label="发音要领">
        <h2>发音要领</h2>
        <PracticeTextList :steps="level.practice ?? []" />
      </section>

      <!-- 2 本关录音（FR-609）：由页面挂载 assessment 区 -->
      <section v-if="$slots.assessment" id="record" class="level-section sec-record" aria-label="本关录音">
        <slot name="assessment" />
      </section>

      <!-- 3 本次检测结果（docs §3.2 页内闭环）：提交成功后才出现，由页面挂载 result 区 -->
      <section
        v-if="$slots.result && hasResult"
        id="result"
        class="level-section sec-result"
        aria-label="本次检测结果"
      >
        <h2>本次检测结果</h2>
        <slot name="result" />
      </section>
    </main>
  </article>
</template>

<style scoped lang="sass">
/* 窄屏（默认）：单列认知顺序。aside/main 摊平（display:contents）。 */
.level-view
  max-width: 820px
  margin: 0 auto
  display: flex
  flex-direction: column

.level-aside,
.level-main
  display: contents

.level-header
  order: 0

.sec-figure
  order: 1

.sec-demo
  order: 2

.sec-practice
  order: 3

.sec-record
  order: 4

.sec-result
  order: 5

/* 头部冻结：贴着页面顶部（顶栏下方），滚动时常驻可见；底色与页面一致 + 模糊，卡片从下方穿过 */
.level-header
  position: sticky
  top: var(--lv-top, 0px)
  z-index: 50
  background: rgba(var(--vs-bg-rgb), 0.92)
  -webkit-backdrop-filter: blur(10px)
  backdrop-filter: blur(10px)
  margin-bottom: 10px
  padding: 10px 0 10px
  border-bottom: 1px solid var(--vs-line2)

.level-identity
  display: flex
  align-items: center
  gap: 8px
  flex-wrap: wrap

.level-header h1
  font-family: var(--vs-font-display)
  font-size: 23px
  margin: 0
  line-height: 1.25
  font-weight: 600
  letter-spacing: -0.01em

.level-pinyin
  color: var(--vs-ink2)
  font-size: 15px

.ipa-badge
  font-size: 15px
  color: var(--vs-coffee)
  background: var(--vs-soft)
  border: 1px solid var(--vs-brand-line)
  border-radius: 6px
  padding: 0 6px
  font-family: var(--font-ipa)

/* 每个模块一张卡：内容区留白与边框统一 */
.level-section
  margin-top: 16px
  background: var(--vs-card)
  border: 1px solid var(--vs-line)
  border-radius: 8px
  padding: 24px
  box-shadow: var(--vs-sh-1)
  h2
    font-size: 20px
    font-weight: 900
    letter-spacing: -0.3px
    color: var(--vs-ink)
    margin: 0 0 12px
    display: flex
    align-items: center
    gap: 8px
  h2::before
    content: ''
    display: block
    flex: none
    width: 4px
    height: 18px
    border-radius: 2px
    background: linear-gradient(180deg, var(--vs-sand), var(--vs-brand))

/* 构形自带卡片外观，不再套一层 */
.sec-figure
  background: transparent
  border: none
  box-shadow: none
  padding: 0

/* 每栏首个内容模块紧贴标题栏，不吃 section 的上边距 */
.level-aside .level-section:first-child,
.level-main .level-section:first-child,
.sec-figure
  margin-top: 0

/* 桌面（≥1024px）：双栏工作台。左栏为主（58%，构形/示范常驻参照，sticky），
   右栏 42% 训练与检测流；行距收紧让主体贴近冻结头部。 */
@media (min-width: 1024px)
  .level-view
    max-width: 1200px
    margin-top: -40px
    min-height: calc(100dvh - var(--lv-top, 0px))
    display: grid
    grid-template-columns: 58fr 42fr
    grid-template-rows: auto minmax(0, 1fr)
    grid-template-areas: "header header" "aside main"
    gap: 14px 28px
    align-content: start

  .level-header
    grid-area: header

  .level-aside
    display: block
    grid-area: aside
    position: sticky
    /* 让位冻结头部：顶栏高度 + 头部自身高度 + 原有间隙 */
    top: calc(var(--lv-top, 0px) + var(--lv-head-h, 0px) + 16px)
    align-self: start
    max-height: calc(100dvh - var(--lv-top, 0px) - var(--lv-head-h, 0px) - 16px)
    overflow-y: auto

  .level-main
    display: block
    grid-area: main
</style>
