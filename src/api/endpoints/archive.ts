/** archive / feedback 模块端点 */
import { apiRequest } from '../client'
import type {
  ArchiveListResponse,
  ClearArchiveResponse,
  FeedbackPayload,
  FeedbackResponse,
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
