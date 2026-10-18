/** 错误码 → 文案与下一步映射单测（§7 表 / §10 文案集中） */
import { describe, expect, it } from 'vitest'
import { ApiError } from '@/api'
import { errorCopy } from '../usePageCopy'

describe('errorCopy', () => {
  it('QUALITY_FAIL 使用固定「本次不能评」口径并给重录指引', () => {
    const copy = errorCopy(new ApiError({ status: 200, code: 'QUALITY_FAIL', message: '' }))
    expect(copy.title).toBe('本次不能评')
    expect(copy.hint).toContain('重录')
  })

  it('DETECTION_OFF 保留学习入口提示', () => {
    const copy = errorCopy(new ApiError({ status: 503, code: 'DETECTION_OFF', message: '' }))
    expect(copy.hint).toContain('学习')
  })

  it('TIMEOUT 提示同页面重试边界', () => {
    const copy = errorCopy(new ApiError({ status: 504, code: 'TIMEOUT', message: '' }))
    expect(copy.hint).toContain('重试')
  })

  it('未知错误码回落状态码映射，再回落通用错误', () => {
    const byStatus = errorCopy(new ApiError({ status: 500, code: 'SOMETHING', message: '' }))
    expect(byStatus.title).toBeTruthy()
    const unknown = errorCopy(new ApiError({ status: 599, code: 'UNKNOWN_CODE', message: '' }))
    expect(unknown.title).toBeTruthy()
  })

  it('非 ApiError 的未知异常给通用文案', () => {
    const copy = errorCopy(new Error('boom'))
    expect(copy.title).toBeTruthy()
  })
})
