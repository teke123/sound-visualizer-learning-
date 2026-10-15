<script setup lang="ts">
/** ProcessingStage：检查录音 / 评分中 / 分析曲线（FR-906 / D-19），含超时与重试说明 */
import { computed } from 'vue'

const props = defineProps<{
  stage?: string | null
  retryAfterMs?: number
}>()

const STAGE_LABELS: Record<string, string> = {
  queued: '排队中',
  signal_check: '检查录音',
  scoring: '评分中',
  analyzing: '分析曲线',
  finalizing: '整理结果',
}

const label = computed(() => (props.stage ? STAGE_LABELS[props.stage] ?? '处理中' : '处理中'))
const retryHint = computed(() =>
  props.retryAfterMs ? `约 ${Math.max(1, Math.round(props.retryAfterMs / 1000))} 秒后自动查询` : '稍后自动查询结果',
)
</script>

<template>
  <div class="processing-stage" role="status" aria-live="polite">
    <span class="stage-spinner" aria-hidden="true"></span>
    <div class="stage-text">
      <p class="stage-label">{{ label }}</p>
      <p class="stage-sub">{{ retryHint }}；超过 30 秒会按失败处理，可重试。</p>
      <p class="stage-sub muted">你可以离开本页，之后从「声音档案 / 本会话记录」回来看结果。</p>
    </div>
  </div>
</template>

<style scoped lang="sass">
.processing-stage
  display: flex
  align-items: center
  gap: 16px
  padding: 28px 18px
  border: 1px solid #eceff1
  border-radius: 12px
  background: #fff

.stage-spinner
  width: 32px
  height: 32px
  border: 4px solid #b2dfdb
  border-top-color: #00897b
  border-radius: 50%
  animation: stage-spin 0.9s linear infinite
  flex-shrink: 0

@keyframes stage-spin
  to
    transform: rotate(360deg)

.stage-label
  margin: 0
  font-size: 17px
  font-weight: 700
  color: #00695c

.stage-sub
  margin: 4px 0 0
  font-size: 13px
  color: #78909c
  &.muted
    color: #b0bec5
</style>
