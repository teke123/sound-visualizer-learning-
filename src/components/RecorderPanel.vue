<script setup lang="ts">
/**
 * RecorderPanel：录音控制面板（FR-905，P05 / P08 共用）。
 * 状态由 useAssessmentFlow 提供；实时波形 canvas + AnalyserNode；
 * 上传与提交期间禁用按钮防重复提交；有未提交录音时 beforeunload 由流程挂载。
 */
import { onBeforeUnmount, ref, watch } from 'vue'
import type { FlowError, FlowState } from '@/features/assessment'
import { RECORD_MAX_MS, type RecorderStatus } from '@/stores/recorder'
import { usePlayerStore } from '@/stores/player'
import { errorCopy } from '@/copy/usePageCopy'
import RecordingTips from './RecordingTips.vue'
import MicPermissionGuide from './MicPermissionGuide.vue'

const props = defineProps<{
  state: FlowState
  recorderStatus: RecorderStatus
  elapsedMs: number
  maxMs?: number
  blobUrl: string | null
  hasTake: boolean
  waveform: number[]
  error: FlowError | null
  busy: boolean
  recorderError: string | null
}>()

const emit = defineEmits<{
  (e: 'begin'): void
  (e: 'retry-mic'): void
  (e: 'start'): void
  (e: 'stop'): void
  (e: 're-record'): void
  (e: 'submit'): void
}>()

const player = usePlayerStore()
const canvas = ref<HTMLCanvasElement | null>(null)
const showTips = ref(true)

const maxMs = props.maxMs ?? RECORD_MAX_MS.recording

function draw() {
  const el = canvas.value
  if (!el) return
  const ctx = el.getContext('2d')
  if (!ctx) return
  const { width, height } = el
  ctx.clearRect(0, 0, width, height)
  const data = props.waveform.slice(-120)
  const barWidth = width / 120
  ctx.fillStyle = '#26a69a'
  data.forEach((value, index) => {
    const barHeight = Math.max(2, value * height * 1.6)
    ctx.fillRect(index * barWidth, (height - barHeight) / 2, Math.max(1, barWidth - 1), barHeight)
  })
  requestAnimationFrame(draw)
}

watch(
  () => props.recorderStatus,
  (status) => {
    if (status === 'recording') {
      showTips.value = false
      requestAnimationFrame(draw)
    }
  },
  { immediate: true },
)
watch(canvas, (el) => {
  if (el) requestAnimationFrame(draw)
})
onBeforeUnmount(() => player.stop())

const elapsedSec = () => (props.elapsedMs / 1000).toFixed(1)
const progressPercent = () => Math.min(100, (props.elapsedMs / maxMs) * 100)
</script>

<template>
  <div class="recorder-panel">
    <RecordingTips v-if="showTips && state !== 'recording'" />

    <!-- 未开始 -->
    <div v-if="state === 'idle' || state === 'mic-request'" class="panel-center">
      <button type="button" class="record-btn primary" @click="emit('begin')">开始录音</button>
    </div>

    <!-- 麦克风被拒 -->
    <div v-else-if="state === 'mic-denied'">
      <MicPermissionGuide />
      <div class="panel-center">
        <button type="button" class="record-btn" @click="emit('retry-mic')">已开启，重试</button>
      </div>
    </div>

    <!-- 待机 -->
    <div v-else-if="state === 'ready'" class="panel-center">
      <button type="button" class="record-btn primary" @click="emit('start')">● 开始录音</button>
    </div>

    <!-- 录音中 -->
    <div v-else-if="state === 'recording'" class="recording-box">
      <p class="recording-hint">录音中…读完提示词后点「停止」，{{ Math.round(maxMs / 1000) }} 秒会自动停止</p>
      <canvas ref="canvas" class="waveform" width="360" height="72" aria-label="录音音量波形"></canvas>
      <div class="recording-meta">
        <span class="elapsed">{{ elapsedSec() }}s</span>
        <div class="progress"><div class="progress-fill" :style="{ width: `${progressPercent()}%` }"></div></div>
      </div>
      <button type="button" class="record-btn stop" @click="emit('stop')">■ 停止</button>
    </div>

    <!-- 已录制 -->
    <div v-else-if="state === 'recorded' || state === 'uploading' || state === 'submitting'" class="recorded-box">
      <p class="recorded-hint">已录好一段（{{ elapsedSec() }} 秒），先试听一下再提交：</p>
      <div class="panel-row">
        <button
          v-if="blobUrl"
          type="button"
          class="record-btn"
          @click="player.play({ key: 'take-preview', url: blobUrl!, label: '试听' })"
        >
          {{ player.isCurrent('take-preview') ? '⏸ 暂停试听' : '▶ 试听' }}
        </button>
        <button type="button" class="record-btn" :disabled="busy" @click="emit('re-record')">重录</button>
      </div>
      <button
        type="button"
        class="record-btn primary submit"
        :disabled="busy || !hasTake"
        @click="emit('submit')"
      >
        {{ busy ? '提交中…' : '提交检测' }}
      </button>
    </div>

    <!-- 版本变化：丢弃旧录音，刷新后回待机 -->
    <div v-else-if="state === 'version-changed'" class="panel-center">
      <p class="state-note">关卡内容刚刚更新，正在刷新任务…请稍后按新内容重录。</p>
    </div>

    <!-- 熔断 / 限流 -->
    <div v-else-if="state === 'blocked'" class="blocked-box">
      <p class="state-note err">{{ error?.copy.title ?? '录音检测暂停中' }}</p>
      <p class="state-sub">{{ error?.copy.hint ?? '学习内容不受影响，可先回到关卡继续学习。' }}</p>
      <div class="panel-row">
        <RouterLink v-if="error" to="/library" class="record-btn">先去学习</RouterLink>
      </div>
    </div>

    <!-- 失败 -->
    <div v-else-if="state === 'failed' || error" class="failed-box">
      <p class="state-note err">{{ error?.copy.title ?? recorderError ?? '出错了' }}</p>
      <p class="state-sub">{{ error?.copy.hint ?? '请重试。' }}</p>
      <p v-if="error?.requestId" class="request-id">requestId：{{ error.requestId }}</p>
      <div class="panel-row">
        <button v-if="hasTake" type="button" class="record-btn primary" @click="emit('submit')">重试提交</button>
        <button v-else type="button" class="record-btn" @click="emit('begin')">重新开始</button>
      </div>
    </div>

    <p v-if="recorderError && state !== 'failed'" class="recorder-error">{{ errorCopy(recorderError).title }}</p>
  </div>
</template>

<style scoped lang="sass">
.recorder-panel
  display: flex
  flex-direction: column
  gap: 14px

.panel-center
  display: flex
  flex-direction: column
  align-items: center
  gap: 10px
  padding: 8px 0

.panel-row
  display: flex
  gap: 12px
  justify-content: center
  flex-wrap: wrap

.record-btn
  min-height: 48px
  min-width: 120px
  padding: 6px 24px
  border-radius: 999px
  border: 2px solid #90a4ae
  background: #fff
  color: #37474f
  font-size: 16px
  cursor: pointer
  text-decoration: none
  display: inline-flex
  align-items: center
  justify-content: center
  &.primary
    border-color: #d32f2f
    background: #d32f2f
    color: #fff
    font-weight: 700
  &.stop
    border-color: #455a64
    background: #455a64
    color: #fff
  &.submit
    margin-top: 4px
  &:disabled
    opacity: 0.55
    cursor: default

.recording-box, .recorded-box
  display: flex
  flex-direction: column
  align-items: center
  gap: 10px
  border: 2px solid #ffcdd2
  border-radius: 12px
  padding: 14px

.recording-hint, .recorded-hint
  margin: 0
  font-size: 14px
  color: #5d4037

.waveform
  width: 100%
  max-width: 400px
  height: 72px
  background: #fafafa
  border-radius: 8px

.recording-meta
  display: flex
  align-items: center
  gap: 10px
  width: 100%
  max-width: 400px

.elapsed
  font-variant-numeric: tabular-nums
  color: #d32f2f
  font-weight: 700
  min-width: 44px

.progress
  flex: 1
  height: 6px
  background: #eceff1
  border-radius: 3px
  overflow: hidden

.progress-fill
  height: 100%
  background: #d32f2f
  transition: width 0.12s linear

.state-note
  margin: 0
  font-size: 15px
  &.err
    color: #c62828

.state-sub
  margin: 4px 0 0
  font-size: 13px
  color: #78909c
  text-align: center

.request-id
  font-size: 12px
  color: #b0bec5

.blocked-box, .failed-box
  display: flex
  flex-direction: column
  align-items: center
  gap: 6px
  border: 1px solid #ffcdd2
  background: #fff5f5
  border-radius: 10px
  padding: 14px

.recorder-error
  color: #c62828
  font-size: 13px
  margin: 0
</style>
