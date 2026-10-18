// 发音单元类型
export interface PronunciationUnit {
  id: string
  pinyin: string
  character: string
  pinyinTone: string
  description: string
  audioUrl: string
  videoUrl?: string
  modelUrl?: string
  category: 'initial' | 'final' | 'tone'
  order: number
  createdAt: string
  updatedAt: string
}

// 学习记录类型
export interface LearningRecord {
  id: string
  userId: string
  unitId: string
  pinyin: string
  character: string
  score: number
  accuracy: number
  fluency: number
  pronunciation: number
  duration: number
  audioUrl: string
  feedback: string
  createdAt: string
}

// 后台管理统计数据
export interface AdminStats {
  totalUsers: number
  totalRecords: number
  todayRecords: number
  averageScore: number
  completionRate: number
}

// 用户进度类型
export interface UserProgress {
  userId: string
  totalUnits: number
  completedUnits: number
  totalPractice: number
  averageScore: number
  lastPracticeAt: string
  unitProgress: UnitProgress[]
}

// 单元进度类型
export interface UnitProgress {
  unitId: string
  pinyin: string
  character: string
  bestScore: number
  practiceCount: number
  lastPracticeAt: string
  status: 'not_started' | 'in_progress' | 'completed'
}

// 音素级分析结果类型（深度学习识别）
export interface PhonemeScore {
  phoneme: string // 声母 / 韵母 / 声调
  expected: string // 目标音素
  detected: string // 识别到的音素
  score: number // 该项得分 0-100
  feedback: string // 针对该项的反馈
}

// 音频分析结果类型
export interface AudioAnalysisResult {
  f0: number[] // 基频曲线
  f1: number[] // 第一共振峰
  f2: number[] // 第二共振峰
  energy: number[] // 能量曲线
  duration: number // 时长
  sampleRate: number // 采样率
  mfcc: number[][] // MFCC特征
  //新增：
  voiced_flag?: boolean[]
  voiced_probs?: number[]

  /**
   * 逐帧时间戳（秒）。
   * 契约来源：A（2026-10-11）——时间戳「我还没做」，将来会「按帧返回时间戳」，
   * 并且明确「分析的时候的帧率可能会变」。
   * 所以：横轴有它就用它；没有就退化为帧序号，**不要写死帧长**。
   */
  timestamps?: number[]
  
  // 深度学习分析结果
  recognizedText: string // Wav2Vec2 识别出的拼音文本
  detectedTone: number // 识别出的声调 (0-4)
  toneScore: number // 声调评估得分
  phonemeScore: number // 音素级准确度得分
  phonemes: PhonemeScore[] // 音素级分析明细
  standardF0: number[] // 标准声调曲线（后端生成）
}

export interface QualityItem {
  key: string
  label: string
  status: 'ok' | 'warn' | 'fail'
  message: string
}

export interface RecordingQuality {
  passed: boolean
  summary: string
  items: QualityItem[]
}

export interface ResultBoundary {
  statement: string
  scope?: string
  factors?: string[]
}

// 发音评估结果类型
export interface PronunciationAssessment {
  score: number
  accuracy: number
  fluency: number
  pronunciation: number
  feedback: FeedbackItem[]
  audioAnalysis: AudioAnalysisResult | null
  evaluable: boolean
  quality: RecordingQuality
  reliability: 'reliable' | 'reference_only' | 'not_available'
  reliabilityNote: string
  boundary: ResultBoundary
  /** 一句话结论（当前任务最重要的一项） */
  headline?: string
}

// 反馈项类型（四步反馈 RES-05）
export interface FeedbackItem {
  type: 'error' | 'warning' | 'suggestion'
  category: 'tone' | 'pronunciation' | 'fluency' | 'rhythm' | 'quality'
  phenomenon: string
  link: string
  hint: string
  practice: string
  message: string
  detail: string
  improvement: string
}

export interface CmsUnit {
  id: string
  pinyin: string
  character: string
  category: string
  description: string
  conclusion: string
  detail: string
  mistakes: Array<Record<string, string>>
  steps: Array<Record<string, string>>
  related: string[]
  status: 'draft' | 'published'
  verified: boolean
  order: number
  /**
   * 正式示范音地址（第 5 周 D：关卡页至少一关示范可播放）
   * 由 I 提供音频、C 走 CMS 审核发布；后端以 demoAudio 返回。
   * 未提供时前端回落浏览器语音合成，并挂 TTS 声明，不冒充正式示范音。
   */
  demoAudio?: string | null
  /**
   * 以下为排期第 4/5 周请 C 补的 30 关正式列。
   * 全部可选：C 补列并发布后前端自动生效，不需要再改前端代码。
   */
  target?: string
  group?: string
  practice?: Array<Record<string, string>>
  detectionOpen?: boolean
  reviewStatus?: string
  version?: number
}

export interface UserFeedbackItem {
  id: string
  userId: string
  type: string
  page: string
  unitId: string
  rating: string
  message: string
  status: 'pending' | 'adopted' | 'rejected'
  handleNote: string
  createdAt: string
}

// 3D模型数据类型
export interface VocalTractModel {
  id: string
  name: string
  description: string
  modelUrl: string
  textureUrl?: string
  animations: AnimationData[]
}

// 动画数据类型
export interface AnimationData {
  name: string
  duration: number
  keyframes: KeyframeData[]
}

// 关键帧数据类型
export interface KeyframeData {
  time: number
  position: { x: number; y: number; z: number }
  rotation: { x: number; y: number; z: number }
  scale: { x: number; y: number; z: number }
}

// WebSocket消息类型
export interface WebSocketMessage {
  type: 'audio_data' | 'analysis_result' | 'error' | 'status'
  data: any
  timestamp: number
}

// 录音状态类型
export interface RecordingState {
  isRecording: boolean
  isPaused: boolean
  duration: number
  audioBlob: Blob | null
  audioUrl: string | null
}

// 波形图数据类型
export interface WaveformData {
  labels: number[]
  datasets: {
    label: string
    data: number[]
    borderColor: string
    backgroundColor: string
    fill: boolean
  }[]
}

// 声调曲线数据类型
export interface ToneCurveData {
  labels: number[]
  datasets: {
    label: string
    data: number[]
    borderColor: string
    backgroundColor: string
    fill: boolean
    tension: number
  }[]
}

// 对比结果类型
export interface ComparisonResult {
  userAudio: AudioAnalysisResult
  standardAudio: AudioAnalysisResult
  similarity: number
  differences: {
    f0: number
    f1: number
    f2: number
    energy: number
    duration: number
  }
}

// 学习计划类型
export interface LearningPlan {
  id: string
  userId: string
  name: string
  description: string
  units: string[] // unitId列表
  startDate: string
  endDate: string
  progress: number
  status: 'active' | 'completed' | 'paused'
}

// 成就类型
export interface Achievement {
  id: string
  name: string
  description: string
  icon: string
  condition: string
  unlockedAt?: string
}

// 媒体资源类型
export interface MediaAsset {
  id: string
  name: string
  type: 'audio' | 'video' | 'image' | '3d_model'
  url: string
  size: number
  duration?: number
  createdAt: string
}

// API响应类型
export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  timestamp: number
}

// 分页响应类型
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// 搜索参数类型
export interface SearchParams {
  keyword?: string
  category?: string
  page?: number
  pageSize?: number
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}