/**
 * 个人标定会话流程（FR-1006 / 个人标定流程改造方案）：
 * 四个元音 i/u/a/ü 各 2 条（一致性不足补第 3 条）+ 一段音域短文，共约 9 条录音。
 * 会话持久化在服务端：打开面板时创建或恢复进行中的会话，刷新后从服务端继续。
 * 每条录音独立验收（accepted / retry_take / additional_take_required /
 * vowel_dispersed）；任务齐备后发起最终计算，轮询 GET 至完成，成功刷新 context。
 * 网络或服务失败保留 blob 可重试。
 */
import { computed, ref } from 'vue'
import {
  detectionApi,
  type CalibrationNextTask,
  type CalibrationSessionView,
  type CalibrationTakeOutcome,
} from '@/api'
import { RECORD_MAX_MS, useRecorderStore } from '@/stores/recorder'
import { useContextStore } from '@/stores/context'

export type CalibrationPhase =
  | 'loading'
  | 'intro'
  | 'recording'
  | 'recorded'
  | 'uploading'
  | 'submitting'
  | 'computing'
  | 'success'
  | 'failed'

const COMPLETE_POLL_INTERVAL_MS = 2000
const COMPLETE_POLL_MAX = 60

export function useCalibration() {
  const recorder = useRecorderStore()
  const contextStore = useContextStore()

  const phase = ref<CalibrationPhase>('loading')
  const session = ref<CalibrationSessionView | null>(null)
  const error = ref<unknown>(null)
  /** retry_take 的原因与重录指引（当前任务内重录，不影响其它任务进度） */
  const failAdvice = ref<string | null>(null)
  /** vowel_dispersed 提示：几条录音差异大，需要重录该元音 */
  const dispersedNotice = ref(false)
  /** 成功结果（音域区间 + 四个元音完成状态展示） */
  const result = ref<CalibrationSessionView['result'] | null>(null)
  const busy = computed(() => phase.value === 'uploading' || phase.value === 'submitting')

  /** 当前待办任务（会话视图的 nextTask） */
  const currentTask = computed<CalibrationNextTask | null>(() => session.value?.nextTask ?? null)

  function signalAdvice(data: CalibrationTakeOutcome): string {
    const s = data.signal
    return [
      s?.volume?.advice,
      s?.noise?.advice,
      s?.clipping?.advice,
      s?.duration?.advice,
    ]
      .filter(Boolean)
      .join('；')
  }

  /** 创建或恢复进行中的会话；已完成会话直接展示结果 */
  async function openSession(): Promise<void> {
    phase.value = 'loading'
    error.value = null
    failAdvice.value = null
    dispersedNotice.value = false
    result.value = null
    try {
      const res = await detectionApi.createCalibrationSession()
      session.value = res.data
      if (res.data.status === 'completed' && res.data.result) {
        result.value = res.data.result
        phase.value = 'success'
      } else {
        phase.value = 'intro'
      }
    } catch (err) {
      error.value = err
      phase.value = 'failed'
    }
  }

  async function startRecording(): Promise<void> {
    failAdvice.value = null
    dispersedNotice.value = false
    const maxMs = currentTask.value?.kind === 'pitch'
      ? RECORD_MAX_MS.calibration
      : RECORD_MAX_MS.calibrationVowel
    const ok = await recorder.start({ maxMs })
    if (ok) phase.value = 'recording'
  }

  function onStop() {
    if (phase.value === 'recording' && recorder.blob) phase.value = 'recorded'
  }

  function discard() {
    recorder.reRecord()
    phase.value = 'intro'
  }

  /** 发起最终计算并轮询至完成；失败时停留在 computing，可重试 */
  async function requestCompletion(): Promise<boolean> {
    if (!session.value) return false
    phase.value = 'computing'
    try {
      const res = await detectionApi.completeCalibrationSession(session.value.sessionId)
      session.value = res.data
    } catch (err) {
      error.value = err
      phase.value = 'failed'
      return false
    }
    // 轮询 GET 查询完成结果（方案 §接口与会话：complete 返回会话状态，由 GET 查询）
    for (let i = 0; i < COMPLETE_POLL_MAX; i += 1) {
      if (session.value.calcState === 'done') break
      if (session.value.calcState === 'failed') return false
      await new Promise((resolve) => setTimeout(resolve, COMPLETE_POLL_INTERVAL_MS))
      try {
        const poll = await detectionApi.getCalibrationSession(session.value!.sessionId)
        session.value = poll.data
      } catch (err) {
        error.value = err
        phase.value = 'failed'
        return false
      }
    }
    if (session.value.calcState === 'done' && session.value.result) {
      result.value = session.value.result
      phase.value = 'success'
      await contextStore.refresh()
      recorder.release()
      return true
    }
    // 超时仍未完成：停在 computing，用户可手动重试
    return false
  }

  /** 提交当前任务的单条录音；网络/服务失败保留 blob，可再次调用重试 */
  async function submit(): Promise<boolean> {
    const task = currentTask.value
    if (!recorder.blob || !session.value || !task) return false
    error.value = null
    failAdvice.value = null
    dispersedNotice.value = false
    try {
      phase.value = 'uploading'
      // 录音链路输出为前端封装的无损 WAV（见 stores/recorder.ts）
      const filename = task.kind === 'pitch' ? 'calibration-pitch.wav' : `calibration-${task.vowel}.wav`
      const uploaded = await detectionApi.uploadAudio(recorder.blob, 'calibration', filename)
      phase.value = 'submitting'
      const res = await detectionApi.submitCalibrationTake({
        sessionId: session.value.sessionId,
        audioId: uploaded.data.audioId,
        kind: task.kind,
        vowel: task.vowel ?? undefined,
      })
      const data = res.data
      session.value = data.session
      if (data.outcome === 'retry_take') {
        failAdvice.value = signalAdvice(data) || data.reason || '这条录音没有通过质量检查，请重录。'
        recorder.reRecord()
        phase.value = 'intro'
        return false
      }
      recorder.reRecord()
      if (data.outcome === 'vowel_dispersed') {
        dispersedNotice.value = true
        phase.value = 'intro'
        return false
      }
      // accepted / additional_take_required：任务齐备则发起最终计算
      if (!session.value.nextTask) return await requestCompletion()
      phase.value = 'intro'
      return true
    } catch (err) {
      error.value = err
      // 上传或提交失败：保留 blob 可重试（§6.3）
      phase.value = recorder.blob ? 'recorded' : 'failed'
      return false
    }
  }

  function reset() {
    recorder.release()
    phase.value = 'loading'
    error.value = null
    failAdvice.value = null
    dispersedNotice.value = false
    result.value = null
    session.value = null
  }

  return {
    phase,
    session,
    currentTask,
    result,
    error,
    failAdvice,
    dispersedNotice,
    busy,
    recorder,
    openSession,
    startRecording,
    onStop,
    discard,
    submit,
    requestCompletion,
    reset,
  }
}
