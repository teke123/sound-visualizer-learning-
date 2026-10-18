<script setup lang="ts">
/**
 * QualityVerdict：录音质量友好提示卡（FR-1001 / FR-1301）。
 * 只作辅助提示、不拦截评分与声学可视化：展示音量偏小 / 底噪偏大 / 爆音 /
 * 时长过短等信号状态与朗读完整性提示，并给出环境改善建议。
 * 信号维为结构化检查项（dbfs/snrDb/ratio/valueSec），朗读维为漏读/增读等列表。
 */
import { computed } from 'vue'
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

/** 检测到的质量提示项（label + 改善建议） */
const tips = computed(() => {
  const found: Array<{ label: string; note: string }> = []
  for (const { key, label } of SIGNAL_CHECKS) {
    const check = props.quality.signal?.[key]
    if (check && check.pass === false) {
      found.push({ label, note: check.advice ?? '建议调整后重录' })
    }
  }
  const reading = props.quality.reading
  if (reading) {
    for (const { key, label } of READING_CHECKS) {
      const value = reading[key]
      if (value === true || (Array.isArray(value) && value.length > 0)) {
        found.push({
          label,
          note: Array.isArray(value) ? `（${value.join('、')}）` : (reading.advice ?? '未按要求朗读'),
        })
      }
    }
    if (found.some((item) => READING_CHECKS.some((rc) => rc.label === item.label)) && reading.advice) {
      found.push({ label: '建议', note: reading.advice })
    }
  }
  return found
})

const clean = computed(() => tips.value.length === 0)
const advice = computed(
  () => props.quality.advice || '找一个安静的地方，嘴巴离麦克风约一拳距离，用平常说话的音量再录一次，声学图像会更清晰。',
)
</script>

<template>
  <section class="quality-verdict" :class="clean ? 'clean' : 'tips'" aria-label="录音质量提示">
    <div class="verdict-head">
      <span class="verdict-icon" aria-hidden="true">{{ clean ? '✅' : '💡' }}</span>
      <div>
        <p class="verdict-title">{{ clean ? '录音质量良好' : '录音质量小提示' }}</p>
        <p class="verdict-sub">
          {{ clean ? '下面展示本次评分与声学对比。' : '这些提示只关于录音环境与朗读完整性，不影响本次评分和对比展示。' }}
        </p>
      </div>
    </div>
    <ul v-if="tips.length > 0" class="issue-list">
      <li v-for="issue in tips" :key="issue.label + issue.note">
        <span class="issue-label">{{ issue.label }}</span>
        <span>{{ issue.note }}</span>
      </li>
    </ul>
    <div v-if="!clean" class="advice">
      <h3>怎样录得更清楚</h3>
      <p>{{ advice }}</p>
    </div>
  </section>
</template>

<style scoped lang="sass">
.quality-verdict
  border-radius: 12px
  padding: 16px
  border: 1px solid
  &.clean
    background: #f1f8e9
    border-color: #c5e1a5
  &.tips
    background: #fffde7
    border-color: #ffe082

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
  white-space: nowrap

.advice
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
