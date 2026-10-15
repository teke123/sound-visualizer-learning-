/**
 * useAssessmentFlow：检测流程状态机（P05 内嵌与 P08 共用，docs/architecture/04 §6.2）。
 *
 *   Idle → (无有效音域) Calibrating → MicRequest → Ready → Recording → Recorded
 *        → Uploading → Submitting → Navigate(/result/:id)
 *   分支：CALIBRATION_REQUIRED → Calibrating（标定后自动重提交原 audioId/submissionId）
 *         CONTENT_VERSION_CHANGED → VersionChanged → 刷新任务后 Ready
 *         DETECTION_OFF / 429 → Blocked；可重试失败 → Failed（同 submissionId 重试）
 */
import { computed, onScopeDispose, ref, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, detectionApi, type LevelDetail } from '@/api'
import { RECORD_MAX_MS, useRecorderStore } from '@/stores/recorder'
import { useContextStore } from '@/stores/context'
import { uuid } from '@/utils'
import { setSubmittedEntry } from './result'

export type FlowState =
  | 'idle'
  | 'calibrating'
  | 'mic-request'
  | 'mic-denied'
  | 'ready'
  | 'recording'
  | 'recorded'
  | 'uploading'
  | 'submitting'
  | 'version-changed'
  | 'blocked'
  | 'failed'
  | 'navigating'

export interface FlowError {
  copy: { title: string; hint: string }
  requestId?: string
  /** true = 可在同页面用原 submissionId 重试；false = 需重新录音 */
  retryable: boolean
}

export interface AssessmentFlowOptions {
  level: Ref<LevelDetail>
  /** CONTENT_VERSION_CHANGED 后由页面重新拉取关卡详情 */
  reloadLevel: () => Promise<void>
}

export function useAssessmentFlow(options: AssessmentFlowOptions) {
  const router = useRouter()
  const recorder = useRecorderStore()
  const contextStore = useContextStore()

  const state = ref<FlowState>('idle')
  const submissionId = ref<string | null>(null)
  const audioId = ref<string | null>(null)
  const flowError = ref<FlowError | null>(null)
  /** 标定由检测流程触发时：成功后用原 audioId/submissionId 自动重提交 */
  const resubmitAfterCalibration = ref(false)

  const busy = computed(() => state.value === 'uploading' || state.value === 'submitting')

  /* ------------------------------ 进入流程 ------------------------------ */

  async function begin() {
    flowError.value = null
    if (!contextStore.calibrationValid) {
      resubmitAfterCalibration.value = false
      state.value = 'calibrating'
      return
    }
    await requestMic()
  }

  async function requestMic() {
    state.value = 'mic-request'
    const ok = await recorder.request()
    if (!ok) {
      state.value = recorder.status === 'denied' ? 'mic-denied' : 'failed'
      if (recorder.status === 'unsupported') {
        flowError.value = {
          copy: { title: '当前浏览器不支持录音', hint: '请使用新版 Chrome、Edge 或 Safari 打开本页。' },
          retryable: false,
        }
      }
      return
    }
    state.value = 'ready'
  }

  /* -------------------------------- 录音 -------------------------------- */

  async function startRecording() {
    flowError.value = null
    const ok = await recorder.start({
      maxMs: RECORD_MAX_MS.recording,
      onAutoStop: () => {
        if (state.value === 'recording') state.value = 'recorded'
      },
    })
    if (ok) {
      // 一次录音生成一个 submissionId，与 audioId 一起保留到跳转或重录
      submissionId.value = uuid()
      state.value = 'recording'
    }
  }

  function stopRecording() {
    recorder.stop()
    if (state.value === 'recording') state.value = 'recorded'
  }

  function reRecord() {
    recorder.reRecord()
    submissionId.value = null
    flowError.value = null
    state.value = recorder.status === 'ready' ? 'ready' : 'idle'
  }

  /* -------------------------------- 提交 -------------------------------- */

  async function submit(): Promise<void> {
    if (!recorder.blob || !submissionId.value) return
    flowError.value = null
    try {
      if (!audioId.value) {
        state.value = 'uploading'
        const ext = recorder.mimeType?.includes('mp4') ? 'm4a' : 'webm'
        const uploaded = await detectionApi.uploadAudio(
          recorder.blob,
          'recording',
          `take-${Date.now()}.${ext}`,
        )
        audioId.value = uploaded.data.audioId
      }
      state.value = 'submitting'
      await submitPayload()
    } catch (error) {
      onSubmitError(error)
    }
  }

  async function submitPayload(): Promise<void> {
    const level = options.level.value
    if (!audioId.value || !submissionId.value) return
    const res = await detectionApi.submitRecording({
      audioId: audioId.value,
      levelId: level.id,
      contentVersion: level.contentVersion,
      submissionId: submissionId.value,
    })
    const recording = res.data.recording
    setSubmittedEntry({
      recordingId: recording.recordingId,
      submissionId: submissionId.value,
      audioId: audioId.value,
      levelId: level.id,
      contentVersion: level.contentVersion,
    })
    state.value = 'navigating'
    recorder.release()
    await router.push(`/result/${recording.recordingId}`)
  }

  function onSubmitError(error: unknown) {
    if (!(error instanceof ApiError)) {
      flowError.value = {
        copy: { title: '提交失败', hint: '请重试；录音仍保留在页面上。' },
        retryable: true,
      }
      state.value = recorder.blob ? 'recorded' : 'failed'
      return
    }
    // 409 CALIBRATION_REQUIRED：进入标定，成功后自动重提交（FD-06）
    if (error.code === 'CALIBRATION_REQUIRED') {
      resubmitAfterCalibration.value = true
      state.value = 'calibrating'
      return
    }
    if (error.code === 'CONTENT_VERSION_CHANGED') {
      state.value = 'version-changed'
      void options.reloadLevel().finally(() => {
        // 丢弃旧录音，按新内容重录
        reRecord()
      })
      return
    }
    if (error.code === 'IDEMPOTENCY_CONFLICT') {
      // 客户端缺陷处理：重新生成 submissionId 并提示重提交
      submissionId.value = uuid()
      flowError.value = {
        copy: { title: '提交记录冲突', hint: '已生成新的提交标识，请再点一次提交。' },
        retryable: true,
      }
      state.value = 'recorded'
      return
    }
    if (error.code === 'DETECTION_OFF' || error.code === 'RATE_LIMITED' || error.code === 'SERVER_BUSY') {
      flowError.value = { copy: { title: error.message, hint: error.nextStep ?? '请稍后重试。' }, requestId: error.requestId, retryable: true }
      state.value = 'blocked'
      return
    }
    if (error.code === 'FILE_TOO_LARGE' || error.code === 'DECODE_FAILED') {
      flowError.value = { copy: { title: error.message, hint: '请重新录制一段较短的录音再提交。' }, requestId: error.requestId, retryable: false }
      state.value = 'recorded'
      return
    }
    if (error.code === 'AUTH_REQUIRED' || error.code === 'CONSENT_REQUIRED') {
      contextStore.onAuthError(error)
    }
    const retryAfter = error.retryAfterMs
    flowError.value = {
      copy: {
        title: error.message || '提交失败',
        hint: retryAfter
          ? `约 ${Math.max(1, Math.round(retryAfter / 1000))} 秒后可重试；录音仍保留在页面上。`
          : '可直接重试；录音仍保留在页面上。',
      },
      requestId: error.requestId,
      retryable: true,
    }
    state.value = recorder.blob ? 'recorded' : 'failed'
  }

  /** 同键重试：保留 audioId 与 submissionId（仅在提交页面内，FD-15） */
  async function retry(): Promise<void> {
    await submit()
  }

  /* ------------------------------ 标定回调 ------------------------------ */

  function onCalibrationDone() {
    void contextStore.refresh()
    if (resubmitAfterCalibration.value) {
      resubmitAfterCalibration.value = false
      // 标定成功：用原 audioId 与原 submissionId 自动重提交，无需重录
      state.value = 'submitting'
      submitPayload().catch(onSubmitError)
      return
    }
    void requestMic()
  }

  function onCalibrationCancel() {
    resubmitAfterCalibration.value = false
    state.value = 'idle'
  }

  /* ---------------------------- 离开页面保护 ---------------------------- */

  function onBeforeUnload(event: BeforeUnloadEvent) {
    if (recorder.hasPendingTake && state.value !== 'navigating') {
      event.preventDefault()
    }
  }
  window.addEventListener('beforeunload', onBeforeUnload)
  onScopeDispose(() => {
    window.removeEventListener('beforeunload', onBeforeUnload)
  })

  return {
    state,
    submissionId,
    audioId,
    flowError,
    busy,
    recorder,
    begin,
    requestMic,
    startRecording,
    stopRecording,
    reRecord,
    submit,
    retry,
    onCalibrationDone,
    onCalibrationCancel,
  }
}
