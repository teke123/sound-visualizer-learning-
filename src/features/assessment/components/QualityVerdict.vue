<script setup lang="ts">
/**
 * QualityVerdict：录音质量提示（FR-1001 / FR-1301）。
 * 只以小标签列出检测到的质量项（信号维 + 朗读维），不作卡片、不带底色，
 * 不展示标题、说明与改善建议；不拦截评分与声学可视化。
 * 无任何质量问题时整块不渲染。
 */
import { computed } from 'vue'
import type { Quality } from '@/api'
import AppIcon from '@/components/ui/AppIcon.vue'

const props = defineProps<{ quality: Quality }>()

const SIGNAL_CHECKS: Array<{ key: 'volume' | 'noise' | 'clipping' | 'duration' | 'bandwidth'; label: string }> = [
  { key: 'volume', label: '音量偏小' },
  { key: 'noise', label: '底噪偏大' },
  { key: 'clipping', label: '爆音' },
  { key: 'duration', label: '时长过短' },
  { key: 'bandwidth', label: '疑似蓝牙耳机录音' },
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
    <span class="quality-head"><AppIcon name="info" size="sm" />录音质量提示</span>
    <span v-for="tag in tags" :key="tag" class="vs-tag quality-tag">{{ tag }}</span>
  </div>
</template>

<style scoped lang="sass">
.quality-tags
  display: flex
  align-items: center
  gap: 6px
  flex-wrap: wrap
  background: var(--vs-amber-soft)
  border: 1px solid var(--vs-line2)
  border-radius: 8px
  padding: 10px 14px

.quality-head
  display: inline-flex
  align-items: center
  gap: 4px
  font-size: 12.5px
  font-weight: 600
  color: var(--vs-amber-ink)

.quality-tag
  background: var(--vs-on-coffee)
  color: var(--vs-amber-ink)
</style>
