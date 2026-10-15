<script setup lang="ts">
/** ScoreCard：分数展示（FR-1002）：分数只表示本关本次录音 */
import { computed } from 'vue'

const props = defineProps<{ score: number }>()

const band = computed(() => {
  if (props.score >= 90) return { label: '很棒', color: '#2e7d32' }
  if (props.score >= 75) return { label: '不错', color: '#7cb342' }
  if (props.score >= 60) return { label: '有进步空间', color: '#f9a825' }
  return { label: '需要多练', color: '#d32f2f' }
})
</script>

<template>
  <section class="score-card" aria-label="本次分数">
    <div class="score-number" :style="{ color: band.color }">{{ Math.round(score) }}</div>
    <div class="score-meta">
      <p class="score-band">{{ band.label }}</p>
      <p class="score-note">分数只表示本关这一次录音的表现，供学习参考。</p>
    </div>
  </section>
</template>

<style scoped lang="sass">
.score-card
  display: flex
  align-items: center
  gap: 18px
  border: 1px solid #eceff1
  border-radius: 12px
  padding: 16px 20px
  background: #fff

.score-number
  font-size: 52px
  font-weight: 800
  font-variant-numeric: tabular-nums
  min-width: 84px
  text-align: center

.score-band
  margin: 0
  font-size: 16px
  font-weight: 600

.score-note
  margin: 4px 0 0
  font-size: 13px
  color: #90a4ae
</style>
