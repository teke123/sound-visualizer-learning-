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
  <section class="phenomena-list vs-card" aria-label="检测到的现象">
    <h3>听到了什么</h3>
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
  padding: 24px

.phenomena-list h3
  font-size: 20px
  font-weight: 900
  letter-spacing: -0.3px
  margin: 0 0 10px

.phen-empty
  color: var(--vs-green)
  font-size: 13.5px
  margin: 0

.phen-list
  list-style: none
  margin: 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 10px

.phen-item
  border: 1px solid var(--vs-line)
  border-left: 4px solid var(--vs-sand)
  border-radius: 8px
  background: var(--vs-panel)
  padding: 10px 14px

.phen-label
  font-weight: 700
  font-size: 15px
  color: var(--vs-ink)

.phen-position
  margin-left: 8px
  font-size: 13px
  color: var(--vs-brand-d)

.phen-desc
  margin: 4px 0 0
  font-size: 13.5px
  color: var(--vs-ink2)
  line-height: 1.7
</style>
