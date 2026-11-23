<script setup lang="ts">
/**
 * SearchBox：首页与搜索页共用的白色搜索条（V3）：
 * 图标 + 输入框 + 深咖啡「搜一个音」按钮；回车与点击都走同一出口。
 */
import { ref, watch } from 'vue'
import AppIcon from '@/components/ui/AppIcon.vue'

const props = defineProps<{
  /** 受控初值（P02 从 URL q 同步） */
  modelValue?: string
  placeholder?: string
}>()

const emit = defineEmits<{ (e: 'search', q: string): void }>()

const query = ref(props.modelValue ?? '')

watch(
  () => props.modelValue,
  (value) => {
    if (value !== undefined) query.value = value
  },
)

function submit() {
  const q = query.value.trim()
  if (q) emit('search', q)
}
</script>

<template>
  <form class="searchbar" role="search" @submit.prevent="submit">
    <AppIcon name="search" size="sm" class="s-ico" />
    <input
      v-model="query"
      type="search"
      :placeholder="placeholder ?? '输入汉字、拼音或关卡名，例如「a」「妈」「翘舌」'"
      aria-label="搜索关卡"
      enterkeyhint="search"
    />
    <button type="submit" class="vs-btn">搜一个音</button>
  </form>
</template>

<style scoped lang="sass">
.searchbar
  width: 100%
  max-width: 560px
  box-sizing: border-box
  display: flex
  gap: 8px
  align-items: center
  background: var(--vs-field)
  border: 1px solid var(--vs-line2)
  border-radius: 8px
  padding: 8px
  box-shadow: var(--vs-sh-2)
  transition: border-color 0.16s var(--vs-ease), box-shadow 0.16s var(--vs-ease)

.searchbar:focus-within
  border-color: var(--vs-line-strong)
  box-shadow: 0 0 0 4px rgba(var(--vs-glow-rgb), 0.08), var(--vs-sh-2)

.s-ico
  color: var(--vs-mute)
  margin-left: 8px

input
  flex: 1
  border: none
  outline: none
  background: transparent
  font-family: inherit
  font-size: 15px
  color: var(--vs-ink)
  min-width: 0
  height: 40px

input::placeholder
  color: var(--vs-mute)
  font-size: 13.5px

.vs-btn
  flex: none

@media (max-width: 560px)
  .searchbar
    padding: 6px
    gap: 6px
  input::placeholder
    font-size: 12px
  .vs-btn
    padding: 0 12px
    font-size: 13px
</style>
