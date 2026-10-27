<script setup lang="ts">
/**
 * QualityVerdict：录音质量提示（FR-1001 / FR-1301）。
 * 只以小标签列出检测到的质量项（信号维 + 朗读维），不作卡片、不带底色，
 * 不展示标题、说明与改善建议；不拦截评分与声学可视化。
 * 无任何质量问题时整块不渲染。
 */
import { computed } from 'vue'
import { QBadge } from 'quasar'
import type { Quality } from '@/api'

const props = defineProps<{ quality: Quality }>()

const SIGNAL_CHECKS: Array<{ key: 'volume' | 'noise' | 'clipping' | 'duration'; label: string }> = [
  { key: 'volume', label: '音量偏小' },
  { key: 'noise', label: '底噪偏大' },
  { key: 'clipping', label: '爆音' },
  { key: 'duration', label: '时长过短' },
]

const READING_CHECKS: Array<{ key: 'missing' | 'extra' | 'repeated' | 'replaced' | 'disordered'; label: string }> = [
  { key: 'missing', label: '漏读' },
  { key: 'extra', label: '增读' },
  { key: 'repeated', label: '回读' },
  { key: 'replaced', label: '替换' },
  { key: 'disordered', label: '乱读' },
]

/** 检测到的质量提示项标签 */
const tags = computed(() => {
  const found: string[] = []
  for (const { key, label } of SIGNAL_CHECKS) {
    const check = props.quality.signal?.[key]
    if (check && check.pass === false) found.push(label)
  }
  const reading = props.quality.reading
  if (reading) {
    for (const { key, label } of READING_CHECKS) {
      const value = reading[key]
      if (value === true || (Array.isArray(value) && value.length > 0)) found.push(label)
    }
  }
  return found
})
</script>

<template>
  <div v-if="tags.length > 0" class="quality-tags" aria-label="录音质量提示">
    <QBadge v-for="tag in tags" :key="tag" outline color="warning" :label="tag" />
  </div>
</template>

<style scoped lang="sass">
.quality-tags
  display: flex
  gap: 6px
  flex-wrap: wrap
</style>
