/**
 * 音系数据不变量测试：
 * - 音节表内每个音节的拼写必须能被 splitPinyinSyllable 往返解析回同一坐标；
 * - 声母/韵母/声调计数与语音学事实一致（现代语音学口径：IPA 部位/方法、介音 × 韵尾）；
 * - seed 关卡的 targetSound 均能被 matchLevel 命中。
 */
import { describe, expect, it } from 'vitest'
import {
  CONFUSABLE_GROUPS,
  FINAL_BY_KEY,
  FINAL_CELLS,
  FINALS_COMBINING,
  INITIAL_PLACES,
  INITIALS,
  MANNER_ROWS,
  SYLLABLES,
  TONES,
  VOWEL_GLIDES_FALLING,
  VOWEL_GLIDES_RISING,
  VOWEL_POSITIONS,
  matchLevel,
  splitPinyinSyllable,
  stripToneMarks,
  syllableIpa,
  toneNumberOf,
} from '../mandarin'

describe('辅音（声母）矩阵', () => {
  it('21 个起始辅音 + ŋ（仅韵尾）+ y/w/ɥ 零声母拼写', () => {
    expect(INITIALS.filter((i) => !i.zeroSpelling && !i.codaOnly)).toHaveLength(21)
    expect(INITIALS.filter((i) => i.zeroSpelling).map((i) => i.key).sort()).toEqual(['w', 'y', 'ɥ'])
    expect(INITIALS.filter((i) => i.codaOnly).map((i) => i.key)).toEqual(['ŋ'])
  })

  it('7 个被动发音部位 × 6 个发音方法，条目全部落位', () => {
    expect(INITIAL_PLACES).toHaveLength(7)
    expect(MANNER_ROWS.map((r) => r.key)).toEqual([
      'stop', 'affricate', 'fricative', 'nasal', 'approximant', 'lateral',
    ])
    for (const i of INITIALS) {
      expect(INITIAL_PLACES, i.key).toContain(i.place)
      expect(MANNER_ROWS.some((r) => r.key === i.rowKey), i.key).toBe(true)
    }
  })

  it('现代 IPA 标音：r 主标近音 ɻ，舌尖成音节辅音 z̩/ʐ̩', () => {
    expect(INITIALS.find((i) => i.key === 'r')?.ipa).toBe('ɻ')
    expect(FINAL_BY_KEY.get('-i')?.ipa).toBe('z̩')
  })
})

describe('韵母矩阵', () => {
  it('39 个音位条目（舌尖 -i 两读），ê/er 不拼合', () => {
    expect(FINAL_CELLS).toHaveLength(39)
    expect(FINAL_CELLS.filter((f) => !f.combineable).map((f) => f.key).sort()).toEqual(['er', 'ê'])
    expect(FINAL_CELLS.filter((f) => f.key === '-i')).toHaveLength(2)
  })

  it('拼合列 = 39 − ê − er − 舌尖第二读 = 36', () => {
    expect(FINALS_COMBINING).toHaveLength(36)
  })
})

describe('音节表', () => {
  it('每个音节拼写往返解析回同一 (声母, 韵母)', () => {
    for (const [initialKey, row] of Object.entries(SYLLABLES)) {
      for (const [finalKey, cell] of Object.entries(row)) {
        const split = splitPinyinSyllable(cell.pinyin)
        expect(split, `${initialKey}+${finalKey} → ${cell.pinyin}`).toEqual({
          initial: initialKey,
          final: finalKey,
        })
      }
    }
  })

  it('省写规则已应用（jü→ju、diou→diu、Øuei→wei）', () => {
    expect(SYLLABLES.j!.ü).toMatchObject({ pinyin: 'ju' })
    expect(SYLLABLES.d!.iou).toMatchObject({ pinyin: 'diu' })
    expect(SYLLABLES['']!.uei).toMatchObject({ pinyin: 'wei' })
  })
})

describe('拼音解析', () => {
  it('零声母拼写还原', () => {
    expect(splitPinyinSyllable('yuan')).toEqual({ initial: '', final: 'üan' })
    expect(splitPinyinSyllable('weng')).toEqual({ initial: '', final: 'ueng' })
    expect(splitPinyinSyllable('yi')).toEqual({ initial: '', final: 'i' })
  })

  it('平翘舌后的 i 解析为舌尖 -i', () => {
    expect(splitPinyinSyllable('zhi')).toEqual({ initial: 'zh', final: '-i' })
    expect(splitPinyinSyllable('si')).toEqual({ initial: 's', final: '-i' })
    expect(splitPinyinSyllable('bi')).toEqual({ initial: 'b', final: 'i' })
  })

  it('j/q/x 的 ü 省写还原', () => {
    expect(splitPinyinSyllable('ju')).toEqual({ initial: 'j', final: 'ü' })
    expect(splitPinyinSyllable('xun')).toEqual({ initial: 'x', final: 'ün' })
    expect(splitPinyinSyllable('nü')).toEqual({ initial: 'n', final: 'ü' })
  })

  it('声调符号剥离与声调号', () => {
    expect(stripToneMarks('mā')).toBe('ma')
    expect(stripToneMarks('lǜ')).toBe('lü')
    expect(stripToneMarks('nǚ')).toBe('nü')
    expect(toneNumberOf('má')).toBe(2)
    expect(toneNumberOf('ma')).toBe(0)
  })
})

describe('关卡匹配', () => {
  it('声母关 / 单韵母关 / 拼读关（seed 关卡口径）', () => {
    expect(matchLevel({ layer: 'initial', targetSound: 'zh', pinyin: 'zhī' })).toMatchObject({
      kind: 'initial',
      ipa: 'ʈʂ',
    })
    expect(matchLevel({ layer: 'vowel', targetSound: 'ü', pinyin: 'yū' })).toMatchObject({
      kind: 'final',
      ipa: 'y',
    })
    expect(matchLevel({ layer: 'syllable', targetSound: 'mā', pinyin: 'mā' })).toMatchObject({
      kind: 'syllable',
      ipa: 'mä',
      tones: [1],
    })
  })

  it('旧式 "m+a" targetSound 写法仍可拆分（兼容历史数据）', () => {
    expect(matchLevel({ layer: 'syllable', targetSound: 'm+a', pinyin: 'mā' })).toMatchObject({
      kind: 'syllable',
      ipa: 'mä',
    })
  })

  it('无 targetSound 时按 pinyin 兜底', () => {
    expect(matchLevel({ layer: 'syllable', targetSound: '', pinyin: 'zhēn' })).toMatchObject({
      kind: 'syllable',
      initial: expect.objectContaining({ key: 'zh' }),
      final: expect.objectContaining({ key: 'en' }),
    })
  })

  it('声母关标签：卷舌 · 塞擦音 · 清 · 不送气', () => {
    expect(matchLevel({ layer: 'initial', targetSound: 'zh', pinyin: '' }).labels).toEqual([
      '卷舌',
      '塞擦音',
      '清',
      '不送气',
    ])
  })
})

describe('音节 IPA 组合', () => {
  it('零声母不带 Ø，直接韵母 IPA', () => {
    expect(syllableIpa('', FINAL_BY_KEY.get('ai'))).toBe('ai̯')
    expect(syllableIpa(null, FINAL_BY_KEY.get('a'))).toBe('ä')
  })

  it('舌尖 -i 成音节辅音：翘舌后取 ʐ̩，平舌后取 z̩，r 后整个音节为 ɻ̩', () => {
    expect(syllableIpa('zh', FINAL_BY_KEY.get('-i'))).toBe('ʈʂʐ̩')
    expect(syllableIpa('r', FINAL_BY_KEY.get('-i'))).toBe('ɻ̩')
    expect(syllableIpa('z', FINAL_BY_KEY.get('-i'))).toBe('tsz̩')
    expect(matchLevel({ layer: 'syllable', targetSound: 'zh+i', pinyin: 'zhī' })).toMatchObject({
      kind: 'syllable',
      ipa: 'ʈʂʐ̩',
    })
  })
})

describe('phonology 字段消费（§5.1）', () => {
  it('phonology 优先于 layer/targetSound/pinyin 猜测', () => {
    const m = matchLevel({
      layer: 'syllable',
      targetSound: '',
      pinyin: '',
      phonology: { kind: 'initial', initial: 'zh', ipa: 'ʈʂ' },
    })
    expect(m.kind).toBe('initial')
    expect(m.ipa).toBe('ʈʂ')
    expect(m.labels).toEqual(['卷舌', '塞擦音', '清', '不送气'])
  })

  it('tones 覆盖声调（如某拼读关显式四声 [1,2,3,4]）', () => {
    const m = matchLevel({
      layer: 'syllable',
      targetSound: 'ma',
      pinyin: 'ma',
      phonology: { kind: 'syllable', initial: 'm', final: 'a', tones: [1, 2, 3, 4] },
    })
    expect(m.kind).toBe('syllable')
    expect(m.tones).toEqual([1, 2, 3, 4])
  })

  it('零声母音节 phonology：IPA 不带 Ø', () => {
    const m = matchLevel({
      layer: 'syllable',
      targetSound: '',
      pinyin: 'ai',
      phonology: { kind: 'syllable', initial: '', final: 'ai' },
    })
    expect(m.ipa).toBe('ai̯')
    expect(m.labels).toContain('零声母')
  })

  it('特征覆盖：段内 place/manner/aspiration 落到标签', () => {
    const m = matchLevel({
      layer: 'initial',
      targetSound: 'b',
      pinyin: 'bō',
      phonology: { kind: 'initial', initial: 'b', aspiration: 'aspirated' },
    })
    expect(m.labels).toContain('送气')
    expect(m.labels).toContain('双唇')
  })

  it('韵母 phonology：hu/finalStructure 覆盖标签', () => {
    const m = matchLevel({
      layer: 'vowel',
      targetSound: 'an',
      pinyin: 'ān',
      phonology: { kind: 'final', final: 'an', hu: 'kaikou', finalStructure: 'front_nasal' },
    })
    expect(m.labels).toEqual(['Ø- 无介音', '前鼻音韵母'])
  })

  it('kind=tone：透出 ipa 与 tones，不做声韵定位', () => {
    const m = matchLevel({
      layer: 'syllable',
      targetSound: '',
      pinyin: '',
      phonology: { kind: 'tone', ipa: '˧˥', tones: [2] },
    })
    expect(m.kind).toBe('tone')
    expect(m.ipa).toBe('˧˥')
    expect(m.tones).toEqual([2])
  })

  it('phonology 无可用定位时回落到兜底猜测', () => {
    const m = matchLevel({
      layer: 'initial',
      targetSound: 'zh',
      pinyin: 'zhī',
      phonology: {},
    })
    expect(m.kind).toBe('initial')
    expect(m.ipa).toBe('ʈʂ')
  })
})

describe('声调与易混组', () => {
  it('四声调值与调号', () => {
    expect(TONES.map((t) => t.value)).toEqual(['55', '35', '214', '51'])
    expect(TONES.map((t) => t.ipa)).toEqual(['˥', '˧˥', '˨˩˦', '˥˩'])
  })

  it('五个易混组，各组键都存在于声母/韵母表', () => {
    expect(CONFUSABLE_GROUPS).toHaveLength(5)
    for (const group of CONFUSABLE_GROUPS) {
      for (const key of group.pairs.flat()) {
        const known = INITIALS.some((i) => i.key === key) || FINAL_CELLS.some((f) => f.key === key)
        expect(known, `${group.name}: ${key}`).toBe(true)
      }
    }
  })

  it('元音舌位 11 个点位（严式含条件变体），ə 为央区参考位且关联韵母键有效', () => {
    expect(VOWEL_POSITIONS).toHaveLength(11)
    for (const vowel of VOWEL_POSITIONS) {
      if (vowel.finalKey === null) continue
      expect(FINAL_CELLS.some((f) => f.key === vowel.finalKey), vowel.finalKey).toBe(true)
    }
    // ə 无独立韵母，仅作央区参考位；o 有独立点位（喔 / uo 韵腹）
    expect(VOWEL_POSITIONS.filter((v) => v.finalKey === null).map((v) => v.ipa)).toEqual(['ə'])
    expect(VOWEL_POSITIONS.some((v) => v.finalKey === 'o')).toBe(true)
  })

  it('音位变体分组：/a/ 三变体、/ə/ 系四变体互补分布', () => {
    expect(VOWEL_POSITIONS.filter((v) => v.phoneme === '/a/').map((v) => v.ipa)).toEqual([
      'a', 'ä', 'ɑ',
    ])
    expect(VOWEL_POSITIONS.filter((v) => v.phoneme === '/ə/').map((v) => v.ipa)).toEqual([
      'ɤ', 'o', 'e', 'ə',
    ])
  })

  it('双元音滑动图（升 6 / 降 5）关联韵母键有效，uo 含央化变体', () => {
    expect(VOWEL_GLIDES_RISING.map((g) => `${g.finalKey}[${g.ipa}]`)).toEqual([
      'ia[jä]',
      'ie[jɛ]',
      'üe[ɥɛ]',
      'ua[wä]',
      'uo[wo]',
      'uo[wə]',
    ])
    expect(VOWEL_GLIDES_FALLING.map((g) => `${g.finalKey}[${g.ipa}]`)).toEqual([
      'ai[ai̯]',
      'ei[ei̯]',
      'ao[ɑu̯]',
      'ou[ou̯]',
      'iou[jou̯]',
    ])
    for (const g of [...VOWEL_GLIDES_RISING, ...VOWEL_GLIDES_FALLING]) {
      expect(FINAL_CELLS.some((f) => f.key === g.finalKey), g.finalKey).toBe(true)
    }
  })
})
