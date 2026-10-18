<script setup lang="ts">
/** SearchBox：P01 / P02 搜索入口（FR-203，提示“请输入拼音”；也支持汉字、关卡名） */
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
      placeholder="请输入拼音"
      aria-label="搜索关卡"
      enterkeyhint="search"
    />
    <button type="submit" class="search-btn" aria-label="搜索">
      <span class="material-icons" aria-hidden="true">search</span>
    </button>
  </form>
</template>

<style scoped lang="sass">
.search-box
  position: relative
  width: 100%
  max-width: 560px

.search-input
  width: 100%
  min-height: 46px
  padding: 6px 52px 6px 14px
  border: 2px solid #b2dfdb
  border-radius: 10px
  font-size: 15px
  outline: none
  box-sizing: border-box
  &:focus
    border-color: #00897b
  /* 隐藏 WebKit 原生清除按钮，避免与右侧图标按钮重叠 */
  &::-webkit-search-cancel-button
    display: none

.search-btn
  position: absolute
  top: 50%
  right: 5px
  transform: translateY(-50%)
  width: 34px
  height: 34px
  border: none
  border-radius: 8px
  background: #00897b
  color: #fff
  display: inline-flex
  align-items: center
  justify-content: center
  cursor: pointer
  &:hover
    background: #00796b

.material-icons
  font-size: 20px
</style>
