<script setup lang="ts">
/**
 * RecorderPanel：录音控制面板（FR-905 / FR-907，P05 录音区）。
 * 状态由 useAssessmentFlow 提供；录音中与已录制阶段常驻
 * RealtimeAcousticCanvas（实时 → 定格回看，试听时画播放游标）；
 * 上传与提交期间禁用按钮防重复提交；有未提交录音时 beforeunload 由流程挂载。
 */
import { computed, onBeforeUnmount } from 'vue'
import type { FlowError, FlowState } from '@/features/assessment'
import { RECORD_MAX_MS, type RecorderStatus } from '@/stores/recorder'
import { usePlayerStore } from '@/stores/player'
import type { PitchRangeHz, ToneValue } from '@/utils/realtimeAcoustics'
import { errorCopy } from '@/copy/usePageCopy'
import AppIcon from '@/components/ui/AppIcon.vue'
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
  /** 是否已登录：录音与结果都要落账号，未登录时入口直接改为「登录后录音」 */
  authenticated: boolean
  /** 实时反馈主视图：声母关看包络，其余看音高轨迹（FR-907 按关卡聚焦） */
  focus?: 'pitch' | 'onset'
  /** 本关目标调型（可推导时），画五度刻度 */
  targetTone?: ToneValue | null
  /** 个人音域（前置标定）：实时纵轴按音域锚定五度（docs §6.1） */
  rangeHz?: PitchRangeHz | null
}>()

const emit = defineEmits<{
  (e: 'begin'): void
  (e: 'login'): void
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

const startLabel = computed(() => {
  if (props.state === 'mic-request') return '正在开启麦克风…'
  return props.authenticated ? '点一下开始录' : '登录后录音'
})
</script>

<template>
  <div class="recorder-panel">
    <!-- 未开始（mic-request：授权在途，防重复点击）；按钮下方附一行环境提醒 -->
    <div v-if="state === 'idle' || state === 'mic-request'" class="panel-center">
      <button
        type="button"
        class="rec-btn"
        :class="{ busy: state === 'mic-request' }"
        :disabled="state === 'mic-request'"
        @click="authenticated ? emit('begin') : emit('login')"
      >
        <AppIcon name="mic" size="lg" />
        <span>{{ startLabel }}</span>
      </button>
      <p v-if="!authenticated" class="auth-hint">录音与检测结果会存到你的账号里，先登录再开始。</p>
      <RecordingTips />
    </div>

    <!-- 未登录 / 会话过期：录音入口改为登录引导（登录后回跳本关重新录） -->
    <div v-else-if="state === 'auth-required'" class="failed-box auth-box">
      <p class="state-note">录音检测需要登录</p>
      <p class="state-sub">
        录音、检测结果与声音档案都保存在账号里。登录后会回到本关，重新录一遍即可提交。
      </p>
      <div class="panel-row">
        <button type="button" class="vs-btn" @click="emit('login')">去登录</button>
      </div>
    </div>

    <!-- 麦克风被拒 -->
    <div v-else-if="state === 'mic-denied'">
      <MicPermissionGuide />
      <div class="panel-center">
        <button type="button" class="vs-btn vs-btn--ghost" @click="emit('retry-mic')">已开启，重试</button>
      </div>
    </div>

    <!-- 待机（回退态）：直录开播失败或重录后落在此处，点击立即开始录音 -->
    <div v-else-if="state === 'ready'" class="panel-center">
      <button type="button" class="rec-btn" @click="emit('start')">
        <AppIcon name="mic" size="lg" />
        <span>点一下开始录</span>
      </button>
      <RecordingTips />
    </div>

    <!-- 录音中 / 已录制：实时反馈画布常驻 -->
    <div v-if="canvasVisible" class="recording-box" :class="{ recorded: !isRecording }">
      <p v-if="isRecording" class="recording-hint">
        正在录。读完提示词后点「停止」，{{ Math.round(maxMs / 1000) }} 秒会自动停止。
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
        <div class="progress"><div class="progress-fill" :style="{ width: `${progressPercent()}%` }" /></div>
        <button type="button" class="vs-btn vs-btn--ghost" @click="emit('stop')">停止</button>
      </div>
      <template v-else>
        <p class="recorded-hint">已录好一段（{{ elapsedSec() }} 秒），先试听一下再提交：</p>
        <!-- 提交失败但录音保留（state 停在 recorded）时，错误必须就地可见，否则表现为「点了没反应」 -->
        <template v-if="error">
          <p class="state-note err">{{ error.copy.title }}</p>
          <p class="state-sub">{{ error.copy.hint }}</p>
          <p v-if="error.requestId" class="request-id">requestId：{{ error.requestId }}</p>
        </template>
        <div class="panel-row">
          <button
            v-if="blobUrl"
            type="button"
            class="vs-btn vs-btn--ghost"
            @click="player.play({ key: 'take-preview', url: blobUrl!, label: '试听' })"
          >
            <AppIcon :name="player.isCurrent('take-preview') ? 'pause' : 'play'" size="sm" />
            {{ player.isCurrent('take-preview') ? '暂停试听' : '试听' }}
          </button>
          <button type="button" class="vs-btn vs-btn--ghost" :disabled="busy" @click="emit('re-record')">
            <AppIcon name="mic" size="sm" />重录
          </button>
        </div>
        <button type="button" class="vs-btn submit-btn" :disabled="busy || !hasTake" @click="emit('submit')">
          {{ busy ? '提交中…' : '提交检测' }}
        </button>
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
        <button v-if="hasTake" type="button" class="vs-btn" @click="emit('submit')">重试提交</button>
        <button v-else type="button" class="vs-btn vs-btn--ghost" @click="emit('begin')">重新开始</button>
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
  gap: 12px
  padding: 8px 0

.panel-row
  display: flex
  gap: 12px
  justify-content: center
  flex-wrap: wrap

/* 圆形录音键：深咖啡渐变，录音时换成品牌红并呼吸（对应原型 .rec-btn） */
.rec-btn
  width: 136px
  height: 136px
  border: none
  cursor: pointer
  border-radius: 50%
  color: var(--vs-on-coffee)
  font-family: inherit
  font-size: 14px
  font-weight: 700
  line-height: 1.5
  background: linear-gradient(180deg, var(--vs-coffee-a), var(--vs-coffee-b))
  box-shadow: 0 10px 26px rgba(var(--vs-shadow-rgb), 0.32)
  display: flex
  flex-direction: column
  align-items: center
  justify-content: center
  gap: 6px
  transition: transform 0.2s var(--vs-ease), background 0.2s var(--vs-ease)
  -webkit-tap-highlight-color: transparent
  user-select: none

.rec-btn:hover:not(:disabled)
  transform: translateY(-2px)

.rec-btn.busy,
.rec-btn:disabled
  opacity: 0.45
  cursor: default

.recording-box
  display: flex
  flex-direction: column
  align-items: center
  gap: 12px
  border: 1px solid var(--vs-danger-line)
  border-radius: 8px
  padding: 16px
  background: var(--vs-danger-soft)
  &.recorded
    border-color: var(--vs-line2)
    background: var(--vs-card)

.recording-hint
  margin: 0
  font-size: 13.5px
  color: var(--vs-ink2)

.recording-meta
  display: flex
  align-items: center
  gap: 10px
  width: 100%

.elapsed
  font-variant-numeric: tabular-nums
  color: var(--vs-brand)
  font-weight: 700
  min-width: 44px

.progress
  flex: 1
  height: 6px
  background: var(--vs-line2)
  border-radius: 3px
  overflow: hidden

.progress-fill
  height: 100%
  background: var(--vs-brand)
  transition: width 0.12s linear

.recorded-hint
  margin: 0
  font-size: 13.5px
  color: var(--vs-ink2)

.submit-btn
  width: 100%

.state-note
  margin: 0
  font-size: 15px
  font-weight: 600
  &.err
    color: var(--vs-brand-d)

.state-sub
  margin: 4px 0 0
  font-size: 13px
  color: var(--vs-sub)
  text-align: center

.request-id
  font-size: 12px
  color: var(--vs-mute)

.failed-box
  display: flex
  flex-direction: column
  align-items: center
  gap: 6px
  border: 1px solid var(--vs-danger-line)
  background: var(--vs-danger-soft)
  border-radius: 8px
  padding: 16px

.recorder-error
  color: var(--vs-brand-d)
  font-size: 13px
  margin: 0

.auth-hint
  margin: 0
  font-size: 13px
  color: var(--vs-sub)
  text-align: center

.auth-box
  border-color: var(--vs-brand-line)
  background: var(--vs-brand-soft)
</style>
