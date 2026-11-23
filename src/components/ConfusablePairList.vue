<script setup lang="ts">
/**
 * ConfusablePairList：音素对比并排入口（FR-403 / FD-05）。
 * 仅显示双方都已开放的比较；点击打开 ComparePanel（?compare=，可分享）。
 */
import { computed } from 'vue'
import type { ConfusablePair, LevelSummary } from '@/api'
import AppIcon from '@/components/ui/AppIcon.vue'

const props = defineProps<{
  pairs: ConfusablePair[]
  levelsById: Map<string, LevelSummary>
}>()

const emit = defineEmits<{ (e: 'compare', pair: ConfusablePair): void }>()

interface PairView {
  pair: ConfusablePair
  a?: LevelSummary
  b?: LevelSummary
}

const visiblePairs = computed<PairView[]>(() =>
  props.pairs
    .map((pair) => ({ pair, a: props.levelsById.get(pair.a), b: props.levelsById.get(pair.b) }))
    .filter((item): item is PairView & { a: LevelSummary; b: LevelSummary } => Boolean(item.a && item.b)),
)
</script>

<template>
  <section class="confusable-pairs" aria-label="音素对比">
    <div class="pair-head">
      <h2>容易混的音，并排比一比</h2>
      <p class="vs-note">两边都已经开放的音，才可以并排听示范。</p>
    </div>
    <div v-if="visiblePairs.length === 0" class="pair-empty">暂无可比较的音素对（需双方都已开放）</div>
    <ul v-else class="pair-list">
      <li v-for="item in visiblePairs" :key="item.pair.a" class="pair-item">
        <div class="pair-sounds">
          <span class="pair-sound">{{ item.a!.targetSound }}</span>
          <span class="pair-vs">vs</span>
          <span class="pair-sound">{{ item.b!.targetSound }}</span>
        </div>
        <div class="pair-names">{{ item.a!.title }} · {{ item.b!.title }}</div>
        <button type="button" class="vs-btn vs-btn--ghost vs-btn--small" @click="emit('compare', item.pair)">
          <AppIcon name="scale" size="sm" />并排比较
        </button>
      </li>
    </ul>
  </section>
</template>

<style scoped lang="sass">
.pair-head
  margin-bottom: 12px
  h2
    font-size: 20px
    font-weight: 800
    letter-spacing: -0.3px
    margin: 0 0 4px
    display: flex
    align-items: center
    gap: 8px

.pair-empty
  color: var(--vs-mute)
  font-size: 14px
  padding: 12px 0

.pair-list
  list-style: none
  margin: 0
  padding: 0
  display: grid
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr))
  gap: 16px

.pair-item
  border: 1px solid var(--vs-line)
  border-radius: 8px
  background: var(--vs-card)
  box-shadow: var(--vs-sh-1)
  padding: 16px
  display: flex
  flex-direction: column
  align-items: center
  gap: 8px
  transition: border-color 0.2s var(--vs-ease), box-shadow 0.2s var(--vs-ease)

.pair-item:hover
  border-color: var(--vs-line-hover)
  box-shadow: var(--vs-sh-2)

.pair-sounds
  display: flex
  align-items: center
  gap: 10px

.pair-sound
  font-size: 26px
  font-weight: 800
  color: var(--vs-ink)
  letter-spacing: -0.5px

.pair-vs
  font-size: 12px
  color: var(--vs-mute)

.pair-names
  font-size: 12px
  color: var(--vs-mute)
  text-align: center

.pair-item .vs-btn
  margin-top: 4px
</style>
