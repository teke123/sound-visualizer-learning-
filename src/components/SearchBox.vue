<script setup lang="ts">
/** SearchBox：P01 / P02 搜索入口（FR-203，提示“请输入拼音”；也支持汉字、关卡名） */
import { ref } from 'vue'
import { QBtn, QInput } from 'quasar'

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
    <QInput
      v-model="query"
      outlined
      placeholder="请输入拼音"
      aria-label="搜索关卡"
      enterkeyhint="search"
    >
      <template #append>
        <QBtn type="submit" unelevated color="primary" icon="search" aria-label="搜索" />
      </template>
    </QInput>
  </form>
</template>

<style scoped lang="sass">
.search-box
  width: 100%
  max-width: 560px
</style>
