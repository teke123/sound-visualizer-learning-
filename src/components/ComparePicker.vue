<script setup lang="ts">
/** ComparePicker：同关存档两条选择（最多选 2，先选 A 后选 B） */
import { ref } from 'vue'
import type { ArchiveRecordingSummary } from '@/api'
import { formatDateTime } from '@/utils'

const props = defineProps<{ items: ArchiveRecordingSummary[] }>()
const emit = defineEmits<{ (e: 'pick', a: string, b: string): void }>()

const selected = ref<string[]>([])

function toggle(id: string) {
  if (selected.value.includes(id)) {
    selected.value = selected.value.filter((x) => x !== id)
  } else {
    selected.value = [...selected.value.slice(-1), id]
  }
}

function compare() {
  if (selected.value.length === 2) emit('pick', selected.value[0]!, selected.value[1]!)
}

function label(item: ArchiveRecordingSummary): string {
  const score = typeof item.score === 'number' ? ` · ${Math.round(item.score)}分` : ''
  return `${formatDateTime(item.createdAt ?? undefined)}${score}`
}
</script>

<template>
  <div class="compare-picker">
    <span class="cp-label">选两条比较：</span>
    <button
      v-for="item in items"
      :key="item.recordingId"
      type="button"
      :class="['cp-chip', { active: selected.includes(item.recordingId) }]"
      @click="toggle(item.recordingId)"
    >
      {{ label(item) }}
    </button>
    <button type="button" class="cp-go" :disabled="selected.length !== 2" @click="compare">比较</button>
  </div>
</template>

<style scoped lang="sass">
.compare-picker
  display: flex
  gap: 8px
  align-items: center
  flex-wrap: wrap

.cp-label
  font-size: 13px
  color: #78909c

.cp-chip
  min-height: 40px
  padding: 2px 12px
  border: 1px solid #cfd8dc
  border-radius: 999px
  background: #fff
  cursor: pointer
  font-size: 12px
  &.active
    border-color: #0288d1
    background: #e1f5fe
    color: #01579b

.cp-go
  min-height: 40px
  padding: 2px 16px
  border: none
  border-radius: 8px
  background: #0288d1
  color: #fff
  cursor: pointer
  &:disabled
    opacity: 0.45
    cursor: default
</style>
