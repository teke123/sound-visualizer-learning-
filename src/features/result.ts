/**
 * useRecordingResult：按 recordingId 读取与轮询结果（docs/architecture/04 §6.4）。
 * 202 → ProcessingStage + 按 Retry-After（缺省 2 秒）轮询；
 * 页面隐藏时暂停，恢复可见时立即查询。
 * 从提交页面跳转而来的 submissionId 与负载经内存传递（FD-15：跨页面只提供重新录音）。
 */
import { onScopeDispose, ref, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useDocumentVisibility } from '@vueuse/core'
import { ApiError, DEFAULT_RETRY_AFTER_MS, detectionApi } from '@/api'
import type { AssessmentResult, RecordingDTO } from '@/api'
import { useContextStore } from '@/stores/context'
import { useLevelsStore } from '@/stores/levels'

/** 提交页面 → 结果页的内存交接（刷新/直接打开后为 null，只提供重新录音） */
export interface SubmittedEntry {
  recordingId: string
  submissionId: string
  audioId: string
  levelId: string
}

let submittedEntry: SubmittedEntry | null = null

export function setSubmittedEntry(entry: SubmittedEntry | null) {
  submittedEntry = entry
}

export function getSubmittedEntry(): SubmittedEntry | null {
  return submittedEntry
}

export type ResultPhase = 'loading' | 'processing' | 'completed' | 'failed' | 'not-found'

export function useRecordingResult(recordingId: Ref<string>) {
  const router = useRouter()
  const contextStore = useContextStore()
  const levelsStore = useLevelsStore()

  const phase = ref<ResultPhase>('loading')
  const recording = ref<RecordingDTO | null>(null)
  const result = ref<AssessmentResult | null>(null)
  const stage = ref<string | null>(null)
  const error = ref<unknown>(null)
  const entry = ref<SubmittedEntry | null>(getSubmittedEntry())

  let timer: number | null = null
  let pollHandle: number | null = null
  const visibility = useDocumentVisibility()

  function clearTimer() {
    if (timer !== null) window.clearTimeout(timer)
    timer = null
  }

  async function fetchOnce() {
    clearTimer()
    try {
      const res = await detectionApi.getRecording(recordingId.value)
      if (res.status === 202) {
        phase.value = 'processing'
        recording.value = res.data.recording ?? null
        stage.value = res.data.recording?.stage ?? null
        schedulePoll(res.retryAfterMs ?? DEFAULT_RETRY_AFTER_MS)
        return
      }
      const { recording: rec, result: rst } = res.data
      recording.value = rec
      result.value = rst ?? null
      stage.value = null
      phase.value = 'completed'
    } catch (err) {
      if (err instanceof ApiError && (err.status === 404 || err.code === 'NOT_FOUND')) {
        phase.value = 'not-found'
        return
      }
      if (err instanceof ApiError && err.code === 'TIMEOUT') {
        // 504：可重试失败（提交页面内可「重试」，否则重新录音）
        phase.value = 'failed'
        error.value = err
        return
      }
      // failed 记录按真实状态码返回并带 {recording}
      if (err instanceof ApiError && err.data) {
        const data = err.data as { recording?: RecordingDTO }
        if (data.recording) {
          recording.value = data.recording
          error.value = err
          phase.value = 'failed'
          return
        }
      }
      if (err instanceof ApiError && err.code === 'AUTH_REQUIRED') {
        contextStore.onAuthError(err)
      }
      error.value = err
      phase.value = 'failed'
    }
  }

  function schedulePoll(delayMs: number) {
    clearTimer()
    pollHandle = window.setTimeout(() => {
      void fetchOnce()
    }, delayMs)
  }

  /** 页面隐藏暂停轮询；恢复可见立即查询（§6.4） */
  watch(visibility, (state) => {
    if (state === 'visible' && phase.value === 'processing') {
      void fetchOnce()
    }
  })

  watch(
    recordingId,
    () => {
      entry.value = getSubmittedEntry()
      phase.value = 'loading'
      void fetchOnce()
    },
    { immediate: true },
  )

  onScopeDispose(() => {
    clearTimer()
    if (pollHandle !== null) window.clearTimeout(pollHandle)
  })

  /** 提交页面内的同键重试（仅当内存 entry 匹配本记录；FD-15）；同 submissionId 重放返回同一 recordingId */
  async function retrySubmission(): Promise<void> {
    const current = entry.value
    if (!current || current.recordingId !== recordingId.value) return
    const res = await detectionApi.submitRecording({
      audioId: current.audioId,
      levelId: current.levelId,
      submissionId: current.submissionId,
    })
    if (res.data.recording.recordingId !== current.recordingId) {
      // 保险：后端返回了新的记录 ID 时跟随跳转
      entry.value = { ...current, recordingId: res.data.recording.recordingId }
      setSubmittedEntry(entry.value)
      void router.push(`/result/${res.data.recording.recordingId}`)
      return
    }
    void fetchOnce()
  }

  /** 重新录音去向：回到关卡页 P05 录音区 */
  function retakeRoute(): string {
    const levelId = recording.value?.levelId ?? entry.value?.levelId
    return levelId ? `/learn/${levelId}#record` : '/library'
  }

  function refreshLevels() {
    levelsStore.invalidate()
    void levelsStore.refresh({ background: true })
  }

  return {
    phase,
    recording,
    result,
    stage,
    error,
    entry,
    fetchOnce,
    retrySubmission,
    retakeRoute,
    refreshLevels,
  }
}
