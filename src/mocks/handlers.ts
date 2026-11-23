/**
 * MSW handlers：按后端决策图契约模拟全部 1.0 端点（dev:mock 模式）。
 * 覆盖：内容/搜索/文章/媒体、上传、标定、检测（202 → 完成）、
 * 档案、进度、账号、反馈。
 * 口径：注册 / 登录即默认同意服务条款；进度与录音归属登录账号；
 * 进度完成 = 本关至少一条检测录音；录音质量仅作提示，不拦截评分；
 * 未标定可跳过（D-20）。
 */
import { http, HttpResponse } from 'msw'
import { stripToneMarks } from '@/phonology/mandarin'
import type {
  LevelsResponse,
  MeContext,
  RecordingDTO,
  SearchResponse,
} from '@/api'
import {
  ARTICLES,
  ARTICLE_CATEGORIES,
  ARTICLE_SUMMARIES,
  CALIBRATION_TEXT,
  CONFUSABLE_PAIRS,
  LEVEL_DETAILS,
  LEVEL_SUMMARIES,
  PUBLISHED_IDS,
  SKELETONS,
  VOWEL_TASKS,
} from './fixtures'
import { buildResult, deriveProgress, resetSession, state } from './state'
import { TINY_PNG, freqForMediaId, makeMouthGlb, makeMouthSvg, makeToneWav } from './media'

const requestId = () => `mock-${Math.random().toString(36).slice(2, 10)}`

/** 与后端 identity.usecases.DIALECT_CODES 对齐（FR-107） */
const DIALECT_CODES = new Set([
  'mandarin_north', 'mandarin_southwest', 'wu', 'yue', 'min', 'xiang', 'gan',
  'hakka', 'english', 'japanese', 'korean', 'other',
])

/** 与后端 identity.usecases.GENDER_CODES 对齐（FR-107） */
const GENDER_CODES = new Set(['male', 'female', 'other'])

function envelope<T>(data: T, init: { code?: string; message?: string; status?: number; headers?: Record<string, string> } = {}) {
  const { code = 'OK', message = '', status = 200, headers } = init
  return HttpResponse.json(
    { code, message, data, requestId: requestId() },
    { status, headers },
  )
}

function fail(status: number, code: string, message: string) {
  return HttpResponse.json({ code, message, data: null, requestId: requestId() }, { status })
}

const PROCESSING_MS = 4000

function currentUser() {
  return state.session.authenticated
}

function meContext(): MeContext {
  const user = currentUser()
  return {
    authenticated: user !== null,
    accountId: user ? `acct-${user.username}` : undefined,
    username: user?.username,
    dialectBackground: user?.dialectBackground ?? undefined,
    gender: user?.gender ?? undefined,
    calibration: state.session.calibration,
    nextLevelId: user ? deriveProgress().nextLevelId : LEVEL_SUMMARIES[0]?.id,
  }
}

/** 组装会话视图（进度由 takes 派生，与后端口径一致） */
function calibSessionView() {
  const session = state.calibSession
  if (!session) return null
  const acceptedOf = (vowel: string) =>
    session.takes.filter((t) => t.kind === 'vowel' && t.vowel === vowel && t.status === 'accepted').length
  const vowels = VOWEL_TASKS.map((cfg) => ({
    ...cfg,
    acceptedTakes: acceptedOf(cfg.key),
    done: acceptedOf(cfg.key) >= cfg.targetTakes,
  }))
  const pitchAccepted = session.takes.some((t) => t.kind === 'pitch' && t.status === 'accepted')
  const pendingVowel = vowels.find((v) => !v.done)
  const nextTask = session.status === 'completed'
    ? null
    : pendingVowel
      ? { kind: 'vowel' as const, vowel: pendingVowel.key, ordinal: pendingVowel.acceptedTakes + 1 }
      : pitchAccepted
        ? null
        : { kind: 'pitch' as const }
  return {
    sessionId: session.id,
    textVersion: CALIBRATION_TEXT.textVersion,
    passageText: CALIBRATION_TEXT.text,
    status: session.status,
    calcState: session.calcState,
    vowels,
    passageAccepted: pitchAccepted,
    nextTask,
    takes: session.takes.map((t) => ({
      audioId: t.audioId,
      kind: t.kind,
      vowel: t.vowel,
      ordinal: t.ordinal,
      status: t.status,
      measurements: t.measurements,
      createdAt: t.createdAt,
    })),
    ...(session.result
      ? {
          result: {
            ok: true,
            status: 'personal',
            pitchRange: session.result.pitchRange,
            vowelSpaceReady: true,
            rangeSnapshotId: session.result.rangeSnapshotId,
            updatedAt: session.result.updatedAt,
          },
        }
      : {}),
  }
}

export const handlers = [
  /* ------------------------------ 平台与内容 ------------------------------ */

  http.get('/api/health', () => envelope({ status: 'ok' })),

  http.get('/api/me/context', () => envelope(meContext())),

  http.get('/api/levels', () => {
    const data: LevelsResponse = {
      levels: LEVEL_SUMMARIES,
      skeleton: SKELETONS,
      confusablePairs: CONFUSABLE_PAIRS,
    }
    return envelope(data)
  }),

  http.get('/api/levels/:id', ({ params }) => {
    const id = String(params.id)
    const detail = LEVEL_DETAILS[id]
    if (!detail || !PUBLISHED_IDS.includes(id)) {
      return fail(404, 'LEVEL_NOT_PUBLISHED', '这一关未开放或已下架')
    }
    return envelope(detail)
  }),

  http.get('/api/search', ({ request }) => {
    const q = stripToneMarks((new URL(request.url).searchParams.get('q') ?? '').trim().toLowerCase())
    // 与后端同口径：带调拼音去声调符号后再比对（搜「ma」可命中「mā」）
    const match = (level: (typeof LEVEL_SUMMARIES)[number]) =>
      stripToneMarks(
        [level.targetSound, level.pinyin, level.title, level.representativeChar ?? '', level.type]
          .join(' ')
          .toLowerCase(),
      ).includes(q)
    const results = LEVEL_SUMMARIES.filter(match)
    const near = results.length === 0 ? LEVEL_SUMMARIES.slice(0, 3) : []
    const data: SearchResponse = { results, near, query: q }
    return envelope(data)
  }),

  http.get('/api/article-categories', () => envelope({ categories: ARTICLE_CATEGORIES })),

  http.get('/api/articles', ({ request }) => {
    const category = new URL(request.url).searchParams.get('category')
    const articles = category ? ARTICLE_SUMMARIES.filter((a) => a.category === category) : ARTICLE_SUMMARIES
    return envelope({ articles })
  }),

  http.get('/api/articles/:slug', ({ params }) => {
    const article = ARTICLES.find((a) => a.slug === String(params.slug))
    if (!article) return fail(404, 'NOT_FOUND', '文章不存在或未开放')
    return envelope(article)
  }),

  /* --------------------------------- 媒体 --------------------------------- */

  http.get('/api/media/:id', ({ params }) => {
    const id = String(params.id)
    if (id.startsWith('model3d-')) {
      return new HttpResponse(makeMouthGlb(), {
        headers: { 'Content-Type': 'model/gltf-binary', 'Cache-Control': 'no-cache' },
      })
    }
    if (id.startsWith('img-')) {
      const label = decodeURIComponent(id)
      return new HttpResponse(makeMouthSvg(label, '#cb3a2e'), {
        headers: { 'Content-Type': 'image/svg+xml', 'Cache-Control': 'no-cache' },
      })
    }
    const wav = makeToneWav({ durationSec: 0.8, freq: freqForMediaId(id) })
    return new HttpResponse(wav, {
      headers: { 'Content-Type': 'audio/wav', 'Cache-Control': 'no-cache' },
    })
  }),

  /* ------------------------------ 音频与标定 ------------------------------ */

  http.post('/api/audio/uploads', async ({ request }) => {
    const form = await request.formData()
    const purpose = (form.get('purpose') as string) === 'calibration' ? 'calibration' : 'recording'
    const audioId = `au-${Math.random().toString(36).slice(2, 10)}`
    state.uploads.set(audioId, {
      purpose,
      durationSec: 3 + Math.random() * 5,
    })
    return envelope({
      audioId,
      duration: 4,
      format: 'webm;codecs=opus',
    })
  }),

  http.get('/api/audio/:id/file', ({ params }) => {
    const id = String(params.id)
    if (!state.uploads.has(id) && !id.startsWith('au-')) return fail(404, 'NOT_FOUND', '音频不存在或已过期')
    return new HttpResponse(makeToneWav({ durationSec: 2.4, freq: freqForMediaId(id) }), {
      headers: { 'Content-Type': 'audio/wav', 'Cache-Control': 'private, no-store' },
    })
  }),

  http.get('/api/audio/:id/f0', ({ params }) => {
    const id = String(params.id)
    const frames = Array.from({ length: 40 }, (_, i) => ({
      t: Number((i * 0.03).toFixed(3)),
      hz: 150 + 60 * Math.sin(i * 0.25) + (freqForMediaId(id) % 30),
    }))
    return envelope({ algorithmVersion: 'algo-mock-1', hopMs: 30, frames, voicedRanges: [[0, 1.2]], voicedRatio: 0.62 })
  }),

  http.get('/api/audio/:id/formants', () =>
    envelope({
      algorithmVersion: 'algo-mock-1',
      frames: Array.from({ length: 24 }, (_, i) => ({
        t: Number((i * 0.05).toFixed(3)),
        f1: 800 + Math.round(30 * Math.sin(i)),
        f2: 1250 + Math.round(40 * Math.cos(i)),
      })),
      vowelSegments: [{ t: 0, vowel: 'a' }],
    }),
  ),

  http.get('/api/audio/:id/formants.png', () =>
    new HttpResponse(TINY_PNG, { headers: { 'Content-Type': 'image/png', 'Cache-Control': 'private, no-store' } }),
  ),

  http.get('/api/audio/:id/spectrogram.png', () =>
    new HttpResponse(TINY_PNG, { headers: { 'Content-Type': 'image/png', 'Cache-Control': 'private, no-store' } }),
  ),

  // 音高哼鸣（docs §5.2）：用户侧与标准侧共用合成音
  http.get('/api/audio/:id/f0-hum.wav', ({ request, params }) => {
    const url = new URL(request.url)
    const freq = url.searchParams.has('fhi') ? 220 : freqForMediaId(String(params.id))
    return new HttpResponse(makeToneWav({ durationSec: 0.7, freq: Math.max(80, freq % 400 + 120) }), {
      headers: { 'Content-Type': 'audio/wav', 'Cache-Control': 'private, no-store' },
    })
  }),

  http.get('/api/media/:id/f0-hum.wav', ({ request }) => {
    const url = new URL(request.url)
    const freq = url.searchParams.has('fhi') ? 200 : 240
    return new HttpResponse(makeToneWav({ durationSec: 0.7, freq }), {
      headers: { 'Content-Type': 'audio/wav', 'Cache-Control': 'no-cache' },
    })
  }),

  http.get('/api/pitch-calibration', () =>
    envelope({
      text: CALIBRATION_TEXT.text,
      textVersion: CALIBRATION_TEXT.textVersion,
      status: state.session.calibration.status,
      pitchRange: state.session.calibration.status === 'none' ? undefined : { fLo: 120, fHi: 260 },
      vowelSpaceReady: state.session.calibration.status !== 'none',
      vowelTasks: VOWEL_TASKS,
    }),
  ),

  // ---- 标定会话（个人标定流程改造方案）：创建/恢复 → 单条验收 → 最终计算 ----


  http.post('/api/pitch-calibration/sessions', () => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    if (!state.calibSession) {
      state.calibSession = {
        id: `cal-mock-${Math.random().toString(36).slice(2, 10)}`,
        status: 'active',
        calcState: 'idle',
        takes: [],
        result: null,
      }
    }
    return envelope(calibSessionView())
  }),

  http.get('/api/pitch-calibration/sessions/:sessionId', ({ params }) => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    const view = calibSessionView()
    if (!view || view.sessionId !== params.sessionId) return fail(404, 'NOT_FOUND', '标定会话不存在')
    return envelope(view)
  }),

  http.post('/api/pitch-calibration/sessions/:sessionId/takes', async ({ request, params }) => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    const view = calibSessionView()
    if (!view || view.sessionId !== params.sessionId) return fail(404, 'NOT_FOUND', '标定会话不存在')
    const session = state.calibSession!
    const body = (await request.json()) as { audioId: string; kind: 'vowel' | 'pitch'; vowel?: string }
    if (!state.uploads.has(body.audioId)) return fail(404, 'NOT_FOUND', '上传不存在')
    if (view.nextTask?.kind !== body.kind || (body.kind === 'vowel' && view.nextTask.vowel !== body.vowel)) {
      return fail(422, 'VALIDATION_ERROR', '请按当前任务顺序录音')
    }
    // 每几次提交演示一次质检不过（retry_take：本条重录，其余进度保留）
    state.submissionCounter += 1
    if (state.submissionCounter % 5 === 0) {
      return envelope({
        outcome: 'retry_take',
        reason: '未检出足够的有声段',
        signal: {
          verdict: 'fail',
          volume: { dbfs: -30.1, pass: false, advice: '请用平常说话的音量发音' },
          noise: { snrDb: 6.2, pass: false, advice: '环境噪声较大，请找安静的地方重录' },
        },
        session: view,
      })
    }
    session.takes.push({
      audioId: body.audioId,
      kind: body.kind,
      vowel: body.kind === 'vowel' ? body.vowel ?? null : null,
      ordinal: body.kind === 'vowel'
        ? session.takes.filter((t) => t.vowel === body.vowel).length + 1
        : 1,
      status: 'accepted',
      measurements: body.kind === 'pitch'
        ? { fLo: 118.4, fHi: 252.7, f0Median: 176.5, validFrames: 182, textVersion: CALIBRATION_TEXT.textVersion }
        : { f1: 320.5, f2: 2301.2, f3: 3560.8, f1Std: 8.2, f2Std: 21.4, f3Std: 44.9, nFrames: 42, voicedSec: 0.9, steady: [0.25, 0.61], ceiling: 5500 },
      createdAt: new Date().toISOString(),
    })
    return envelope({
      outcome: 'accepted',
      reason: null,
      signal: null,
      session: calibSessionView(),
    })
  }),

  http.post('/api/pitch-calibration/sessions/:sessionId/complete', ({ params }) => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    const view = calibSessionView()
    if (!view || view.sessionId !== params.sessionId) return fail(404, 'NOT_FOUND', '标定会话不存在')
    const session = state.calibSession!
    if (session.status === 'completed' || session.calcState === 'processing') {
      return envelope(view)
    }
    if (view.nextTask) return fail(422, 'VALIDATION_ERROR', '标定任务尚未完成')
    session.calcState = 'processing'
    // 模拟后台计算：稍后落为完成（GET 查询可见）
    setTimeout(() => {
      const s = state.calibSession
      if (!s || s.calcState !== 'processing') return
      s.calcState = 'done'
      s.status = 'completed'
      s.result = {
        pitchRange: { fLo: 110 + Math.round(Math.random() * 30), fHi: 240 + Math.round(Math.random() * 40) },
        rangeSnapshotId: `prs-mock-${Math.random().toString(36).slice(2, 8)}`,
        updatedAt: new Date().toISOString(),
      }
      state.session.calibration = { status: 'personal' }
      // 会话录音用后即删
      for (const take of s.takes) state.uploads.delete(take.audioId)
    }, 1500)
    return envelope({ ...view, calcState: 'processing' })
  }),

  /* ------------------------------ 录音与检测 ------------------------------ */

  http.post('/api/recordings', async ({ request }) => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录后才能录音检测')
    const body = (await request.json()) as { audioId: string; levelId: string; submissionId: string }
    const payload = JSON.stringify(body)
    // 幂等：同 submissionId 同负载重放；不同负载 409
    const replayId = state.submissions.get(body.submissionId)
    if (replayId) {
      const existing = state.recordings.get(replayId)
      if (existing && existing.submissionPayload === payload) {
        if (existing.recording.status === 'processing') {
          return envelope({ recording: existing.recording }, { status: 202, headers: { 'Retry-After': '1' } })
        }
        return envelope({ recording: existing.recording, result: existing.result ?? undefined })
      }
      return fail(409, 'IDEMPOTENCY_CONFLICT', '同一提交标识被用于不同负载')
    }
    if (!state.uploads.has(body.audioId)) return fail(404, 'NOT_FOUND', '上传不存在')
    const level = LEVEL_DETAILS[body.levelId]
    if (!level || !PUBLISHED_IDS.includes(body.levelId)) return fail(404, 'LEVEL_NOT_PUBLISHED', '关卡未开放')

    state.submissionCounter += 1
    const pattern = state.submissionCounter % 4
    const recordingId = `rec-${Math.random().toString(36).slice(2, 10)}`
    const recording: RecordingDTO = {
      recordingId,
      audioId: body.audioId,
      levelId: body.levelId,
      status: 'processing',
      stage: 'queued',
      createdAt: new Date().toISOString(),
    }
    state.recordings.set(recordingId, {
      recording,
      submissionPayload: payload,
      result: null,
      qualityTips: pattern === 3,
      createdAt: Date.now(),
    })
    state.submissions.set(body.submissionId, recordingId)

    if (pattern === 0) {
      // 短同步窗口内完成：直接 200
      finishRecording(recordingId)
      const stored = state.recordings.get(recordingId)!
      return envelope({ recording: stored.recording, result: stored.result ?? undefined })
    }
    return envelope({ recording }, { status: 202, headers: { 'Retry-After': '1' } })
  }),

  http.get('/api/recordings/:id', ({ params }) => {
    const id = String(params.id)
    const stored = state.recordings.get(id)
    if (!stored) return fail(404, 'NOT_FOUND', '记录已删除或不可见')
    const elapsed = Date.now() - stored.createdAt
    if (stored.recording.status === 'processing') {
      if (elapsed < PROCESSING_MS) {
        const stage = elapsed < 1200 ? 'queued' : elapsed < 2600 ? 'scoring' : 'analyzing'
        stored.recording.stage = stage
        return envelope({ recording: stored.recording }, { status: 202, headers: { 'Retry-After': '1' } })
      }
      finishRecording(id)
    }
    return envelope({ recording: stored.recording, result: stored.recording.status === 'failed' ? undefined : stored.result ?? undefined })
  }),

  http.delete('/api/recordings/:id', ({ params }) => {
    state.recordings.delete(String(params.id))
    return envelope({ deleted: true })
  }),

  /* --------------------------- 档案与进度 --------------------------- */

  http.get('/api/me/recordings', () => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    const recordings = [...state.recordings.values()].map((item) => ({
      recordingId: item.recording.recordingId,
      audioId: item.recording.audioId,
      levelId: item.recording.levelId,
      createdAt: item.recording.createdAt,
      verdict: item.result?.quality.signal?.verdict ?? null,
      qualityAdvice: item.result?.quality.advice ?? null,
      score: item.result?.score,
    }))
    return envelope({ recordings, nextCursor: null })
  }),

  http.delete('/api/me/recordings', () => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    const deleted = state.recordings.size
    state.recordings.clear()
    return envelope({ deleted })
  }),

  http.get('/api/me/progress', () => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    // 响应形状：{ levels: [{ levelId, completed }], nextLevelId }；completed = 本关有检测录音
    return envelope(deriveProgress())
  }),

  /* ------------------------------ 账号 ------------------------------ */

  http.post('/api/auth/register', async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string; dialectBackground?: string | null; gender?: string | null }
    if (!/^[\w\u4e00-\u9fa5]{3,32}$/.test(body.username)) {
      return fail(422, 'VALIDATION_ERROR', '用户名需 3–32 个字母、数字、下划线或中文')
    }
    if (body.password.length < 8) return fail(422, 'VALIDATION_ERROR', '密码至少 8 位')
    if (body.dialectBackground && !DIALECT_CODES.has(body.dialectBackground)) {
      return fail(422, 'VALIDATION_ERROR', '方言区/母语背景取值不在支持列表内')
    }
    if (body.gender && !GENDER_CODES.has(body.gender)) {
      return fail(422, 'VALIDATION_ERROR', '性别取值不在支持列表内')
    }
    if (state.users.has(body.username)) return fail(409, 'USERNAME_TAKEN', '用户名已被使用')
    state.users.set(body.username, {
      username: body.username,
      password: body.password,
      dialectBackground: body.dialectBackground || null,
      gender: body.gender || null,
    })
    return envelope({
      accountId: `acct-${body.username}`,
      username: body.username,
      dialectBackground: body.dialectBackground || null,
      gender: body.gender || null,
    })
  }),

  http.patch('/api/me/profile', async ({ request }) => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    const body = (await request.json()) as { dialectBackground?: string | null; gender?: string | null }
    if (body.dialectBackground && !DIALECT_CODES.has(body.dialectBackground)) {
      return fail(422, 'VALIDATION_ERROR', '方言区/母语背景取值不在支持列表内')
    }
    if (body.gender && !GENDER_CODES.has(body.gender)) {
      return fail(422, 'VALIDATION_ERROR', '性别取值不在支持列表内')
    }
    const user = currentUser()!
    user.dialectBackground = body.dialectBackground || null
    user.gender = body.gender || null
    return envelope({
      accountId: `acct-${user.username}`,
      username: user.username,
      dialectBackground: user.dialectBackground,
      gender: user.gender,
    })
  }),

  http.post('/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string }
    const user = state.users.get(body.username)
    if (!user || user.password !== body.password) {
      return fail(401, 'INVALID_CREDENTIALS', '用户名或密码不正确')
    }
    state.session.authenticated = user
    return envelope({ context: meContext() })
  }),

  http.post('/api/auth/logout', () => {
    resetSession()
    return envelope({ loggedOut: true })
  }),

  http.delete('/api/me/account', async ({ request }) => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    const body = (await request.json()) as { password: string }
    const user = currentUser()
    if (user!.password !== body.password) return fail(401, 'INVALID_CREDENTIALS', '密码不正确')
    state.users.delete(user!.username)
    state.recordings.clear()
    resetSession()
    return envelope({ deleted: true })
  }),

  /* ------------------------------ 反馈 ------------------------------ */

  http.post('/api/feedback', () => envelope({ feedbackId: `fb-${Math.random().toString(36).slice(2, 10)}` })),

  http.post('/api/feedback/wishes', () => envelope({ feedbackId: `fb-${Math.random().toString(36).slice(2, 10)}` })),
]

/** 到时完成：写结果快照（质量良好 / 带质量提示两种演示形态，均正常评分） */
function finishRecording(recordingId: string) {
  const stored = state.recordings.get(recordingId)
  if (!stored || stored.recording.status !== 'processing') return
  stored.recording.status = 'completed'
  stored.recording.stage = undefined
  stored.result = buildResult(stored.recording.levelId, stored.recording.audioId, stored.qualityTips)
}
