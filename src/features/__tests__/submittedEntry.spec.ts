/** submittedEntry 内存交接（FD-15）：默认无交接，set 后可读回，set(null) 复原 */
import { beforeEach, describe, expect, it } from 'vitest'
import { getSubmittedEntry, setSubmittedEntry } from '../submittedEntry'

describe('submittedEntry：提交流程 → 结果查询的内存交接（FD-15）', () => {
  beforeEach(() => {
    setSubmittedEntry(null)
  })

  it('默认为 null（刷新/直接打开结果页只提供重新录音）', () => {
    expect(getSubmittedEntry()).toBeNull()
  })

  it('提交成功写入后读回同一 entry', () => {
    const entry = { recordingId: 'R1', submissionId: 'S1', audioId: 'A1', levelId: 'L01' }
    setSubmittedEntry(entry)
    expect(getSubmittedEntry()).toBe(entry)
  })

  it('set(null) 清空交接（不再允许同键重试）', () => {
    setSubmittedEntry({ recordingId: 'R1', submissionId: 'S1', audioId: 'A1', levelId: 'L01' })
    setSubmittedEntry(null)
    expect(getSubmittedEntry()).toBeNull()
  })
})
