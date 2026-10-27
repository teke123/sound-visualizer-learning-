<script setup lang="ts">
/**
 * RecorderPanel：录音控制面板（FR-905 / FR-907，P05 录音区）。
 * 状态由 useAssessmentFlow 提供；录音中与已录制阶段常驻
 * RealtimeAcousticCanvas（实时 → 定格回看，试听时画播放游标）；
 * 上传与提交期间禁用按钮防重复提交；有未提交录音时 beforeunload 由流程挂载。
 */
import { computed, onBeforeUnmount } from 'vue'
import { QBtn } from 'quasar'
import type { FlowError, FlowState } from '@/features/assessment'
import { RECORD_MAX_MS, type RecorderStatus } from '@/stores/recorder'
import { usePlayerStore } from '@/stores/player'
import type { PitchRangeHz, ToneValue } from '@/utils/realtimeAcoustics'
import { errorCopy } from '@/copy/usePageCopy'
import RealtimeAcousticCanvas from '@/components/RealtimeAcousticCanvas.vue'
import RecordingTips from './RecordingTips.vue'
import MicPermissionGuide from './MicPermissionGuide.vue'

const props = defineProps<{
  state: FlowState
  recorderStatus: RecorderStatus
  elapsedMs: number
  maxMs?: number
  blobUrl: string | null
  hasTake: boolean
  error: FlowError | null
  busy: boolean
  recorderError: string | null
  /** 实时反馈主视图：声母关看包络，其余看音高轨迹（FR-907 按关卡聚焦） */
  focus?: 'pitch' | 'onset'
  /** 本关目标调型（可推导时），画五度刻度 */
  targetTone?: ToneValue | null
  /** 个人音域（前置标定）：实时纵轴按音域锚定五度（docs §6.1） */
  rangeHz?: PitchRangeHz | null
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

const maxMs = props.maxMs ?? RECORD_MAX_MS.recording

const isRecording = computed(() => props.state === 'recording')
/** 定格回看：canvas 常驻到提交/重录为止 */
const canvasVisible = computed(
  () => props.state === 'recording' || props.state === 'recorded' || props.state === 'uploading' || props.state === 'submitting',
)

/** 试听游标：只在本面板试听源上显示 */
const playheadSec = computed(() =>
  player.current?.key === 'take-preview' ? player.currentTime : null,
)
const takeDurationSec = computed(() =>
  player.current?.key === 'take-preview' && player.durationSec > 0 ? player.durationSec : props.elapsedMs / 1000,
)

onBeforeUnmount(() => player.stop())

const elapsedSec = () => (props.elapsedMs / 1000).toFixed(1)
const progressPercent = () => Math.min(100, (props.elapsedMs / maxMs) * 100)
</script>

<template>
  <div class="recorder-panel">
    <!-- 未开始（mic-request：授权在途，防重复点击）；按钮下方附一行环境提醒 -->
    <div v-if="state === 'idle' || state === 'mic-request'" class="panel-center">
      <QBtn
        unelevated
        no-caps
        rounded
        color="red-8"
        class="record-btn primary"
        :disable="state === 'mic-request'"
        @click="emit('begin')"
      >
        {{ state === 'mic-request' ? '正在开启麦克风…' : '开始录音' }}
      </QBtn>
      <RecordingTips />
    </div>

    <!-- 麦克风被拒 -->
    <div v-else-if="state === 'mic-denied'">
      <MicPermissionGuide />
      <div class="panel-center">
        <QBtn outline no-caps rounded color="blue-grey-4" text-color="blue-grey-9" class="record-btn" @click="emit('retry-mic')">已开启，重试</QBtn>
      </div>
    </div>

    <!-- 待机（回退态）：直录开播失败或重录后落在此处，点击立即开始录音 -->
    <div v-else-if="state === 'ready'" class="panel-center">
      <QBtn unelevated no-caps rounded color="red-8" class="record-btn primary" @click="emit('start')">● 开始录音</QBtn>
      <RecordingTips />
    </div>

    <!-- 录音中 / 已录制：实时反馈画布常驻 -->
    <div v-if="canvasVisible" class="recording-box" :class="{ recorded: !isRecording }">
      <p v-if="isRecording" class="recording-hint">
        录音中…边发声边看着轨迹调整，读完提示词后点「停止」，{{ Math.round(maxMs / 1000) }} 秒会自动停止
      </p>
      <RealtimeAcousticCanvas
        :active="isRecording"
        :focus="focus ?? 'pitch'"
        :target-tone="targetTone ?? null"
        :range-hz="rangeHz ?? null"
        :playhead-sec="playheadSec"
        :take-duration-sec="takeDurationSec"
      />
      <div v-if="isRecording" class="recording-meta">
        <span class="elapsed">{{ elapsedSec() }}s</span>
        <div class="progress"><div class="progress-fill" :style="{ width: `${progressPercent()}%` }"></div></div>
        <QBtn unelevated no-caps rounded color="blue-grey-8" class="record-btn stop" @click="emit('stop')">■ 停止</QBtn>
      </div>
      <template v-else>
        <p class="recorded-hint">已录好一段（{{ elapsedSec() }} 秒），先试听一下再提交：</p>
        <div class="panel-row">
          <QBtn
            v-if="blobUrl"
            outline
            no-caps
            rounded
            color="blue-grey-4"
            text-color="blue-grey-9"
            class="record-btn"
            @click="player.play({ key: 'take-preview', url: blobUrl!, label: '试听' })"
          >
            {{ player.isCurrent('take-preview') ? '⏸ 暂停试听' : '▶ 试听' }}
          </QBtn>
          <QBtn outline no-caps rounded color="blue-grey-4" text-color="blue-grey-9" class="record-btn" :disable="busy" @click="emit('re-record')">重录</QBtn>
        </div>
        <QBtn
          unelevated
          no-caps
          rounded
          color="red-8"
          class="record-btn primary submit"
          :disable="busy || !hasTake"
          @click="emit('submit')"
        >
          {{ busy ? '提交中…' : '提交检测' }}
        </QBtn>
      </template>
    </div>

    <!-- 版本变化：丢弃旧录音，刷新后回待机 -->
    <div v-else-if="state === 'version-changed'" class="panel-center">
      <p class="state-note">关卡内容刚刚更新，正在刷新任务…请稍后按新内容重录。</p>
    </div>

    <!-- 已提交（页内闭环）：录音区收起，结果区原地展开（FR-611），无需提示文案 -->

    <!-- 失败 -->
    <div v-else-if="state === 'failed' || error" class="failed-box">
      <p class="state-note err">{{ error?.copy.title ?? recorderError ?? '出错了' }}</p>
      <p class="state-sub">{{ error?.copy.hint ?? '请重试。' }}</p>
      <p v-if="error?.requestId" class="request-id">requestId：{{ error.requestId }}</p>
      <div class="panel-row">
        <QBtn v-if="hasTake" unelevated no-caps rounded color="red-8" class="record-btn primary" @click="emit('submit')">重试提交</QBtn>
        <QBtn v-else outline no-caps rounded color="blue-grey-4" text-color="blue-grey-9" class="record-btn" @click="emit('begin')">重新开始</QBtn>
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
  font-size: 16px
  /* 原版 .record-btn.primary（实底红 #d32f2f）字重 700 */
  &.primary
    font-weight: 700
  &.submit
    margin-top: 4px

.recording-box
  display: flex
  flex-direction: column
  align-items: center
  gap: 10px
  border: 2px solid #ffcdd2
  border-radius: 12px
  padding: 14px
  &.recorded
    border-color: #b2dfdb
    background: #ffffff

.recording-hint
  margin: 0
  font-size: 14px
  color: #5d4037

.recording-meta
  display: flex
  align-items: center
  gap: 10px
  width: 100%

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

.recorded-hint
  margin: 0
  font-size: 14px
  color: #5d4037

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

.failed-box
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
