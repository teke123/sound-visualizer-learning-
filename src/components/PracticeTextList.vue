<script setup lang="ts">
/** PracticeTextList：跟着练（FR-605 改版）：仅展示发音步骤与方法的纯文本列表 */
defineProps<{ steps: string[] }>()
</script>

<template>
  <div class="practice-text-list">
    <p v-if="steps.length === 0" class="practice-empty">本关暂无练习步骤</p>
    <ol v-else class="practice-list">
      <li v-for="(text, index) in steps" :key="index" class="practice-item">
        <span class="practice-no">{{ index + 1 }}</span>
        <p class="practice-text">{{ text }}</p>
      </li>
    </ol>
  </div>
</template>

<style scoped lang="sass">
.practice-empty
  color: #90a4ae

.practice-list
  list-style: none
  margin: 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 10px

.practice-item
  display: flex
  gap: 10px
  align-items: baseline

.practice-no
  flex-shrink: 0
  font-size: 13px
  color: #90a4ae
  font-variant-numeric: tabular-nums

.practice-text
  margin: 0
  line-height: 1.8
  color: #37474f
</style>
