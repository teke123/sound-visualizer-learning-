/**
 * 发音库覆盖索引测试（§2.5 / §2.6 点亮口径）：
 * - cellLevelFor：音节关优先 → 声母关（含 Ø 行经 y/w 拼写关）→ 韵母关（点亮整列）；
 * - toneLevelFor：关卡声调必须明确（拼音标调或 phonology.tones），
 *   标调音节关只挂所标声调（L30「mā」只挂阴平）。
 */
import { describe, expect, it } from 'vitest'
import type { LevelSummary } from '@/api'
import { FINAL_BY_KEY } from '@/phonology/mandarin'
import { buildCoverage, cellLevelFor, toneLevelFor } from '../matching'

function mkLevel(partial: Partial<LevelSummary> & Pick<LevelSummary, 'id' | 'layer' | 'targetSound' | 'pinyin'>): LevelSummary {
  return {
    order: 1,
    type: '',
    title: partial.title ?? partial.id,
    availability: 'open',
    ...partial,
  } as LevelSummary
}

/** seed 关卡的代表性子集：b 声母关、a 韵母关、y 零声母拼写关、ma 四声调音节关（L30–L33） */
const LEVELS: LevelSummary[] = [
  mkLevel({ id: 'L04', layer: 'initial', targetSound: 'b', pinyin: 'bō' }),
  mkLevel({ id: 'L01', layer: 'vowel', targetSound: 'a', pinyin: 'ā' }),
  mkLevel({ id: 'L22', layer: 'initial', targetSound: 'y', pinyin: 'yī' }),
  mkLevel({ id: 'L30', layer: 'syllable', targetSound: 'mā', pinyin: 'mā' }),
  mkLevel({ id: 'L31', layer: 'syllable', targetSound: 'má', pinyin: 'má' }),
  mkLevel({ id: 'L32', layer: 'syllable', targetSound: 'mǎ', pinyin: 'mǎ' }),
  mkLevel({ id: 'L33', layer: 'syllable', targetSound: 'mà', pinyin: 'mà' }),
]

describe('cellLevelFor（音节表点亮口径）', () => {
  const cov = buildCoverage(LEVELS)

  it('声母关点亮其全部合法音节（bo 经 b 关点亮）', () => {
    expect(cellLevelFor(cov, 'b', FINAL_BY_KEY.get('o')!)?.id).toBe('L04')
    expect(cellLevelFor(cov, 'b', FINAL_BY_KEY.get('ai')!)?.id).toBe('L04')
  })

  it('韵母关点亮整列（a 关点亮 ba 与 Ø+a）', () => {
    expect(cellLevelFor(cov, 'b', FINAL_BY_KEY.get('a')!)?.id).toBe('L04') // 音节关优先级之外的声母关
    expect(cellLevelFor(cov, 'g', FINAL_BY_KEY.get('a')!)?.id).toBe('L01') // g 无关，回落 a 韵母关
    expect(cellLevelFor(cov, '', FINAL_BY_KEY.get('a')!)?.id).toBe('L01')
  })

  it('音节关优先于声母/韵母关（ma 挂 L30 而非 m/a 关）', () => {
    expect(cellLevelFor(cov, 'm', FINAL_BY_KEY.get('a')!)?.id).toBe('L30')
  })

  it('Ø 行经 y/w 拼写关点亮（yi 列经 y 关，开口呼不归 y/w）', () => {
    expect(cellLevelFor(cov, '', FINAL_BY_KEY.get('i')!)?.id).toBe('L22')
    expect(cellLevelFor(cov, '', FINAL_BY_KEY.get('ie')!)?.id).toBe('L22')
    // 开口呼零声母（如 ai）不经 y/w，且 ai 无韵母关 → 不点亮
    expect(cellLevelFor(cov, '', FINAL_BY_KEY.get('ai')!)).toBeNull()
  })

  it('无关音节返回 null（如 üan 列）', () => {
    expect(cellLevelFor(cov, 'j', FINAL_BY_KEY.get('üan')!)).toBeNull()
  })
})

describe('toneLevelFor（声调表关卡匹配）', () => {
  it('标调音节关各挂一个声调（L30–L33 分别对应妈/麻/马/骂）', () => {
    expect(toneLevelFor(LEVELS, 1)?.id).toBe('L30')
    expect(toneLevelFor(LEVELS, 2)?.id).toBe('L31')
    expect(toneLevelFor(LEVELS, 3)?.id).toBe('L32')
    expect(toneLevelFor(LEVELS, 4)?.id).toBe('L33')
  })

  it('未标调的音节关不参与声调匹配（关卡声调必须明确）', () => {
    const unmarked = [mkLevel({ id: 'L40', layer: 'syllable', targetSound: 'ma', pinyin: 'ma' })]
    expect(toneLevelFor(unmarked, 1)).toBeUndefined()
    expect(toneLevelFor(unmarked, 2)).toBeUndefined()
  })

  it('phonology.tones 显式覆盖声调', () => {
    const explicit = [
      mkLevel({
        id: 'L32',
        layer: 'syllable',
        targetSound: 'ma',
        pinyin: 'ma',
        phonology: { kind: 'syllable', tones: [1, 3] },
      }),
    ]
    expect(toneLevelFor(explicit, 1)?.id).toBe('L32')
    expect(toneLevelFor(explicit, 3)?.id).toBe('L32')
    expect(toneLevelFor(explicit, 4)).toBeUndefined()
  })

  it('非音节关不参与声调匹配', () => {
    const vowelsOnly = [mkLevel({ id: 'L01', layer: 'vowel', targetSound: 'a', pinyin: 'ā' })]
    expect(toneLevelFor(vowelsOnly, 1)).toBeUndefined()
  })
})
