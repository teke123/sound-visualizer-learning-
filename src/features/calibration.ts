/**
 * 音域标定流程（D-20 / FR-1006）：
 * 读取标定文本 → 录音（复用 recorder，40 秒上限）→ 上传 purpose=calibration
 * → POST {audioId}；成功刷新 context；CALIBRATION_FAIL 显示原因与重录指引；
 * 网络或服务失败保留 blob 可重试。
 */
import { computed, ref } from 'vue'
import { detectionApi, type PitchCalibrationInfo } from '@/api'
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
  /** 质检未通过（CALIBRATION_FAIL）：终态，需重新录制 */
  | 'rejected'

/**
 * 单项信号检查。
 *
 * 后端 `app/acoustics/analysis.py` 的 `check_signal()` 实际返回 `pass` 与实测值
 * （volume.dbfs / noise.snrDb / clipping.ratio / duration.valueSec），
 * 但 OpenAPI 只声明了 `advice` 一个字段，生成的类型因此丢掉了它们。
 * 这里补一份前端本地类型来读取真实字段，并已反馈给后端补声明。
 */
export interface CalibrationSignalCheck {
  pass?: boolean
  advice?: string | null
  /** volume：整体 RMS，dBFS */
  dbfs?: number
  /** noise：信噪比，dB */
  snrDb?: number
  /** clipping：削波采样占比 */
  ratio?: number
  /** duration：实际时长，秒 */
  valueSec?: number
  /** duration：期望时长，秒 */
  expectedSec?: number | null
}

export interface CalibrationFailSignalEx {
  verdict?: 'fail' | 'pass' | null
  volume?: CalibrationSignalCheck | null
  noise?: CalibrationSignalCheck | null
  clipping?: CalibrationSignalCheck | null
  duration?: CalibrationSignalCheck | null
  /** 后端已下发未通过的维度键名，OpenAPI 同样未声明 */
  failedDimensions?: string[]
}

export interface CalibrationFailResultEx {
  reason: string
  signal?: CalibrationFailSignalEx | null
}

/** 与后端 analysis.py 的阈值保持一致，仅用于把实测值讲清楚 */
const SIGNAL_RULES: Record<string, { label: string; expect: string; read: (c: CalibrationSignalCheck) => string | null }> = {
  volume: {
    label: '录音音量',
    expect: '−38 ~ −2 dBFS',
    read: (c) => (typeof c.dbfs === 'number' ? `${c.dbfs} dBFS` : null),
  },
  noise: {
    label: '环境噪声',
    expect: '信噪比 ≥ 10 dB',
    read: (c) => (typeof c.snrDb === 'number' ? `信噪比 ${c.snrDb} dB` : null),
  },
  clipping: {
    label: '爆音（削波）',
    expect: '削波占比 ≤ 0.5%',
    read: (c) => (typeof c.ratio === 'number' ? `削波占比 ${(c.ratio * 100).toFixed(2)}%` : null),
  },
  duration: {
    label: '朗读时长',
    expect: '1.5 ~ 40 秒',
    read: (c) => (typeof c.valueSec === 'number' ? `${c.valueSec} 秒` : null),
  },
}

export interface CalibrationFailCheck {
  key: string
  label: string
  advice: string | null
  /** 实测值，例如「−42.1 dBFS」 */
  measured: string | null
  /** 该项合格要求，例如「−38 ~ −2 dBFS」 */
  expect: string
}

export function useCalibration() {
  const recorder = useRecorderStore()
  const contextStore = useContextStore()

  const phase = ref<CalibrationPhase>('loading-text')
  const info = ref<PitchCalibrationInfo | null>(null)
  const error = ref<unknown>(null)
  /** CALIBRATION_FAIL 的原因与重录指引（主因，保留兼容） */
  const failAdvice = ref<string | null>(null)
  /** 逐项未通过明细：主因在前，其余按顺序随后 */
  const failChecks = ref<CalibrationFailCheck[]>([])
  /** 后端给出的总原因 */
  const failReason = ref<string | null>(null)
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
    failChecks.value = []
    failReason.value = null
    error.value = null
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
    failChecks.value = []
    failReason.value = null
    let audioId: string | undefined
    try {
      phase.value = 'uploading'
      const ext = recorder.mimeType?.includes('mp4') ? 'm4a' : 'webm'
      const uploaded = await detectionApi.uploadAudio(recorder.blob, 'calibration', `calibration.${ext}`)
      audioId = uploaded.data.audioId
      phase.value = 'submitting'
      const res = await detectionApi.submitCalibration({ audioId })
      if (res.code === 'CALIBRATION_FAIL') {
        const data = res.data as CalibrationFailResultEx
        const signal = data.signal ?? {}
        const failedKeys = new Set(signal.failedDimensions ?? [])

        // 逐项取未通过的检查：优先用 failedDimensions，缺失时退回「有 advice 即未通过」
        // （后端 advice 在通过时为 null，所以这个回退是可靠的）
        const checks: CalibrationFailCheck[] = []
        for (const key of Object.keys(SIGNAL_RULES)) {
          const check = signal[key as keyof CalibrationFailSignalEx] as CalibrationSignalCheck | null | undefined
          if (!check || typeof check !== 'object') continue
          const isFailed = failedKeys.size > 0
            ? failedKeys.has(key)
            : check.pass === false || Boolean(check.advice)
          if (!isFailed) continue
          const rule = SIGNAL_RULES[key]
          if (!rule) continue
          checks.push({
            key,
            label: rule.label,
            advice: check.advice ?? null,
            measured: rule.read(check),
            expect: rule.expect,
          })
        }

        failChecks.value = checks
        failReason.value = data.reason ?? null
        // 主因：第一条未通过项的指引；没有明细时退回后端总原因，再退回兜底文案
        failAdvice.value = checks[0]?.advice ?? data.reason ?? '这次标定没有得出有效音域，请再试一次。'
        recorder.reRecord()
        // 明确的失败终态：不再静默回到初始态
        phase.value = 'rejected'
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
    failChecks.value = []
    failReason.value = null
    result.value = null
  }

  return {
    phase,
    info,
    result,
    error,
    failAdvice,
    failChecks,
    failReason,
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
