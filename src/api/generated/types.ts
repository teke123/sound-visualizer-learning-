/**
 * API DTO 类型（契约草案）
 * ---------------------------------------------------------------------------
 * 依据 docs/decision-map-backend.md「1.0 API 清单」与「关卡详情中的学习结构」
 * 手写。后端 OpenAPI 就绪后，本文件应改为 openapi-typescript 生成产物并保持
 * 文件名不变（CI 比对契约漂移，docs/architecture/04 §2）。
 * 在此之前：字段口径以后端决策图为准，联调期变动集中登记在 endpoints 层。
 */

/* ---------------------------------- 通用 ---------------------------------- */

/** 统一响应体（JSON camelCase） */
export interface Envelope<T> {
  code: string
  message: string
  data: T
  requestId: string
  nextStep?: string
}

export type Availability = 'open' | 'temporarily_unavailable' | 'closed'
export type LevelLayer = 'vowel' | 'initial' | 'fusion'
export type LevelType = '单韵母' | '声母' | '拼读'
export type ConsentStatus = 'none' | 'granted' | 'rejected' | 'revoked'
export type CalibrationStatus = 'none' | 'session' | 'personal'
export type StorageKind = 'session' | 'archived'

/* ------------------------------- me/context ------------------------------- */

export interface ConsentInfo {
  status: ConsentStatus
  consentTextVersion: string
}

export interface CalibrationInfo {
  status: CalibrationStatus
  expiresAt?: string
}

export interface MeContext {
  authenticated: boolean
  accountId?: string
  username?: string
  consent: ConsentInfo
  currentConsentTextVersion: string
  calibration: CalibrationInfo
  dataEpoch?: number
  /** 未处理同意的账号：同意后将自动转存的条数 */
  pendingTransfer?: number
  /** 登录且同意时由服务端进度派生；否则为第一已发布关（前端用本地进度覆盖） */
  nextLevelId?: string
}

/* --------------------------------- 关卡 ----------------------------------- */

/** 完成度判定键（D-24：全部听辨题各至少答对一次 + 全部练习步骤各至少完成一次） */
export interface CompletionKeys {
  quizIds: string[]
  practiceStepIds: string[]
}

export interface LevelSummary {
  id: string
  order: number
  layer: LevelLayer
  type: LevelType
  targetSound: string
  pinyin: string
  representativeChar?: string
  title: string
  oneLiner: string
  demoMediaId?: string
  availability: Availability
  completionKeys: CompletionKeys
}

/** 地图骨架：仅 CMS 标记 skeletonPublic 的未发布关，不含正文/媒体/任务 */
export interface LevelSkeleton {
  id: string
  order: number
  layer: LevelLayer
  targetSound: string
  availability: Availability
}

export interface ConfusablePair {
  aId: string
  bId: string
}

export interface LevelsResponse {
  levels: LevelSummary[]
  skeletons: LevelSkeleton[]
  confusablePairs: ConfusablePair[]
}

export interface LevelNav {
  prevId?: string
  nextId?: string
  /** 双方均已发布的易混关 */
  confusableIds?: string[]
  /** L30 与 L01/L09 的关系入口；目标未发布时仅展示不可用状态 */
  relatedIds?: string[]
}

export type ArticulationMediaKind = 'image' | 'animation' | 'video'

export interface ArticulationMedia {
  mediaId: string
  kind: ArticulationMediaKind
  altText: string
}

export type LipContact = 'none' | 'bilabial' | 'labiodental'
export type TongueTipPlace =
  | 'rest'
  | 'dental'
  | 'alveolar'
  | 'postalveolar'
  | 'retroflex'
export type Stricture = 'open' | 'approximant' | 'fricative' | 'closure'
export type AirflowKind =
  | 'none'
  | 'oral'
  | 'nasal'
  | 'burst'
  | 'aspirated_burst'
  | 'friction'
  | 'affricate'

/** 声道剖面关键帧（单帧 = 静态口型；多帧 = 发音过程，帧间插值） */
export interface SagittalKeyframe {
  label: string
  holdMs: number
  jaw: number
  lips: { aperture: number; rounding: number; contact: LipContact }
  tongueTip: { place: TongueTipPlace; stricture: Stricture }
  tongueBody: { height: number; backness: number; stricture: Stricture }
  velum: 'raised' | 'lowered'
  airflow: AirflowKind
  voicing: boolean
}

export interface Articulation {
  media: ArticulationMedia[]
  description: string
  sagittal?: { keyframes: SagittalKeyframe[] }
  /** 1.0 预留切换位；无模型时按缺席处理（FD-14） */
  model3dMediaId?: string
}

/** 示范媒体：正常语速必有一条；慢速与男女声可选 */
export interface DemoItem {
  mediaId: string
  speed: 'normal' | 'slow'
  voice?: 'male' | 'female'
  /** 字幕或对应文字（NFR-07 音频有对应文字） */
  text?: string
}

export interface QuizOption {
  text: string
  mediaId?: string
}

export interface QuizQuestion {
  id: string
  stimulusMediaId: string
  prompt: string
  options: QuizOption[]
  answerIndex: number
  explanation?: string
}

export interface PracticeStep {
  id: string
  title: string
  instruction: string
  repeat?: number
  durationSec?: number
  bodyCue: string
  mediaId?: string
  stopNote: string
}

export interface Misconception {
  /** 可能听起来像什么（可观察现象） */
  observable: string
  /** 可以怎么改 */
  fix: string
}

export interface ProReference {
  title: string
  source: string
  license: string
  scope: string
}

export interface ProFold {
  /** 专业解释（Markdown 片段，仅受控指令子集） */
  content: string
  /** 声学参考值及适用说明 */
  acousticNotes?: string
  references?: ProReference[]
}

export interface DetectionTask {
  promptText: string
  sampleMediaId?: string
  allowedMetrics: string[]
  reliabilityNote?: string
  /** 应急熔断（单关或全局）时为 false，学习入口保留 */
  available: boolean
}

export interface LevelDetail {
  id: string
  order: number
  layer: LevelLayer
  type: LevelType
  targetSound: string
  pinyin: string
  representativeChar?: string
  title: string
  oneLiner: string
  /** 本关要学会什么 */
  goal: string
  contentVersion: number
  nav: LevelNav
  articulation: Articulation
  demo: DemoItem[]
  quiz: QuizQuestion[]
  practice: PracticeStep[]
  misconceptions: Misconception[]
  pro: ProFold
  detection: DetectionTask
}

/* --------------------------------- 搜索 ----------------------------------- */

export interface SearchResultItem {
  levelId: string
  matchedOn: string
}

export interface SearchResponse {
  results: LevelSummary[]
  suggestions: LevelSummary[]
}

/* --------------------------------- 文章 ----------------------------------- */

export interface ArticleCategory {
  id: string
  name: string
  /** 分类排序说明（气 → 声 → 口型） */
  order: number
  description?: string
}

export interface ArticleSummary {
  slug: string
  title: string
  category: string
  excerpt?: string
}

export interface ArticleReference {
  title: string
  source: string
  license: string
  scope: string
}

export interface ArticleDetail {
  slug: string
  title: string
  category: string
  contentVersion: number
  excerpt?: string
  /** Markdown 正文（受控 practice/audio/image/levels/pro 指令） */
  content: string
  /** 短练习（结构化兜底；正文内也可能用指令内嵌） */
  practice?: string[]
  demoMediaIds?: string[]
  references?: ArticleReference[]
  /** 关联关卡（仅已发布） */
  levelIds?: string[]
}

/* --------------------------------- 音频 ----------------------------------- */

export type AudioPurpose = 'recording' | 'calibration'

export interface AudioUploadResponse {
  audioId: string
  duration: number
  format: string
  expiresAt: string
}

export interface F0Frame {
  t: number
  hz?: number
}

export interface F0Response {
  algorithmVersion: string
  hopMs: number
  frames: F0Frame[]
  voicedRanges: Array<[number, number]>
}

export interface FormantFrame {
  t: number
  f1?: number
  f2?: number
}

export interface FormantsResponse {
  algorithmVersion: string
  frames: FormantFrame[]
  vowelSegments: Array<{ t: number; vowel?: string }>
}

/* --------------------------------- 标定 ----------------------------------- */

export interface PitchCalibrationInfo {
  text: string
  textVersion: string
  status: CalibrationStatus
  pitchRange?: { floorHz: number; ceilHz: number }
  vowelSpaceReady?: boolean
  expiresAt?: string
  updatedAt?: string
}

export interface PitchRange {
  floorHz: number
  ceilHz: number
  vowelSpaceReady: boolean
  updatedAt: string
}

/* -------------------------------- 录音与结果 ------------------------------- */

export type RecordingStatus = 'processing' | 'completed' | 'failed'
export type ProcessingStage =
  | 'queued'
  | 'signal_check'
  | 'scoring'
  | 'analyzing'
  | 'finalizing'

export interface RecordingError {
  code: string
  retryable: boolean
}

export interface RecordingDTO {
  recordingId: string
  audioId: string
  levelId: string
  contentVersion: number
  status: RecordingStatus
  stage?: ProcessingStage
  error?: RecordingError
  storage: StorageKind
  expiresAt?: string
  createdAt: string
}

export interface QualitySignal {
  volume?: string
  noise?: string
  clipping?: string
  duration?: string
}

export interface QualityReading {
  omission?: string
  addition?: string
  reread?: string
  substitution?: string
  gibberish?: string
}

export interface Quality {
  verdict: 'pass' | 'fail'
  signal: QualitySignal
  reading: QualityReading
  retakeAdvice: string
}

export interface Phenomenon {
  /** 本关已定稿现象标签 */
  label: string
  /** 音节/声韵调定位（如「妈(mā) 的声调」） */
  position?: string
  /** 通俗表述 */
  description: string
}

export interface FourStep {
  phenomenon: string
  possibleCause: string
  cue: string
  practice: { levelId: string; stepRef: string }
  wordingSource: 'rule_template' | 'llm_confirmed'
}

export interface CurvePoint {
  t: number
  /** T 值（0–5，按本人音域换算到统一标度） */
  tone: number
}

export interface CurveSegment {
  syllable: string
  toneValue?: number
  user: CurvePoint[]
  reference: CurvePoint[]
}

export interface ResultCurve {
  status: 'ok' | 'not_available'
  scale: 'T'
  segments: CurveSegment[]
  /** 受理时音域快照（历史结果不重算） */
  rangeSnapshotId?: string
  notAvailableReason?: string
}

export interface FormantPoint {
  f1: number
  f2: number
}

export interface ResultFormants {
  status: 'ok' | 'not_available'
  space: 'normalized'
  user?: FormantPoint
  /** 参考区域（同一元音空间标度） */
  referenceRegion?: { points: FormantPoint[]; center?: FormantPoint }
  notAvailableReason?: string
}

export interface AssessmentResult {
  levelId: string
  contentVersion: number
  ruleVersion: string
  providerVersion: string
  algorithmVersion: string
  storage: StorageKind
  expiresAt?: string
  quality: Quality
  /** 仅质量合格时填写 */
  score?: number
  /** 仅质量合格时填写 */
  phenomena?: Phenomenon[]
  fourSteps?: FourStep[]
  curve?: ResultCurve
  /** 仅单韵母关 */
  formants?: ResultFormants
  boundaryNote: string
}

export interface RecordingWithResult {
  recording: RecordingDTO
  result: AssessmentResult
}

export interface RecordingSubmitResponse {
  recording: RecordingDTO
  result?: AssessmentResult
}

/* -------------------------------- 当前会话 -------------------------------- */

export interface SessionRecordingSummary {
  recordingId: string
  audioId: string
  levelId: string
  createdAt: string
  expiresAt: string
  verdict: 'pass' | 'fail'
  score?: number
}

export interface SessionRecordingsResponse {
  items: SessionRecordingSummary[]
  /** 同意后将转存的条数 */
  transferableCount: number
}

/* ------------------------------ 档案与学习 -------------------------------- */

export interface ArchiveRecordingSummary {
  recordingId: string
  audioId: string
  levelId: string
  contentVersion: number
  ruleVersion: string
  createdAt: string
  verdict: 'pass' | 'fail'
  score?: number
}

export interface ArchiveListResponse {
  items: ArchiveRecordingSummary[]
  nextCursor?: string
}

export interface ArchiveCompareSide extends ArchiveRecordingSummary {
  curve?: ResultCurve
  rangeSnapshotId?: string
}

export interface ArchiveCompareResponse {
  a: ArchiveCompareSide
  b: ArchiveCompareSide
  comparable: { score: boolean; curve: boolean; reasons: string[] }
  differences: Array<{ dimension: string; description: string }>
}

export type LearningEventKind = 'listen_quiz' | 'practice_done'

export type LearningEvent = {
  eventId: string
  levelId: string
  contentVersion: number
} & (
  | { kind: 'listen_quiz'; detail: { questionId: string; choiceIndex: number } }
  | { kind: 'practice_done'; detail: { stepId: string } }
)

export interface LearningEventsResponse {
  accepted: string[]
  duplicates: string[]
  rejected: Array<{ eventId: string; code: string }>
}

export interface ProgressLevel {
  levelId: string
  completed: boolean
  quiz: { passed: number; total: number }
  practice: { done: number; total: number }
}

export interface MeProgress {
  levels: ProgressLevel[]
  nextLevelId?: string
}

/* ------------------------------ 同意与账号 -------------------------------- */

export interface ConsentDecision {
  decision: 'granted' | 'rejected' | 'revoked'
  consentTextVersion: string
  decidedAt: string
}

export interface ConsentStateResponse {
  status: ConsentStatus
  consentTextVersion: string
  decisions: ConsentDecision[]
}

export interface TransferResult {
  status: 'completed' | 'partial' | 'none'
  transferredCount: number
  calibrationUpgraded?: boolean
}

export interface ConsentPostResponse {
  consent: ConsentInfo
  transfer: TransferResult
}

export interface AuthLoginResponse {
  context: MeContext
  transfer?: TransferResult
}

export interface FeedbackType {
  sourcePage: string
  type: 'understanding' | 'correction' | 'result_rating'
  content?: string
  articleSlug?: string
  levelId?: string
  recordingId?: string
  subtype?: 'text' | 'sound' | 'image' | 'subtitle'
  rating?: 'match' | 'mismatch'
}

/* --------------------------------- 预览 ----------------------------------- */

export interface PreviewTokenInfo {
  token: string
  expiresAt: string
}
