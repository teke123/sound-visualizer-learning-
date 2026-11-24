/** acoustics / scoring / detection 模块端点：上传、标定、录音 */
import { apiRequest } from '../client'
import type {
  AudioPurpose,
  AudioUploadResponse,
  CalibrationSessionView,
  CalibrationTakeOutcome,
  F0Response,
  FormantsResponse,
  PitchCalibrationInfo,
  PronunciationAdviceResult,
  RecordingDeleted,
  RecordingSubmitResponse,
  RecordingWithResult,
} from '../generated/types'

export interface SubmitRecordingPayload {
  audioId: string
  levelId: string
  submissionId: string
}

export interface CalibrationTakePayload {
  sessionId: string
  audioId: string
  kind: 'vowel' | 'pitch'
  /** kind=vowel 时必填：i / u / a / ü */
  vowel?: string
}

export const detectionApi = {
  /** multipart 两步提交第一步：上传得到 audioId */
  uploadAudio(file: Blob, purpose: AudioPurpose, filename: string) {
    const formData = new FormData()
    formData.append('purpose', purpose)
    formData.append('file', file, filename)
    return apiRequest<AudioUploadResponse>('/audio/uploads', { method: 'POST', formData })
  },

  rawF0(audioId: string) {
    return apiRequest<F0Response>(`/audio/${encodeURIComponent(audioId)}/f0`)
  },
  rawFormants(audioId: string) {
    return apiRequest<FormantsResponse>(`/audio/${encodeURIComponent(audioId)}/formants`)
  },

  getCalibration() {
    return apiRequest<PitchCalibrationInfo>('/pitch-calibration')
  },

  /** 创建或返回当前用户进行中的标定会话（刷新/重开后由此恢复进度） */
  createCalibrationSession() {
    return apiRequest<CalibrationSessionView>('/pitch-calibration/sessions', { method: 'POST' })
  },
  /** 查询会话进度与最终计算状态 */
  getCalibrationSession(sessionId: string) {
    return apiRequest<CalibrationSessionView>(
      `/pitch-calibration/sessions/${encodeURIComponent(sessionId)}`)
  },
  /** 提交单条标定录音并验收：accepted / retry_take / additional_take_required / vowel_dispersed */
  submitCalibrationTake(payload: CalibrationTakePayload) {
    const { sessionId, ...body } = payload
    return apiRequest<CalibrationTakeOutcome>(
      `/pitch-calibration/sessions/${encodeURIComponent(sessionId)}/takes`,
      { method: 'POST', body })
  },
  /** 任务齐备后启动最终计算；幂等，重复请求返回同一计算状态 */
  completeCalibrationSession(sessionId: string) {
    return apiRequest<CalibrationSessionView>(
      `/pitch-calibration/sessions/${encodeURIComponent(sessionId)}/complete`,
      { method: 'POST' })
  },

  /** 两步提交第二步：窗口内完成 200；未完成 202；幂等冲突 409 */
  submitRecording(payload: SubmitRecordingPayload) {
    return apiRequest<RecordingSubmitResponse>('/recordings', { method: 'POST', body: payload })
  },
  getRecording(id: string, options: { signal?: AbortSignal } = {}) {
    return apiRequest<RecordingWithResult>(`/recordings/${encodeURIComponent(id)}`, { signal: options.signal })
  },
  getPronunciationAdvice(id: string, signal: AbortSignal) {
    return apiRequest<PronunciationAdviceResult>(
      `/recordings/${encodeURIComponent(id)}/pronunciation-advice`,
      { signal },
    )
  },
  deleteRecording(id: string) {
    return apiRequest<RecordingDeleted>(`/recordings/${encodeURIComponent(id)}`, { method: 'DELETE' })
  },
}
