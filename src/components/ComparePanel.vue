<script setup lang="ts">
/**
 * ComparePanel：两关示范与构形并排比较（FR-703 / FD-05）。
 * P03 / P05 / P06 共用；打开方式 ?compare=L13,L14（可分享，后退即关闭）。
 * 两侧语音学标签的差异项（§2.7）下发 CompareSide 高亮：仅本侧有、对侧没有的标签。
 */
import { computed } from 'vue'
import { QBtn, QCard, QCardSection, QDialog } from 'quasar'
import type { LevelDetail } from '@/api'
import { matchLevel } from '@/phonology/mandarin'
import PageState from './PageState.vue'
import CompareSide from './CompareSide.vue'

const props = defineProps<{
  open: boolean
  detailA: LevelDetail | null
  detailB: LevelDetail | null
  loading: boolean
  error: unknown
}>()

const emit = defineEmits<{ (e: 'close'): void }>()

function labelsOf(level: LevelDetail | null): string[] {
  if (!level) return []
  return matchLevel({
    layer: level.layer,
    targetSound: level.targetSound,
    pinyin: level.pinyin,
    phonology: level.phonology,
  }).labels
}

const diffA = computed(() => {
  const a = labelsOf(props.detailA)
  const b = labelsOf(props.detailB)
  return a.filter((label) => !b.includes(label))
})
const diffB = computed(() => {
  const a = labelsOf(props.detailA)
  const b = labelsOf(props.detailB)
  return b.filter((label) => !a.includes(label))
})
</script>

<template>
  <QDialog :model-value="open" @update:model-value="(value: boolean) => !value && emit('close')">
    <QCard flat bordered class="compare-panel" style="width: min(860px, 94vw)" role="dialog" aria-label="关卡比较">
      <QCardSection>
        <header class="compare-head">
          <h2>并排比较</h2>
          <QBtn flat round dense icon="close" aria-label="关闭比较" @click="emit('close')" />
        </header>
        <PageState v-if="loading" state="loading" />
        <PageState v-else-if="error" state="not-visible" text="这一组比较暂时打不开" />
        <div v-else-if="detailA && detailB" class="compare-body">
          <CompareSide :level="detailA" :diff-labels="diffA" />
          <span class="compare-divider" aria-hidden="true">vs</span>
          <CompareSide :level="detailB" :diff-labels="diffB" />
        </div>
      </QCardSection>
    </QCard>
  </QDialog>
</template>

<style scoped lang="sass">
.compare-panel
  max-height: 88vh
  overflow: auto

.compare-head
  display: flex
  justify-content: space-between
  align-items: center
  h2
    margin: 0
    font-size: 18px

.compare-body
  display: grid
  grid-template-columns: 1fr auto 1fr
  gap: 12px
  align-items: stretch
  margin-top: 12px

.compare-divider
  align-self: center
  background: #eceff1
  border-radius: 999px
  padding: 4px 10px
  font-size: 12px
  color: #78909c

@media (max-width: 640px)
  .compare-body
    grid-template-columns: 1fr
  .compare-divider
    justify-self: center
</style>
