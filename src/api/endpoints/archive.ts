/** archive / learning / feedback / session 模块端点（docs/decision-map-backend.md） */
import { apiRequest } from '../client'
import type {
  ArchiveCompareResponse,
  ArchiveListResponse,
  ClearArchiveResponse,
  FeedbackPayload,
  FeedbackResponse,
  LearningEvent,
  LearningEventsResponse,
  SessionRecordingsResponse,
  SessionResetResponse,
  WishResponse,
} from '../generated/types'

export const archiveApi = {
  listMine(levelId?: string, cursor?: string) {
    const params = new URLSearchParams()
    if (levelId) params.set('levelId', levelId)
    if (cursor) params.set('cursor', cursor)
    const query = params.size > 0 ? `?${params.toString()}` : ''
    return apiRequest<ArchiveListResponse>(`/me/recordings${query}`)
  },
  clearMine() {
    return apiRequest<ClearArchiveResponse>('/me/recordings', { method: 'DELETE' })
  },
  /** 本人同关 archived 两条比较 */
  compare(a: string, b: string) {
    return apiRequest<ArchiveCompareResponse>(`/me/recordings/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`)
  },
}

export const learningApi = {
  /** 单批 ≤50；按 eventId 去重 */
  postEvents(events: LearningEvent[]) {
    return apiRequest<LearningEventsResponse>('/learning-events', {
      method: 'POST',
      body: { events },
    })
  },
}

export const sessionApi = {
  /** 当前会话临时记录 + 同意后将转存条数 */
  recordings() {
    return apiRequest<SessionRecordingsResponse>('/session/recordings')
  },
  /** 清空当前会话临时数据；访客同时轮换 sid */
  reset() {
    return apiRequest<SessionResetResponse>('/session/reset', { method: 'POST' })
  },
}

export interface WishPayload {
  content: string
  searchQuery?: string
}

export const feedbackApi = {
  /** type ∈ clarity / result_match / content_error / wish_more；rating：符合=1，不符合=0 */
  submit(payload: FeedbackPayload) {
    return apiRequest<FeedbackResponse>('/feedback', {
      method: 'POST',
      body: payload,
    })
  },
  submitWish(payload: WishPayload) {
    return apiRequest<WishResponse>('/wishes', { method: 'POST', body: payload })
  },
}
