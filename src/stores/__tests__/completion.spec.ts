/** nextLevelId 派生单测（完成度口径：本关有检测录音即完成，见 completion.ts） */
import { describe, expect, it } from 'vitest'
import { computeNextLevelId } from '../completion'

describe('computeNextLevelId（FR-205 / FD-02）', () => {
  const levels = [
    { id: 'L01', order: 1 },
    { id: 'L07', order: 7 },
    { id: 'L30', order: 30 },
  ]

  it('返回公开顺序中第一个未完成的已开放关', () => {
    const completed = new Set(['L01'])
    expect(computeNextLevelId(levels, (l) => completed.has(l.id))).toBe('L07')
  })

  it('顺序打乱时仍按 order 找第一个未完成关', () => {
    const shuffled = [...levels].reverse()
    const completed = new Set(['L01', 'L07'])
    expect(computeNextLevelId(shuffled, (l) => completed.has(l.id))).toBe('L30')
  })

  it('全部完成时回落 L01', () => {
    expect(computeNextLevelId(levels, () => true)).toBe('L01')
  })

  it('L01 未开放时回落第一已开放关', () => {
    const withoutL01 = levels.slice(1)
    expect(computeNextLevelId(withoutL01, () => true)).toBe('L07')
  })

  it('无进度时从第一关开始', () => {
    expect(computeNextLevelId(levels, () => false)).toBe('L01')
  })

  it('空关卡列表返回 null', () => {
    expect(computeNextLevelId([], () => false)).toBe(null)
  })
})
