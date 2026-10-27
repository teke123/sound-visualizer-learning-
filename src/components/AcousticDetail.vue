<script setup lang="ts">
/**
 * AcousticDetail：P09 折叠区（FD-16）：按 audioId 读取原始 F0（Hz）与共振峰，
 * 展开时才请求；共振峰散点图直接 <img> 引用。
 */
import { ref, watch } from 'vue'
import { QBtn } from 'quasar'
import { ApiError, audioF0Url, audioFormantsPngUrl, audioFormantsUrl, detectionApi } from '@/api'
import type { F0Response, FormantsResponse } from '@/api'

const props = defineProps<{ audioId: string }>()

const expanded = ref(false)
const loading = ref(false)
const f0 = ref<F0Response | null>(null)
const formants = ref<FormantsResponse | null>(null)
const error = ref<unknown>(null)

watch(expanded, async (open) => {
  if (!open || f0.value || loading.value) return
  loading.value = true
  error.value = null
  const [f0Res, formantsRes] = await Promise.allSettled([
    detectionApi.rawF0(props.audioId),
    detectionApi.rawFormants(props.audioId),
  ])
  if (f0Res.status === 'fulfilled') f0.value = f0Res.value.data
  if (formantsRes.status === 'fulfilled') formants.value = formantsRes.value.data
  if (f0Res.status === 'rejected' && formantsRes.status === 'rejected') error.value = f0Res.reason
  loading.value = false
})

function voicedSummary(): string {
  if (!f0.value) return ''
  const ranges = f0.value.voicedRanges
  if (!ranges || ranges.length === 0) return '未检出浊音段'
  // 契约为 [start, end] 对（OpenAPI 只能表达 number[][]），缺项的条目跳过
  const total = ranges.reduce((sum, r) => (r.length >= 2 ? sum + (r[1]! - r[0]!) : sum), 0)
  return `${ranges.length} 个浊音段，共约 ${total.toFixed(2)} 秒`
}

function hzSummary(): string {
  if (!f0.value) return ''
  const values = f0.value.frames.map((frame) => frame.hz).filter((hz): hz is number => typeof hz === 'number')
  if (values.length === 0) return '无有效 F0 帧'
  const min = Math.min(...values)
  const max = Math.max(...values)
  const avg = values.reduce((sum, v) => sum + v, 0) / values.length
  return `F0 范围 ${min.toFixed(0)}–${max.toFixed(0)} Hz，均值 ${avg.toFixed(0)} Hz（hop ${f0.value.hopMs}ms，算法 ${f0.value.algorithmVersion}）`
}

const formantsPng = () => audioFormantsPngUrl(props.audioId)
const isApiError = (e: unknown) => e instanceof ApiError
</script>

<template>
  <section class="acoustic-detail" aria-label="原始声学特征（选看）">
    <QBtn flat no-caps class="ac-toggle" :aria-expanded="expanded" @click="expanded = !expanded">
      {{ expanded ? '收起原始声学数据' : '展开原始声学数据（选看，原始 F0 / 共振峰）' }}
    </QBtn>
    <div v-if="expanded" class="ac-body">
      <p v-if="loading" class="ac-loading">读取中…</p>
      <template v-if="f0">
        <h4>原始音高（F0）</h4>
        <p>{{ hzSummary() }}</p>
        <p>{{ voicedSummary() }}</p>
      </template>
      <template v-if="formants">
        <h4>原始共振峰</h4>
        <img :src="formantsPng()" alt="共振峰散点图" loading="lazy" class="ac-png" />
      </template>
      <p v-if="error && !f0" class="ac-error">
        原始数据读取失败{{ isApiError(error) && error.requestId ? `（requestId：${error.requestId}）` : '' }}。
      </p>
    </div>
  </section>
</template>

<style scoped lang="sass">
.acoustic-detail
  border: 1px dashed #cfd8dc
  border-radius: 10px
  background: #fafafa

.ac-toggle
  width: 100%
  min-height: 48px
  font-size: 14px
  color: #546e7a

.ac-body
  padding: 0 16px 14px
  h4
    margin: 10px 0 4px
    font-size: 14px
    color: #37474f
  p
    font-size: 13px
    color: #607d8b
    margin: 2px 0

.ac-loading, .ac-error
  color: #90a4ae

.ac-error
  color: #c62828

.ac-png
  max-width: 100%
  border-radius: 8px
  background: #fff
</style>
