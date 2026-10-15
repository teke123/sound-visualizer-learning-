/**
 * API DTO 类型 · 生成类型转发层
 * ---------------------------------------------------------------------------
 * 后端 OpenAPI 为契约真源（backend/app/api/schemas.py → /openapi.json），
 * openapi-typescript 生成 ./schema.d.ts，本文件仅做同名转发，保持全部消费方
 * import 路径不变（唯一接缝）。后端契约变更后执行：
 *   npm run api:dump && npm run api:types
 * 并提交 openapi.json 与 schema.d.ts（漂移比对锚点，npm run api:check 校验）。
 * 少数请求侧类型与 Envelope 保留手写（生成产物为宽松 object，收窄以保类型安全）。
 */

import type { components } from './schema'

type Schemas = components['schemas']

/* ---------------------------------- 通用 ---------------------------------- */

/** 统一响应体（client.ts 自行解析，不依赖生成的 Envelope_X_） */
export interface Envelope<T> {
  code: string
  message: string
  data: T
  requestId: string
  nextStep?: string
}

// 字面量联合从生成组件派生，避免手写漂移
export type ConsentStatus = Schemas['ConsentInfo']['status']
export type CalibrationStatus = Schemas['PitchCalibrationInfo']['status']
export type StorageKind = RecordingDTO['storage']

/* ------------------------------- me/context ------------------------------- */

export type MeContext = Schemas['MeContext']

/* --------------------------------- 关卡 ----------------------------------- */

export type CompletionKeys = Schemas['CompletionKeys']
export type LevelSummary = Schemas['LevelSummary']
export type LevelSkeleton = Schemas['LevelSkeleton']
export type ConfusablePair = Schemas['ConfusablePair']
export type LevelsResponse = Schemas['LevelsResponse']
export type LevelNav = Schemas['LevelNav']
export type SagittalKeyframe = Schemas['SagittalKeyframe']
export type Articulation = Schemas['Articulation']
export type DemoItem = Schemas['DemoItem']
export type QuizQuestion = Schemas['QuizQuestion']
export type PracticeStep = Schemas['PracticeStep']
export type Misconception = Schemas['Misconception']
export type Professional = Schemas['Professional']
export type LevelDetail = Schemas['LevelDetail']

/* --------------------------------- 搜索 ----------------------------------- */

export type SearchResponse = Schemas['SearchResponse']

/* --------------------------------- 文章 ----------------------------------- */

export type ArticleCategory = Schemas['ArticleCategory']
export type ArticleCategoriesResponse = Schemas['ArticleCategoriesResponse']
export type ArticleSummary = Schemas['ArticleSummary']
export type ArticlesResponse = Schemas['ArticlesResponse']
export type ArticleDetail = Schemas['ArticleDetail']

/* --------------------------------- 音频 ----------------------------------- */

export type AudioPurpose = 'recording' | 'calibration'
export type AudioUploadResponse = Schemas['AudioUploadResponse']
export type F0Response = Schemas['F0Response']
export type FormantsResponse = Schemas['FormantsResponse']

/* --------------------------------- 标定 ----------------------------------- */

export type PitchCalibrationInfo = Schemas['PitchCalibrationInfo']

/** POST /api/pitch-calibration 成功响应（后端 schema 名 CalibrationOkResult） */
export type CalibrationPostResult = Schemas['CalibrationOkResult']

/** CALIBRATION_FAIL（HTTP 200 业务结果）的 data */
export type CalibrationFailResult = Schemas['CalibrationFailResult']

/* -------------------------------- 录音与结果 ------------------------------- */

export type RecordingError = Schemas['RecordingError']
export type RecordingDTO = Schemas['RecordingDTO']
export type QualitySignal = Schemas['QualitySignal']
export type QualityReading = Schemas['QualityReading']
export type Quality = Schemas['Quality']
export type Phenomenon = Schemas['Phenomenon']
export type FourStep = Schemas['FourStep']
export type CurvePoint = Schemas['CurvePoint']
export type CurveSegment = Schemas['CurveSegment']
export type ResultCurve = Schemas['ResultCurve']
export type FormantRaw = Schemas['FormantRaw']
export type FormantUser = Schemas['FormantUser']
export type FormantRegion = Schemas['FormantRegion']
export type ResultFormants = Schemas['ResultFormants']
export type AssessmentResult = Schemas['AssessmentResult']
export type RecordingWithResult = Schemas['RecordingWithResult']
export type RecordingSubmitResponse = Schemas['RecordingWithResult']
export type RecordingDeleted = Schemas['RecordingDeleted']

/* -------------------------------- 当前会话 -------------------------------- */

export type SessionRecordingSummary = Schemas['SessionRecordingSummary']
export type SessionRecordingsResponse = Schemas['SessionRecordingsResponse']
export type SessionResetResponse = Schemas['SessionResetResponse']

/* ------------------------------ 档案与学习 -------------------------------- */

export type ArchiveRecordingSummary = Schemas['ArchiveRecordingSummary']
export type ArchiveListResponse = Schemas['ArchiveListResponse']
export type ClearArchiveResponse = Schemas['ClearArchiveResponse']
export type ArchiveCompareSide = Schemas['ArchiveCompareSide']
export type ArchiveCompareResponse = Schemas['ArchiveCompareResponse']

/** 请求负载：判别联合（生成的 EventItem.detail 为宽松 object，此处收窄） */
export type LearningEvent = {
  eventId: string
  levelId: string
  contentVersion: number
} & (
  | { kind: 'listen_quiz'; detail: { questionId: string; choiceIndex: number } }
  | { kind: 'practice_done'; detail: { stepId: string } }
)

export type LearningEventsResponse = Schemas['LearningEventsResponse']
export type ProgressLevel = Schemas['ProgressLevel']
export type MeProgress = Schemas['MeProgress']

/* ------------------------------ 同意与账号 -------------------------------- */

/** 后端 schema 名 ConsentDecisionItem，时间字段为 createdAt */
export type ConsentDecision = Schemas['ConsentDecisionItem']
export type ConsentStateResponse = Schemas['ConsentStateResponse']
export type TransferResult = Schemas['TransferResult']
export type ConsentPostResponse = Schemas['ConsentPostResponse']
export type ConsentRevokedResponse = Schemas['ConsentRevokedResponse']
export type RegisterResponse = Schemas['RegisterResponse']
export type AuthLoginResponse = Schemas['AuthLoginResponse']
export type LoggedOutResponse = Schemas['LoggedOutResponse']
export type DeletedResponse = Schemas['DeletedResponse']

/** 请求负载：生成的 FeedbackBody.type 为宽松 string，此处收窄以约束构造侧 */
export interface FeedbackPayload {
  sourcePage?: string
  type: 'clarity' | 'result_match' | 'content_error' | 'wish_more'
  content?: string
  articleSlug?: string
  levelId?: string
  recordingId?: string
  /** 纠错子类型（text / audio / image / subtitle） */
  subtype?: 'text' | 'audio' | 'image' | 'subtitle'
  /** 结果感受评分：符合 = 1，不符合 = 0 */
  rating?: number
}

export type FeedbackResponse = Schemas['FeedbackResponse']
export type WishResponse = Schemas['WishResponse']
