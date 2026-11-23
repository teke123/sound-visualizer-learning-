<script setup lang="ts">
/** ScoreCard：分数展示（FR-1002）：综合分大字 + 声母/韵母/声调三项分项进度条。
 *  分数只表示本关本次录音，不折算总榜。分项无音节时缺省。 */
import { computed } from 'vue'
import type { ScoreBreakdown } from '@/api'

const props = defineProps<{ score: ScoreBreakdown }>()

/** 分数等级 → 文案与语气（不做排名，只给一句人话） */
function band(value: number) {
  if (value >= 90) return { label: '很棒', tone: 'a' }
  if (value >= 75) return { label: '不错', tone: 'a' }
  if (value >= 60) return { label: '有进步空间', tone: 'b' }
  return { label: '需要多练', tone: 'b' }
}

const overall = computed(() => band(props.score.overall))
const overallRounded = computed(() => Math.round(props.score.overall))

const parts = computed(() => [
  { key: 'initial', label: '声母', value: props.score.initial },
  { key: 'final', label: '韵母', value: props.score.final },
  { key: 'tone', label: '声调', value: props.score.tone },
] as const)

function width(value: number | null | undefined): string {
  if (typeof value !== 'number') return '0%'
  return `${Math.round(Math.max(0, Math.min(100, value)))}%`
}
</script>

<template>
  <section class="score-card vs-card" aria-label="本次分数">
    <div class="score-row">
      <div class="score-num">{{ overallRounded }}<small>分</small></div>
      <div class="score-word">
        <b :class="`tone-${overall.tone}`">{{ overall.label }}</b>
      </div>
    </div>

    <div class="dims">
      <div v-for="part in parts" :key="part.key" class="dim">
        <div class="n">{{ part.label }}</div>
        <div class="v">
          <template v-if="typeof part.value === 'number'">{{ Math.round(part.value) }}</template>
          <template v-else>本关不比</template>
        </div>
        <div class="bar"><i :style="{ width: width(part.value) }" /></div>
      </div>
    </div>
  </section>
</template>

<style scoped lang="sass">
.score-card
  padding: 24px

.score-row
  display: flex
  align-items: flex-start
  gap: 24px
  flex-wrap: wrap

.score-num
  font-size: 44px
  font-weight: 800
  color: var(--vs-ink)
  line-height: 1
  letter-spacing: -1.5px
  small
    font-size: 13px
    font-weight: 600
    color: var(--vs-sub)
    margin-left: 4px
    letter-spacing: 0

.score-word
  font-size: 13.5px
  color: var(--vs-sub)
  flex: 1
  min-width: 200px
  line-height: 1.8
  b
    color: var(--vs-ink)
  .tone-a
    color: var(--vs-green)
  .tone-b
    color: var(--vs-brand-d)

.dims
  display: grid
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr))
  gap: 12px
  margin-top: 24px

.dim
  background: var(--vs-panel)
  border: 1px solid var(--vs-line)
  border-radius: 8px
  padding: 16px

.dim .n
  font-size: 12px
  color: var(--vs-sub)

.dim .v
  margin-top: 4px
  font-size: 16px
  font-weight: 700
  color: var(--vs-ink)

.dim .bar
  margin-top: 12px
  height: 4px
  border-radius: 2px
  background: var(--vs-line2)
  overflow: hidden

.dim .bar i
  display: block
  height: 100%
  border-radius: 2px
  background: var(--vs-brand)
  transition: width 0.5s var(--vs-ease)
</style>
