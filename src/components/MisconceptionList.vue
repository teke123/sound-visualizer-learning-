<script setup lang="ts">
/** MisconceptionList：误区（FR-608）：用可观察的话说「像什么、怎么改」，避免病理化表述 */
import type { Misconception } from '@/api'

defineProps<{ items: Misconception[] }>()
</script>

<template>
  <div class="misconception-list">
    <p v-if="items.length === 0" class="m-empty">本关暂无误区说明</p>
    <ul v-else class="m-list">
      <li v-for="(item, index) in items" :key="index" class="m-item">
        <p class="m-observable">👂 {{ item.phenomenon }}</p>
        <p class="m-fix">✅ 可以这样改：{{ item.fix }}</p>
      </li>
    </ul>
  </div>
</template>

<style scoped lang="sass">
.m-empty
  color: #90a4ae

.m-list
  list-style: none
  margin: 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 12px

.m-item
  border: 1px solid #eceff1
  border-radius: 10px
  padding: 12px 14px
  p
    margin: 4px 0

.m-observable
  color: #5d4037

.m-fix
  color: #2e7d32
</style>
