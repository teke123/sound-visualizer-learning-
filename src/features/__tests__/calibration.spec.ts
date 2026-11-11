/**
 * useCalibration 会话流程契约（个人标定流程改造方案）：
 * 创建/恢复会话 → 单条验收推进（accepted / retry_take / additional_take_required）
 * → 任务齐备后发起最终计算并轮询 → 成功刷新 context；网络失败保留 blob 可重试。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

const {
  uploadAudioMock,
  createSessionMock,
  getSessionMock,
  submitTakeMock,
  completeSessionMock,
  contextMock,
} = vi.hoisted(() => ({
  uploadAudioMock: vi.fn(),
  createSessionMock: vi.fn(),
  getSessionMock: vi.fn(),
  submitTakeMock: vi.fn(),
  completeSessionMock: vi.fn(),
  contextMock: vi.fn(),
}))

vi.mock('@/api', () => ({
  ApiError: class ApiError extends Error {},
  DEFAULT_RETRY_AFTER_MS: 2000,
  detectionApi: {
    uploadAudio: uploadAudioMock,
    createCalibrationSession: createSessionMock,
    getCalibrationSession: getSessionMock,
    submitCalibrationTake: submitTakeMock,
    completeCalibrationSession: completeSessionMock,
  },
  identityApi: { context: contextMock },
}))

import { useCalibration } from '../calibration'
import { useContextStore } from '@/stores/context'
import { useRecorderStore } from '@/stores/recorder'

/** 会话视图替身：进度与 nextTask 由调用方按场景给定 */
function sessionView(overrides: Record<string, unknown> = {}) {
  return {
    sessionId: 'cal_test',
    textVersion: 'cal-v1',
    passageText: '短文',
    status: 'active',
    calcState: 'idle',
    vowels: [
      { key: 'i', displayText: '衣', pinyin: 'yī', ipa: '[i]', targetTakes: 2, acceptedTakes: 0, done: false },
      { key: 'u', displayText: '乌', pinyin: 'wū', ipa: '[u]', targetTakes: 2, acceptedTakes: 0, done: false },
      { key: 'a', displayText: '啊', pinyin: 'ā', ipa: '[a]', targetTakes: 2, acceptedTakes: 0, done: false },
      { key: 'ü', displayText: '迂', pinyin: 'yū', ipa: '[y]', targetTakes: 2, acceptedTakes: 0, done: false },
    ],
    passageAccepted: false,
    nextTask: { kind: 'vowel', vowel: 'i', ordinal: 1 },
    takes: [],
    ...overrides,
  }
}

function setup() {
  const scope = effectScope()
  const calibration = scope.run(() => useCalibration())!
  const recorder = useRecorderStore()
  const contextStore = useContextStore()
  return { scope, calibration, recorder, contextStore }
}

/** 把一条录音放进 recorder（模拟录完待提交状态） */
function withBlob(recorder: { blob: Blob | null }) {
  recorder.blob = new Blob(['wav'], { type: 'audio/wav' })
}

describe('useCalibration：会话创建与恢复', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    uploadAudioMock.mockReset()
    createSessionMock.mockReset()
    getSessionMock.mockReset()
    submitTakeMock.mockReset()
    completeSessionMock.mockReset()
    contextMock.mockReset().mockResolvedValue({
      data: { authenticated: true, username: 't', calibration: { status: 'personal' } },
    })
  })

  it('新会话：创建后进入 intro，当前待办为元音 i 第 1 条', async () => {
    const { scope, calibration } = setup()
    createSessionMock.mockResolvedValue({ data: sessionView() })
    await calibration.openSession()
    expect(calibration.phase.value).toBe('intro')
    expect(calibration.currentTask.value?.kind).toBe('vowel')
    expect(calibration.currentTask.value?.vowel).toBe('i')
    scope.stop()
  })

  it('已完成会话：直接进入 success 并展示结果', async () => {
    const { scope, calibration } = setup()
    createSessionMock.mockResolvedValue({
      data: sessionView({
        status: 'completed',
        calcState: 'done',
        result: { ok: true, pitchRange: { fLo: 100, fHi: 240 } },
      }),
    })
    await calibration.openSession()
    expect(calibration.phase.value).toBe('success')
    expect(calibration.result.value?.pitchRange.fLo).toBe(100)
    scope.stop()
  })

  it('创建失败：进入 failed 并保留错误', async () => {
    const { scope, calibration } = setup()
    createSessionMock.mockRejectedValue(new Error('network'))
    await calibration.openSession()
    expect(calibration.phase.value).toBe('failed')
    scope.stop()
  })
})

describe('useCalibration：单条验收推进', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    uploadAudioMock.mockReset().mockResolvedValue({ data: { audioId: 'au_1' } })
    createSessionMock.mockReset().mockResolvedValue({ data: sessionView() })
    getSessionMock.mockReset()
    submitTakeMock.mockReset()
    completeSessionMock.mockReset()
    contextMock.mockReset().mockResolvedValue({
      data: { authenticated: true, username: 't', calibration: { status: 'personal' } },
    })
  })

  it('accepted：以响应中的会话视图推进到下一任务，并给出提交反馈', async () => {
    const { scope, calibration, recorder } = setup()
    await calibration.openSession()
    withBlob(recorder)
    submitTakeMock.mockResolvedValue({
      data: {
        outcome: 'accepted',
        session: sessionView({
          vowels: [sessionView().vowels[0], ...sessionView().vowels.slice(1).map((v) => ({ ...v }))],
          nextTask: { kind: 'vowel', vowel: 'u', ordinal: 1 },
        }),
      },
    })
    const ok = await calibration.submit()
    expect(ok).toBe(true)
    expect(submitTakeMock).toHaveBeenCalledWith({
      sessionId: 'cal_test', audioId: 'au_1', kind: 'vowel', vowel: 'i',
    })
    expect(calibration.currentTask.value?.vowel).toBe('u')
    expect(calibration.phase.value).toBe('intro')
    expect(calibration.notice.value).toBe('「衣」已提交')
    scope.stop()
  })

  it('accepted 且该元音完成：反馈为已完成', async () => {
    const { scope, calibration, recorder } = setup()
    await calibration.openSession()
    withBlob(recorder)
    const vowels = sessionView().vowels.map((v) =>
      v.key === 'i' ? { ...v, acceptedTakes: 2, done: true } : v)
    submitTakeMock.mockResolvedValue({
      data: {
        outcome: 'accepted',
        session: sessionView({ vowels, nextTask: { kind: 'vowel', vowel: 'u', ordinal: 1 } }),
      },
    })
    await calibration.submit()
    expect(calibration.notice.value).toBe('「衣」已完成')
    scope.stop()
  })

  it('retry_take：显示重录指引并停留在当前任务', async () => {
    const { scope, calibration, recorder } = setup()
    await calibration.openSession()
    withBlob(recorder)
    submitTakeMock.mockResolvedValue({
      data: {
        outcome: 'retry_take',
        reason: '环境噪声较大',
        signal: { noise: { advice: '环境噪声较大，请找安静的地方重录' } },
        session: sessionView(),
      },
    })
    const ok = await calibration.submit()
    expect(ok).toBe(false)
    expect(calibration.failAdvice.value).toContain('安静的地方')
    expect(calibration.currentTask.value?.vowel).toBe('i')
    expect(calibration.phase.value).toBe('intro')
    scope.stop()
  })

  it('vowel_dispersed：提示重录该元音，任务不推进', async () => {
    const { scope, calibration, recorder } = setup()
    await calibration.openSession()
    withBlob(recorder)
    submitTakeMock.mockResolvedValue({
      data: { outcome: 'vowel_dispersed', session: sessionView() },
    })
    const ok = await calibration.submit()
    expect(ok).toBe(false)
    expect(calibration.dispersedNotice.value).toBe(true)
    expect(calibration.currentTask.value?.vowel).toBe('i')
    scope.stop()
  })

  it('additional_take_required：补录反馈明确，不阻塞推进', async () => {
    const { scope, calibration, recorder } = setup()
    await calibration.openSession()
    withBlob(recorder)
    submitTakeMock.mockResolvedValue({
      data: {
        outcome: 'additional_take_required',
        session: sessionView({ nextTask: { kind: 'vowel', vowel: 'i', ordinal: 3, additionalTake: true } }),
      },
    })
    const ok = await calibration.submit()
    expect(ok).toBe(true)
    expect(calibration.currentTask.value?.ordinal).toBe(3)
    expect(calibration.currentTask.value?.additionalTake).toBe(true)
    expect(calibration.notice.value).toBe('「衣」的录音差异较大，请再录一条')
    scope.stop()
  })
})

describe('useCalibration：最终计算', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    uploadAudioMock.mockReset().mockResolvedValue({ data: { audioId: 'au_1' } })
    createSessionMock.mockReset()
    getSessionMock.mockReset()
    submitTakeMock.mockReset()
    completeSessionMock.mockReset()
    contextMock.mockReset().mockResolvedValue({
      data: { authenticated: true, username: 't', calibration: { status: 'personal' } },
    })
  })

  async function completedFlow() {
    const { scope, calibration, recorder, contextStore } = setup()
    const doneSession = sessionView({
      status: 'completed',
      calcState: 'done',
      nextTask: null,
      passageAccepted: true,
      result: { ok: true, pitchRange: { fLo: 110, fHi: 250 }, rangeSnapshotId: 'prs_1' },
    })
    createSessionMock.mockResolvedValue({ data: sessionView() })
    await calibration.openSession()
    withBlob(recorder)
    // 最后一条（短文）验收通过 → nextTask 为空 → 自动发起最终计算
    submitTakeMock.mockResolvedValue({
      data: { outcome: 'accepted', session: sessionView({ nextTask: null, passageAccepted: true }) },
    })
    completeSessionMock.mockResolvedValue({ data: doneSession })
    const ok = await calibration.submit()
    return { ok, calibration, contextStore, scope, doneSession }
  }

  it('任务齐备：自动 complete → 轮询至 done → 刷新 context', async () => {
    const { ok, calibration, contextStore, scope } = await completedFlow()
    expect(ok).toBe(true)
    expect(completeSessionMock).toHaveBeenCalledWith('cal_test')
    expect(calibration.phase.value).toBe('success')
    expect(calibration.result.value?.pitchRange.fHi).toBe(250)
    expect(contextStore.context.calibration.status).toBe('personal')
    scope.stop()
  })

  it('计算失败：停留 computing 可重试（requestCompletion）', async () => {
    const { scope, calibration, recorder } = setup()
    createSessionMock.mockResolvedValue({ data: sessionView() })
    await calibration.openSession()
    withBlob(recorder)
    submitTakeMock.mockResolvedValue({
      data: { outcome: 'accepted', session: sessionView({ nextTask: null, passageAccepted: true }) },
    })
    completeSessionMock.mockResolvedValue({
      data: sessionView({ calcState: 'processing', nextTask: null, passageAccepted: true }),
    })
    getSessionMock.mockResolvedValue({
      data: sessionView({ calcState: 'failed', nextTask: null, passageAccepted: true, lastError: 'boom' }),
    })
    const ok = await calibration.submit()
    expect(ok).toBe(false)
    expect(calibration.phase.value).toBe('computing')

    // 手动重试：完成
    completeSessionMock.mockResolvedValue({
      data: sessionView({
        status: 'completed', calcState: 'done', nextTask: null, passageAccepted: true,
        result: { ok: true, pitchRange: { fLo: 110, fHi: 250 } },
      }),
    })
    const retried = await calibration.requestCompletion()
    expect(retried).toBe(true)
    expect(calibration.phase.value).toBe('success')
    scope.stop()
  })

  it('上传网络失败：保留 blob 回到 recorded 可重试', async () => {
    const { scope, calibration, recorder } = setup()
    createSessionMock.mockResolvedValue({ data: sessionView() })
    await calibration.openSession()
    withBlob(recorder)
    uploadAudioMock.mockRejectedValue(new Error('network'))
    const ok = await calibration.submit()
    expect(ok).toBe(false)
    expect(calibration.phase.value).toBe('recorded')
    expect(recorder.blob).not.toBeNull()
    scope.stop()
  })
})
