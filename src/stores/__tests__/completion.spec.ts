/** D-24 完成度与 nextLevelId 单测（docs/architecture/04 §11 单元层） */
import { describe, expect, it } from 'vitest'
import type { LevelSummary } from '@/api'
import { computeNextLevelId, isLevelCompleted } from '../completion'

function level(id: string, order: number, quizIds: string[], stepIds: string[]): LevelSummary {
  return {
    id,
    order,
    layer: 'vowel',
    type: '单韵母',
    targetSound: id,
    pinyin: id,
    title: id,
    oneLiner: '',
    availability: 'open',
    completionKeys: { quizIds, practiceStepIds: stepIds },
  }
}

describe('isLevelCompleted（D-24）', () => {
  const keys = { quizIds: ['q1', 'q2'], practiceStepIds: ['s1', 's2'] }

  it('全部听辨题各答对一次且全部练习步骤各完成一次才算完成', () => {
    expect(isLevelCompleted(keys, new Set(['q1', 'q2']), new Set(['s1', 's2']))).toBe(true)
  })

  it('听辨题答错不计入：缺一题即未完成', () => {
    expect(isLevelCompleted(keys, new Set(['q1']), new Set(['s1', 's2']))).toBe(false)
  })

  it('练习步骤缺一步即未完成', () => {
    expect(isLevelCompleted(keys, new Set(['q1', 'q2']), new Set(['s1']))).toBe(false)
  })

  it('无题无步骤的关卡视为已完成', () => {
    expect(isLevelCompleted({ quizIds: [], practiceStepIds: [] }, new Set(), new Set())).toBe(true)
  })
})

describe('computeNextLevelId（FR-205 / FD-02）', () => {
  const levels = [
    level('L01', 1, ['q1'], ['s1']),
    level('L07', 7, ['q2'], ['s2']),
    level('L30', 30, ['q3'], ['s3']),
  ]

  it('返回公开顺序中第一个未完成的已发布关', () => {
    const completed = new Set(['L01'])
    expect(computeNextLevelId(levels, (l) => completed.has(l.id))).toBe('L07')
  })

  it('全部完成时回落 L01', () => {
    expect(computeNextLevelId(levels, () => true)).toBe('L01')
  })

  it('L01 未发布时回落第一已发布关', () => {
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
