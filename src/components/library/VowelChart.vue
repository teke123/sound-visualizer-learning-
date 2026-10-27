<script setup lang="ts">
/**
 * 元音舌位图（IPA 梯形）：按 docs/Beijing_Mandarin_{monophthongs,diphthongs_1,diphthongs_2}.svg
 * 的梯形几何与舌位坐标重绘。三个分页对应三张参考图：单元音（严式含条件变体，
 * 虚线框圈出同一音位的变体）/ 升双元音（介音起头）/ 降双元音（韵腹在前）。
 * 双元音 = 起点圆点 + 滑动箭头（终点取自参考图的箭头端点）；
 * 点击圆点或标签选中对应韵母（央元音 ə 仅为参考位，不可选）；选中韵母变化时自动切到所在分页。
 */
import { computed, ref, watch } from 'vue'
import { QBtn } from 'quasar'
import {
  VOWEL_GLIDES_FALLING,
  VOWEL_GLIDES_RISING,
  VOWEL_POSITIONS,
  type VowelGlide,
  type VowelPoint,
} from '@/phonology/mandarin'

const props = withDefaults(
  defineProps<{
    /** 当前选中的韵母键（详情侧栏联动高亮，并自动切到所在分页） */
    activeKey?: string | null
    /** 搜索 / 易混组命中的韵母键集合（点亮对应舌位点或箭头） */
    hitKeys?: ReadonlySet<string> | readonly string[]
  }>(),
  { activeKey: null, hitKeys: () => [] },
)

const emit = defineEmits<{ (e: 'selectVowel', finalKey: string): void }>()

type TabKey = 'mono' | 'rising' | 'falling'
const TABS: Array<{ key: TabKey; label: string }> = [
  { key: 'mono', label: '单元音' },
  { key: 'rising', label: '升双元音' },
  { key: 'falling', label: '降双元音' },
]
const tab = ref<TabKey>('mono')

/* 梯形几何与参考图同形：前高（左上）→ 后高（右上）→ 后低（右下）→ 前低（左下），右侧竖直 */
const OUTLINE = 'M 5.3 2.9 L 881.3 2.5 L 882.5 659.4 L 442.8 658.8 Z'
/** 央/后分界线：顶边中点 → 底边（参考图 path2） */
const CENTRAL_LINE = { x1: 443.8, y1: 2.9, x2: 661.1, y2: 658.8 } as const
/** 半高 / 半低横线：高度 1/3 与 2/3（参考图 path3/path4），自倾斜的左缘画到竖直的右缘 */
const GUIDE_LINES = ['半高', '半低'].map((label, i) => {
  const h = (i + 1) / 3
  return {
    label,
    x1: 5.3 + (442.8 - 5.3) * h,
    x2: 881.3 + (882.5 - 881.3) * h,
    y: 2.7 + (659.4 - 2.7) * h,
  }
})

/** 舌位坐标 → 梯形内像素：height 沿左缘（前）插值，frontness 1=左缘（前）→ 0=右缘（后） */
function pt(p: VowelPoint): { x: number; y: number } {
  const xl = 5.3 + (442.8 - 5.3) * p.height
  const xr = 881.3 + (882.5 - 881.3) * p.height
  return { x: xl + (xr - xl) * (1 - p.frontness), y: 2.7 + (659.4 - 2.7) * p.height }
}

const hitSet = computed(() => new Set(props.hitKeys))

function pointText(label: string, ipa: string): string {
  return label === ipa ? label : `${label} [${ipa}]`
}

const monoPoints = computed(() =>
  VOWEL_POSITIONS.map((v) => {
    const { x, y } = pt(v)
    const front = v.frontness >= 0.5
    return {
      v,
      x,
      y,
      text: pointText(v.label, v.ipa),
      title: v.finalKey ? `韵母 ${v.finalKey}：${v.note ?? ''}` : (v.note ?? ''),
      clickable: v.finalKey !== null,
      active: v.finalKey !== null && props.activeKey === v.finalKey,
      hl: v.finalKey !== null && hitSet.value.has(v.finalKey),
      labelX: x + (front ? 26 : -26),
      labelY: y + 11,
      anchor: front ? ('start' as const) : ('end' as const),
    }
  }),
)

/** 音位变体分组框：圈住同 phoneme 的舌位点（虚线圆角矩形 + 左上角音位标记） */
const allophoneBoxes = computed(() => {
  const groups = new Map<string, { x1: number; y1: number; x2: number; y2: number }>()
  for (const p of monoPoints.value) {
    const phoneme = p.v.phoneme
    if (!phoneme) continue
    const g = groups.get(phoneme) ?? { x1: p.x, y1: p.y, x2: p.x, y2: p.y }
    g.x1 = Math.min(g.x1, p.x)
    g.y1 = Math.min(g.y1, p.y)
    g.x2 = Math.max(g.x2, p.x)
    g.y2 = Math.max(g.y2, p.y)
    groups.set(phoneme, g)
  }
  const pad = 32
  return [...groups.entries()].map(([phoneme, g]) => ({
    phoneme,
    x: g.x1 - pad,
    y: g.y1 - pad,
    w: g.x2 - g.x1 + pad * 2,
    h: g.y2 - g.y1 + pad * 2,
  }))
})

const glideViews = computed(() => {
  const list = tab.value === 'rising' ? VOWEL_GLIDES_RISING : VOWEL_GLIDES_FALLING
  return list.map((g: VowelGlide) => ({
    g,
    from: pt(g.from),
    to: pt(g.to),
    label: pt(g.labelAt),
    text: pointText(g.label, g.ipa),
    active: props.activeKey === g.finalKey,
    hl: hitSet.value.has(g.finalKey),
  }))
})

/** 选中韵母变化时自动切到所在分页（当前分页已可见则不打扰） */
watch(
  () => props.activeKey,
  (key) => {
    if (!key) return
    const seen = (keys: Array<string | null>) => keys.includes(key)
    const monoKeys = VOWEL_POSITIONS.map((v) => v.finalKey)
    const risingKeys = VOWEL_GLIDES_RISING.map((g) => g.finalKey)
    const fallingKeys = VOWEL_GLIDES_FALLING.map((g) => g.finalKey)
    if (tab.value === 'mono' && seen(monoKeys)) return
    if (tab.value === 'rising' && seen(risingKeys)) return
    if (tab.value === 'falling' && seen(fallingKeys)) return
    if (seen(monoKeys)) tab.value = 'mono'
    else if (seen(risingKeys)) tab.value = 'rising'
    else if (seen(fallingKeys)) tab.value = 'falling'
  },
  { immediate: true },
)

const NOTE_BY_TAB: Record<TabKey, string> = {
  mono: '● 圆唇 ○ 不圆唇 · 虚线框 = 同一音位的条件变体（/a/ = [a ä ɑ]；/ə/ 系 = [ɤ o e ə] 互补分布）· 点击舌位点选中对应韵母',
  rising: '介音起头，滑向韵腹（G → V）· uo 的韵腹可央化为 [wə] · 点击圆点或标签选中对应韵母',
  falling: '韵腹在前，滑向韵尾（V → -i̯ / -u̯）· iu 为 iou 的省写 · 点击圆点或标签选中对应韵母',
}
</script>

<template>
  <div class="vc-root">
    <div class="vc-head">
      <h3>元音舌位图</h3>
      <div class="vc-tabs" role="group" aria-label="元音图分页">
        <QBtn
          v-for="t in TABS"
          :key="t.key"
          no-caps
          rounded
          class="vc-tab"
          :unelevated="tab === t.key"
          :flat="tab !== t.key"
          :color="tab === t.key ? 'primary' : 'blue-grey-6'"
          :label="t.label"
          @click="tab = t.key"
        />
      </div>
    </div>

    <svg
      class="vc-svg"
      viewBox="-42 -46 952 756"
      role="img"
      :aria-label="tab === 'mono' ? '单元音舌位梯形图' : tab === 'rising' ? '升双元音舌位滑动图' : '降双元音舌位滑动图'"
    >
      <defs>
        <!-- userSpaceOnUse：箭头尺寸不随线宽缩放（原 strokeWidth 单位下 5×12 会被放大成巨箭头）；填色内联防止 marker 内样式失效变黑 -->
        <marker id="vc-arrow" orient="auto" markerUnits="userSpaceOnUse" markerWidth="19" markerHeight="14" refX="16" refY="6.5">
          <path d="M 0 0 L 18 6.5 L 0 13 z" fill="#00897b" />
        </marker>
        <marker id="vc-arrow-on" orient="auto" markerUnits="userSpaceOnUse" markerWidth="19" markerHeight="14" refX="16" refY="6.5">
          <path d="M 0 0 L 18 6.5 L 0 13 z" fill="#0288d1" />
        </marker>
      </defs>

      <path class="vc-outline" :d="OUTLINE" />
      <line v-for="g in GUIDE_LINES" :key="g.label" class="vc-guide" :x1="g.x1" :y1="g.y" :x2="g.x2" :y2="g.y" />
      <line class="vc-guide" :x1="CENTRAL_LINE.x1" :y1="CENTRAL_LINE.y1" :x2="CENTRAL_LINE.x2" :y2="CENTRAL_LINE.y2" />
      <text class="vc-axis" x="224" y="-14" text-anchor="middle">前</text>
      <text class="vc-axis" x="552" y="-14" text-anchor="middle">央</text>
      <text class="vc-axis" x="771" y="-14" text-anchor="middle">后</text>
      <text class="vc-axis" x="-12" y="14" text-anchor="end">高</text>
      <text class="vc-axis" x="434" y="686" text-anchor="end">低</text>
      <text
        v-for="g in GUIDE_LINES"
        :key="`label-${g.label}`"
        class="vc-axis small"
        :x="g.x1 - 10"
        :y="g.y + 8"
        text-anchor="end"
      >
        {{ g.label }}
      </text>

      <!-- 复元音分页：单元音参考位（浅灰小点）+ 起点圆点 + 滑动箭头 -->
      <template v-if="tab !== 'mono'">
        <circle
          v-for="(p, i) in monoPoints"
          :key="`ref-${i}`"
          class="vc-ref"
          :cx="p.x"
          :cy="p.y"
          r="7"
        >
          <title>{{ p.text }}（单元音参考位）</title>
        </circle>
        <g
          v-for="gv in glideViews"
          :key="`${gv.g.finalKey}-${gv.g.ipa}`"
          class="vc-glide"
          :class="{ active: gv.active, hl: gv.hl }"
          @click="emit('selectVowel', gv.g.finalKey)"
        >
          <circle class="vc-hit" :cx="gv.from.x" :cy="gv.from.y" r="34" />
          <line
            class="vc-arrow"
            :x1="gv.from.x"
            :y1="gv.from.y"
            :x2="gv.to.x"
            :y2="gv.to.y"
            :marker-end="gv.active || gv.hl ? 'url(#vc-arrow-on)' : 'url(#vc-arrow)'"
          />
          <circle v-if="gv.active" class="vc-ring" :cx="gv.from.x" :cy="gv.from.y" r="20" />
          <circle class="vc-dot" :cx="gv.from.x" :cy="gv.from.y" r="11" />
          <text class="vc-label" :x="gv.label.x" :y="gv.label.y" text-anchor="middle">{{ gv.text }}</text>
        </g>
      </template>

      <!-- 单元音分页 -->
      <template v-if="tab === 'mono'">
        <!-- 音位变体分组框（虚线圈住同一音位的条件变体） -->
        <g v-for="b in allophoneBoxes" :key="b.phoneme" class="vc-allo-group">
          <rect class="vc-allo" :x="b.x" :y="b.y" :width="b.w" :height="b.h" rx="20" />
          <text class="vc-allo-label" :x="b.x + 8" :y="b.y - 10">{{ b.phoneme }} 音位变体</text>
        </g>
        <g
          v-for="(p, i) in monoPoints"
          :key="p.v.finalKey ?? `ref-${i}`"
          class="vc-point"
          :class="{ active: p.active, hl: p.hl, ref: !p.clickable }"
          @click="p.clickable && p.v.finalKey && emit('selectVowel', p.v.finalKey)"
        >
          <circle v-if="!p.clickable" class="vc-ref-dot" :cx="p.x" :cy="p.y" r="9">
            <title>{{ p.title }}</title>
          </circle>
          <template v-else>
            <circle class="vc-hit" :cx="p.x" :cy="p.y" r="34" />
            <circle v-if="p.active" class="vc-ring" :cx="p.x" :cy="p.y" r="20" />
            <circle class="vc-dot" :class="{ rounded: p.v.rounded }" :cx="p.x" :cy="p.y" r="12">
              <title>{{ p.text }}{{ p.title ? ` · ${p.title}` : '' }}</title>
            </circle>
          </template>
          <text :x="p.labelX" :y="p.labelY" :text-anchor="p.anchor" class="vc-label">{{ p.text }}</text>
        </g>
      </template>
    </svg>

    <p class="vc-note">{{ NOTE_BY_TAB[tab] }}</p>
  </div>
</template>

<style scoped lang="sass">
.vc-root
  display: flex
  flex-direction: column
  gap: 6px

.vc-head
  display: flex
  align-items: center
  justify-content: space-between
  gap: 8px
  flex-wrap: wrap
  h3
    margin: 0
    font-size: 15px
    color: #37474f

.vc-tabs
  display: inline-flex
  gap: 3px
  background: #eceff1
  border-radius: 999px
  padding: 3px

.vc-tab
  min-height: 32px
  padding: 2px 12px
  font-size: 13px
  white-space: nowrap

.vc-svg
  width: 100%
  height: auto
  display: block
  user-select: none

.vc-outline
  fill: #f6faf9
  fill-opacity: 0.6
  stroke: #546e7a
  stroke-width: 4

.vc-guide
  stroke: #cfd8dc
  stroke-width: 2
  stroke-dasharray: 10 10

.vc-allo
  fill: rgba(2, 136, 209, 0.03)
  stroke: #90a4ae
  stroke-width: 3
  stroke-dasharray: 14 10

.vc-allo-label
  font-size: 22px
  fill: #90a4ae
  font-family: var(--font-ipa)

.vc-axis
  font-size: 26px
  fill: #90a4ae
  &.small
    font-size: 22px
    fill: #b0bec5

.vc-ref
  fill: #cfd8dc

.vc-point
  cursor: pointer
  &.ref
    cursor: default

  .vc-hit
    fill: transparent
    stroke: none

  .vc-dot
    stroke-width: 4
    &.rounded
      fill: #00897b
      stroke: #00897b
    &:not(.rounded)
      fill: #fff
      stroke: #00897b

  .vc-ref-dot
    fill: #cfd8dc
    stroke: #b0bec5
    stroke-width: 3

  &.hl .vc-dot
    stroke: #0288d1
    &.rounded
      fill: #0288d1

  .vc-ring
    fill: none
    stroke: #0288d1
    stroke-width: 4

  &:hover .vc-dot
    stroke: #0288d1
    &.rounded
      fill: #0288d1

.vc-glide
  cursor: pointer

  .vc-hit
    fill: transparent
    stroke: none

  .vc-arrow
    stroke: #00897b
    stroke-width: 3.5
    stroke-linecap: round

  .vc-dot
    fill: #00897b
    stroke: #fff
    stroke-width: 2.5

  .vc-ring
    fill: none
    stroke: #0288d1
    stroke-width: 4

  &.hl,
  &.active
    .vc-arrow
      stroke: #0288d1
    .vc-dot
      fill: #0288d1

  &:hover
    .vc-arrow
      stroke: #0288d1
    .vc-dot
      fill: #0288d1

.vc-label
  font-size: 30px
  font-weight: 600
  fill: #455a64
  font-family: var(--font-ipa)
  paint-order: stroke
  stroke: #fff
  stroke-width: 7px
  stroke-linejoin: round

.vc-glide.active .vc-label,
.vc-point.active .vc-label
  fill: #0288d1

.vc-note
  margin: 0
  font-size: 12px
  color: #90a4ae
</style>
