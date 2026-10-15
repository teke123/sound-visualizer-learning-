/**
 * MSW handler 共享的内存状态与结果合成（dev:mock 模式专用）。
 */
import type {
  AssessmentResult,
  AudioPurpose,
  CalibrationStatus,
  ConsentStatus,
  LearningEvent,
  RecordingDTO,
} from '@/api'
import { LEVEL_DETAILS, LEVEL_SUMMARIES } from './fixtures'

export interface MockUser {
  username: string
  password: string
}

export interface MockSession {
  authenticated: MockUser | null
  consentStatus: ConsentStatus
  decisions: Array<{ decision: 'granted' | 'rejected' | 'revoked'; consentTextVersion: string; createdAt: string }>
  calibration: { status: CalibrationStatus; expiresAt?: string }
  dataEpoch: number
}

export interface MockRecording {
  recording: RecordingDTO
  submissionPayload: string
  result: AssessmentResult | null
  /** 质量不合格（每 N 次演示一次） */
  qualityFail: boolean
  createdAt: number
}

export const state = {
  users: new Map<string, MockUser>([['learner', { username: 'learner', password: '12345678' }]]),
  session: {
    authenticated: null,
    consentStatus: 'none',
    decisions: [],
    calibration: { status: 'none' },
    dataEpoch: 1,
  } as MockSession,
  uploads: new Map<string, { purpose: AudioPurpose; durationSec: number; expiresAt: string }>(),
  recordings: new Map<string, MockRecording>(),
  submissions: new Map<string, string>(),
  learningEvents: [] as LearningEvent[],
  submissionCounter: 0,
}

export function resetSession() {
  state.session.authenticated = null
  state.session.consentStatus = 'none'
  state.session.decisions = []
  state.session.calibration = { status: 'none' }
  state.session.dataEpoch += 1
}

export const CONSENT_TEXT_VERSION = 'consent-v1'

/* ------------------------------ 结果合成 ------------------------------ */

function hashOf(text: string): number {
  let hash = 7
  for (let i = 0; i < text.length; i += 1) hash = (hash * 31 + text.charCodeAt(i)) % 1000
  return hash
}

function buildCurve(levelId: string, audioId: string): AssessmentResult['curve'] {
  const seed = hashOf(audioId)
  const level = LEVEL_DETAILS[levelId]
  const syllable = level?.representativeChar ?? level?.targetSound ?? 'a'
  const points = 12
  const reference: Array<{ t: number; v: number }> = []
  const user: Array<{ t: number; v: number }> = []
  for (let i = 0; i < points; i += 1) {
    const t = (i / (points - 1)) * 0.6
    const ref = 2.8 + 0.35 * Math.sin((i / points) * Math.PI)
    const drift = ((seed % 40) - 20) / 40 // -0.5 ~ 0.5 的个体差
    const userTone = ref + drift * (0.4 + 0.6 * Math.sin(i * 0.7))
    reference.push({ t: Number(t.toFixed(3)), v: Number(ref.toFixed(3)) })
    user.push({ t: Number(t.toFixed(3)), v: Number(Math.min(5, Math.max(0, userTone)).toFixed(3)) })
  }
  return {
    status: 'ok',
    scale: 'T',
    segments: [{ syllable, toneValue: 1, user, reference }],
    rangeSnapshotId: 'range-mock-1',
  }
}

function buildFormants(): AssessmentResult['formants'] {
  return {
    status: 'ok',
    space: 'normalized',
    user: { f1: 0.4, f2: -0.2, raw: { f1Mean: 830, f2Mean: 1250 } },
    referenceRegion: { center: [0.55, -0.3], radius: 0.9, vowel: 'a' },
    deviation: 0.42,
  }
}

export function buildResult(levelId: string, audioId: string, qualityFail: boolean, archived: boolean): AssessmentResult {
  const level = LEVEL_DETAILS[levelId]
  const scoreBase = 62 + (hashOf(audioId) % 34)
  const score = Math.min(98, scoreBase)
  if (qualityFail) {
    return {
      levelId,
      contentVersion: level?.contentVersion ?? 1,
      ruleVersion: 'rule-v1',
      providerVersion: 'provider-mock-1',
      algorithmVersion: 'algo-mock-1',
      storage: archived ? 'archived' : 'session',
      expiresAt: archived ? undefined : new Date(Date.now() + 72 * 3_600_000).toISOString(),
      quality: {
        verdict: 'fail',
        signal: {
          verdict: 'fail',
          volume: { dbfs: -30.2, pass: false, advice: '音量偏轻，请离麦克风近一些' },
          noise: { snrDb: 8.5, pass: false, advice: '环境噪声较大，请找安静的地方重录' },
          clipping: { ratio: 0, pass: true, advice: null },
          duration: { valueSec: 1.2, expectedSec: 2, pass: false, advice: '录音偏短，请读完整段提示词' },
        },
        reading: {},
        retakeAdvice: '找一个安静的地方，嘴巴离麦克风约一拳距离，用平常说话的音量再读一遍。',
      },
      boundaryNote: '学习参考，不作为普通话等级认定或医学诊断。',
    }
  }
  return {
    levelId,
    contentVersion: level?.contentVersion ?? 1,
    ruleVersion: 'rule-v1',
    providerVersion: 'provider-mock-1',
    algorithmVersion: 'algo-mock-1',
    storage: archived ? 'archived' : 'session',
    expiresAt: archived ? undefined : new Date(Date.now() + 72 * 3_600_000).toISOString(),
    quality: {
      verdict: 'pass',
      signal: {
        verdict: 'pass',
        volume: { dbfs: -22.1, pass: true, advice: null },
        noise: { snrDb: 21.4, pass: true, advice: null },
        clipping: { ratio: 0, pass: true, advice: null },
        duration: { valueSec: 4.2, expectedSec: 2, pass: true, advice: null },
      },
      reading: { missing: [], extra: [], repeated: [], replaced: [], disordered: false, advice: null },
      retakeAdvice: '',
    },
    score,
    phenomena: [
      {
        tag: 'tone_flat',
        syllable: level?.representativeChar ?? level?.targetSound ?? '',
        position: { syllableIndex: 0, part: 'tone' },
        description: `「${level?.representativeChar ?? level?.targetSound ?? ''}」的音高走向偏平，起伏比标准曲线小。`,
      },
    ],
    fourSteps: [
      {
        phenomenon: '音高走势偏平',
        possibleCause: '可能跟呼吸支撑和声带松紧有关',
        cue: '读之前先吸一口气，让声音自然起伏，不要压着说。',
        practice: { levelId, stepRef: `${levelId}-s2` },
        wordingSource: 'rule_template',
      },
    ],
    curve: buildCurve(levelId, audioId),
    formants: level?.layer === 'vowel' ? buildFormants() : undefined,
    boundaryNote: '学习参考，不作为普通话等级认定或医学诊断。',
  }
}

/* ------------------------------ 进度派生（D-24） ------------------------------ */

export function deriveProgress(): {
  levels: Array<{ levelId: string; completed: boolean; quiz: { passed: number; total: number }; practice: { done: number; total: number } }>
  nextLevelId?: string
} {
  const passed = new Map<string, Set<string>>()
  const done = new Map<string, Set<string>>()
  for (const event of state.learningEvents) {
    const summary = LEVEL_SUMMARIES.find((item) => item.id === event.levelId)
    if (!summary) continue
    if (event.kind === 'listen_quiz') {
      const set = passed.get(event.levelId) ?? new Set<string>()
      set.add(event.detail.questionId)
      passed.set(event.levelId, set)
    } else {
      const set = done.get(event.levelId) ?? new Set<string>()
      set.add(event.detail.stepId)
      done.set(event.levelId, set)
    }
  }
  const levels = LEVEL_SUMMARIES.map((summary) => {
    const quizPassed = passed.get(summary.id) ?? new Set<string>()
    const practiceDone = done.get(summary.id) ?? new Set<string>()
    const quizOk = summary.completionKeys.quizIds.every((id) => quizPassed.has(id))
    const practiceOk = summary.completionKeys.practiceStepIds.every((id) => practiceDone.has(id))
    return {
      levelId: summary.id,
      completed: quizOk && practiceOk,
      quiz: { passed: quizPassed.size, total: summary.completionKeys.quizIds.length },
      practice: { done: practiceDone.size, total: summary.completionKeys.practiceStepIds.length },
    }
  })
  const ordered = [...LEVEL_SUMMARIES].sort((a, b) => a.order - b.order)
  const next = ordered.find((item) => {
    const entry = levels.find((l) => l.levelId === item.id)
    return !entry?.completed
  })
  return { levels, nextLevelId: next?.id ?? ordered[0]?.id }
}
