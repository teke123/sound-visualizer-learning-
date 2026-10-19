/**
 * MSW handler 共享的内存状态与结果合成（dev:mock 模式专用）。
 */
import type {
  AssessmentResult,
  AudioPurpose,
  LearningEvent,
  RecordingDTO,
  VotSpan,
} from '@/api'
import { LEVEL_DETAILS, LEVEL_SUMMARIES } from './fixtures'

export interface MockUser {
  username: string
  password: string
  /** 方言区/母语背景（FR-107，可选） */
  dialectBackground?: string | null
}

export interface MockSession {
  authenticated: MockUser | null
  calibration: { status: 'none' | 'personal' }
}

export interface MockRecording {
  recording: RecordingDTO
  submissionPayload: string
  result: AssessmentResult | null
  /** 质量提示演示（每 N 次一次；仅提示，不拦截评分） */
  qualityTips: boolean
  createdAt: number
}

export const state = {
  users: new Map<string, MockUser>([['learner', { username: 'learner', password: '12345678' }]]),
  session: {
    authenticated: null,
    calibration: { status: 'none' },
  } as MockSession,
  uploads: new Map<string, { purpose: AudioPurpose; durationSec: number }>(),
  recordings: new Map<string, MockRecording>(),
  submissions: new Map<string, string>(),
  learningEvents: [] as LearningEvent[],
  submissionCounter: 0,
}

export function resetSession() {
  state.session.authenticated = null
  state.session.calibration = { status: 'none' }
}

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
  const userRange = { fLo: 110, fHi: 320 }
  const refRange = { fLo: 130, fHi: 350 }
  const drift = ((seed % 40) - 20) / 80 // -0.25 ~ 0.25 度个体差
  const hzOf = (degree: number, range: { fLo: number; fHi: number }) =>
    range.fLo * Math.pow(range.fHi / range.fLo, (degree - 1) / 4)
  const buildSide = (range: { fLo: number; fHi: number }, offset: number) => {
    const nFrames = 61
    const analysisStart = 0.04
    const analysisEnd = 0.64
    const frames = Array.from({ length: nFrames }, (_, i) => {
      const t = analysisStart + (i / (nFrames - 1)) * (analysisEnd - analysisStart)
      const u = i / (nFrames - 1)
      const degree = 3 + 0.4 * Math.sin(u * Math.PI * 2) + offset * (0.4 + 0.6 * Math.sin(u * 3))
      const hz = hzOf(Math.min(5.4, Math.max(0.6, degree)), range)
      const gap = u > 0.44 && u < 0.52 // 模拟静音缺口：null 占位断开
      return {
        t: Number(t.toFixed(3)),
        hz: gap ? null : Number(hz.toFixed(1)),
        degree: gap ? null : Number(Math.min(5.4, Math.max(0.6, degree)).toFixed(2)),
        confidence: u > 0.7 ? 0.36 : 0.92,
        source: 'measured' as const,
        intensityDb: 60 + Math.round(8 * Math.sin(u * Math.PI)),
      }
    })
    const comparisonPoints = Array.from({ length: 21 }, (_, i) => {
      const u = i / 20
      const cp = frames[Math.round(u * (nFrames - 1))]!
      return {
        u: Number(u.toFixed(3)),
        hz: cp.hz,
        degree: cp.degree,
        confidence: cp.hz ? Math.min(cp.confidence, 0.9) : 0,
        source: cp.hz ? 'measured' : null,
      }
    })
    return {
      frames,
      t0: 0,
      t1: 0.8,
      analysisStart,
      analysisEnd,
      duration: 0.8,
      analysisDuration: Number((analysisEnd - analysisStart).toFixed(3)),
      comparisonPoints,
      chao: '33',
      shape: 'mid level',
      featurePoints: {
        start: { u: 0.05, degree: 3.1 },
        end: { u: 0.95, degree: 3.0 },
        turning: null,
      },
      quality: { validFrames: 52, coverage: 0.85, jumpDensity: 0.04, canDiagnose: true },
    }
  }
  return {
    status: 'ok',
    scale: 'degree',
    algorithmVersion: 'algo-mock-2',
    segments: [
      {
        syllable,
        toneValue: 1,
        user: buildSide(userRange, drift),
        reference: buildSide(refRange, 0),
      },
    ],
    rangeSnapshotId: 'range-mock-1',
    userRange,
    referenceRange: refRange,
    sampleMediaId: 'md-mock-sample',
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

/* 送气段（FR-1005）：按声母是否送气定参考值；user 随 hashOf 在 30–90 ms 波动 */
const ASPIRATED_INITIALS = ['p', 't', 'k', 'c', 'ch', 'q']
const FRICATIVE_INITIALS = ['f', 's', 'sh', 'x', 'h']
const VOICED_INITIALS = ['m', 'n', 'l', 'r']

function votSpan(onsetSec: number, votMs: number): VotSpan {
  return {
    onsetSec,
    voicingOnsetSec: Number((onsetSec + votMs / 1000).toFixed(3)),
    votMs,
  }
}

function buildVot(levelId: string): AssessmentResult['vot'] {
  const level = LEVEL_DETAILS[levelId]
  const target = level?.targetSound ?? ''
  const aspirated = ASPIRATED_INITIALS.includes(target)
  const referenceMs = !target ? 55 : aspirated ? 62 : 12
  const userMs = 30 + (hashOf(levelId) % 61)
  const aspiration: NonNullable<AssessmentResult['vot']>['aspiration'] = aspirated
    ? 'aspirated'
    : FRICATIVE_INITIALS.includes(target)
      ? 'fricative'
      : VOICED_INITIALS.includes(target)
        ? 'voiced'
        : 'unaspirated'
  return {
    status: 'ok',
    targetSound: target || null,
    aspiration,
    user: votSpan(0.3, userMs),
    reference: votSpan(0.15, referenceMs),
    referenceMediaId: 'md-mock-sample',
    note: null,
  }
}

export function buildResult(levelId: string, audioId: string, qualityTips: boolean): AssessmentResult {
  const level = LEVEL_DETAILS[levelId]
  const scoreBase = 62 + (hashOf(audioId) % 34)
  const score = Math.min(98, scoreBase)
  if (qualityTips) {
    // 质量字段仅作友好提示（FR-1301）：照常给出分数、现象与声学图像
    return {
      levelId,
      providerVersion: 'provider-mock-1',
      algorithmVersion: 'algo-mock-1',
      quality: {
        signal: {
          verdict: 'fail',
          volume: { dbfs: -30.2, pass: false, advice: '音量偏小，建议离麦克风近一些重录，共振峰图像会更清晰' },
          noise: { snrDb: 8.5, pass: false, advice: '底噪偏大，建议换一个安静的环境再录' },
          clipping: { ratio: 0, pass: true, advice: null },
          duration: { valueSec: 1.2, expectedSec: 2, pass: false, advice: '时长偏短，请读完整段提示词' },
        },
        reading: {},
        advice: '找一个安静的地方，嘴巴离麦克风约一拳距离，用平常说话的音量再录一次。',
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
      vot: level?.layer === 'initial' ? buildVot(levelId) : undefined,
    }
  }
  return {
    levelId,
    providerVersion: 'provider-mock-1',
    algorithmVersion: 'algo-mock-1',
    quality: {
      signal: {
        verdict: 'pass',
        volume: { dbfs: -22.1, pass: true, advice: null },
        noise: { snrDb: 21.4, pass: true, advice: null },
        clipping: { ratio: 0, pass: true, advice: null },
        duration: { valueSec: 4.2, expectedSec: 2, pass: true, advice: null },
      },
      reading: { missing: [], extra: [], repeated: [], replaced: [], disordered: false, advice: null },
      advice: null,
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
    vot: level?.layer === 'initial' ? buildVot(levelId) : undefined,
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
