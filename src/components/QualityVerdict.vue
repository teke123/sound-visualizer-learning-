<script setup lang="ts">
/**
 * QualityVerdict：质量结论先行（FR-1001 / FR-1301）。
 * 质量结论与本关分数分开显示；不合格显示「本次不能评」+ 原因 + 重录指引，不显示分数。
 */
import { computed } from 'vue'
import type { Quality } from '@/api'

const props = defineProps<{ quality: Quality }>()

const DIMENSION_LABELS: Array<{ key: keyof Quality['signal'] | keyof Quality['reading']; label: string }> = [
  { key: 'volume', label: '音量' },
  { key: 'noise', label: '噪音' },
  { key: 'clipping', label: '爆音' },
  { key: 'duration', label: '时长' },
  { key: 'omission', label: '漏读' },
  { key: 'addition', label: '增读' },
  { key: 'reread', label: '回读' },
  { key: 'substitution', label: '替换' },
  { key: 'gibberish', label: '乱读' },
]

const issues = computed(() => {
  const found: Array<{ label: string; note: string }> = []
  for (const { key, label } of DIMENSION_LABELS) {
    const signalNote = props.quality.signal[key as keyof Quality['signal']]
    if (signalNote) found.push({ label, note: signalNote })
    const readingNote = props.quality.reading[key as keyof Quality['reading']]
    if (readingNote) found.push({ label, note: readingNote })
  }
  return found
})

const passed = computed(() => props.quality.verdict === 'pass')
</script>

<template>
  <section class="quality-verdict" :class="passed ? 'pass' : 'fail'" aria-label="录音质量结论">
    <div class="verdict-head">
      <span class="verdict-icon" aria-hidden="true">{{ passed ? '✅' : '🛑' }}</span>
      <div>
        <p class="verdict-title">{{ passed ? '录音质量合格' : '本次不能评' }}</p>
        <p class="verdict-sub">
          {{ passed ? '下面展示本次评分与曲线对比。' : '这次录音不满足评分要求——这不是发音问题，请按下面的指引重录一次。' }}
        </p>
      </div>
    </div>
    <ul v-if="issues.length > 0" class="issue-list">
      <li v-for="issue in issues" :key="issue.label">
        <span class="issue-label">{{ issue.label }}</span>
        <span>{{ issue.note }}</span>
      </li>
    </ul>
    <div v-if="!passed" class="retake">
      <h3>怎么重录</h3>
      <p>{{ quality.retakeAdvice || '找一个安静的地方，按页面上的朗读提示，用平常说话的音量再录一次。' }}</p>
    </div>
  </section>
</template>

<style scoped lang="sass">
.quality-verdict
  border-radius: 12px
  padding: 16px
  border: 1px solid
  &.pass
    background: #f1f8e9
    border-color: #c5e1a5
  &.fail
    background: #fff3e0
    border-color: #ffcc80

.verdict-head
  display: flex
  gap: 12px
  align-items: flex-start

.verdict-icon
  font-size: 26px

.verdict-title
  margin: 0
  font-size: 18px
  font-weight: 700

.verdict-sub
  margin: 4px 0 0
  font-size: 13px
  color: #5d4037

.issue-list
  list-style: none
  margin: 12px 0 0
  padding: 0
  display: flex
  flex-direction: column
  gap: 6px
  li
    display: flex
    gap: 10px
    font-size: 14px
    color: #5d4037

.issue-label
  background: #ffe0b2
  color: #8d5b00
  font-size: 12px
  border-radius: 4px
  padding: 1px 8px
  height: fit-content

.retake
  margin-top: 12px
  background: #fff
  border-radius: 8px
  padding: 10px 14px
  h3
    margin: 0 0 4px
    font-size: 14px
  p
    margin: 0
    font-size: 14px
    color: #37474f
</style>
