<script setup lang="ts">
/** ScoreCard：分数展示（FR-1002）：声母/韵母/声调三项为主要分（该项读对的
 * 音节比例），整体综合分为次要。分数只表示本关本次录音；分项无音节时缺省。 */
import { computed } from 'vue'
import { QBadge, QCard, QCardSection } from 'quasar'
import type { ScoreBreakdown } from '@/api'

const props = defineProps<{ score: ScoreBreakdown }>()

/** 分数等级 → Quasar 语义/调色板色名（配合 text-* / QBadge color 使用） */
function band(value: number) {
  if (value >= 90) return { label: '很棒', color: 'positive' }
  if (value >= 75) return { label: '不错', color: 'light-green-6' }
  if (value >= 60) return { label: '有进步空间', color: 'warning' }
  return { label: '需要多练', color: 'negative' }
}

const overall = computed(() => band(props.score.overall))

const parts = computed(() => [
  { key: 'initial', label: '声母', value: props.score.initial },
  { key: 'final', label: '韵母', value: props.score.final },
  { key: 'tone', label: '声调', value: props.score.tone },
] as const)
</script>

<template>
  <QCard flat bordered class="score-card" aria-label="本次分数">
    <QCardSection class="score-body">
      <div class="score-parts">
        <div v-for="part in parts" :key="part.key" class="score-part">
          <div
            class="part-number"
            :class="typeof part.value === 'number' ? `text-${band(part.value).color}` : 'text-blue-grey-2'"
          >
            {{ typeof part.value === 'number' ? Math.round(part.value) : '—' }}
          </div>
          <p class="part-label">{{ part.label }}</p>
        </div>
      </div>
      <div class="score-overall">
        <span class="overall-number" :class="`text-${overall.color}`">{{ Math.round(score.overall) }}</span>
        <div class="overall-meta">
          综合分 · <QBadge :color="overall.color" :label="overall.label" />
        </div>
      </div>
    </QCardSection>
  </QCard>
</template>

<style scoped lang="sass">
.score-body
  display: flex
  align-items: center
  gap: 24px
  flex-wrap: wrap
  padding: 16px 22px

.score-parts
  display: flex
  gap: 26px

.score-part
  text-align: center

.part-number
  font-size: 44px
  font-weight: 800
  font-variant-numeric: tabular-nums
  min-width: 72px
  line-height: 1.1

.part-label
  margin: 4px 0 0
  font-size: 14px
  font-weight: 600
  color: #546e7a

.score-overall
  border-left: 1px solid #eceff1
  padding-left: 22px
  display: flex
  flex-direction: column
  align-items: center

.overall-number
  font-size: 26px
  font-weight: 700
  font-variant-numeric: tabular-nums
  line-height: 1.2

.overall-meta
  margin: 2px 0 0
  font-size: 13px
  color: #78909c
</style>
