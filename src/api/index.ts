/** api 层唯一出口：client、类型、端点、媒体地址（docs/architecture/04 §3） */
export { apiRequest, ApiError, API_BASE, DEFAULT_RETRY_AFTER_MS } from './client'
export type { ApiResult, RequestOptions } from './client'
export * from './generated/types'
export { contentApi } from './endpoints/content'
export { detectionApi } from './endpoints/detection'
export type { SubmitRecordingPayload } from './endpoints/detection'
export { identityApi } from './endpoints/identity'
export { archiveApi, learningApi, sessionApi, feedbackApi } from './endpoints/archive'
export type { WishPayload } from './endpoints/archive'
export {
  mediaUrl,
  audioFileUrl,
  audioF0Url,
  audioFormantsUrl,
  audioFormantsPngUrl,
} from './mediaUrl'
export type { MediaUrlOptions } from './mediaUrl'
