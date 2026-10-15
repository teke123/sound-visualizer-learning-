<script setup lang="ts">
/** SearchBox：P01 / P02 搜索入口（FR-203 提示可输入汉字、拼音或关卡名） */
import { ref } from 'vue'

const props = defineProps<{
  /** 受控初值（P02 从 URL q 同步） */
  modelValue?: string
}>()

const emit = defineEmits<{ (e: 'search', q: string): void }>()
const query = ref(props.modelValue ?? '')

function submit() {
  const q = query.value.trim()
  if (q) emit('search', q)
}
</script>

<template>
  <form class="search-box" role="search" @submit.prevent="submit">
    <input
      v-model="query"
      type="search"
      class="search-input"
      placeholder="搜一个音：可输入汉字、拼音或关卡名，例如 a、妈、翘舌"
      aria-label="搜索关卡"
      enterkeyhint="search"
    />
    <button type="submit" class="search-btn">搜一个音</button>
  </form>
</template>

<style scoped lang="sass">
.search-box
  display: flex
  gap: 8px
  width: 100%
  max-width: 560px

.search-input
  flex: 1
  min-height: 46px
  padding: 6px 14px
  border: 2px solid #b2dfdb
  border-radius: 10px
  font-size: 15px
  outline: none
  &:focus
    border-color: #00897b

.search-btn
  min-height: 46px
  padding: 6px 20px
  border: none
  border-radius: 10px
  background: #00897b
  color: #fff
  font-size: 15px
  font-weight: 600
  cursor: pointer
  &:hover
    background: #00796b
</style>
