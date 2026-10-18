/**
 * 音域标定流程（D-20 / FR-1006 / docs/architecture/04 §6.3）：
 * 读取标定文本 → 录音（复用 recorder，40 秒上限）→ 上传 purpose=calibration
 * → POST {audioId}；成功刷新 context；CALIBRATION_FAIL 显示原因与重录指引；
 * 网络或服务失败保留 blob 可重试。
 */
import { computed, ref } from 'vue'
import { detectionApi, type CalibrationFailResult, type PitchCalibrationInfo } from '@/api'
import { RECORD_MAX_MS, useRecorderStore } from '@/stores/recorder'
import { useContextStore } from '@/stores/context'

export type CalibrationPhase =
  | 'loading-text'
  | 'intro'
  | 'recording'
  | 'recorded'
  | 'uploading'
  | 'submitting'
  | 'success'
  | 'failed'

export function useCalibration() {
  const recorder = useRecorderStore()
  const contextStore = useContextStore()

  const phase = ref<CalibrationPhase>('loading-text')
  const info = ref<PitchCalibrationInfo | null>(null)
  const error = ref<unknown>(null)
  /** CALIBRATION_FAIL 的原因与重录指引 */
  const failAdvice = ref<string | null>(null)
  /** 成功结果（音域区间展示） */
  const result = ref<{ pitchRange: { fLo: number; fHi: number } } | null>(null)
  const busy = computed(() => phase.value === 'uploading' || phase.value === 'submitting')

  async function loadText(): Promise<void> {
    phase.value = 'loading-text'
    error.value = null
    try {
      const res = await detectionApi.getCalibration()
      info.value = res.data
      phase.value = 'intro'
    } catch (err) {
      error.value = err
      phase.value = 'failed'
    }
  }

  async function startRecording(): Promise<void> {
    failAdvice.value = null
    const ok = await recorder.start({ maxMs: RECORD_MAX_MS.calibration })
    if (ok) phase.value = 'recording'
  }

  function onStop() {
    if (phase.value === 'recording' && recorder.blob) phase.value = 'recorded'
  }

  function discard() {
    recorder.reRecord()
    phase.value = recorder.status === 'ready' ? 'intro' : 'intro'
  }

  /** 提交标定；网络/服务失败保留 blob，可再次调用重试 */
  async function submit(): Promise<boolean> {
    if (!recorder.blob || !info.value) return false
    error.value = null
    failAdvice.value = null
    let audioId: string | undefined
    try {
      phase.value = 'uploading'
      const ext = recorder.mimeType?.includes('mp4') ? 'm4a' : 'webm'
      const uploaded = await detectionApi.uploadAudio(recorder.blob, 'calibration', `calibration.${ext}`)
      audioId = uploaded.data.audioId
      phase.value = 'submitting'
      const res = await detectionApi.submitCalibration({ audioId })
      if (res.code === 'CALIBRATION_FAIL') {
        const data = res.data as CalibrationFailResult
        const signalAdvice = [
          data.signal?.volume?.advice,
          data.signal?.noise?.advice,
          data.signal?.clipping?.advice,
          data.signal?.duration?.advice,
        ]
          .filter(Boolean)
          .join('；')
        failAdvice.value = signalAdvice || data.reason || '这次标定没有得出有效音域，请再试一次。'
        recorder.reRecord()
        phase.value = 'intro'
        return false
      }
      phase.value = 'success'
      result.value = res.data as { pitchRange: { fLo: number; fHi: number } }
      await contextStore.refresh()
      recorder.release()
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
    phase.value = 'loading-text'
    error.value = null
    failAdvice.value = null
    result.value = null
  }

  return {
    phase,
    info,
    result,
    error,
    failAdvice,
    busy,
    recorder,
    loadText,
    startRecording,
    onStop,
    discard,
    submit,
    reset,
  }
}
