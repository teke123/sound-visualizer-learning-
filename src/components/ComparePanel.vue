<script setup lang="ts">
/**
 * ComparePanel：两关示范与构形并排比较（FR-703 / FD-05）。
 * P03 / P05 / P06 共用；打开方式 ?compare=L13,L14（可分享，后退即关闭）。
 */
import { QDialog } from 'quasar'
import PageState from './PageState.vue'
import CompareSide from './CompareSide.vue'

defineProps<{
  open: boolean
  detailA: import('@/api').LevelDetail | null
  detailB: import('@/api').LevelDetail | null
  loading: boolean
  error: unknown
}>()

const emit = defineEmits<{ (e: 'close'): void }>()
</script>

<template>
  <QDialog :model-value="open" @update:model-value="(value: boolean) => !value && emit('close')">
    <div class="compare-panel" role="dialog" aria-label="关卡比较">
      <header class="compare-head">
        <h2>并排比较</h2>
        <button type="button" class="compare-close" aria-label="关闭比较" @click="emit('close')">✕</button>
      </header>
      <PageState v-if="loading" state="loading" />
      <PageState v-else-if="error" state="not-visible" text="这一组比较暂时打不开" />
      <div v-else-if="detailA && detailB" class="compare-body">
        <CompareSide :level="detailA" />
        <span class="compare-divider" aria-hidden="true">vs</span>
        <CompareSide :level="detailB" />
      </div>
    </div>
  </QDialog>
</template>

<style scoped lang="sass">
.compare-panel
  background: #fff
  border-radius: 14px
  width: min(860px, 94vw)
  max-height: 88vh
  overflow: auto
  padding: 18px

.compare-head
  display: flex
  justify-content: space-between
  align-items: center
  h2
    margin: 0
    font-size: 18px

.compare-close
  min-width: 44px
  min-height: 44px
  border: none
  background: none
  font-size: 18px
  cursor: pointer
  color: #78909c

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
