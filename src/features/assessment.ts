/**
 * useAssessmentFlow：录音检测流程状态机（P05 内嵌录音区，FR-902–906 / D-20）。
 *
 *   Idle → (未标定：可选) Calibrating → MicRequest → Ready → Recording → Recorded
 *        → Uploading → Submitting → Navigate(/result/:id)
 *   分支：CONTENT_VERSION_CHANGED → VersionChanged → 刷新任务后 Ready
 *         可重试失败 → Failed（同 submissionId 重试）
 *   标定可跳过（D-20）：跳过标定直接进入录音，提交流程不因未标定阻断。
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

  const busy = computed(() => state.value === 'uploading' || state.value === 'submitting')

  /* ------------------------------ 进入流程 ------------------------------ */

  async function begin() {
    flowError.value = null
    if (!contextStore.calibrationValid) {
      // 未标定：先引导标定（可跳过，D-20）；跳过后直接进入录音
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
      submissionId: submissionId.value,
    })
    const recording = res.data.recording
    setSubmittedEntry({
      recordingId: recording.recordingId,
      submissionId: submissionId.value,
      audioId: audioId.value,
      levelId: level.id,
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
    if (error.code === 'FILE_TOO_LARGE' || error.code === 'DECODE_FAILED') {
      flowError.value = { copy: { title: error.message, hint: '请重新录制一段较短的录音再提交。' }, requestId: error.requestId, retryable: false }
      state.value = 'recorded'
      return
    }
    if (error.code === 'AUTH_REQUIRED') {
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

  /* ------------------------------ 标定回调 ------------------------------ */

  function onCalibrationDone() {
    void contextStore.refresh()
    void requestMic()
  }

  /** 跳过标定，直接录音（D-20：未标定不阻断提交流程） */
  function onCalibrationCancel() {
    void requestMic()
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
    onCalibrationDone,
    onCalibrationCancel,
  }
}
