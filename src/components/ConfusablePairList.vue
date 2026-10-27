<script setup lang="ts">
/**
 * ConfusablePairList：音素对比并排入口（FR-403 / FD-05）。
 * 仅显示双方都已开放的比较；点击打开 ComparePanel（?compare=，可分享）。
 */
import { computed } from 'vue'
import { QBtn } from 'quasar'
import type { ConfusablePair, LevelSummary } from '@/api'

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
    <h2>音素对比</h2>
    <div v-if="visiblePairs.length === 0" class="pair-empty">暂无可比较的音素对（需双方都已开放）</div>
    <ul v-else class="pair-list">
      <li v-for="item in visiblePairs" :key="item.pair.a" class="pair-item">
        <div class="pair-sounds">
          <span class="pair-sound">{{ item.a!.targetSound }}</span>
          <span class="pair-vs">vs</span>
          <span class="pair-sound">{{ item.b!.targetSound }}</span>
        </div>
        <div class="pair-names">{{ item.a!.title }} · {{ item.b!.title }}</div>
        <QBtn
          outline
          no-caps
          color="primary"
          text-color="teal-9"
          class="pair-btn"
          label="并排比较"
          @click="emit('compare', item.pair)"
        />
      </li>
    </ul>
  </section>
</template>

<style scoped lang="sass">
.confusable-pairs
  h2
    font-size: 17px
    margin: 0 0 12px

.pair-empty
  color: #90a4ae
  font-size: 14px
  padding: 12px 0

.pair-list
  list-style: none
  margin: 0
  padding: 0
  display: grid
  grid-template-columns: repeat(auto-fill, minmax(210px, 1fr))
  gap: 12px

.pair-item
  border: 1px solid #eceff1
  border-radius: 10px
  padding: 12px
  display: flex
  flex-direction: column
  align-items: center
  gap: 6px

.pair-sounds
  display: flex
  align-items: center
  gap: 10px

.pair-sound
  font-size: 26px
  font-weight: 700
  color: #00695c

.pair-vs
  font-size: 12px
  color: #b0bec5

.pair-names
  font-size: 12px
  color: #78909c

/* 「并排比较」原 #e1f5fe/#0288d1 蓝软底，按用户指定统一为浅青填充：青细描边 + 浅青底 + 深青字（原 40px 高补回）；
   Quasar outline 底色为 transparent !important，覆盖需同为 important */
.pair-btn
  min-height: 40px
  background: #e0f2f1 !important
</style>
