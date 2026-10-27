/**
 * useRecordingResult 同键重试返回契约（FD-15）：
 * 返回 null = 无匹配 entry 未重试；changed = 后端重放产生新 recordingId，
 * composable 只同步内存交接，跳转与否由调用方决定（不再依赖 vue-router）。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, ref } from 'vue'
import { createPinia, setActivePinia } from 'pinia'

const { getRecordingMock, submitRecordingMock } = vi.hoisted(() => ({
  getRecordingMock: vi.fn(),
  submitRecordingMock: vi.fn(),
}))

vi.mock('@/api', () => ({
  ApiError: class ApiError extends Error {},
  DEFAULT_RETRY_AFTER_MS: 2000,
  detectionApi: {
    getRecording: getRecordingMock,
    submitRecording: submitRecordingMock,
  },
  identityApi: { context: vi.fn() },
}))

import { useRecordingResult } from '../result'
import { getSubmittedEntry, setSubmittedEntry } from '../submittedEntry'

/** 200 完成态响应：避免 202 分支在 node 测试环境走 window 轮询 */
const completed = { status: 200, data: { recording: { recordingId: 'R1', levelId: 'L01' }, result: null } }

function setup(recordingId: string) {
  const scope = effectScope()
  const result = scope.run(() => useRecordingResult(ref(recordingId)))!
  return { scope, result }
}

describe('useRecordingResult：retrySubmission 返回契约（FD-15）', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getRecordingMock.mockReset().mockResolvedValue(completed)
    submitRecordingMock.mockReset()
    setSubmittedEntry(null)
  })

  it('无内存 entry（刷新/直接打开）时不重试，返回 null', async () => {
    const { scope, result } = setup('R1')
    expect(await result.retrySubmission()).toBeNull()
    expect(submitRecordingMock).not.toHaveBeenCalled()
    scope.stop()
  })

  it('entry 与当前记录不匹配时不重试（同键重试仅对本记录）', async () => {
    setSubmittedEntry({ recordingId: 'R9', submissionId: 'S1', audioId: 'A1', levelId: 'L01' })
    const { scope, result } = setup('R1')
    expect(await result.retrySubmission()).toBeNull()
    expect(submitRecordingMock).not.toHaveBeenCalled()
    scope.stop()
  })

  it('同键重放返回同一 recordingId：changed = false 并原地重查', async () => {
    setSubmittedEntry({ recordingId: 'R1', submissionId: 'S1', audioId: 'A1', levelId: 'L01' })
    submitRecordingMock.mockResolvedValueOnce({ data: { recording: { recordingId: 'R1' } } })
    const { scope, result } = setup('R1')

    const outcome = await result.retrySubmission()
    expect(outcome).toEqual({ recordingId: 'R1', changed: false })
    expect(submitRecordingMock).toHaveBeenCalledWith({ audioId: 'A1', levelId: 'L01', submissionId: 'S1' })
    // 创建时查询 1 次 + 重试成功后原地重查
    await vi.waitFor(() => expect(getRecordingMock).toHaveBeenCalledTimes(2))
    scope.stop()
  })

  it('后端重放产生新 recordingId：changed = true 且同步内存交接（跳转交调用方）', async () => {
    setSubmittedEntry({ recordingId: 'R1', submissionId: 'S1', audioId: 'A1', levelId: 'L01' })
    submitRecordingMock.mockResolvedValueOnce({ data: { recording: { recordingId: 'R2' } } })
    const { scope, result } = setup('R1')

    const outcome = await result.retrySubmission()
    expect(outcome).toEqual({ recordingId: 'R2', changed: true })
    expect(result.entry.value).toMatchObject({ recordingId: 'R2', submissionId: 'S1', audioId: 'A1', levelId: 'L01' })
    expect(getSubmittedEntry()?.recordingId).toBe('R2')
    scope.stop()
  })
})
