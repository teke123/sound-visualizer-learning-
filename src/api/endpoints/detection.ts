/** acoustics / scoring / detection 模块端点：上传、标定、录音（docs/decision-map-backend.md） */
import { apiRequest } from '../client'
import type {
  AudioPurpose,
  AudioUploadResponse,
  CalibrationFailResult,
  CalibrationPostResult,
  F0Response,
  FormantsResponse,
  PitchCalibrationInfo,
  RecordingDeleted,
  RecordingSubmitResponse,
  RecordingWithResult,
} from '../generated/types'

export interface SubmitRecordingPayload {
  audioId: string
  levelId: string
  submissionId: string
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
  /** 标定：同步处理；未得出有效音域时 HTTP 200 + code=CALIBRATION_FAIL（带重录指引） */
  submitCalibration(payload: { audioId: string }) {
    return apiRequest<CalibrationPostResult | CalibrationFailResult>('/pitch-calibration', {
      method: 'POST',
      body: payload,
    })
  },

  /** 两步提交第二步：窗口内完成 200；未完成 202；幂等冲突 409 */
  submitRecording(payload: SubmitRecordingPayload) {
    return apiRequest<RecordingSubmitResponse>('/recordings', { method: 'POST', body: payload })
  },
  getRecording(id: string, options: { signal?: AbortSignal } = {}) {
    return apiRequest<RecordingWithResult>(`/recordings/${encodeURIComponent(id)}`, { signal: options.signal })
  },
  deleteRecording(id: string) {
    return apiRequest<RecordingDeleted>(`/recordings/${encodeURIComponent(id)}`, { method: 'DELETE' })
  },
}
