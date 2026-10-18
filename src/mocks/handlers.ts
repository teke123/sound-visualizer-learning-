/**
 * MSW handlers：按后端决策图契约模拟全部 1.0 端点（dev:mock 模式）。
 * 覆盖：内容/搜索/文章/媒体、上传、标定、检测（202 → 完成）、当前会话、
 * 档案与比较、学习事件与进度、账号与同意、反馈、预览。
 */
import { http, HttpResponse } from 'msw'
import type {
  ArchiveCompareResponse,
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
} from './fixtures'
import { CONSENT_TEXT_VERSION, buildResult, deriveProgress, resetSession, state } from './state'
import { TINY_PNG, freqForMediaId, makeMouthSvg, makeToneWav } from './media'

const requestId = () => `mock-${Math.random().toString(36).slice(2, 10)}`

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

function consentGranted() {
  return currentUser() !== null && state.session.consentStatus === 'granted'
}

function calibrationValid(): boolean {
  const cal = state.session.calibration
  if (cal.status === 'personal') return true
  if (cal.status === 'session' && cal.expiresAt) return new Date(cal.expiresAt).getTime() > Date.now()
  return cal.status === 'session'
}

function meContext(): MeContext {
  const user = currentUser()
  return {
    authenticated: user !== null,
    accountId: user ? `acct-${user.username}` : undefined,
    username: user?.username,
    consent: { status: user ? state.session.consentStatus : 'none', consentTextVersion: CONSENT_TEXT_VERSION },
    currentConsentTextVersion: CONSENT_TEXT_VERSION,
    calibration: state.session.calibration,
    dataEpoch: user ? state.session.dataEpoch : undefined,
    pendingTransfer:
      user && state.session.consentStatus === 'none'
        ? [...state.recordings.values()].filter((r) => r.recording.storage === 'session' && r.recording.status === 'completed').length
        : undefined,
    nextLevelId: consentGranted() ? deriveProgress().nextLevelId : LEVEL_SUMMARIES[0]?.id,
  }
}

function sessionRecordingList() {
  return [...state.recordings.values()]
    .filter((item) => item.recording.storage === 'session')
    .map((item) => ({
      recordingId: item.recording.recordingId,
      audioId: item.recording.audioId,
      levelId: item.recording.levelId,
      createdAt: item.recording.createdAt,
      expiresAt: item.recording.expiresAt ?? null,
      verdict: item.result?.quality.verdict ?? 'pass',
      score: item.result?.score,
    }))
}

/** 会话记录转档（同意 / 登录触发，D-14/D-21） */
function transferSession(): { transferredCount: number; calibrationUpgraded: boolean } {
  let count = 0
  for (const item of state.recordings.values()) {
    if (item.recording.storage === 'session' && item.recording.status === 'completed') {
      item.recording.storage = 'archived'
      item.recording.expiresAt = undefined
      if (item.result) {
        item.result.storage = 'archived'
        item.result.expiresAt = undefined
      }
      count += 1
    }
  }
  const upgraded = state.session.calibration.status === 'session'
  if (upgraded) state.session.calibration = { status: 'personal' }
  return { transferredCount: count, calibrationUpgraded: upgraded }
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
      return fail(404, 'LEVEL_NOT_PUBLISHED', '这一关未发布或已下架')
    }
    return envelope(detail)
  }),

  http.get('/api/search', ({ request }) => {
    const q = (new URL(request.url).searchParams.get('q') ?? '').trim().toLowerCase()
    const match = (level: (typeof LEVEL_SUMMARIES)[number]) =>
      [level.targetSound, level.pinyin, level.title, level.representativeChar ?? '', level.type]
        .join(' ')
        .toLowerCase()
        .includes(q)
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
    if (!article) return fail(404, 'NOT_FOUND', '文章不存在或未发布')
    return envelope(article)
  }),

  /* --------------------------------- 媒体 --------------------------------- */

  http.get('/api/media/:id', ({ params }) => {
    const id = String(params.id)
    if (id.startsWith('img-')) {
      const label = decodeURIComponent(id)
      return new HttpResponse(makeMouthSvg(label, '#26a69a'), {
        headers: { 'Content-Type': 'image/svg+xml', 'Cache-Control': 'no-cache' },
      })
    }
    const wav = makeToneWav({ durationSec: 0.8, freq: freqForMediaId(id) })
    return new HttpResponse(wav, {
      headers: { 'Content-Type': 'audio/wav', 'Cache-Control': 'no-cache' },
    })
  }),

  http.get('/api/preview/media/:id', ({ request }) => {
    const token = new URL(request.url).searchParams.get('token')
    if (token !== 'demo-token') return fail(401, 'AUTH_REQUIRED', '预览令牌无效')
    const id = new URL(request.url).pathname.split('/').pop() ?? ''
    if (id.startsWith('img-')) {
      return new HttpResponse(makeMouthSvg(id, '#7e57c2'), {
        headers: { 'Content-Type': 'image/svg+xml', 'Cache-Control': 'no-store' },
      })
    }
    return new HttpResponse(makeToneWav({ durationSec: 0.8, freq: freqForMediaId(id) }), {
      headers: { 'Content-Type': 'audio/wav', 'Cache-Control': 'no-store' },
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
      expiresAt: new Date(Date.now() + 72 * 3_600_000).toISOString(),
    })
    return envelope({
      audioId,
      duration: 4,
      format: 'webm;codecs=opus',
      expiresAt: state.uploads.get(audioId)!.expiresAt,
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

  http.get('/api/pitch-calibration', () =>
    envelope({
      text: CALIBRATION_TEXT.text,
      textVersion: CALIBRATION_TEXT.textVersion,
      status: state.session.calibration.status,
      pitchRange: state.session.calibration.status === 'none' ? undefined : { fLo: 120, fHi: 260 },
      vowelSpaceReady: state.session.calibration.status !== 'none',
      expiresAt: state.session.calibration.expiresAt,
    }),
  ),

  http.post('/api/pitch-calibration', async ({ request }) => {
    const body = (await request.json()) as { audioId: string; textVersion: string }
    if (body.textVersion !== CALIBRATION_TEXT.textVersion) {
      return fail(409, 'CONTENT_VERSION_CHANGED', '标定文本已更新，请重新读取')
    }
    if (!state.uploads.has(body.audioId)) return fail(404, 'NOT_FOUND', '上传不存在或已过期')
    // 每两次标定演示一次 CALIBRATION_FAIL（HTTP 200 业务结果）
    state.submissionCounter += 1
    const failThis = state.submissionCounter % 5 === 0
    if (failThis) {
      return envelope(
        {
          reason: '未检出足够的有声段',
          signal: {
            verdict: 'fail',
            volume: { dbfs: -30.1, pass: false, advice: '请用平常说话的音量完整朗读整段文本' },
            noise: { snrDb: 6.2, pass: false, advice: '环境噪声较大，请找安静的地方重录' },
          },
        },
        { code: 'CALIBRATION_FAIL', message: '标定未得出有效音域' },
      )
    }
    const personal = consentGranted()
    state.session.calibration = personal
      ? { status: 'personal' }
      : { status: 'session', expiresAt: new Date(Date.now() + 72 * 3_600_000).toISOString() }
    state.uploads.delete(body.audioId) // 标定音频用后即删
    return envelope({
      ok: true,
      status: state.session.calibration.status,
      pitchRange: { fLo: 110 + Math.round(Math.random() * 30), fHi: 240 + Math.round(Math.random() * 40) },
      vowelSpaceReady: true,
      rangeSnapshotId: `prs-mock-${Math.random().toString(36).slice(2, 8)}`,
      expiresAt: state.session.calibration.expiresAt ?? null,
      updatedAt: new Date().toISOString(),
    })
  }),

  /* ------------------------------ 录音与检测 ------------------------------ */

  http.post('/api/recordings', async ({ request }) => {
    const body = (await request.json()) as { audioId: string; levelId: string; contentVersion: number; submissionId: string }
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
    if (!state.uploads.has(body.audioId)) return fail(404, 'NOT_FOUND', '上传不存在或已过期')
    if (!calibrationValid()) return fail(409, 'CALIBRATION_REQUIRED', '没有有效音域，请先完成标定')
    const level = LEVEL_DETAILS[body.levelId]
    if (!level || !PUBLISHED_IDS.includes(body.levelId)) return fail(404, 'LEVEL_NOT_PUBLISHED', '关卡未发布')
    if (body.contentVersion !== level.contentVersion) {
      return fail(409, 'CONTENT_VERSION_CHANGED', '关卡内容已更新，请刷新任务')
    }

    state.submissionCounter += 1
    const pattern = state.submissionCounter % 4
    const recordingId = `rec-${Math.random().toString(36).slice(2, 10)}`
    const archived = consentGranted()
    const recording: RecordingDTO = {
      recordingId,
      audioId: body.audioId,
      levelId: body.levelId,
      contentVersion: body.contentVersion,
      status: 'processing',
      stage: 'queued',
      storage: archived ? 'archived' : 'session',
      expiresAt: archived ? undefined : new Date(Date.now() + 72 * 3_600_000).toISOString(),
      createdAt: new Date().toISOString(),
    }
    state.recordings.set(recordingId, {
      recording,
      submissionPayload: payload,
      result: null,
      qualityFail: pattern === 3,
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
    if (!stored) return fail(404, 'NOT_FOUND', '记录已过期或不可见')
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

  /* ------------------------------ 当前会话 ------------------------------ */

  http.get('/api/session/recordings', () => {
    const recordings = sessionRecordingList()
    return envelope({ recordings, transferableCount: recordings.length })
  }),

  http.post('/api/session/reset', () => {
    for (const [id, item] of state.recordings) {
      if (item.recording.storage === 'session') state.recordings.delete(id)
    }
    state.session.calibration = { status: 'none' }
    resetSession()
    return envelope({ reset: true, newSidIssued: !currentUser() })
  }),

  /* --------------------------- 档案、学习与进度 --------------------------- */

  http.get('/api/me/recordings', ({ request }) => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    if (!consentGranted()) return fail(403, 'CONSENT_REQUIRED', '需要先同意保存')
    void request
    const recordings = [...state.recordings.values()]
      .filter((item) => item.recording.storage === 'archived')
      .map((item) => ({
        recordingId: item.recording.recordingId,
        audioId: item.recording.audioId,
        levelId: item.recording.levelId,
        contentVersion: item.recording.contentVersion,
        ruleVersion: 'rule-v1',
        createdAt: item.recording.createdAt,
        verdict: item.result?.quality.verdict ?? 'pass',
        score: item.result?.score,
      }))
    return envelope({ recordings, nextCursor: null })
  }),

  http.delete('/api/me/recordings', () => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    let deleted = 0
    for (const [id, item] of state.recordings) {
      if (item.recording.storage === 'archived') {
        state.recordings.delete(id)
        deleted += 1
      }
    }
    return envelope({ deleted })
  }),

  http.get('/api/me/recordings/compare', ({ request }) => {
    const url = new URL(request.url)
    const a = url.searchParams.get('a') ?? ''
    const b = url.searchParams.get('b') ?? ''
    const sideA = state.recordings.get(a)
    const sideB = state.recordings.get(b)
    if (!sideA || !sideB) return fail(404, 'NOT_FOUND', '记录不存在或不可见')
    if (sideA.recording.levelId !== sideB.recording.levelId) {
      return fail(422, 'VALIDATION_ERROR', '只能比较同一关的两条记录')
    }
    const toSide = (item: typeof sideA) => ({
      recording: {
        recordingId: item.recording.recordingId,
        audioId: item.recording.audioId,
        levelId: item.recording.levelId,
        contentVersion: item.recording.contentVersion,
        ruleVersion: 'rule-v1',
        createdAt: item.recording.createdAt,
        verdict: item.result?.quality.verdict ?? 'pass',
        score: item.result?.score,
      },
      result: item.result,
      rangeSnapshot: null,
    })
    const sameVersion = sideA.recording.contentVersion === sideB.recording.contentVersion
    const scoreA = sideA.result?.score
    const scoreB = sideB.result?.score
    const differences: Array<{ dimension: string; description: string }> = []
    if (typeof scoreA === 'number' && typeof scoreB === 'number' && scoreA !== scoreB) {
      const later = new Date(sideB.recording.createdAt ?? 0) > new Date(sideA.recording.createdAt ?? 0) ? '后一条' : '前一条'
      differences.push({
        dimension: '分数',
        description: `两次相差 ${Math.abs(Math.round(scoreA - scoreB))} 分（${later}更高一些）`,
      })
    }
    differences.push({ dimension: '音高曲线', description: '两条曲线的整体走向接近，起伏幅度略有差异。' })
    const data: ArchiveCompareResponse = {
      a: toSide(sideA),
      b: toSide(sideB),
      comparable: { score: sameVersion, curve: true },
      reasons: sameVersion ? [] : ['两条记录的内容版本不同，分数不能直接比较'],
      differences: sameVersion ? differences : differences.filter((d) => d.dimension !== '分数'),
    }
    return envelope(data)
  }),

  http.post('/api/learning-events', async ({ request }) => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    if (!consentGranted()) return fail(403, 'CONSENT_REQUIRED', '需要先同意保存')
    const body = (await request.json()) as { events: Array<{ eventId: string; levelId: string; kind: string; detail: Record<string, unknown> }> }
    let accepted = 0
    let duplicates = 0
    const rejected: Array<{ eventId: string; code: string }> = []
    for (const event of body.events.slice(0, 50)) {
      const exists = state.learningEvents.some((e) => e.eventId === event.eventId)
      if (exists) {
        duplicates += 1
        continue
      }
      const summary = LEVEL_SUMMARIES.find((item) => item.id === event.levelId)
      if (!summary) {
        rejected.push({ eventId: event.eventId, code: 'LEVEL_NOT_PUBLISHED' })
        continue
      }
      if (event.kind === 'listen_quiz') {
        state.learningEvents.push({
          eventId: event.eventId,
          levelId: event.levelId,
          contentVersion: 1,
          kind: 'listen_quiz',
          detail: { questionId: String(event.detail.questionId), choiceIndex: Number(event.detail.choiceIndex) },
        })
      } else {
        state.learningEvents.push({
          eventId: event.eventId,
          levelId: event.levelId,
          contentVersion: 1,
          kind: 'practice_done',
          detail: { stepId: String(event.detail.stepId) },
        })
      }
      accepted += 1
    }
    return envelope({ accepted, duplicates, rejected })
  }),

  http.get('/api/me/progress', () => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    if (!consentGranted()) return fail(403, 'CONSENT_REQUIRED', '需要先同意保存')
    return envelope(deriveProgress())
  }),

  /* ------------------------------ 账号与同意 ------------------------------ */

  http.post('/api/auth/register', async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string }
    if (!/^[\w\u4e00-\u9fa5]{3,32}$/.test(body.username)) {
      return fail(422, 'VALIDATION_ERROR', '用户名需 3–32 位字母、数字、下划线或中文')
    }
    if (body.password.length < 8) return fail(422, 'VALIDATION_ERROR', '密码至少 8 位')
    if (state.users.has(body.username)) return fail(409, 'USERNAME_TAKEN', '用户名已被使用')
    state.users.set(body.username, { username: body.username, password: body.password })
    return envelope({ accountId: `acct-${body.username}`, username: body.username })
  }),

  http.post('/api/auth/login', async ({ request }) => {
    const body = (await request.json()) as { username: string; password: string }
    const user = state.users.get(body.username)
    if (!user || user.password !== body.password) {
      return fail(401, 'INVALID_CREDENTIALS', '用户名或密码不正确')
    }
    state.session.authenticated = user
    let transfer: { status: string; transferredCount: number; calibrationUpgraded?: boolean } | undefined
    if (state.session.consentStatus === 'granted') {
      const result = transferSession()
      transfer = { status: 'completed', ...result }
    }
    return envelope({ context: meContext(), transfer })
  }),

  http.post('/api/auth/logout', () => {
    resetSession()
    return envelope({ loggedOut: true })
  }),

  http.get('/api/me/consent', () => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    return envelope({
      status: state.session.consentStatus,
      consentTextVersion: CONSENT_TEXT_VERSION,
      currentConsentTextVersion: CONSENT_TEXT_VERSION,
      consentText:
        '同意保存后，将保存你的学习进度、录音与检测结果；当前会话未过期的临时录音与音域标定会一并转存。临时录音最长保留 72 小时；你可随时删除或撤回同意（撤回将删除全部录音、进度与音域）。',
      timeline: state.session.decisions,
    })
  }),

  http.post('/api/me/consent', async ({ request }) => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    const body = (await request.json()) as { decision: 'granted' | 'rejected'; consentTextVersion: string }
    if (body.consentTextVersion !== CONSENT_TEXT_VERSION) {
      return fail(409, 'CONTENT_VERSION_CHANGED', '同意文案版本不一致')
    }
    let transfer = { status: 'none', transferredCount: 0 }
    if (body.decision === 'granted') {
      const already = state.session.consentStatus === 'granted'
      if (!already) {
        state.session.decisions.push({ decision: 'granted', consentTextVersion: CONSENT_TEXT_VERSION, createdAt: new Date().toISOString() })
        state.session.consentStatus = 'granted'
      }
      const result = transferSession()
      transfer = { status: 'completed', ...result }
    } else {
      state.session.decisions.push({ decision: 'rejected', consentTextVersion: CONSENT_TEXT_VERSION, createdAt: new Date().toISOString() })
      state.session.consentStatus = 'rejected'
    }
    return envelope({
      consent: { status: state.session.consentStatus, consentTextVersion: CONSENT_TEXT_VERSION },
      transfer,
    })
  }),

  http.delete('/api/me/consent', () => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    state.recordings.clear()
    state.learningEvents = []
    state.session.calibration = { status: 'none' }
    state.session.dataEpoch += 1
    state.session.decisions.push({ decision: 'revoked', consentTextVersion: CONSENT_TEXT_VERSION, createdAt: new Date().toISOString() })
    state.session.consentStatus = 'revoked'
    return envelope({ consent: { status: 'revoked' as const }, dataEpoch: state.session.dataEpoch })
  }),

  http.delete('/api/me/account', async ({ request }) => {
    if (!currentUser()) return fail(401, 'AUTH_REQUIRED', '需要登录')
    const body = (await request.json()) as { password: string }
    const user = currentUser()
    if (user!.password !== body.password) return fail(401, 'INVALID_CREDENTIALS', '密码不正确')
    state.users.delete(user!.username)
    state.recordings.clear()
    state.learningEvents = []
    resetSession()
    return envelope({ deleted: true })
  }),

  /* ------------------------------ 反馈与预览 ------------------------------ */

  http.post('/api/feedback', () => envelope({ feedbackId: `fb-${Math.random().toString(36).slice(2, 10)}` })),

  http.post('/api/wishes', () => envelope({ wishId: `wish-${Math.random().toString(36).slice(2, 10)}` })),

  http.get('/api/preview/levels/:id', ({ request }) => {
    const token = new URL(request.url).searchParams.get('token')
    if (token !== 'demo-token') return fail(401, 'AUTH_REQUIRED', '预览令牌无效或已过期')
    const id = String(params0(request))
    const base = LEVEL_DETAILS[id]
    if (!base) return fail(404, 'NOT_FOUND', '草稿不存在')
    return envelope({ ...base, contentVersion: 99 })
  }),

  http.get('/api/preview/articles/:slug', ({ request }) => {
    const token = new URL(request.url).searchParams.get('token')
    if (token !== 'demo-token') return fail(401, 'AUTH_REQUIRED', '预览令牌无效或已过期')
    const article = ARTICLES.find((a) => a.slug === String(params0(request)))
    if (!article) return fail(404, 'NOT_FOUND', '草稿不存在')
    return envelope({ ...article, contentVersion: 99, title: `${article.title}（草稿）` })
  }),
]

function params0(request: Request): string {
  const parts = new URL(request.url).pathname.split('/')
  return parts[parts.length - 1] ?? ''
}

/** 到时完成：写结果快照（质量合格 / 不合格两种演示形态） */
function finishRecording(recordingId: string) {
  const stored = state.recordings.get(recordingId)
  if (!stored || stored.recording.status !== 'processing') return
  stored.recording.status = 'completed'
  stored.recording.stage = undefined
  stored.result = buildResult(
    stored.recording.levelId,
    stored.recording.audioId,
    stored.qualityFail,
    stored.recording.storage === 'archived',
  )
}
