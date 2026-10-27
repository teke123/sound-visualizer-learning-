/**
 * useAssessmentFlow：录音检测流程状态机（P05 内嵌录音区，FR-902–906 / D-20）。
 *
 *   Idle → (未标定：可选) Calibrating → MicRequest → Recording → Recorded
 *        （授权成功即刻开播，不停在待机；Ready 仅作开播失败时的回退态）
 *        → Uploading → Submitting → Navigate(/result/:id) 或 Submitted(页内结果)
 *   分支：CONTENT_VERSION_CHANGED → VersionChanged → 刷新任务后 Ready
 *         可重试失败 → Failed（同 submissionId 重试）
 *   标定可跳过（D-20）：跳过标定直接进入录音，提交流程不因未标定阻断。
 *   提交成功后的去向（docs §3.2 页内结果闭环）：
 *   - 未提供 onSubmitted → 跳转独立结果页（state='navigating'）；
 *   - 提供 onSubmitted → 停留本页（state='submitted'），由页面在 #result 区
 *     挂 InlineResultSection 展示结果，「再录一次」经 reRecord 回到待录。
 */
import { computed, onScopeDispose, ref, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { ApiError, detectionApi, type LevelDetail } from '@/api'
import { RECORD_MAX_MS, useRecorderStore } from '@/stores/recorder'
import { useContextStore } from '@/stores/context'
import { uuid } from '@/utils'
import { setSubmittedEntry } from './submittedEntry'

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
  | 'submitted'

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
  /**
   * 提交成功后的页内闭环回调（docs §3.2）：提供时不跳转独立结果页，
   * 状态停在 'submitted'，由页面用 recordingId 在页内展示结果。
   */
  onSubmitted?: (recordingId: string) => void
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
    // 授权请求/录音已在途时忽略重复点击（一键直录后误双击不至于重复开播）
    if (state.value === 'mic-request' || state.value === 'calibrating' || state.value === 'recording') return
    flowError.value = null
    if (!contextStore.calibrationValid) {
      // 未标定：先引导标定（可跳过，D-20）；跳过后直接进入录音
      state.value = 'calibrating'
      return
    }
    await requestMic(true)
  }

  /**
   * 请求麦克风授权。autoStart = true 时授权成功即刻开始录音，
   * 不停在待机态（ready 仅在直接开播失败等异常时回退）。
   */
  async function requestMic(autoStart = false) {
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
    if (autoStart) {
      const started = await startRecording()
      if (!started) state.value = 'ready'
    } else {
      state.value = 'ready'
    }
  }

  /* -------------------------------- 录音 -------------------------------- */

  /** 开播成功返回 true（调用方可据此决定是否回退待机态） */
  async function startRecording(): Promise<boolean> {
    flowError.value = null
    const ok = await recorder.start({
      maxMs: RECORD_MAX_MS.recording,
      onAutoStop: () => {
        if (state.value === 'recording') state.value = 'recorded'
      },
    })
    if (ok) {
      // 一次录音生成一个 submissionId；audioId 是上一次上传成功后的缓存
      //（仅供「提交失败重试」复用，重录即作废），与本段录音不同生命周期
      submissionId.value = uuid()
      state.value = 'recording'
    }
    return ok
  }

  function stopRecording() {
    recorder.stop()
    if (state.value === 'recording') state.value = 'recorded'
  }

  function reRecord() {
    recorder.reRecord()
    submissionId.value = null
    // 重录即作废上一段录音：连同缓存的 audioId 一起清空，
    // 否则 submit() 里「audioId 已存在则跳过上传」会复用旧音频评分
    audioId.value = null
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
    recorder.release()
    if (options.onSubmitted) {
      // 页内结果闭环（§3.2）：不跳转，停在 submitted，由页面挂 InlineResultSection
      state.value = 'submitted'
      options.onSubmitted(recording.recordingId)
      return
    }
    state.value = 'navigating'
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
    void requestMic(true)
  }

  /** 跳过标定，直接录音（D-20：未标定不阻断提交流程） */
  function onCalibrationCancel() {
    void requestMic(true)
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
