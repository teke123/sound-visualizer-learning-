<script setup lang="ts">
/** PhenomenaList：可观察现象（FR-1004）：仅使用已检测维度，通俗表述来自后端 */
import type { Phenomenon } from '@/api'

const POSITION_LABELS: Record<string, string> = {
  overall: '整体',
  initial: '声母',
  final: '韵母',
  tone: '声调',
}

function positionText(item: Phenomenon): string {
  const part = item.position?.part
  if (!part) return item.syllable ?? ''
  const label = POSITION_LABELS[part] ?? part
  return item.syllable ? `「${item.syllable}」的${label}` : label
}

defineProps<{ phenomena: Phenomenon[] }>()
</script>

<template>
  <section class="phenomena-list" aria-label="检测到的现象">
    <h2>听到了什么</h2>
    <p v-if="phenomena.length === 0" class="phen-empty">本次没有检出明显问题，继续保持！</p>
    <ul v-else class="phen-list">
      <li v-for="(item, index) in phenomena" :key="`${item.tag}-${index}`" class="phen-item">
        <span class="phen-label">{{ item.tag }}</span>
        <span v-if="positionText(item)" class="phen-position">{{ positionText(item) }}</span>
        <p class="phen-desc">{{ item.description }}</p>
      </li>
    </ul>
  </section>
</template>

<style scoped lang="sass">
.phenomena-list
  h2
    font-size: 18px
    margin: 0 0 10px

.phen-empty
  color: #2e7d32
  font-size: 14px

.phen-list
  list-style: none
  margin: 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 10px

.phen-item
  border: 1px solid #eceff1
  border-left: 4px solid #ff8a65
  border-radius: 8px
  padding: 10px 14px

.phen-label
  font-weight: 700
  font-size: 15px

.phen-position
  margin-left: 8px
  font-size: 13px
  color: #00838f

.phen-desc
  margin: 4px 0 0
  font-size: 14px
  color: #455a64
</style>
